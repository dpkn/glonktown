from direct.directnotify import DirectNotifyGlobal
from toontown.parties.DistributedPartyCatchActivityAI import DistributedPartyCatchActivityAI
from toontown.toonbase import TTLocalizer


class DistributedPartyWinterCatchActivityAI(DistributedPartyCatchActivityAI):
    """The winter party's catch game: presents instead of fruit, the same game otherwise."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyWinterCatchActivityAI')
    RewardMessage = TTLocalizer.WinterPartyCatchRewardMessage
