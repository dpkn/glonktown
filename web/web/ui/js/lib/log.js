import { server, isTestServer } from './server.js';
import { visit } from './storage.js';

// Test sessions (the local test servers, or a page opened with ?log=1, kept for the rest of the visit) send everything the game prints,
// plus any page error or crash message, to the server's /__log, where it is saved with the time and this device's address.
if (/[?&]log=1/.test(location.search)) visit.set('ttr.log', '1');
const fullLogging = isTestServer || visit.get('ttr.log') === '1';

function beacon(line) {
  try { navigator.sendBeacon(server.url('/__log'), line); } catch {}
}

// Everyone else is logged quietly: only crash information (Python tracebacks, errors, lost connections, page errors) and one line about
// the device and the sign-in name. No passwords, no touches, no frame timings. At most 400 lines per visit.
const QUIET_LIMIT = 400;
const WORTH_SENDING = /Traceback|[A-Za-z_]*(Error|Exception)\b|STEP FAILED|reconnecting|webnet: (closed|error)|game ended|Aborted/;
let quietSent = 0;
let tracebackLinesLeft = 0;
let lastQuietLine = '';

function isWorthSending(line) {
  if (line.startsWith('PY|')) {
    const text = line.slice(3).trim();
    if (/Traceback \(most recent call last\)/.test(text)) {
      tracebackLinesLeft = 30;
      return true;
    }
    if (tracebackLinesLeft > 0) {
      tracebackLinesLeft--;
      if (/^[A-Za-z_.]*(Error|Exception)\b/.test(text)) tracebackLinesLeft = 0;    // the traceback's last line
      return true;
    }
    return WORTH_SENDING.test(text);
  }
  return /^JS\| (page error|unhandled|console\.error|session)/.test(line);
}

function quietLog(line) {
  if (quietSent >= QUIET_LIMIT || !isWorthSending(line) || line === lastQuietLine) return;
  lastQuietLine = line;
  quietSent++;
  beacon(line);
}

// The screen facts ("JS| env ..." lines, see dev.js): a few per visit, as a plain request the web server's own log records.
let screenFactsSent = 0;
function screenFact(line) {
  if (screenFactsSent >= 12) return;
  screenFactsSent++;
  try { new Image().src = server.url('/__d?') + encodeURIComponent(line) + '&r=' + Date.now(); } catch {}
}

export function log(line) {
  if (fullLogging) beacon(line);
  else if (line.startsWith('JS| env')) screenFact(line);
  else quietLog(line);
}

export function startLogging() {
  addEventListener('error', (e) => log('JS| page error: ' + e.message + ' @ ' + (e.filename || '') + ':' + (e.lineno || '')));
  addEventListener('unhandledrejection', (e) => log('JS| unhandled rejection: ' + (e.reason && (e.reason.stack || e.reason.message) || e.reason)));

  for (const level of fullLogging ? ['error', 'warn'] : ['error']) {
    const original = console[level];
    console[level] = function (...args) {
      original.apply(console, args);
      try { log('JS| console.' + level + ': ' + args.map(String).join(' ').slice(0, 600)); } catch {}
    };
  }

  // the game prints through console.log, every line starting with "PY|"
  const originalLog = console.log;
  console.log = function (...args) {
    originalLog.apply(console, args);
    try {
      const line = String(args[0]);
      if (line.startsWith('PY|')) log(line);
    } catch {}
  };

  log((fullLogging ? 'JS| log session started: ' : 'JS| session: ') + navigator.userAgent + ' ' + innerWidth + 'x' + innerHeight);
}
