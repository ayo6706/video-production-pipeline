export type Layout = 'landscape' | 'portrait';

export type Word = {text: string; start: number; end: number};

export type Scene =
  | {kind: 'title'; headline: string; kicker?: string; source_ref?: string}
  | {kind: 'stat'; value: string; label: string; before?: string; source_ref?: string}
  | {kind: 'points'; items: string[]; heading?: string; source_ref?: string}
  | {kind: 'quote'; text: string; attribution: string; source_ref?: string}
  | {kind: 'screenshot'; image: string; caption?: string; source_ref?: string}
  | {kind: 'clip'; video: string; video_portrait?: string; start?: number; rate?: number; fit?: 'cover' | 'contain'; position?: string; caption?: string}
  | {kind: 'query'; text: string; label?: string; source_ref?: string}
  | {kind: 'cta'; line: string; handle?: string};

export type Segment = {
  id: string;
  type: 'presenter' | 'screen';
  durationInFrames: number;
  audio?: string;
  video?: string;
  onScreen?: string;
  scene?: Scene;
  words: Word[];
};

export type Theme = {
  bg: string;
  fg: string;
  accent: string;
  muted: string;
  panel: string;
  font: string;
};

export type JobProps = {
  slug: string;
  title: string;
  fps: number;
  layout: Layout;
  theme: Theme;
  personaName: string;
  showName: boolean;
  handle: string;
  music: string;
  musicVolume: number;
  segments: Segment[];
};

// Generic preview data only. Replace it with a configured persona and approved script.
export const sampleJob: JobProps = {
  slug: 'demo',
  title: 'Sample presenter video',
  fps: 30,
  layout: 'landscape',
  theme: {
    bg: '#111827',
    fg: '#F9FAFB',
    accent: '#3B82F6',
    muted: '#9CA3AF',
    panel: '#1F2937',
    font: 'Arial, sans-serif',
  },
  personaName: 'Presenter',
  showName: false,
  handle: '',
  music: '',
  musicVolume: 0.08,
  segments: [
    {
      id: 's01',
      type: 'presenter',
      durationInFrames: 120,
      onScreen: 'Your opening line',
      words: 'Replace this with your approved narration.'
        .split(' ')
        .map((t, i) => ({text: t, start: i * 0.3, end: (i + 1) * 0.3})),
    },
    {
      id: 's02',
      type: 'screen',
      durationInFrames: 120,
      scene: {kind: 'title', headline: 'Your example headline'},
      words: [],
    },
  ],
};
