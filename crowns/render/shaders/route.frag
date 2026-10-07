#version 330
// Chevrons of ink pointing the way, creeping forward along this month's march; the months after it
// drawn as a quieter dotted line.
uniform float width;
uniform float time;
in vec2 tc;
in vec4 color;
out vec4 frag;
void main() {
    float side = abs(tc.y);
    float along = tc.x / width;
    float edge = 1.0 - smoothstep(0.75, 1.0, side);
    float ink;
    if (color.a > 0.75) {
        float v = fract((along - side * 1.3) / 3.2 - time * 0.6);
        float aa = fwidth(along) / 3.2 * 1.5;
        ink = smoothstep(0.0, aa, v) * (1.0 - smoothstep(0.42, 0.42 + aa, v));
    } else {
        float v = fract(along / 2.4);
        float aa = fwidth(along) / 2.4 * 1.5;
        ink = (1.0 - smoothstep(0.45, 0.45 + aa, v)) * (1.0 - smoothstep(0.35, 0.6, side));
    }
    float a = ink * edge * color.a;
    if (a < 0.02) discard;
    frag = vec4(color.rgb, a);
}
