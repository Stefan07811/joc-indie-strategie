#version 330
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat3 p3d_NormalMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 p3d_Color;
out vec3 normal;
out vec4 color;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    normal = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
    color = p3d_Color;
}
