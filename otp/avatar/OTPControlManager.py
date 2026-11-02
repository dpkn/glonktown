from direct.controls.ControlManager import ControlManager
from direct.showbase.InputStateGlobal import inputState
from otp.otpbase import KeyBindings

class OTPControlManager(ControlManager):
    # Panda's ControlManager hardcodes the arrow keys (or WASD); this one
    # follows the player's key bindings instead.
    MovementActions = (KeyBindings.Forward,
     KeyBindings.Reverse,
     KeyBindings.TurnLeft,
     KeyBindings.TurnRight)
    InputSource = 'KeyBindings'

    def __init__(self, enable = True, passMessagesThrough = False):
        self.passMessagesThrough = passMessagesThrough
        self.inputStateTokens = []
        self.WASDTurnTokens = []
        self.controls = {}
        self.currentControls = None
        self.currentControlsName = None
        self.isEnabled = 0
        self.forceAvJumpToken = None
        if enable:
            self.enable()
        else:
            self.__watchInputs()
        return

    def enable(self):
        if self.isEnabled:
            return
        self.isEnabled = 1
        self.__watchInputs()
        if self.currentControls:
            self.currentControls.enableAvatarControls()

    def disable(self):
        self.isEnabled = 0
        self.__watchInputs()
        if self.currentControls:
            self.currentControls.disableAvatarControls()

    def __watchInputs(self):
        for token in self.inputStateTokens:
            token.release()

        self.inputStateTokens = []
        # passMessagesThrough keeps the movement InputState events coming while
        # disabled, which things like racing rely on.
        if not self.isEnabled and not self.passMessagesThrough:
            return
        ist = self.inputStateTokens
        for action in self.MovementActions:
            event = KeyBindings.getEvent(action)
            ist.append(inputState.watch(action, event, event + '-up', inputSource=self.InputSource))

        if not self.isEnabled:
            return
        jumpEvent = KeyBindings.getEvent(KeyBindings.Jump)
        ist.append(inputState.watch('jump', jumpEvent, jumpEvent + '-up', inputSource=self.InputSource))
        ist.append(inputState.watch('run', 'runningEvent', 'running-on', 'running-off'))
        ist.append(inputState.watch('forward', 'force-forward', 'force-forward-stop'))
        ist.append(inputState.watchWithModifiers('reverse', 'mouse4', inputSource=inputState.Mouse))
        ist.append(inputState.watch('turnLeft', 'mouse-look_left', 'mouse-look_left-done'))
        ist.append(inputState.watch('turnLeft', 'force-turnLeft', 'force-turnLeft-stop'))
        ist.append(inputState.watch('turnRight', 'mouse-look_right', 'mouse-look_right-done'))
        ist.append(inputState.watch('turnRight', 'force-turnRight', 'force-turnRight-stop'))
