#version 330
uniform sampler2D p3d_Texture0;
uniform vec3 haze;
uniform float fog;
uniform struct p3d_LightSourceParameters {
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
} p3d_LightSource[1];
in vec2 uv;
in vec4 shadow_coord;
in vec3 vpos;
out vec4 frag;

float sunlit() {
    vec3 c = shadow_coord.xyz / shadow_coord.w;
    if (c.x <= 0.0 || c.x >= 1.0 || c.y <= 0.0 || c.y >= 1.0 || c.z >= 1.0) return 1.0;
    return texture(p3d_LightSource[0].shadowMap, vec3(c.xy, c.z - 0.002));
}

void main() {
    vec4 t = texture(p3d_Texture0, uv);
    if (t.a < 0.5) discard;
    float light = 0.72 + 0.28 * sunlit();
    vec3 c = t.rgb * light * (0.85 + 0.2 * uv.y);          // a little darker at the foot
    frag = vec4(mix(c, haze, 1.0 - exp(-pow(length(vpos) * fog, 2.0))), 1.0);
}
