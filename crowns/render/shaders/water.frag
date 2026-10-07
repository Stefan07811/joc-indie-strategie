#version 330
// The sea: coloured by its real depth, rippled by small moving waves that catch the sun.
uniform sampler2D heightmap;    // metres (negative at sea)
uniform vec3 sun_dir;
uniform vec3 cam_pos;
uniform vec3 haze;
uniform vec2 map_size;
uniform float time;
in vec2 uv;
in vec3 wpos;
out vec4 frag;

vec2 wave(vec2 p, vec2 dir, float freq, float speed) {
    float k = dot(p, dir) * freq + time * speed;
    return dir * cos(k) * freq;
}

void main() {
    float depth = -texture(heightmap, uv).r;
    if (depth <= 0.0) discard;
    vec2 p = wpos.xy;
    vec2 g = wave(p, normalize(vec2(1.0, 0.3)), 0.35, 1.1) + wave(p, normalize(vec2(-0.4, 1.0)), 0.55, 1.6)
           + wave(p, normalize(vec2(0.7, -0.7)), 0.9, 2.3) * 0.5 + wave(p, normalize(vec2(-1.0, -0.2)), 1.7, 3.1) * 0.25;
    float d = length(cam_pos - wpos);
    vec3 n = normalize(vec3(-g * 0.06 * (1.0 - smoothstep(150.0, 700.0, d)), 1.0));  // no shimmer far away
    vec3 view = normalize(cam_pos - wpos);
    float shallow = 1.0 - smoothstep(0.0, 120.0, depth);
    vec3 deep = mix(vec3(0.05, 0.16, 0.30), vec3(0.03, 0.10, 0.22), smoothstep(200.0, 2000.0, depth));
    vec3 col = mix(deep, vec3(0.16, 0.42, 0.48), shallow * 0.8);
    float diff = max(dot(n, sun_dir), 0.0);
    col *= 0.65 + 0.45 * diff;
    float fresnel = pow(1.0 - max(dot(view, n), 0.0), 4.0);
    col = mix(col, vec3(0.62, 0.72, 0.82), fresnel * 0.5);
    vec3 h = normalize(view + sun_dir);
    col += vec3(1.0, 0.95, 0.85) * pow(max(dot(n, h), 0.0), 140.0) * 0.6;
    float coast = smoothstep(0.0, 25.0, depth);
    float fog = clamp((d - 600.0) / 4000.0, 0.0, 0.45);
    vec2 edge = min(uv, 1.0 - uv) * map_size;
    fog = max(fog, 1.0 - clamp(min(edge.x, edge.y) / 40.0, 0.0, 1.0));
    col = mix(col, haze, fog);
    frag = vec4(col, 0.35 + 0.65 * coast);
}
