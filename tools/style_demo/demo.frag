#version 330
// Three ways to paint the same pieces: 0 painted miniatures (bands of light, ink outline),
// 1 painted realism (smooth light, no outline), 2 illuminated manuscript (flat colour, heavy ink, paper).
uniform vec3 sun_dir;
uniform float outline;
uniform vec3 haze;
uniform float fog;
uniform float style;
uniform float ground;
uniform struct p3d_LightSourceParameters {
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
} p3d_LightSource[1];
in vec3 normal;
in vec4 color;
in vec4 shadow_coord;
in vec3 vpos;
in vec3 wpos;
out vec4 frag;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float sunlit() {
    vec3 c = shadow_coord.xyz / shadow_coord.w;
    if (c.x <= 0.0 || c.x >= 1.0 || c.y <= 0.0 || c.y >= 1.0 || c.z >= 1.0) return 1.0;
    vec2 texel = 1.0 / vec2(textureSize(p3d_LightSource[0].shadowMap, 0));
    float lit = 0.0;
    for (int i = -1; i <= 1; i++)
        for (int j = -1; j <= 1; j++)
            lit += texture(p3d_LightSource[0].shadowMap, vec3(c.xy + vec2(i, j) * texel * 1.5, c.z - 0.00012));
    return lit / 9.0;
}

void main() {
    float hk = 1.0 - exp(-pow(length(vpos) * fog, 2.0));
    if (outline > 0.0) {
        vec3 ink = style > 1.5 ? vec3(0.10, 0.06, 0.03) : vec3(0.16, 0.10, 0.06);
        frag = vec4(mix(ink, haze, hk), 1.0);
        return;
    }
    vec3 n = normalize(normal);
    float sl = sunlit();
    float d = max(dot(n, sun_dir), 0.0);
    vec3 base = color.rgb;
    if (ground > 0.5) {
        float g = noise(wpos.xy * 0.08) * 0.6 + noise(wpos.xy * 0.6) * 0.4;
        base *= 0.86 + 0.26 * g;
    }
    vec3 c;
    if (style < 0.5) {
        float l = d * sl;
        float tone = l > 0.55 ? 1.0 : (l > 0.22 ? 0.80 : 0.62);
        if (ground > 0.5) tone = 0.62 + 0.38 * smoothstep(0.1, 0.5, l);
        c = base * (0.35 * (0.5 + 0.5 * n.z) + 0.8 * tone);
        c = mix(vec3(dot(c, vec3(0.33))), c, 1.15);
        if (ground > 0.5) {       // ink hatching in the shadows, as on the map
            float v = dot(wpos.xy, vec2(0.6, 0.8)) / 0.7;
            float f = abs(fract(v) - 0.5) * 2.0;
            float aa = fwidth(v) * 2.0;
            float hatch = (1.0 - smoothstep(0.2 - aa, 0.2 + aa, f)) * (1.0 - smoothstep(0.2, 0.6, l));
            c = mix(c, vec3(0.22, 0.14, 0.08), hatch * 0.35);
        }
    } else if (style < 1.5) {
        float sky = 0.5 + 0.5 * n.z;
        vec3 amb = mix(vec3(0.42, 0.39, 0.35), vec3(0.55, 0.62, 0.74), sky) * 0.85;
        vec3 sun = vec3(1.08, 1.0, 0.88) * d * sl;
        c = base * (amb + sun * 1.0);
        float rim = pow(1.0 - max(dot(n, normalize(-vpos)), 0.0), 3.0);
        c += rim * 0.06 * vec3(0.9, 0.95, 1.0);
        c = mix(vec3(dot(c, vec3(0.3, 0.59, 0.11))), c, 0.88);
    } else {
        float l = d * sl;
        float tone = l > 0.25 ? 1.0 : 0.80;
        c = base * tone * 1.04;
        c = mix(vec3(dot(c, vec3(0.33))), c, 1.3);
        // the paper shows through
        float paper = noise(gl_FragCoord.xy * 0.35) * 0.5 + noise(gl_FragCoord.xy * 0.05) * 0.5;
        c = mix(c, vec3(0.93, 0.87, 0.72), 0.12 + 0.08 * paper);
        if (ground > 0.5) c = mix(c, vec3(0.90, 0.84, 0.66), 0.35);
    }
    frag = vec4(mix(c, haze, hk), 1.0);
}
