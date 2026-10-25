import React from 'react';
import {AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame} from 'remotion';
import {fadeIn, isPortrait, rise, size} from '../layout';
import {JobProps, Segment} from '../types';

const Clip: React.FC<{seg: Segment; job: JobProps}> = ({seg, job}) =>
  seg.video ? (
    // Muted: narration comes from the segment audio track, the clip is lip-synced to it.
    <OffthreadVideo src={staticFile(seg.video)} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
  ) : (
    <AbsoluteFill style={{background: job.theme.panel, justifyContent: 'center', alignItems: 'center', color: job.theme.muted, fontSize: 40}}>
      presenter clip {seg.id} missing
    </AbsoluteFill>
  );

export const Presenter: React.FC<{seg: Segment; job: JobProps}> = ({seg, job}) => {
  const frame = useCurrentFrame();
  const s = size(job.layout);

  if (isPortrait(job.layout)) {
    return (
      <AbsoluteFill>
        <Clip seg={seg} job={job} />
      </AbsoluteFill>
    );
  }

  // Landscape: portrait clip in a panel on the left, the segment's key line on the right.
  return (
    <AbsoluteFill style={{flexDirection: 'row', background: job.theme.bg}}>
      <div style={{width: 760, height: '100%', overflow: 'hidden', position: 'relative'}}>
        <Clip seg={seg} job={job} />
      </div>
      <div style={{flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: `0 ${s.pad}px`}}>
        <div style={{width: 90, height: 8, background: job.theme.accent, borderRadius: 4, marginBottom: 36, opacity: fadeIn(frame, 4)}} />
        {seg.onScreen ? (
          <div style={{fontSize: s.headline * 0.8, fontWeight: 800, lineHeight: 1.15, opacity: fadeIn(frame, 6), transform: `translateY(${rise(frame, 6)}px)`}}>
            {seg.onScreen}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
