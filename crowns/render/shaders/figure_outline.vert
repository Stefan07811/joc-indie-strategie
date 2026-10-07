#version 330
// The miniature's ink outline: the figure inflated along its normals (only back faces are drawn).
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform float outline;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 p3d_Color;
out vec3 normal;
out vec4 color;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * vec4(p3d_Vertex.xyz + p3d_Normal * outline, 1.0);
    normal = p3d_Normal;
    color = p3d_Color;
}
