#version 330
// The last touch on every frame: edges smoothed (FXAA, where the card cannot multisample), the colours
// warmed a little like varnished paint, and the corners darkened like an old picture.
uniform sampler2D scene;
uniform float smooth_edges;
uniform float grade;
uniform vec2 uv_scale;
in vec2 uv;
out vec4 frag;

float luma(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }

vec3 fxaa(vec2 p) {
    vec2 px = 1.0 / vec2(textureSize(scene, 0));
    vec3 rgbM = texture(scene, p).rgb;
    vec3 rgbNW = texture(scene, p + vec2(-1.0, -1.0) * px).rgb;
    vec3 rgbNE = texture(scene, p + vec2(1.0, -1.0) * px).rgb;
    vec3 rgbSW = texture(scene, p + vec2(-1.0, 1.0) * px).rgb;
    vec3 rgbSE = texture(scene, p + vec2(1.0, 1.0) * px).rgb;
    float lM = luma(rgbM), lNW = luma(rgbNW), lNE = luma(rgbNE), lSW = luma(rgbSW), lSE = luma(rgbSE);
    float lMin = min(lM, min(min(lNW, lNE), min(lSW, lSE)));
    float lMax = max(lM, max(max(lNW, lNE), max(lSW, lSE)));
    if (lMax - lMin < max(0.0312, lMax * 0.125)) return rgbM;
    vec2 dir = vec2(-((lNW + lNE) - (lSW + lSE)), (lNW + lSW) - (lNE + lSE));
    float reduce = max((lNW + lNE + lSW + lSE) * 0.25 * 0.125, 1.0 / 128.0);
    float scale = 1.0 / (min(abs(dir.x), abs(dir.y)) + reduce);
    dir = clamp(dir * scale, vec2(-8.0), vec2(8.0)) * px;
    vec3 a = 0.5 * (texture(scene, p + dir * (1.0 / 3.0 - 0.5)).rgb + texture(scene, p + dir * (2.0 / 3.0 - 0.5)).rgb);
    vec3 b = a * 0.5 + 0.25 * (texture(scene, p - dir * 0.5).rgb + texture(scene, p + dir * 0.5).rgb);
    float lB = luma(b);
    return (lB < lMin || lB > lMax) ? a : b;
}

void main() {
    vec2 p = uv * uv_scale;
    vec3 c = smooth_edges > 0.5 ? fxaa(p) : texture(scene, p).rgb;
    if (grade > 0.0) {
        // a gentle S-curve, warm lights and cool shadows, a touch more colour
        vec3 s = c * c * (3.0 - 2.0 * c);
        c = mix(c, s, 0.25 * grade);
        float l = luma(c);
        c += grade * (vec3(0.025, 0.012, -0.02) * l + vec3(-0.01, 0.0, 0.015) * (1.0 - l));
        c = mix(vec3(l), c, 1.0 + 0.08 * grade);
        // the corners darkened and warmed, like the edge of a varnished panel
        vec2 q = uv - 0.5;
        float v = smoothstep(0.35, 0.85, length(q * vec2(1.15, 1.0)));
        c = mix(c, c * vec3(0.78, 0.70, 0.58), v * 0.55 * grade);
    }
    frag = vec4(clamp(c, 0.0, 1.0), 1.0);
}
