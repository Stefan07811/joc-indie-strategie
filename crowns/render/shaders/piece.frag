#version 330
// Painted in flat bands of light like a figure painter's work, with the sun's shadows laid on as a
// darker band, and the far pieces fading into the haze.
uniform vec3 sun_dir;
uniform float outline;
uniform vec3 haze;
uniform float fog;
uniform struct p3d_LightSourceParameters {
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
} p3d_LightSource[1];
in vec3 normal;
in vec4 color;
in vec4 shadow_coord;
in float vdist;
out vec4 frag;

const vec3 INK = vec3(0.16, 0.10, 0.06);

float sunlit() {
    vec3 c = shadow_coord.xyz / shadow_coord.w;
    if (c.x <= 0.0 || c.x >= 1.0 || c.y <= 0.0 || c.y >= 1.0 || c.z >= 1.0) return 1.0;
    vec2 texel = 1.0 / vec2(textureSize(p3d_LightSource[0].shadowMap, 0));
    float lit = 0.0;
    for (int i = -1; i <= 1; i++)
        for (int j = -1; j <= 1; j++)
            lit += texture(p3d_LightSource[0].shadowMap, vec3(c.xy + vec2(i, j) * texel, c.z - 0.0004));
    return lit / 9.0;
}

void main() {
    float haze_k = 1.0 - exp(-pow(vdist * fog, 2.0));
    if (outline > 0.0) {
        frag = vec4(mix(INK, haze, haze_k), 1.0);
        return;
    }
    vec3 n = normalize(normal);
    float diff = max(dot(n, sun_dir), 0.0) * sunlit();
    float tone = diff > 0.6 ? 1.0 : (diff > 0.25 ? 0.80 : 0.60);   // painted in bands
    float sky = 0.5 + 0.5 * n.z;
    vec3 c = color.rgb * (0.35 * sky + 0.8 * tone);
    c = mix(vec3(dot(c, vec3(0.33))), c, 1.15);                      // a little more saturated, like paint
    frag = vec4(mix(c, haze, haze_k), 1.0);
}
