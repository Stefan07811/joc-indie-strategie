#version 330
// The piece's ink outline: the piece swollen along its normals, only its back faces drawn.
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform float outline;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 p3d_Color;
out vec3 normal;
out vec4 color;
out vec4 shadow_coord;
out float vdist;
void main() {
    vec4 v = vec4(p3d_Vertex.xyz + p3d_Normal * outline, 1.0);
    gl_Position = p3d_ModelViewProjectionMatrix * v;
    normal = p3d_Normal;
    color = p3d_Color;
    shadow_coord = vec4(0.0);
    vdist = length((p3d_ModelViewMatrix * v).xyz);
}
