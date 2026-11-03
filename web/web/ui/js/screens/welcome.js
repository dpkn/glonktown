import Alpine from '../../vendor/alpine-3.17.4.min.js';
import { server, serverIsOpen } from '../lib/server.js';
import { shell } from '../shell.js';

// The welcome page: one card on the sky with the title half over its top edge, a bit of Glonktown's story, and the way in. PLAY only
// shows while the game server answers; a closed server gets a note that says so, and is asked again every half minute. Under it, the
// Save Glonktown card: the goal the whole town works on together, its rewards and what happened lately (the server's
// /community_goal.json). Then the leaderboard: every toon on the server, best first (/leaderboard.json), with who is playing right now
// and when the others last were. Each card stays hidden on a server without its file.

const RECHECK_EVERY = 30000;
const SPECIES = { dog: '🐶', cat: '🐱', horse: '🐴', mouse: '🐭', rabbit: '🐰', duck: '🦆', pig: '🐷', bear: '🐻', monkey: '🐵' };
const MEDALS = ['🥇', '🥈', '🥉'];
const relativeTime = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

function ago(secondsAgo) {
  for (const [unit, size] of [['week', 604800], ['day', 86400], ['hour', 3600], ['minute', 60]]) {
    if (secondsAgo >= size) return relativeTime.format(-Math.floor(secondsAgo / size), unit);
  }
  return 'just now';
}

const points = (number) => number.toLocaleString('en');

let recheckTimer = 0;
let leaderboardTimer = 0;
let goalTimer = 0;

export const welcome = Alpine.reactive({
  state: 'checking',      // checking | open | closed
  retrying: false,
  toons: [],
  now: 0,
  goal: null,
  goalLoadedAt: 0,

  get visible() { return shell.screen === 'welcome'; },
  get playingCount() { return this.toons.filter((toon) => toon.online).length; },
  get summary() {
    const playing = this.playingCount;
    if (!playing) return 'Nobody is playing right now.';
    return (playing === 1 ? '1 toon is' : playing + ' toons are') + ' playing right now. Come say hi!';
  },
  rank: (index) => MEDALS[index] || index + 1,
  face: (toon) => SPECIES[toon.species] || '⭐',
  whereabouts(toon) {
    if (toon.online) return 'Playing now' + (toon.where ? ' in ' + toon.where : '');
    return 'Last seen ' + ago(this.now - toon.lastSeen);
  },
  gagTracks: (toon) => toon.tracks === 1 ? 'gag track' : 'gag tracks',

  get goalPercent() { return Math.min(100, Math.floor(100 * this.goal.points / this.goal.target)); },
  get goalSaved() { return this.goal.points >= this.goal.target; },
  get goalSummary() {
    if (this.goalSaved) return 'Glonktown is saved! Thank you, everyone.';
    return points(this.goal.points) + ' of ' + points(this.goal.target) + ' points';
  },
  get goalNext() { return this.goal.milestones.find((milestone) => !milestone.reached); },
  get goalHelpers() {
    return Object.values(this.goal.helpers).filter((helper) => helper.points > 0).sort((a, b) => b.points - a.points).slice(0, 5);
  },
  milestoneLabel: (milestone) => points(milestone.at) + ' points',
  helperPoints: (helper) => points(helper.points),
  eventTime(event) { return ago(this.goalLoadedAt - event.time); },

  setState(state) {
    this.state = state;
    this.retrying = false;
    if (state === 'open') {
      this.loadLeaderboard();
      this.loadGoal();
    }
  },

  async checkServer() {
    clearTimeout(recheckTimer);
    const open = await serverIsOpen();
    if (!this.visible) return open;
    this.setState(open ? 'open' : 'closed');
    if (!open) this.recheckLater();
    return open;
  },
  recheckLater() {
    clearTimeout(recheckTimer);
    recheckTimer = setTimeout(() => this.checkServer(), RECHECK_EVERY);
  },
  retry() {
    this.retrying = true;
    this.checkServer();
  },

  async loadLeaderboard() {
    clearTimeout(leaderboardTimer);
    if (!this.visible) return;
    try {
      const response = await fetch(server.url('/leaderboard.json'), { cache: 'no-store' });
      if (response.ok) {
        const { now, toons } = await response.json();
        this.now = now;
        this.toons = toons;
      }
    } catch {}
    leaderboardTimer = setTimeout(() => this.loadLeaderboard(), RECHECK_EVERY);
  },

  async loadGoal() {
    clearTimeout(goalTimer);
    if (!this.visible) return;
    try {
      const response = await fetch(server.url('/community_goal.json'), { cache: 'no-store' });
      if (response.ok) {
        this.goal = await response.json();
        this.goalLoadedAt = Math.floor(Date.now() / 1000);
      }
    } catch {}
    goalTimer = setTimeout(() => this.loadGoal(), RECHECK_EVERY);
  },
});
