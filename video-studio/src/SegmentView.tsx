import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {fadeIn} from './layout';
import {Presenter} from './scenes/Presenter';
import {Clip, Cta, Points, Query, Quote, Screenshot, Stat, Title} from './scenes/Cards';
import {JobProps, Segment} from './types';

export const SegmentView: React.FC<{seg: Segment; job: JobProps}> = ({seg, job}) => {
  const frame = useCurrentFrame();
  const body = (() => {
    if (seg.type === 'presenter') return <Presenter seg={seg} job={job} />;
    const sc = seg.scene;
    if (!sc) return null;
    switch (sc.kind) {
      case 'title':
        return <Title scene={sc} job={job} />;
      case 'stat':
        return <Stat scene={sc} job={job} />;
      case 'points':
        return <Points scene={sc} job={job} duration={seg.durationInFrames} />;
      case 'quote':
        return <Quote scene={sc} job={job} />;
      case 'screenshot':
        return <Screenshot scene={sc} job={job} duration={seg.durationInFrames} />;
      case 'clip':
        return <Clip scene={sc} job={job} />;
      case 'query':
        return <Query scene={sc} job={job} duration={seg.durationInFrames} />;
      case 'cta':
        return <Cta scene={sc} job={job} />;
      default:
        return null;
    }
  })();
  return <AbsoluteFill style={{opacity: fadeIn(frame, 0, 8)}}>{body}</AbsoluteFill>;
};
