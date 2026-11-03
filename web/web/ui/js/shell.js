import Alpine from '../vendor/alpine-3.17.4.min.js';
import { isCoarsePointer } from './lib/device.js';

// What the page is showing. The screens follow each other as
//   loading (start-up) -> welcome -> login -> loading (download, then the game starting) -> game
// with the install instructions, the turn-your-phone prompt and the Display dialog over whichever is up.
export const shell = Alpine.reactive({
  screen: 'loading',
  installing: false,      // the add-to-home-screen instructions are up
  dialog: null,           // 'display' | 'keys'
  titleRaised: false,     // the title moves up to make room for the sign-in dialog, and stays there
  skyUrl: '',             // the game's sky behind everything, once loaded
  portrait: false,        // a phone or tablet held upright

  get playing() { return this.screen === 'game'; },
  get showsFloatingTitle() { return this.screen === 'loading' || this.screen === 'login'; },
  // iOS has no way to lock a page to landscape, so it asks
  get asksToRotate() { return this.portrait && !this.installing && this.screen !== 'welcome'; },
});

export function watchOrientation() {
  const update = () => { shell.portrait = isCoarsePointer() && innerHeight > innerWidth; };
  update();
  addEventListener('resize', update);
  addEventListener('orientationchange', () => setTimeout(update, 150));
}
