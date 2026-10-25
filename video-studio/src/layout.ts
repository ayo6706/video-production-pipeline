import {interpolate} from 'remotion';
import {Layout} from './types';

export const isPortrait = (layout: Layout) => layout === 'portrait';

// Type scale per layout. Portrait is viewed small on a phone, so text is larger relative to width.
export const size = (layout: Layout) =>
  isPortrait(layout)
    ? {pad: 80, headline: 92, body: 54, stat: 190, small: 34, caption: 58}
    : {pad: 110, headline: 88, body: 48, stat: 170, small: 30, caption: 50};

// Portrait safe area: keep text out of the top ~12% and bottom ~20% (platform UI).
export const safe = (layout: Layout) =>
  isPortrait(layout) ? {top: 240, bottom: 400} : {top: 90, bottom: 150};

export const fadeIn = (frame: number, delay = 0, length = 10) =>
  interpolate(frame - delay, [0, length], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

export const rise = (frame: number, delay = 0, length = 12, distance = 24) =>
  interpolate(frame - delay, [0, length], [distance, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
