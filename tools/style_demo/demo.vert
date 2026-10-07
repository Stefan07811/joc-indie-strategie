#version 330
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ModelMatrix;
uniform float outline;
uniform struct p3d_LightSourceParameters {
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
} p3d_LightSource[1];
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 p3d_Color;
out vec3 normal;
out vec4 color;
out vec4 shadow_coord;
out vec3 vpos;
out vec3 wpos;
void main() {
    vec4 v = vec4(p3d_Vertex.xyz + p3d_Normal * outline, 1.0);
    gl_Position = p3d_ModelViewProjectionMatrix * v;
    normal = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
    color = p3d_Color;
    vpos = (p3d_ModelViewMatrix * v).xyz;
    wpos = (p3d_ModelMatrix * v).xyz;
    shadow_coord = p3d_LightSource[0].shadowViewMatrix * (p3d_ModelViewMatrix * vec4(p3d_Vertex.xyz + p3d_Normal * 0.04, 1.0));
}
