import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile} from 'remotion';
import {Brand} from './Brand';
import {Captions} from './Captions';
import {SegmentView} from './SegmentView';
import {JobProps} from './types';

export const Video: React.FC<JobProps> = (job) => {
  let from = 0;
  return (
    <AbsoluteFill style={{background: job.theme.bg, color: job.theme.fg, fontFamily: job.theme.font}}>
      {job.segments.map((seg) => {
        const start = from;
        from += seg.durationInFrames;
        return (
          <Sequence key={seg.id} name={seg.id} from={start} durationInFrames={seg.durationInFrames}>
            <SegmentView seg={seg} job={job} />
            {seg.audio ? <Audio src={staticFile(seg.audio)} /> : null}
            <Captions words={seg.words} job={job} />
          </Sequence>
        );
      })}
      {job.music ? <Audio src={staticFile(job.music)} volume={job.musicVolume} loop /> : null}
      <Brand job={job} />
    </AbsoluteFill>
  );
};
