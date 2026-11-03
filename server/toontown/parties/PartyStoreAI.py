import json
import os
import traceback

from direct.directnotify import DirectNotifyGlobal


class PartyStoreAI:
    """Every planned party and its invites, in one JSON file in the server's data folder so they survive restarts:

      {"nextPartyId": 2, "nextInviteKey": 3,
       "parties": {"1": {"hostId": 100000001, "hostName": "Flippy", "start": "2026-11-03 20:00:00", "end": "2026-11-03 20:30:00",
                         "isPrivate": 0, "inviteTheme": 1, "activities": [[id, x, y, h], ...], "decorations": [[id, x, y, h], ...],
                         "status": 0, "cost": 300, "invites": {"100000002": {"inviteKey": 1, "status": 0}}}}}

    Times are wall-clock times in the game's time zone, as the planner sends them."""
    notify = DirectNotifyGlobal.directNotify.newCategory('PartyStoreAI')
    FILE = os.environ.get('OT_PARTIES_FILE', '/ot/data/parties.json')

    def __init__(self):
        self.data = self.__load()

    def __load(self):
        data = {}
        try:
            with open(self.FILE) as f:
                data = json.load(f)
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            self.notify.warning('could not read the parties, starting with none: ' + traceback.format_exc())
            try:
                os.replace(self.FILE, self.FILE + '.bad')
            except OSError:
                pass
        data.setdefault('nextPartyId', 1)
        data.setdefault('nextInviteKey', 1)
        data.setdefault('parties', {})
        return data

    def save(self):
        try:
            tmp = self.FILE + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(self.data, f)
            os.replace(tmp, self.FILE)
        except OSError:
            self.notify.warning('could not save the parties: ' + traceback.format_exc())

    def parties(self):
        return [(int(partyId), party) for partyId, party in self.data['parties'].items()]

    def getParty(self, partyId):
        return self.data['parties'].get(str(partyId))

    def addParty(self, party, inviteeIds):
        partyId = self.data['nextPartyId']
        self.data['nextPartyId'] += 1
        party['invites'] = {}
        for inviteeId in inviteeIds:
            party['invites'][str(inviteeId)] = {'inviteKey': self.data['nextInviteKey'], 'status': 0}
            self.data['nextInviteKey'] += 1
        self.data['parties'][str(partyId)] = party
        return partyId

    def removeParty(self, partyId):
        self.data['parties'].pop(str(partyId), None)

    def findInvite(self, inviteeId, inviteKey):
        for partyId, party in self.parties():
            invite = party['invites'].get(str(inviteeId))
            if invite and invite['inviteKey'] == inviteKey:
                return partyId, party, invite
        return None
