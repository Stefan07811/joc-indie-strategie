#version 330
// "Codex" sea: pale blue-green wash on parchment, the coast echoed by engraved lines ("waterlining"),
// little engraved waves, and the rhumb lines of a portolan chart radiating from wind roses.
uniform sampler2D heightmap;
uniform sampler2D coast;
uniform vec3 sun_dir;
uniform vec3 cam_pos;
uniform vec3 haze;
uniform vec2 map_size;
uniform float time;
in vec2 uv;
in vec3 wpos;
out vec4 frag;

const vec3 INK = vec3(0.22, 0.14, 0.08);
const vec3 PARCHMENT = vec3(0.94, 0.88, 0.73);
const vec2 ROSES[6] = vec2[6](vec2(1214.7, 707.6), vec2(727.7, 353.7), vec2(229.8, 648.6),
                              vec2(383.0, 221.0), vec2(1039.6, 88.4), vec2(1346.0, 913.9));

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}

float line(float v, float weight) {
    float f = abs(fract(v) - 0.5) * 2.0;
    float aa = fwidth(v) * 1.5;
    return 1.0 - smoothstep(weight - aa, weight + aa, f);
}

void main() {
    float depth = -texture(heightmap, uv).r;
    if (depth <= 0.0) discard;
    float shore = texture(coast, uv).r;                 // map pixels from the coast
    float d = length(cam_pos - wpos);
    float grain = noise(wpos.xy * 0.08) * 0.6 + noise(wpos.xy * 0.9) * 0.4;
    vec3 sea = mix(PARCHMENT, vec3(0.55, 0.70, 0.72), 0.55) * (0.92 + 0.1 * grain);
    sea = mix(sea, sea * vec3(0.84, 0.9, 0.95), smoothstep(100.0, 2500.0, depth));

    // waterlining: lines echoing the shore, fading out to sea
    float wl = line(shore / 2.6, 0.12) * (1.0 - smoothstep(4.0, 20.0, shore)) * step(1.2, shore);
    sea = mix(sea, INK, wl * 0.45);

    // engraved waves: short wavy strokes in loose rows
    vec2 p = wpos.xy;
    float row = p.y / 3.2 + sin(p.x * 0.35 + floor(p.y / 3.2) * 1.7) * 0.18;
    float dash = smoothstep(0.35, 0.5, noise(vec2(p.x * 0.12, floor(row))));
    float waves = line(row, 0.08) * dash * smoothstep(18.0, 30.0, shore) * (1.0 - smoothstep(500.0, 1100.0, d));
    sea = mix(sea, INK, waves * 0.3);

    // rhumb lines from the wind roses: black for the eight winds, green and red between them
    for (int i = 0; i < 6; i++) {
        vec2 r = p - ROSES[i];
        float ang = atan(r.y, r.x) / 6.2831853 * 32.0;
        float far = length(r);
        float k = abs(fract(ang + 0.5) - 0.5);
        float aa = fwidth(ang) * 1.2;
        float on = 1.0 - smoothstep(0.0, aa, k);
        int wind = int(floor(ang + 0.5)) & 3;
        vec3 ink = wind == 0 ? INK : (wind == 2 ? vec3(0.20, 0.42, 0.24) : vec3(0.62, 0.16, 0.12));
        sea = mix(sea, ink, on * 0.45 * smoothstep(8.0, 30.0, far) * step(3.0, shore));
        float ring = line(far / 12.0, 0.06) * (1.0 - smoothstep(18.0, 26.0, far)) * step(10.0, far);
        sea = mix(sea, INK, ring * 0.7);
    }

    vec2 edge = min(uv, 1.0 - uv) * map_size;
    sea = mix(PARCHMENT * 0.82, sea, clamp(min(edge.x, edge.y) / 60.0, 0.0, 1.0));
    frag = vec4(sea, smoothstep(0.0, 1.2, shore));
}
