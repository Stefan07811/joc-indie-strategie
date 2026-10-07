#version 330
// A painted piece on the battlefield (a miniature, a tray, a tree): lit by the sun, in its shadows, in the haze.
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ModelMatrix;
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
out float vdist;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    normal = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
    color = p3d_Color;
    vdist = length((p3d_ModelViewMatrix * p3d_Vertex).xyz);
    // looked up a little off the surface, so that a face does not shadow itself
    shadow_coord = p3d_LightSource[0].shadowViewMatrix * (p3d_ModelViewMatrix * vec4(p3d_Vertex.xyz + p3d_Normal * 0.05, 1.0));
}
