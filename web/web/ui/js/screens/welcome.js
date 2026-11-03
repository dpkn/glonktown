import Alpine from '../../vendor/alpine-3.17.4.min.js';
import { server, serverIsOpen } from '../lib/server.js';
import { shell } from '../shell.js';

// The welcome page: one card on the sky with the title half over its top edge, a bit of Glonktown's story, and the way in. PLAY only
// shows while the game server answers; a closed server gets a note that says so, and is asked again every half minute. Under it, the
// leaderboard: every toon on the server, best first (the server's /leaderboard.json), with who is playing right now and when the others
// last were. It stays hidden on a server without one.

const RECHECK_EVERY = 30000;
const SPECIES = { dog: '🐶', cat: '🐱', horse: '🐴', mouse: '🐭', rabbit: '🐰', duck: '🦆', pig: '🐷', bear: '🐻', monkey: '🐵' };
const MEDALS = ['🥇', '🥈', '🥉'];
const relativeTime = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

function lastSeen(secondsAgo) {
  for (const [unit, size] of [['week', 604800], ['day', 86400], ['hour', 3600], ['minute', 60]]) {
    if (secondsAgo >= size) return 'Last seen ' + relativeTime.format(-Math.floor(secondsAgo / size), unit);
  }
  return 'Last seen just now';
}

let recheckTimer = 0;
let leaderboardTimer = 0;

export const welcome = Alpine.reactive({
  state: 'checking',      // checking | open | closed
  retrying: false,
  toons: [],
  now: 0,

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
    return lastSeen(this.now - toon.lastSeen);
  },
  gagTracks: (toon) => toon.tracks === 1 ? 'gag track' : 'gag tracks',

  setState(state) {
    this.state = state;
    this.retrying = false;
    if (state === 'open') this.loadLeaderboard();
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
});
