import Alpine from '../../vendor/alpine-3.17.4.min.js';

// The loading screen: the game's loading bar under a status line, a spinner while the game itself starts, and what went wrong if the
// download failed.
export const loading = Alpine.reactive({
  status: 'Getting ready...',
  detail: '',
  progress: 0,          // 0 to 1
  starting: false,      // the files are in, the game is starting: a spinner instead of the bar
  error: '',

  report(status, detail = '', progress = null) {
    this.status = status;
    this.detail = detail;
    if (progress !== null) {
      this.progress = Math.max(0, Math.min(1, progress));
      this.starting = false;
    }
  },
  showStarting() {
    this.report('Starting Glonktown...');
    this.starting = true;
  },
  fail(message) {
    this.starting = false;
    this.status = 'Something went wrong';
    this.error = message;
  },
  reset() {
    this.error = '';
    this.starting = false;
  },
});
