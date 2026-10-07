#version 330
// The sky over the field, washed in like a watercolour: pale at the horizon where it meets the haze,
// deeper overhead, with soft clouds drifting and a glow about the sun.
uniform vec3 sun_dir;
uniform vec3 haze;
uniform vec3 zenith;
uniform float time;
in vec3 dir;
out vec4 frag;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 5; i++) { v += a * noise(p); p = p * 2.03 + vec2(1.7, 9.2); a *= 0.5; }
    return v;
}

void main() {
    vec3 d = normalize(dir);
    float up = clamp(d.z, 0.0, 1.0);
    vec3 col = mix(haze, zenith, pow(up, 0.4));
    // clouds on a high flat ceiling, thinning toward the horizon
    if (d.z > 0.0) {
        vec2 p = d.xy / (d.z + 0.06) * 1.2 + vec2(time * 0.004, time * 0.0015);
        float c = fbm(p);
        float cover = smoothstep(0.45, 0.75, c) * smoothstep(0.0, 0.06, d.z);
        float lit = 0.85 + 0.15 * clamp(dot(d, sun_dir), 0.0, 1.0);
        vec3 cloud = mix(vec3(0.80, 0.80, 0.82), vec3(1.0, 0.98, 0.94), smoothstep(0.55, 0.85, c)) * lit;
        col = mix(col, cloud, cover * 0.85);
    }
    // the warm glow about the sun
    float s = max(dot(d, sun_dir), 0.0);
    col += vec3(1.0, 0.86, 0.6) * (pow(s, 24.0) * 0.25 + pow(s, 400.0) * 0.6);
    frag = vec4(col, 1.0);
}
