#version 330
// The land: its colour, lit by the sun through a detailed normal map; the map mode's colours painted
// per province (palette lookup), realm and province borders, the selected and hovered province; and the
// haze of distance.
uniform sampler2D colormap;
uniform sampler2D normalmap;
uniform sampler2D provinces;    // province index / 65535 per texel (nearest filtering)
uniform sampler2D palette;      // one texel per province index: rgb colour, a strength
uniform vec2 index_size;
uniform float palette_size;
uniform int selected;
uniform int hovered;
uniform vec3 sun_dir;
uniform vec3 cam_pos;
uniform vec3 haze;
uniform vec2 map_size;
uniform float overlay_mix;
in vec2 uv;
in vec3 wpos;
out vec4 frag;

int prov_at(vec2 p) { return int(texture(provinces, p).r * 65535.0 + 0.5); }
vec4 pal(int i) { return texture(palette, vec2((float(i) + 0.5) / palette_size, 0.5)); }

void main() {
    vec3 n = normalize(texture(normalmap, uv).xyz * 2.0 - 1.0);
    vec3 base = texture(colormap, uv).rgb;
    float d = length(cam_pos - wpos);
    // fine grain close up, so the land does not look smeared
    float grain = sin(wpos.x * 2.3 + sin(wpos.y * 1.7)) * sin(wpos.y * 2.9 + sin(wpos.x * 1.3));
    base *= 1.0 + grain * 0.06 * (1.0 - smoothstep(80.0, 400.0, d));
    float diff = max(dot(n, sun_dir), 0.0);
    float sky = 0.5 + 0.5 * n.z;
    vec3 lit = base * (0.30 * sky + 0.85 * diff) * vec3(1.02, 1.0, 0.96);

    int c = prov_at(uv);
    if (c > 0) {
        vec4 col = pal(c);
        lit = mix(lit, col.rgb * (0.55 + 0.55 * diff), col.a * overlay_mix);
        // borders: neighbours that belong to another province (or another realm), sampled at a
        // distance that grows with the camera's, so the lines stay visible from high up
        vec2 t = max(1.0, d / 380.0) / index_size;
        float pb = 0.0, rb = 0.0, sb = 0.0;
        for (int i = 0; i < 8; i++) {
            float a = float(i) * 0.785398;
            int m = prov_at(uv + vec2(cos(a), sin(a)) * t);
            if (m > 0 && m != c) {
                pb += 1.0;
                if (distance(pal(m).rgb, col.rgb) > 0.01) rb += 1.0;
            }
            if (c == selected && m != selected) sb += 1.0;
        }
        float far = smoothstep(250.0, 1200.0, d);
        lit = mix(lit, vec3(0.10, 0.08, 0.06), clamp(pb / 3.0, 0.0, 1.0) * mix(0.28, 0.4, far));
        lit = mix(lit, vec3(0.05, 0.035, 0.03), clamp(rb / 3.0, 0.0, 1.0) * mix(0.7, 0.9, far));
        if (c == hovered) lit = mix(lit, vec3(1.0, 0.95, 0.8), 0.12);
        if (c == selected) {
            lit = mix(lit, vec3(1.0, 0.9, 0.55), 0.18);
            lit = mix(lit, vec3(1.0, 0.84, 0.30), clamp(sb / 2.0, 0.0, 1.0));
        }
    }

    // the haze of distance, and the map's edges fading into it
    float fog = clamp((d - 1400.0) / 5000.0, 0.0, 0.35);
    vec2 edge = min(uv, 1.0 - uv) * map_size;
    fog = max(fog, 1.0 - clamp(min(edge.x, edge.y) / 40.0, 0.0, 1.0));
    lit = mix(lit, haze, fog);
    frag = vec4(lit, 1.0);
}
