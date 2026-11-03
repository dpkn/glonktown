import Alpine from '../../vendor/alpine-3.17.4.min.js';
import { isAndroid, isIOS, standalone } from '../lib/device.js';
import { visit } from '../lib/storage.js';

// Opened in a normal browser tab on a phone or tablet: show how to add Glonktown to the Home Screen, where it plays full screen.
// ?install=1 always shows it, ?install=0 never does.
const asked = new URLSearchParams(location.search).get('install');
export const needsInstallHelp = asked === '1'
  || ((isIOS || isAndroid) && !standalone && visit.get('ttr.skipInstall') !== '1' && asked !== '0');

let installPrompt = null;     // Chrome on Android offers a one-tap install through this event

export const install = Alpine.reactive({
  android: isAndroid,
  canInstallNow: false,
  installNow() {
    installPrompt?.prompt();
    installPrompt?.userChoice.catch(() => {});
  },
});

export function watchInstallPrompt() {
  addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    installPrompt = e;
    install.canInstallNow = true;
  });
}
