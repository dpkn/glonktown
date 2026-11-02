from direct.showbase.DirectObject import DirectObject
from direct.directnotify import DirectNotifyGlobal
Forward = 'forward'
Reverse = 'reverse'
TurnLeft = 'turnLeft'
TurnRight = 'turnRight'
Jump = 'jump'
Quests = 'quests'
Inventory = 'inventory'
Chat = 'chat'
Actions = (Forward,
 Reverse,
 TurnLeft,
 TurnRight,
 Jump,
 Quests,
 Inventory,
 Chat)
ArrowKeysPreset = 'arrows'
WASDPreset = 'wasd'
Presets = {ArrowKeysPreset: {Forward: 'arrow_up',
                   Reverse: 'arrow_down',
                   TurnLeft: 'arrow_left',
                   TurnRight: 'arrow_right',
                   Jump: 'control',
                   Quests: 'end',
                   Inventory: 'home',
                   Chat: 'enter'},
 WASDPreset: {Forward: 'w',
              Reverse: 's',
              TurnLeft: 'a',
              TurnRight: 'd',
              Jump: 'space',
              Quests: 'end',
              Inventory: 'home',
              Chat: 'enter'}}
ChangedEvent = 'keyBindingsChanged'
ModifierKeys = ('shift', 'control', 'alt')
ModifierPatterns = ('%s', 'control-%s', 'shift-control-%s', 'alt-%s', 'control-alt-%s', 'shift-%s', 'shift-alt-%s')

def getEvent(action):
    # Game code listens for these instead of raw key names, so it never needs
    # to know which key is bound.  Releasing the key sends getEvent(action) + '-up'.
    return 'keybind-%s' % action


ForwardEvent = getEvent(Forward)
ReverseEvent = getEvent(Reverse)
TurnLeftEvent = getEvent(TurnLeft)
TurnRightEvent = getEvent(TurnRight)
JumpEvent = getEvent(Jump)
QuestsEvent = getEvent(Quests)
InventoryEvent = getEvent(Inventory)
ChatEvent = getEvent(Chat)

def isTypingKey(key):
    return len(key) == 1 or key == 'space'


class KeyBindings(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('KeyBindings')
    SettingName = 'key-bindings'

    def __init__(self):
        self.keys = self.__loadKeys()
        self.activeKeys = {}
        self.heldActions = set()
        self.typing = False
        self.__listen()

    def destroy(self):
        self.typing = False
        self.keys = {}
        self.__listen()
        self.ignoreAll()

    def __loadKeys(self):
        keys = dict(Presets[ArrowKeysPreset])
        saved = base.settings.getSetting(self.SettingName, {})
        if isinstance(saved, dict):
            for action, key in saved.items():
                if action in keys and isinstance(key, str) and key:
                    keys[action] = key

        if len(set(keys.values())) != len(keys):
            self.notify.warning('Saved key bindings share a key; using the defaults.')
            keys = dict(Presets[ArrowKeysPreset])
        return keys

    def getKey(self, action):
        return self.keys[action]

    def setKey(self, action, key):
        # Every action keeps exactly one key, so an action already using this
        # key takes over the old key of the one being changed.
        oldKey = self.keys[action]
        for otherAction, otherKey in self.keys.items():
            if otherKey == key and otherAction != action:
                self.keys[otherAction] = oldKey

        self.keys[action] = key
        self.__changed()

    def usePreset(self, preset):
        self.keys = dict(Presets[preset])
        self.__changed()

    def hasTypingKeys(self):
        for key in self.keys.values():
            if isTypingKey(key):
                return True

        return False

    def watchTextEntry(self, entry):
        self.accept(entry.guiItem.getFocusInEvent(), self.setTyping, [True])
        self.accept(entry.guiItem.getFocusOutEvent(), self.setTyping, [False])

    def ignoreTextEntry(self, entry):
        self.ignore(entry.guiItem.getFocusInEvent())
        self.ignore(entry.guiItem.getFocusOutEvent())
        self.setTyping(False)

    def setTyping(self, typing):
        # While a text entry has focus, keys you'd type go into it instead of
        # triggering their actions.
        if typing != self.typing:
            self.typing = typing
            self.__listen()

    def __changed(self):
        self.__listen()
        base.settings.updateSetting(self.SettingName, dict(self.keys))
        base.settings.writeSettings()
        messenger.send(ChangedEvent)

    def __listen(self):
        activeKeys = {}
        for action, key in self.keys.items():
            if not (self.typing and isTypingKey(key)):
                activeKeys[action] = key

        for action in list(self.heldActions):
            if activeKeys.get(action) != self.activeKeys.get(action):
                self.__keyReleased(action)

        for key in self.activeKeys.values():
            for event in self.__getKeyEvents(key):
                self.ignore(event)

            self.ignore(key + '-up')

        self.activeKeys = activeKeys
        for action, key in activeKeys.items():
            for event in self.__getKeyEvents(key):
                self.accept(event, self.__keyPressed, [action])

            self.accept(key + '-up', self.__keyReleased, [action])

    def __getKeyEvents(self, key):
        # A modifier key is never prefixed by the others, but any other key
        # is, so listen for it with whatever modifiers happen to be held.
        if key in ModifierKeys:
            return [key]
        return [ pattern % key for pattern in ModifierPatterns ]

    def __keyPressed(self, action):
        if action not in self.heldActions:
            self.heldActions.add(action)
            messenger.send(getEvent(action))

    def __keyReleased(self, action):
        if action in self.heldActions:
            self.heldActions.discard(action)
            messenger.send(getEvent(action) + '-up')
