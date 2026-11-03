"""Shared data for the walking toons that make the playgrounds and streets feel busy (DistributedNPCWalker).

Each playground borrows the walking route of its classic character (Mickey's in Glonktown Central, and so on): those routes are
known to stay on the ground and out of the water. A playground without a route here gets no walkers. On the streets they walk the
Cogs' paths, and fight.
"""
import math
import random
from panda3d.core import Point3, Vec3
from toontown.toonbase import ToontownGlobals, TTLocalizer, ToontownBattleGlobals
from toontown.classicchars import CCharPaths

# Walkers per playground and per street when gameconfig.json has no "walkers" or "street_walkers" setting
DEFAULT_COUNT = 15
DEFAULT_STREET_COUNT = 8
MAX_COUNT = 30

WALK_SPEED = ToontownGlobals.ToonForwardSlowSpeed
RUN_SPEED = ToontownGlobals.ToonForwardSpeed

# setWalk flags
FLAG_RUN = 1
FLAG_RAYCAST = 2
FLAG_HIDDEN = 4

# doTeleport directions
TELEPORT_IN = 0
TELEPORT_OUT = 1

# setWalk heading meaning "keep facing the way you walked"
KEEP_HEADING = -1

# Seconds a walker spends on one hop through the trolley before it may come back
TROLLEY_TRIP_TIME = (60, 150)

# The hood's classic character whose route the walkers use, as (name, CCharPaths location)
_Routes = {
    ToontownGlobals.ToontownCentral: (TTLocalizer.Mickey, 0),
    ToontownGlobals.TheBrrrgh: (TTLocalizer.Pluto, 0),
    ToontownGlobals.MinniesMelodyland: (TTLocalizer.Minnie, 0),
    ToontownGlobals.DaisyGardens: (TTLocalizer.Daisy, 0),
    ToontownGlobals.OutdoorZone: (TTLocalizer.Chip, 0),
    ToontownGlobals.GoofySpeedway: (TTLocalizer.Goofy, 1),
    ToontownGlobals.DonaldsDreamland: (TTLocalizer.Donald, 0),
}

# Trolley stations from the playground DNA files: position and heading
_TrolleyStations = {
    ToontownGlobals.ToontownCentral: (Point3(-120.945, -77.5626, 0.525), 128),
    ToontownGlobals.TheBrrrgh: (Point3(52.5, 55.8, 6.15), -70),
    ToontownGlobals.MinniesMelodyland: (Point3(-54.0463, 55.8937, 6.5), 45),
    ToontownGlobals.DaisyGardens: (Point3(8.37, 222.32, 10), 0),
    ToontownGlobals.DonaldsDreamland: (Point3(64, -105.2, 0), -180),
}

# Where a toon stands in front of the trolley, and where it hops to, in the station's own frame (the client puts toons who step
# off the trolley at (12..21, -5))
_TrolleyApproach = Point3(15, -8, 0)
_TrolleyHop = Point3(15, 4, 0)

# Speed Chat phrases (OTPLocalizer.SpeedChatStaticTextToontown) a walker says now and then
IdlePhrases = (300, 301, 303, 304, 306, 307, 308, 310, 311, 315, 505, 506, 509, 705, 1000, 1003, 1009, 1100, 1117, 1102,
               1103, 1105, 1106, 1107, 1108, 1109, 1110, 1111, 1203, 1205, 1299)
GreetPhrases = (100, 101, 102, 103, 104, 107, 108, 600, 601, 602, 700, 701, 510)
TrolleyPhrases = (1100, 301, 1000, 304)
LeavePhrases = (200, 201, 202, 204, 206, 207, 208)

# Emote indices (TTEmote.EmoteFunc)
EmoteWave = 0
IdleEmotes = (1, 5, 6, 7, 8, 9, 11, 13, 17, 22, 24)


def getRoute(hoodId):
    """The route graph {node: (Point3, (neighbour, ...))} for a playground, or None."""
    route = _Routes.get(hoodId)
    if not route:
        return None
    return CCharPaths.getPaths(*route)


def getNeighbours(route, node):
    neighbours = CCharPaths.getAdjacentNodes(node, route)
    if isinstance(neighbours, str):
        return (neighbours,)
    return tuple(neighbours)


def getLegPoints(route, fromNode, toNode):
    """The points between two neighbouring nodes, without the two ends, and whether the leg needs the floor raycast."""
    return CCharPaths.getWayPoints(fromNode, toNode, route), CCharPaths.getRaycastFlag(fromNode, toNode, route)


def _stationPoint(hoodId, local):
    pos, h = _TrolleyStations[hoodId]
    rad = math.radians(h)
    x = local[0] * math.cos(rad) - local[1] * math.sin(rad)
    y = local[0] * math.sin(rad) + local[1] * math.cos(rad)
    return Point3(pos[0] + x, pos[1] + y, pos[2] + local[2])


def getTrolleyApproach(hoodId):
    if hoodId not in _TrolleyStations:
        return None
    return _stationPoint(hoodId, _TrolleyApproach)


def getTrolleyHop(hoodId):
    return _stationPoint(hoodId, _TrolleyHop)


def pathLength(points):
    return sum((Vec3(points[i + 1] - points[i]).length() for i in range(len(points) - 1)))


def getStreetRoute(suitPlanner):
    """A street's route graph, in the same form as a playground's, made from the Cogs' street paths (not the building doors)."""
    store = suitPlanner.dnaStore
    points = dict((p.getIndex(), p) for p in suitPlanner.streetPointList)
    neighbours = dict((i, set()) for i in points)
    for i, point in points.items():
        adjacent = store.getAdjacentPoints(point)
        for n in range(adjacent.getNumPoints()):
            j = adjacent.getPointIndex(n)
            if j in points and j != i:
                neighbours[i].add(j)
                neighbours[j].add(i)
    route = {}
    for i, point in points.items():
        if neighbours[i]:
            route[i] = (Point3(point.getPos()), tuple(sorted(neighbours[i])))
    return route


# Gag tracks a walker may carry. Walkers do not lure or trap: those need planning with the other toons
FIGHT_TRACKS = (ToontownBattleGlobals.THROW_TRACK, ToontownBattleGlobals.SQUIRT_TRACK, ToontownBattleGlobals.SOUND_TRACK,
                ToontownBattleGlobals.DROP_TRACK)


def randomFighter():
    """Laff, gag tracks and experience for a new walker, from a fresh toon to a well-trained one."""
    tier = random.choice((1, 2, 2, 3, 3, 4, 4, 5, 5, 6))
    tracks = [0] * len(ToontownBattleGlobals.Tracks)
    tracks[ToontownBattleGlobals.THROW_TRACK] = 1
    tracks[ToontownBattleGlobals.SQUIRT_TRACK] = 1
    for track in (ToontownBattleGlobals.HEAL_TRACK, ToontownBattleGlobals.SOUND_TRACK, ToontownBattleGlobals.DROP_TRACK):
        if random.random() < 0.25 + tier * 0.1:
            tracks[track] = 1
    experience = []
    for track in range(len(tracks)):
        if tracks[track]:
            level = max(1, min(6, tier + random.choice((-1, 0, 0, 1))))
            experience.append(ToontownBattleGlobals.Levels[track][level])
        else:
            experience.append(0)
    maxHp = min(ToontownGlobals.MaxHpLimit, 15 + tier * 15 + random.randint(0, 10))
    return {'maxHp': maxHp, 'tracks': tracks, 'experience': experience, 'maxCarry': 20 + tier * 10}
