import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {fadeIn, isPortrait, rise, safe, size} from '../layout';
import {JobProps, Scene} from '../types';

type Of<K extends Scene['kind']> = Extract<Scene, {kind: K}>;

const Frame: React.FC<{job: JobProps; children: React.ReactNode; align?: 'center' | 'flex-start'}> = ({job, children, align = 'flex-start'}) => {
  const s = size(job.layout);
  const sa = safe(job.layout);
  return (
    <AbsoluteFill
      style={{
        background: job.theme.bg,
        padding: `${sa.top}px ${s.pad}px ${sa.bottom}px`,
        justifyContent: 'center',
        alignItems: align,
        textAlign: align === 'center' ? 'center' : 'left',
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

const Kicker: React.FC<{job: JobProps; text?: string; delay?: number}> = ({job, text, delay = 0}) => {
  const frame = useCurrentFrame();
  if (!text) return null;
  return (
    <div style={{fontSize: size(job.layout).small, fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', color: job.theme.accent, marginBottom: 28, opacity: fadeIn(frame, delay)}}>
      {text}
    </div>
  );
};

export const Title: React.FC<{scene: Of<'title'>; job: JobProps}> = ({scene, job}) => {
  const frame = useCurrentFrame();
  return (
    <Frame job={job}>
      <Kicker job={job} text={scene.kicker} />
      <div style={{fontSize: size(job.layout).headline, fontWeight: 800, lineHeight: 1.1, maxWidth: 1500, opacity: fadeIn(frame, 4), transform: `translateY(${rise(frame, 4)}px)`}}>
        {scene.headline}
      </div>
    </Frame>
  );
};

export const Stat: React.FC<{scene: Of<'stat'>; job: JobProps}> = ({scene, job}) => {
  const frame = useCurrentFrame();
  const s = size(job.layout);
  const portrait = isPortrait(job.layout);
  return (
    <Frame job={job}>
      {scene.before ? (
        <div style={{display: 'flex', flexDirection: portrait ? 'column' : 'row', alignItems: portrait ? 'flex-start' : 'center', gap: portrait ? 10 : 40}}>
          <div style={{fontSize: s.stat * 0.45, fontWeight: 700, color: job.theme.muted, textDecoration: 'line-through', opacity: fadeIn(frame, 2)}}>{scene.before}</div>
          <div style={{fontSize: s.stat * 0.4, color: job.theme.muted, opacity: fadeIn(frame, 10)}}>{portrait ? '↓' : '→'}</div>
          <div style={{fontSize: s.stat * 0.7, fontWeight: 900, color: job.theme.accent, opacity: fadeIn(frame, 16), transform: `translateY(${rise(frame, 16)}px)`}}>{scene.value}</div>
        </div>
      ) : (
        <div style={{fontSize: s.stat, fontWeight: 900, color: job.theme.accent, lineHeight: 1, opacity: fadeIn(frame, 2), transform: `translateY(${rise(frame, 2)}px)`}}>{scene.value}</div>
      )}
      <div style={{fontSize: s.body, marginTop: 36, maxWidth: 1400, lineHeight: 1.3, opacity: fadeIn(frame, 20)}}>{scene.label}</div>
    </Frame>
  );
};

export const Points: React.FC<{scene: Of<'points'>; job: JobProps; duration: number}> = ({scene, job, duration}) => {
  const frame = useCurrentFrame();
  const s = size(job.layout);
  // Reveal items evenly through the first ~75% of the segment.
  const step = (duration * 0.75) / Math.max(1, scene.items.length);
  return (
    <Frame job={job}>
      <Kicker job={job} text={scene.heading} />
      {scene.items.map((item, i) => {
        const d = 6 + i * step;
        return (
          <div key={i} style={{display: 'flex', alignItems: 'center', gap: 28, marginBottom: 34, opacity: fadeIn(frame, d), transform: `translateY(${rise(frame, d)}px)`}}>
            <div style={{width: s.body * 0.9, height: s.body * 0.9, borderRadius: 999, background: job.theme.accent, color: job.theme.bg, fontWeight: 900, fontSize: s.body * 0.55, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0}}>
              {i + 1}
            </div>
            <div style={{fontSize: s.body * 1.1, fontWeight: 700, lineHeight: 1.2}}>{item}</div>
          </div>
        );
      })}
    </Frame>
  );
};

export const Quote: React.FC<{scene: Of<'quote'>; job: JobProps}> = ({scene, job}) => {
  const frame = useCurrentFrame();
  const s = size(job.layout);
  return (
    <Frame job={job}>
      <div style={{fontSize: s.stat * 0.6, color: job.theme.accent, lineHeight: 0.6, height: s.stat * 0.35, opacity: fadeIn(frame)}}>“</div>
      <div style={{fontSize: s.headline * 0.72, fontWeight: 700, lineHeight: 1.25, maxWidth: 1500, opacity: fadeIn(frame, 4)}}>{scene.text}</div>
      <div style={{fontSize: s.small, color: job.theme.muted, marginTop: 36, opacity: fadeIn(frame, 14)}}>{scene.attribution}</div>
    </Frame>
  );
};

export const Screenshot: React.FC<{scene: Of<'screenshot'>; job: JobProps; duration: number}> = ({scene, job, duration}) => {
  const frame = useCurrentFrame();
  const s = size(job.layout);
  const sa = safe(job.layout);
  const zoom = interpolate(frame, [0, duration], [1, 1.06], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: job.theme.bg, padding: `${sa.top}px ${s.pad * 0.6}px ${sa.bottom}px`, justifyContent: 'center', alignItems: 'center'}}>
      <div style={{width: '100%', flex: 1, overflow: 'hidden', borderRadius: 20, background: job.theme.panel, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <Img src={staticFile(scene.image)} style={{maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', transform: `scale(${zoom})`}} />
      </div>
      {scene.caption ? <div style={{fontSize: s.small, color: job.theme.muted, marginTop: 20}}>{scene.caption}</div> : null}
    </AbsoluteFill>
  );
};

export const Clip: React.FC<{scene: Of<'clip'>; job: JobProps}> = ({scene, job}) => {
  // Real screen recording, full frame. Portrait uses video_portrait (e.g. a phone recording) when given.
  const src = isPortrait(job.layout) && scene.video_portrait ? scene.video_portrait : scene.video;
  return (
    <AbsoluteFill style={{background: '#000'}}>
      <OffthreadVideo
        src={staticFile(src)}
        muted
        trimBefore={Math.round((scene.start ?? 0) * job.fps)}
        playbackRate={scene.rate ?? 1}
        style={{width: '100%', height: '100%', objectFit: scene.fit ?? 'cover', objectPosition: scene.position ?? 'center'}}
      />
    </AbsoluteFill>
  );
};

export const Cta: React.FC<{scene: Of<'cta'>; job: JobProps}> = ({scene, job}) => {
  const frame = useCurrentFrame();
  const s = size(job.layout);
  const handle = scene.handle || job.handle;
  return (
    <Frame job={job} align="center">
      <div style={{fontSize: s.headline * 0.75, fontWeight: 800, lineHeight: 1.2, maxWidth: 1400, opacity: fadeIn(frame, 2), transform: `translateY(${rise(frame, 2)}px)`}}>{scene.line}</div>
      {handle ? (
        <div style={{marginTop: 50, fontSize: s.body, fontWeight: 700, color: job.theme.bg, background: job.theme.accent, padding: '14px 36px', borderRadius: 999, opacity: fadeIn(frame, 14)}}>
          {handle}
        </div>
      ) : null}
      {job.showName ? <div style={{marginTop: 28, fontSize: s.small, color: job.theme.muted, opacity: fadeIn(frame, 20)}}>{job.personaName}</div> : null}
    </Frame>
  );
};

export const Query: React.FC<{scene: Of<'query'>; job: JobProps; duration: number}> = ({scene, job, duration}) => {
  const frame = useCurrentFrame();
  const s = size(job.layout);
  const portrait = isPortrait(job.layout);
  // Type the query over the first ~55% of the segment, then hold it.
  const typed = Math.round(interpolate(frame, [8, Math.max(9, duration * 0.55)], [0, scene.text.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const cursorOn = Math.floor(frame / 15) % 2 === 0;
  return (
    <Frame job={job}>
      <Kicker job={job} text={scene.label} />
      <div
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 24,
          background: '#FFFFFF',
          color: '#202124',
          borderRadius: 999,
          padding: portrait ? '30px 40px' : '28px 48px',
          boxShadow: '0 10px 40px rgba(0,0,0,0.35)',
          opacity: fadeIn(frame, 0, 8),
        }}
      >
        <svg width={s.body} height={s.body} viewBox="0 0 24 24" style={{flexShrink: 0}}>
          <circle cx="10" cy="10" r="6.5" stroke="#5F6368" strokeWidth="2.2" fill="none" />
          <line x1="15" y1="15" x2="21" y2="21" stroke="#5F6368" strokeWidth="2.4" strokeLinecap="round" />
        </svg>
        <div style={{fontFamily: "Consolas, 'Courier New', monospace", fontSize: portrait ? s.body * 0.95 : s.body, fontWeight: 600, wordBreak: 'break-word'}}>
          {scene.text.slice(0, typed)}
          <span style={{opacity: cursorOn ? 1 : 0, color: job.theme.accent}}>|</span>
        </div>
      </div>
    </Frame>
  );
};
