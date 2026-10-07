#version 330
// "Codex": the land as a hand-coloured engraving of the fifteenth century. Parchment, relief drawn
// with ink hatching that thickens in shadow, ridges and cliffs inked, realms washed in watercolour
// that pools darker at its edges, borders drawn with a pen.
uniform sampler2D colormap;
uniform sampler2D normalmap;
uniform sampler2D provinces;
uniform sampler2D palette;
uniform sampler2D coast;        // map pixels to the coast: + at sea, - on land
uniform sampler2D borderdist;   // texels to the nearest province border
uniform vec2 index_size;
uniform float palette_size;
uniform int selected;
uniform int hovered;
uniform vec3 sun_dir;
uniform vec3 cam_pos;
uniform vec3 haze;
uniform vec2 map_size;
uniform float overlay_mix;
uniform float time;
uniform sampler2D reach;        // the chosen army's march: km to every place / its month's budget
uniform vec4 reach_rect;        // the map pixels that texture covers: left, top, width, height
uniform float reach_on;
in vec2 uv;
in vec3 wpos;
out vec4 frag;

const vec3 INK = vec3(0.22, 0.14, 0.08);
const vec3 PARCHMENT = vec3(0.94, 0.88, 0.73);
const vec3 RUBRIC = vec3(0.68, 0.15, 0.09);   // the scribes' red ink

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p) { return 0.5 * noise(p) + 0.25 * noise(p * 2.1) + 0.125 * noise(p * 4.3); }

// one family of parallel pen strokes, slightly wavering; returns ink coverage 0..1
float hatch(vec2 p, float angle, float spacing, float weight) {
    vec2 dir = vec2(cos(angle), sin(angle));
    float wobble = (noise(p * 0.35) - 0.5) * 0.35;
    float v = dot(p, dir) / spacing + wobble;
    float f = abs(fract(v) - 0.5) * 2.0;           // 0 on a stroke, 1 between
    float aa = fwidth(v) * 2.0;
    return 1.0 - smoothstep(weight - aa, weight + aa, f);
}

int prov_at(vec2 p) { return int(texture(provinces, p).r * 65535.0 + 0.5); }

vec4 pal(int i) { return texture(palette, vec2((float(i) + 0.5) / palette_size, 0.5)); }

void main() {
    vec3 n = normalize(texture(normalmap, uv).xyz * 2.0 - 1.0);
    vec3 terrain = texture(colormap, uv).rgb;
    float d = length(cam_pos - wpos);
    float diff = max(dot(n, sun_dir), 0.0);
    float light = clamp(0.25 + 0.95 * diff, 0.0, 1.0);

    // parchment, tinted faintly by what grows there (green lowlands, ochre steppe, grey stone)
    float grain = fbm(wpos.xy * 0.08) * 0.6 + fbm(wpos.xy * 0.9) * 0.4;
    vec3 paper = PARCHMENT * (0.9 + 0.12 * grain);
    vec3 col = mix(paper, paper * (terrain * 1.6 + 0.25), 0.45);

    // which province, and how far (in texels, smoothly) to the nearest province border; across that
    // border lies `other`
    int c = prov_at(uv);
    vec2 tx = 1.0 / index_size;
    float bd = texture(borderdist, uv).r;
    vec2 grad = vec2(texture(borderdist, uv + vec2(tx.x, 0.0)).r - texture(borderdist, uv - vec2(tx.x, 0.0)).r,
                     texture(borderdist, uv + vec2(0.0, tx.y)).r - texture(borderdist, uv - vec2(0.0, tx.y)).r);
    int other = prov_at(uv - normalize(grad + vec2(1e-6)) * (bd + 1.0) * tx);
    vec4 realm = c > 0 ? pal(c) : vec4(0.0);
    bool realm_edge = c > 0 && other > 0 && other != c && distance(pal(other).rgb, realm.rgb) > 0.01;
    bool province_edge = c > 0 && other > 0 && other != c && !realm_edge;

    // watercolour wash of the realm, darker where the pigment pooled along its edges
    if (c > 0) {
        float pigment = realm.a * overlay_mix * 0.8 * (0.75 + 0.35 * fbm(wpos.xy * 0.15));
        if (realm_edge) pigment *= 1.0 + 0.7 * (1.0 - smoothstep(0.0, 6.0, bd));
        vec3 tint = mix(realm.rgb, vec3(dot(realm.rgb, vec3(0.33))), 0.3) * 1.2;  // pigments, not neon
        vec3 wash = mix(vec3(1.0), tint, clamp(pigment, 0.0, 1.0));
        col *= wash;  // watercolour multiplies over the paper
    }

    // relief in ink: hatching in shadow, cross-hatching in deep shadow, strokes down steep slopes
    float shade = 1.0 - light;
    float spacing = 1.1 * max(1.0, d / 260.0);
    float strokes = 1.0 - smoothstep(900.0, 1800.0, d);    // far away the strokes merge into tone
    float ink = 0.0;
    ink += hatch(wpos.xy, 0.62, spacing, 0.18 + 0.5 * smoothstep(0.25, 0.85, shade)) * smoothstep(0.2, 0.4, shade);
    ink += hatch(wpos.xy, -0.62, spacing, 0.15 + 0.4 * smoothstep(0.55, 0.95, shade)) * smoothstep(0.55, 0.7, shade);
    float steep = 1.0 - n.z;
    vec2 downhill = normalize(n.xy + 1e-4);
    ink += hatch(wpos.xy, atan(downhill.x, -downhill.y), spacing * 0.8, 0.25) * smoothstep(0.18, 0.45, steep) * 0.8;
    ink = clamp(ink, 0.0, 1.0) * strokes + shade * 0.55 * (1.0 - strokes);
    col = mix(col, INK, ink * 0.62);
    col *= 0.86 + 0.18 * light;

    // the shore drawn twice with the pen
    float shore = texture(coast, uv).r;
    col = mix(col, INK, (1.0 - smoothstep(0.0, 1.2, abs(shore + 0.6))) * 0.8);

    // borders drawn with the pen as smooth curves: dotted between provinces, a firm line between realms;
    // lines keep their width on screen as the camera rises
    if (c > 0) {
        float w = max(1.0, d / 520.0);   // at least as wide as the steps of the index texture
        float aa = max(fwidth(bd), 0.05);
        float pen = 1.0 - smoothstep(w - aa, w + aa, bd);
        float dots = step(0.45, fract((wpos.x + wpos.y) / max(1.4, d / 200.0)));
        if (province_edge) col = mix(col, INK, pen * 0.55 * dots);
        float firm = 1.0 - smoothstep(w * 1.9 - aa, w * 1.9 + aa, bd);
        if (realm_edge) col = mix(col, mix(INK, realm.rgb * 0.45, 0.45), firm * 0.95);
        if (c == hovered) col = mix(col, vec3(1.0, 0.97, 0.88), 0.18);
        if (c == selected) {
            col = mix(col, vec3(0.98, 0.84, 0.42), 0.16);
            float gold = 1.0 - smoothstep(w * 2.2 - aa, w * 2.2 + aa, bd);
            if (other != c && other > 0) col = mix(col, vec3(0.75, 0.52, 0.10), gold);  // gold leaf
        }
    }

    // the chosen army's month of marching, ruled in red ink like an itinerary: its bound drawn firmly,
    // a fine line for every week of the march, and the lands beyond it greyed
    if (reach_on > 0.5) {
        vec2 m = (vec2(wpos.x, map_size.y - wpos.y) - reach_rect.xy) / reach_rect.zw;
        float r = 1.5;
        if (m.x >= 0.0 && m.y >= 0.0 && m.x <= 1.0 && m.y <= 1.0) r = texture(reach, vec2(m.x, 1.0 - m.y)).r;
        float aa = max(fwidth(r), 1e-4);
        float inside = 1.0 - smoothstep(1.0 - aa, 1.0 + aa, r);
        col = mix(mix(col, vec3(dot(col, vec3(0.3, 0.45, 0.25))) * 0.92, 0.55), col, inside);
        float bound = 1.0 - smoothstep(aa * 1.2, aa * 2.4, abs(r - 1.0));
        col = mix(col, RUBRIC, bound * 0.9);
        float wk = r * 4.0;
        float week = (1.0 - smoothstep(0.0, fwidth(wk) * 1.1, abs(fract(wk + 0.5) - 0.5))) * step(0.5, wk) * inside;
        float dotted = step(0.4, fract((wpos.x - wpos.y) / max(1.2, d / 240.0)));
        col = mix(col, RUBRIC, week * dotted * 0.3);
    }

    // the edge of the sheet
    vec2 edge = min(uv, 1.0 - uv) * map_size;
    float sheet = clamp(min(edge.x, edge.y) / 60.0, 0.0, 1.0);
    col = mix(PARCHMENT * 0.82, col, sheet);
    frag = vec4(col, 1.0);
}
