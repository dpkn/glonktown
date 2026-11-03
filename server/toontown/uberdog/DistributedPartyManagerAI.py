from datetime import datetime, timedelta

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyAI import DistributedPartyAI
from toontown.parties.PartyGlobals import ActivityIds, AddPartyErrorCode, ChangePartyFieldErrorCode, GoToPartyStatus, \
    InviteStatus, PartyGateDenialReasons, PartyStatus
from toontown.parties.PartyStoreAI import PartyStoreAI
from toontown.parties.ToontownTimeManager import ToontownTimeManager


class DistributedPartyManagerAI(DistributedObjectAI):
    """Parties: planning, invites, the Events page, and running them. There is one district, so the parties live here
    (saved by PartyStoreAI) and the UberDOG's party messages (the *UdToAi and *AiToUd fields) are not used.

    A party is Pending until its start time, then CanStart until the host starts it from the Events page (Started) or its
    planned end passes (NeverStarted, most of the cost back). A started party runs for PARTY_DURATION, then everyone is
    sent home (Finished)."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyManagerAI')
    ActiveStatuses = (PartyStatus.Pending, PartyStatus.CanStart, PartyStatus.Started)
    PartyDuration = timedelta(hours=PartyGlobals.DefaultPartyDuration)
    RunningTime = timedelta(seconds=PartyGlobals.PARTY_DURATION)
    KeepEndedPartiesFor = timedelta(hours=PartyGlobals.UberdogPurgePartyPeriod)
    TickSeconds = 10.0

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.store = PartyStoreAI()
        self.planningZones = {}
        self.runningParties = {}

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        self.__forgetEndedParties()
        self.__recoverStartedParties()
        taskMgr.doMethodLater(self.TickSeconds, self.__tick, self.uniqueName('partyTick'))

    def delete(self):
        taskMgr.remove(self.uniqueName('partyTick'))
        DistributedObjectAI.delete(self)

    def canBuyParties(self):
        return True

    def now(self):
        return self.air.toontownTimeManager.getCurServerDateTime()

    def parseTime(self, text):
        naive = datetime.strptime(text, ToontownTimeManager.formatStr)
        return self.air.toontownTimeManager.serverTimeZone.localize(naive)

    def __forgetEndedParties(self):
        cutoff = self.now() - self.KeepEndedPartiesFor
        for partyId, party in self.store.parties():
            if party['status'] not in self.ActiveStatuses and self.parseTime(party['end']) < cutoff and 'refundOwed' not in party:
                self.store.removeParty(partyId)
        self.store.save()

    def __recoverStartedParties(self):
        """A party that was running when the district stopped can be started again by its host for the rest of its time."""
        for partyId, party in self.store.parties():
            if party['status'] == PartyStatus.Started:
                stillRunning = self.parseTime(party['startedAt']) + self.RunningTime > self.now()
                party['status'] = int(PartyStatus.CanStart if stillRunning else PartyStatus.Finished)
        self.store.save()

    def __lastMomentToStart(self, party):
        if 'startedAt' in party:
            return self.parseTime(party['startedAt']) + self.RunningTime
        return self.parseTime(party['end'])

    def __tick(self, task):
        now = self.now()
        for partyId, party in self.store.parties():
            status = party['status']
            if status in (PartyStatus.Pending, PartyStatus.CanStart) and self.__lastMomentToStart(party) <= now:
                self.__neverStarted(partyId, party)
            elif status == PartyStatus.Pending and self.parseTime(party['start']) <= now:
                self.__setStatus(partyId, party, PartyStatus.CanStart)
                host = self.air.doId2do.get(party['hostId'])
                if host is not None:
                    host.setPartyCanStart(partyId)
                    host.sendUpdate('setPartyCanStart', [partyId])
            elif status == PartyStatus.Started:
                partyAI = self.runningParties.get(partyId)
                if partyAI is None:
                    self.__setStatus(partyId, party, PartyStatus.Finished)
                elif not partyAI.isPartyEnding:
                    if self.parseTime(party['startedAt']) + self.RunningTime <= now:
                        self.__endParty(partyId)
                    else:
                        partyAI.removeGuestsWhoLeft()
        return task.again

    def __setStatus(self, partyId, party, status):
        """Saves the new status and tells the host and the guests who are online."""
        party['status'] = int(status)
        self.store.save()
        for avId in [party['hostId']] + [int(inviteeId) for inviteeId in party['invites']]:
            toon = self.air.doId2do.get(avId)
            if toon is not None:
                toon.setPartyStatus(partyId, status)
                toon.sendUpdate('setPartyStatus', [partyId, status])

    def __neverStarted(self, partyId, party):
        party['refundOwed'] = int(party['cost'] * PartyGlobals.PartyRefundPercentage)
        self.__setStatus(partyId, party, PartyStatus.NeverStarted)
        host = self.air.doId2do.get(party['hostId'])
        if host is not None:
            self.__payRefund(host, partyId, party)

    def __payRefund(self, host, partyId, party):
        refund = party.pop('refundOwed')
        self.store.save()
        host.addMoney(refund)
        host.sendUpdate('setNeverStartedPartyRefunded', [partyId, PartyStatus.NeverStarted, refund])
        self.air.writeServerEvent('party-never-started', host.doId, '%s|%s' % (partyId, refund))

    # ---- what a toon is sent about its parties
    def toonArrived(self, toon):
        self.sendPartyFields(toon)
        for partyId, party in self.store.parties():
            if party['hostId'] == toon.doId and 'refundOwed' in party:
                self.__payRefund(toon, partyId, party)

    def sendPartyFields(self, toon):
        """Sends the toon the parties it hosts (with its guests' replies) and the ones it is invited to (with its invites).
        The invites go before the parties, because receiving the parties is what updates the mailbox."""
        key = str(toon.doId)
        hosted = sorted(((partyId, party) for partyId, party in self.store.parties() if party['hostId'] == toon.doId), reverse=True)
        invitedTo = [(partyId, party) for partyId, party in self.store.parties() if key in party['invites']]
        hostedParties = [self.partyTuple(partyId, party) for partyId, party in hosted]
        replies = [(partyId, [(int(inviteeId), invite['status']) for inviteeId, invite in party['invites'].items()]) for partyId, party in hosted]
        invites = [(party['invites'][key]['inviteKey'], partyId, party['invites'][key]['status']) for partyId, party in invitedTo]
        partiesInvitedTo = [self.partyTuple(partyId, party) for partyId, party in invitedTo]
        for fieldName, setter, value in (('setHostedParties', toon.setHostedParties, hostedParties),
                                         ('setPartyReplies', toon.setPartyReplyInfoBases, replies),
                                         ('setInvites', toon.setInvites, invites),
                                         ('setPartiesInvitedTo', toon.setPartiesInvitedTo, partiesInvitedTo)):
            setter(value)
            toon.sendUpdate(fieldName, [value])

    def partyTuple(self, partyId, party):
        start = datetime.strptime(party['start'], ToontownTimeManager.formatStr)
        end = datetime.strptime(party['end'], ToontownTimeManager.formatStr)
        return (partyId, party['hostId'], start.year, start.month, start.day, start.hour, start.minute,
                end.year, end.month, end.day, end.hour, end.minute, party['isPrivate'], party['inviteTheme'],
                party['activities'], party['decorations'], party['status'])

    def __sendPartyFieldsTo(self, avIds):
        for avId in avIds:
            toon = self.air.doId2do.get(avId)
            if toon is not None:
                self.sendPartyFields(toon)

    # ---- the Party Planner
    def allocatePlanningZone(self, avId):
        """A zone of the Party Grounds for the toon to plan in, freed when the planner closes or the toon leaves."""
        self.freePlanningZone(avId)
        zoneId = self.air.allocateZone()
        self.planningZones[avId] = zoneId
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.freePlanningZone, extraArgs=[avId])
        return zoneId

    def freePlanningZone(self, avId):
        zoneId = self.planningZones.pop(avId, None)
        if zoneId is not None:
            self.ignore(self.air.getAvatarExitEvent(avId))
            self.air.deallocateZone(zoneId)

    def getPartyZone(self, avId, zoneId, planningParty):
        """Where a toon on its way to the Party Grounds goes: the planning zone it was given, the host's own party (zone 0,
        which starts it if it may start), or the party in the zone it asked for. All zeros sends it back."""
        senderId = self.air.getAvatarIdFromSender()
        if planningParty:
            if self.planningZones.get(senderId) == zoneId:
                self.sendUpdateToAvatarId(senderId, 'receivePartyZone', [senderId, 0, zoneId])
            else:
                self.sendUpdateToAvatarId(senderId, 'receivePartyZone', [0, 0, 0])
            return
        if zoneId == 0:
            partyAI = self.__startOrFindPartyHostedBy(senderId)
        else:
            partyAI = self.__partyInZone(zoneId)
        if partyAI is not None and self.__mayEnter(senderId, partyAI) == GoToPartyStatus.AllowedToGo:
            self.sendUpdateToAvatarId(senderId, 'receivePartyZone', [partyAI.getHostId(), partyAI.partyId, partyAI.zoneId])
        else:
            self.sendUpdateToAvatarId(senderId, 'receivePartyZone', [0, 0, 0])

    def requestShardIdZoneIdForHostId(self, hostId):
        """The Events page's Go button, for a guest or for a host going back to their party."""
        senderId = self.air.getAvatarIdFromSender()
        partyAI = self.__runningPartyHostedBy(hostId)
        if partyAI is not None and self.__mayEnter(senderId, partyAI) == GoToPartyStatus.AllowedToGo:
            self.sendUpdateToAvatarId(senderId, 'sendShardIdZoneIdToAvatar', [self.air.districtId, partyAI.zoneId])
        else:
            self.sendUpdateToAvatarId(senderId, 'sendShardIdZoneIdToAvatar', [0, 0])

    def exitParty(self, zoneId):
        partyAI = self.__partyInZone(zoneId)
        if partyAI is not None:
            partyAI.removeGuest(self.air.getAvatarIdFromSender())

    def removeGuest(self, ownerId, avId):
        senderId = self.air.getAvatarIdFromSender()
        partyAI = self.__runningPartyHostedBy(senderId)
        if partyAI is not None and avId in partyAI.getToonsInZone():
            self.sendUpdateToAvatarId(avId, 'sendAvToPlayground', [avId, 1])

    def __runningPartyHostedBy(self, hostId):
        for partyAI in self.runningParties.values():
            if partyAI.getHostId() == hostId:
                return partyAI
        return None

    def __partyInZone(self, zoneId):
        for partyAI in self.runningParties.values():
            if partyAI.zoneId == zoneId:
                return partyAI
        return None

    def __mayEnter(self, avId, partyAI):
        party = partyAI.party
        if partyAI.isPartyEnding:
            return GoToPartyStatus.PartyOver
        if avId == party['hostId'] or avId in partyAI.avIdsAtParty:
            return GoToPartyStatus.AllowedToGo
        if party['isPrivate'] and str(avId) not in party['invites']:
            return GoToPartyStatus.PrivateParty
        if len(partyAI.avIdsAtParty) >= PartyGlobals.MaxToonsAtAParty:
            return GoToPartyStatus.PartyFull
        return GoToPartyStatus.AllowedToGo

    def __startOrFindPartyHostedBy(self, hostId):
        partyAI = self.__runningPartyHostedBy(hostId)
        if partyAI is not None:
            return partyAI
        for partyId, party in self.store.parties():
            if party['hostId'] == hostId and party['status'] == PartyStatus.CanStart:
                return self.__startParty(partyId, party)
        return None

    def __startParty(self, partyId, party):
        party.setdefault('startedAt', self.now().strftime(ToontownTimeManager.formatStr))
        partyAI = DistributedPartyAI(self.air, self, partyId, party, party['startedAt'])
        partyAI.generateWithRequired(self.air.allocateZone())
        self.runningParties[partyId] = partyAI
        self.__setStatus(partyId, party, PartyStatus.Started)
        self.air.writeServerEvent('party-started', party['hostId'], '%s|%s' % (partyId, partyAI.zoneId))
        return partyAI

    def __endParty(self, partyId):
        """Time is up: everyone at the party gets the "party is over" message, and is sent home a little later."""
        partyAI = self.runningParties[partyId]
        partyAI.b_setPartyState(True)
        for avId in partyAI.getToonsInZone():
            self.sendUpdateToAvatarId(avId, 'sendAvToPlayground', [avId, 0])
        self.__setStatus(partyId, self.store.getParty(partyId), PartyStatus.Finished)
        taskMgr.doMethodLater(PartyGlobals.DelayBeforeAutoKick, self.__closeParty, self.uniqueName('closeParty-%d' % partyId), extraArgs=[partyId])

    def __closeParty(self, partyId):
        partyAI = self.runningParties.pop(partyId)
        for avId in partyAI.getToonsInZone():
            self.sendUpdateToAvatarId(avId, 'sendAvToPlayground', [avId, 1])
        zoneId = partyAI.zoneId
        partyAI.requestDelete()
        taskMgr.doMethodLater(PartyGlobals.DelayBeforeAutoKick, self.air.deallocateZone, self.uniqueName('freePartyZone-%d' % partyId), extraArgs=[zoneId])

    # ---- the party gate's list of public parties
    def getPublicParties(self):
        return [self.__publicPartyInfo(partyAI) for partyAI in self.runningParties.values()
                if not partyAI.party['isPrivate'] and not partyAI.isPartyEnding]

    def __publicPartyInfo(self, partyAI):
        activityIds = sorted(set(activity[0] for activity in partyAI.party['activities']) - {ActivityIds.PartyClock})
        timeLeft = self.parseTime(partyAI.party['startedAt']) + self.RunningTime - self.now()
        minutesLeft = max(0, int(timeLeft.total_seconds() // 60))
        return [self.air.districtId, partyAI.zoneId, len(partyAI.avIdsAtParty), partyAI.getHostName(), activityIds, minutesLeft]

    def choosePublicParty(self, avId, zoneId):
        """The gate's Go button: the party's info to go there with, or why not."""
        partyAI = self.__partyInZone(zoneId)
        if partyAI is None or partyAI.party['isPrivate'] or partyAI.isPartyEnding:
            return None, PartyGateDenialReasons.Unavailable
        if self.__mayEnter(avId, partyAI) == GoToPartyStatus.PartyFull:
            return None, PartyGateDenialReasons.Full
        return self.__publicPartyInfo(partyAI), None

    def freeZoneIdFromPlannedParty(self, avId, zoneId):
        senderId = self.air.getAvatarIdFromSender()
        if self.planningZones.get(senderId) == zoneId:
            self.freePlanningZone(senderId)

    def addPartyRequest(self, hostId, startTime, endTime, isPrivate, inviteTheme, activities, decorations, inviteeIds):
        senderId = self.air.getAvatarIdFromSender()
        host = self.air.doId2do.get(senderId)
        if host is None or hostId != senderId:
            self.air.writeServerEvent('suspicious', senderId, 'addPartyRequest for host %s' % hostId)
            return
        errorCode = self.__addParty(host, startTime, endTime, isPrivate, inviteTheme, activities, decorations, inviteeIds)
        self.sendUpdateToAvatarId(senderId, 'addPartyResponse', [senderId, errorCode])

    def __addParty(self, host, startTime, endTime, isPrivate, inviteTheme, activities, decorations, inviteeIds):
        if self.__activePartiesHostedBy(host.doId) >= PartyGlobals.MaxHostedPartiesPerToon:
            return AddPartyErrorCode.TooManyHostedParties
        try:
            start, end = self.parseTime(startTime), self.parseTime(endTime)
            PartyGlobals.InviteTheme(inviteTheme)
        except ValueError:
            return AddPartyErrorCode.ValidationError
        if end - start != self.PartyDuration or end <= self.now() or start.year > PartyGlobals.MaxPlannedYear:
            return AddPartyErrorCode.ValidationError
        cost = self.__gridCost(activities, decorations)
        if cost is None or not host.takeMoney(cost):
            return AddPartyErrorCode.ValidationError
        inviteeIds = [inviteeId for inviteeId in dict.fromkeys(inviteeIds) if inviteeId != host.doId]
        party = {'hostId': host.doId,
                 'hostName': host.getName(),
                 'start': start.strftime(ToontownTimeManager.formatStr),
                 'end': end.strftime(ToontownTimeManager.formatStr),
                 'isPrivate': int(bool(isPrivate)),
                 'inviteTheme': inviteTheme,
                 'activities': [list(activity) for activity in activities],
                 'decorations': [list(decoration) for decoration in decorations],
                 'status': int(PartyStatus.Pending),
                 'cost': cost}
        partyId = self.store.addParty(party, inviteeIds)
        self.store.save()
        self.air.writeServerEvent('party-planned', host.doId, '%s|%s|%s|%s' % (partyId, party['start'], cost, len(inviteeIds)))
        self.__sendPartyFieldsTo([host.doId] + inviteeIds)
        return AddPartyErrorCode.AllOk

    def __activePartiesHostedBy(self, hostId):
        return sum(1 for partyId, party in self.store.parties() if party['hostId'] == hostId and party['status'] in self.ActiveStatuses)

    def __gridCost(self, activities, decorations):
        """What the planner's grid costs, or None when something on it is unknown, off the grid or over its limit."""
        cost = 0
        for items, information, unreleased in ((activities, PartyGlobals.ActivityInformationDict, PartyGlobals.UnreleasedActivityIds),
                                               (decorations, PartyGlobals.DecorationInformationDict, PartyGlobals.UnreleasedDecorationIds)):
            counts = {}
            for itemId, x, y, h in items:
                if itemId not in information or itemId in unreleased:
                    return None
                if not (0 <= x < PartyGlobals.PartyEditorGridSize[0] and 0 <= y < PartyGlobals.PartyEditorGridSize[1]):
                    return None
                counts[itemId] = counts.get(itemId, 0) + 1
                if counts[itemId] > information[itemId]['limitPerParty']:
                    return None
                cost += information[itemId]['cost']
        return cost

    # ---- invites, answered from the mailbox
    def replyToInvite(self, inviteeId, inviteKey, status):
        """Records the invitee's answer and tells the host. False when there is no such invite or the party is over."""
        found = self.store.findInvite(inviteeId, inviteKey)
        if found is None:
            return False
        partyId, party, invite = found
        if party['status'] not in self.ActiveStatuses:
            return False
        if status == InviteStatus.ReadButNotReplied and invite['status'] != InviteStatus.NotRead:
            return True
        invite['status'] = int(status)
        self.store.save()
        invitee = self.air.doId2do.get(inviteeId)
        if invitee is not None:
            invitee.updateInvite(inviteKey, status)
            invitee.sendUpdate('updateInvite', [inviteKey, status])
        host = self.air.doId2do.get(party['hostId'])
        if host is not None:
            host.updateReply(partyId, inviteeId, status)
            host.sendUpdate('updateReply', [partyId, inviteeId, status])
        return True

    # ---- the Events page
    def changePrivateRequest(self, partyId, newPrivateStatus):
        senderId = self.air.getAvatarIdFromSender()
        party = self.store.getParty(partyId)
        if party is None or party['hostId'] != senderId:
            errorCode = ChangePartyFieldErrorCode.ValidationError
        elif party['status'] not in (PartyStatus.Pending, PartyStatus.CanStart):
            errorCode = ChangePartyFieldErrorCode.AlreadyStarted
        else:
            party['isPrivate'] = int(bool(newPrivateStatus))
            self.store.save()
            errorCode = ChangePartyFieldErrorCode.AllOk
        self.sendUpdateToAvatarId(senderId, 'changePrivateResponse', [partyId, newPrivateStatus, errorCode])

    def changePartyStatusRequest(self, partyId, newPartyStatus):
        """The host cancels a party that has not started yet, and gets most of its cost back."""
        senderId = self.air.getAvatarIdFromSender()
        host = self.air.doId2do.get(senderId)
        party = self.store.getParty(partyId)
        if host is None or party is None or party['hostId'] != senderId or newPartyStatus != PartyStatus.Cancelled:
            self.sendUpdateToAvatarId(senderId, 'changePartyStatusResponse', [partyId, party['status'] if party else newPartyStatus, ChangePartyFieldErrorCode.ValidationError, 0])
            return
        if party['status'] == PartyStatus.NeverStarted:
            self.sendUpdateToAvatarId(senderId, 'changePartyStatusResponse', [partyId, party['status'], ChangePartyFieldErrorCode.AlreadyRefunded, 0])
            return
        if party['status'] not in (PartyStatus.Pending, PartyStatus.CanStart) or 'startedAt' in party:
            self.sendUpdateToAvatarId(senderId, 'changePartyStatusResponse', [partyId, party['status'], ChangePartyFieldErrorCode.AlreadyStarted, 0])
            return
        refund = int(party['cost'] * PartyGlobals.PartyRefundPercentage)
        party['status'] = int(PartyStatus.Cancelled)
        self.store.save()
        host.addMoney(refund)
        host.setPartyStatus(partyId, PartyStatus.Cancelled)
        self.air.writeServerEvent('party-cancelled', senderId, '%s|%s' % (partyId, refund))
        self.sendUpdateToAvatarId(senderId, 'changePartyStatusResponse', [partyId, PartyStatus.Cancelled, ChangePartyFieldErrorCode.AllOk, refund])
        self.__sendPartyFieldsTo([int(inviteeId) for inviteeId in party['invites']])
