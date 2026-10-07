#version 330
// A painted miniature: flat colours in two or three tones of light, as a figure painter would lay them.
uniform vec3 sun_dir;
uniform float outline;
in vec3 normal;
in vec4 color;
out vec4 frag;
void main() {
    if (outline > 0.0) {
        frag = vec4(0.16, 0.10, 0.06, 1.0);
        return;
    }
    vec3 n = normalize(normal);
    float diff = max(dot(n, sun_dir), 0.0);
    float tone = diff > 0.6 ? 1.0 : (diff > 0.25 ? 0.78 : 0.58);   // painted in bands
    float sky = 0.5 + 0.5 * n.z;
    vec3 c = color.rgb * (0.35 * sky + 0.8 * tone);
    c = mix(vec3(dot(c, vec3(0.33))), c, 1.15);                      // a little more saturated, like paint
    frag = vec4(c, 1.0);
}
