from direct.directnotify import DirectNotifyGlobal
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyActivityAI import DistributedPartyActivityAI


class DistributedPartyJukeboxActivityBaseAI(DistributedPartyActivityAI):
    """The party's jukebox, the only music at a party that has one. One toon at a time uses it (for JUKEBOX_TIMEOUT
    seconds) and can queue one song; the queue plays in order with a short gap between songs. With nothing queued it
    plays the party theme, and a newly queued song cuts that short."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyJukeboxActivityBaseAI')
    phaseToMusicData = PartyGlobals.PhaseToMusicData
    IdleSong = (13, 'party_original_theme.ogg')
    NoSong = (0, '')

    def __init__(self, air, party, activityTuple):
        DistributedPartyActivityAI.__init__(self, air, party, activityTuple)
        self.songQueue = []
        self.playingIdleSong = False

    def announceGenerate(self):
        DistributedPartyActivityAI.announceGenerate(self)
        self.__playNextSong()

    def delete(self):
        taskMgr.remove(self.taskName('songTimer'))
        taskMgr.remove(self.taskName('userTimeout'))
        DistributedPartyActivityAI.delete(self)

    def canJoin(self, avId):
        return not self.toonsPlaying

    def toonJoined(self, avId):
        taskMgr.doMethodLater(PartyGlobals.JUKEBOX_TIMEOUT, self.removeToon, self.taskName('userTimeout'), extraArgs=[avId])

    def toonExited(self, avId):
        taskMgr.remove(self.taskName('userTimeout'))

    def __queueIndex(self, avId):
        for index, (queuedAvId, songInfo) in enumerate(self.songQueue):
            if queuedAvId == avId:
                return index
        return -1

    def setNextSong(self, songInfo):
        avId = self.air.getAvatarIdFromSender()
        phase, filename = songInfo
        phase = PartyGlobals.sanitizePhase(phase)
        if avId not in self.toonsPlaying or filename not in self.phaseToMusicData.get(phase, {}):
            return
        songInfo = (phase, filename)
        index = self.__queueIndex(avId)
        if index >= 0:
            self.songQueue[index] = (avId, songInfo)
        else:
            self.songQueue.append((avId, songInfo))
        self.sendUpdateToAvatarId(avId, 'setSongInQueue', [songInfo])
        if self.playingIdleSong:
            self.__stopSong()
            self.__playNextSong()

    def queuedSongsRequest(self):
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.toonsPlaying:
            return
        songs = [songInfo for queuedAvId, songInfo in self.songQueue]
        self.sendUpdateToAvatarId(avId, 'queuedSongsResponse', [songs, self.__queueIndex(avId)])

    def moveHostSongToTopRequest(self):
        avId = self.air.getAvatarIdFromSender()
        index = self.__queueIndex(avId)
        if avId != self.party.getHostId() or avId not in self.toonsPlaying or index < 0:
            return
        self.songQueue.insert(0, self.songQueue.pop(index))
        self.sendUpdateToAvatarId(avId, 'moveHostSongToTop', [])

    def __playNextSong(self):
        if self.songQueue:
            toonId, songInfo = self.songQueue.pop(0)
        else:
            toonId, songInfo = 0, self.IdleSong
        self.playingIdleSong = not toonId
        self.d_setSongPlaying(songInfo, toonId)
        phase, filename = songInfo
        length = self.phaseToMusicData[phase][filename][1]
        duration = length * PartyGlobals.getMusicRepeatTimes(length)
        taskMgr.doMethodLater(duration, self.__songEnded, self.taskName('songTimer'), extraArgs=[])

    def __songEnded(self):
        self.__stopSong()
        taskMgr.doMethodLater(PartyGlobals.MUSIC_GAP, self.__playNextSong, self.taskName('songTimer'), extraArgs=[])

    def __stopSong(self):
        taskMgr.remove(self.taskName('songTimer'))
        self.playingIdleSong = False
        self.d_setSongPlaying(self.NoSong, 0)

    def d_setSongPlaying(self, songInfo, toonId):
        self.sendUpdate('setSongPlaying', [songInfo, toonId])
