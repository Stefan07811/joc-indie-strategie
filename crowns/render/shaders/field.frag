#version 330
// A battlefield painted like the map: watercolour grass and earth, the relief shaded with ink hatching,
// and during deployment each side's ground ruled in its colour.
uniform vec3 sun_dir;
uniform vec4 deploy;          // y from, y to (ours), y from, y to (theirs), in world units
uniform float deploying;
uniform vec3 our_color;
uniform vec3 their_color;
uniform vec2 field_size;      // where the regiments may go; the country beyond is drawn faded
uniform vec3 haze;
uniform float fog;
uniform struct p3d_LightSourceParameters {
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
} p3d_LightSource[1];
in vec3 normal;
in vec4 color;
in vec3 wpos;
in vec4 shadow_coord;
in vec3 vpos;
out vec4 frag;

const vec3 INK = vec3(0.22, 0.14, 0.08);

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
            lit += texture(p3d_LightSource[0].shadowMap, vec3(c.xy + vec2(i, j) * texel * 1.5, c.z - 0.0004));
    return lit / 9.0;
}

void main() {
    vec3 n = normalize(normal);
    float light = clamp(0.3 + 0.9 * max(dot(n, sun_dir), 0.0) * (0.35 + 0.65 * sunlit()), 0.0, 1.0);
    float grain = noise(wpos.xy * 0.15) * 0.6 + noise(wpos.xy * 1.1) * 0.4;
    vec3 col = color.rgb * (0.88 + 0.2 * grain);
    // ink hatching in the shadows, as on the map
    float shade = 1.0 - light;
    float v = dot(wpos.xy, vec2(0.6, 0.8)) / 0.9 + (noise(wpos.xy * 0.4) - 0.5) * 0.4;
    float f = abs(fract(v) - 0.5) * 2.0;
    float aa = fwidth(v) * 2.0;
    float hatch = (1.0 - smoothstep(0.2 - aa, 0.2 + aa, f)) * smoothstep(0.25, 0.5, shade);
    col = mix(col, INK, hatch * 0.45);
    col *= 0.85 + 0.2 * light;
    vec2 beyond = max(-wpos.xy, wpos.xy - field_size);
    float outside = max(beyond.x, beyond.y);
    bool inside = outside <= 0.0;
    if (deploying > 0.5 && inside && wpos.x >= 4.0 && wpos.x <= field_size.x - 4.0) {
        float stripe = step(0.6, fract((wpos.x + wpos.y) / 3.0));
        if (wpos.y >= deploy.x && wpos.y <= deploy.y) col = mix(col, our_color, 0.18 + 0.12 * stripe);
        if (wpos.y >= deploy.z && wpos.y <= deploy.w) col = mix(col, their_color, 0.12 + 0.08 * stripe);
    }
    if (!inside) {
        // the country beyond the field, a little paler
        col = mix(col, vec3(dot(col, vec3(0.33))), 0.25) * 1.04;
    }
    // the edge of the field, a ruled ink line
    float edge = abs(outside);
    float pen = fwidth(outside) * 1.5 + 0.12;
    col = mix(col, INK, (1.0 - smoothstep(pen * 0.5, pen, edge)) * 0.6);
    frag = vec4(mix(col, haze, 1.0 - exp(-pow(length(vpos) * fog, 2.0))), 1.0);
}
