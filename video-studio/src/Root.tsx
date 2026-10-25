import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {Video} from './Video';
import {JobProps, sampleJob} from './types';

const calculateMetadata: CalculateMetadataFunction<JobProps> = ({props}) => ({
  fps: props.fps,
  durationInFrames: Math.max(1, props.segments.reduce((sum, s) => sum + s.durationInFrames, 0)),
});

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Landscape"
      component={Video}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={300}
      defaultProps={{...sampleJob, layout: 'landscape' as const}}
      calculateMetadata={calculateMetadata}
    />
    <Composition
      id="Portrait"
      component={Video}
      width={1080}
      height={1920}
      fps={30}
      durationInFrames={300}
      defaultProps={{...sampleJob, layout: 'portrait' as const}}
      calculateMetadata={calculateMetadata}
    />
  </>
);
