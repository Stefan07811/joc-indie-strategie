#version 330
// A painted plant: a picture standing on the field, lit like the pieces, in their shadows and haze.
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform struct p3d_LightSourceParameters {
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
} p3d_LightSource[1];
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 uv;
out vec4 shadow_coord;
out vec3 vpos;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_MultiTexCoord0;
    vpos = (p3d_ModelViewMatrix * p3d_Vertex).xyz;
    shadow_coord = p3d_LightSource[0].shadowViewMatrix * vec4(vpos, 1.0);
}
