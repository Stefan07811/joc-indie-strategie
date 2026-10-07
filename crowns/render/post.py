"""The last pass over every frame: smoothed edges where the graphics card cannot multisample, colours
warmed like varnished paint, and the corners of the picture darkened a little."""

from direct.filter.FilterManager import FilterManager
from panda3d.core import Shader, Texture

from .figures import SHADERS


class PostProcess:
    def __init__(self, base, grade=1.0):
        self.manager = FilterManager(base.win, base.cam)
        self.scene = Texture("scene")
        self.scene.setWrapU(Texture.WMClamp)
        self.scene.setWrapV(Texture.WMClamp)
        self.quad = self.manager.renderSceneInto(colortex=self.scene)
        if self.quad is None:
            raise RuntimeError("no offscreen buffer for the last pass")
        multisampled = self.manager.buffers[0].getFbProperties().getMultisamples() >= 2
        self.quad.setShader(Shader.load(Shader.SL_GLSL, str(SHADERS / "post.vert"), str(SHADERS / "post.frag")))
        self.quad.setShaderInputs(scene=self.scene, smooth_edges=0.0 if multisampled else 1.0, grade=grade,
                                  uv_scale=(1.0, 1.0))

    def set_grade(self, grade):
        self.quad.setShaderInput("grade", grade)

    def cleanup(self):
        self.manager.cleanup()
