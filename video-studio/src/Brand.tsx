import React from 'react';
import {AbsoluteFill} from 'remotion';
import {isPortrait, size} from './layout';
import {JobProps} from './types';

// Optional persona name top-left (off by default for a clean look).
// No AI tag in the video: platforms apply their own AI-content labels at upload.
export const Brand: React.FC<{job: JobProps}> = ({job}) => {
  if (!job.showName) return null;
  const s = size(job.layout);
  const top = isPortrait(job.layout) ? 130 : 48;
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div style={{position: 'absolute', top, left: s.pad, fontSize: s.small, fontWeight: 700, letterSpacing: 1, color: job.theme.fg, opacity: 0.85}}>
        {job.personaName}
      </div>
    </AbsoluteFill>
  );
};
