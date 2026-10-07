#version 330
// A march drawn on the map: a ribbon along the route, as wide on screen at every height of the camera.
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform float width;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;       // across the route
in vec4 p3d_Color;
in vec2 p3d_MultiTexCoord0;  // distance along the route, side (-1 .. 1)
out vec2 tc;
out vec4 color;
void main() {
    vec4 v = p3d_Vertex;
    v.xy += p3d_Normal.xy * p3d_MultiTexCoord0.y * width;
    gl_Position = p3d_ModelViewProjectionMatrix * v;
    tc = p3d_MultiTexCoord0;
    color = p3d_Color;
}
