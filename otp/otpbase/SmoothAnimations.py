from direct.actor.Actor import Actor
import weakref
# Toontown's animations were exported at a low frame rate (mostly 24 fps), so
# by default each frame is held until the next one is due, which looks choppy
# at 60 fps and above.  When enabled, Panda blends between consecutive frames
# so animations play smoothly at whatever rate the game renders.
#
# The interpolate-frames config variable can't be used for this: the blend flag
# is stored in each .bam file and copied from the model pool's cached copy, so
# it has to be set on every PartBundle as Actors load their models.
SettingName = 'smooth-animations'
_enabled = False
_actors = weakref.WeakSet()
_originalLoadModel = Actor.loadModel

def _loadModel(self, *args, **kwargs):
    _originalLoadModel(self, *args, **kwargs)
    _actors.add(self)
    self.setBlend(frameBlend=_enabled)


Actor.loadModel = _loadModel

def isEnabled():
    return _enabled


def setEnabled(enabled):
    global _enabled
    _enabled = bool(enabled)
    for actor in list(_actors):
        if not actor.isEmpty():
            actor.setBlend(frameBlend=_enabled)

    # Also catch characters whose Actor object has been garbage collected but
    # whose nodes are still in the scene graph.
    for root in (base.render, base.render2d, base.hidden):
        for characterNP in root.findAllMatches('**/+Character;+s'):
            character = characterNP.node()
            for i in range(character.getNumBundles()):
                character.getBundle(i).setFrameBlendFlag(_enabled)
