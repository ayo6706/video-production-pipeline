import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {isPortrait, safe, size} from './layout';
import {JobProps, Word} from './types';

const groupWords = (words: Word[], max: number): Word[][] => {
  const groups: Word[][] = [];
  let cur: Word[] = [];
  for (const w of words) {
    cur.push(w);
    // Break after the max, or early after punctuation once the line has a few words.
    if (cur.length >= max || (/[.,?!]$/.test(w.text) && cur.length >= Math.ceil(max / 2))) {
      groups.push(cur);
      cur = [];
    }
  }
  if (cur.length) groups.push(cur);
  return groups;
};

export const Captions: React.FC<{words: Word[]; job: JobProps}> = ({words, job}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!words.length) return null;
  const t = frame / fps;
  const portrait = isPortrait(job.layout);
  const groups = groupWords(words, portrait ? 4 : 7);
  const group = groups.find((g) => t >= g[0].start && t < g[g.length - 1].end + 0.15);
  if (!group) return null;
  const s = size(job.layout);
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: safe(job.layout).bottom - (portrait ? 40 : 90)}}>
      <div
        style={{
          maxWidth: portrait ? 920 : 1500,
          textAlign: 'center',
          fontSize: s.caption,
          fontWeight: 800,
          lineHeight: 1.2,
          padding: '10px 24px',
          borderRadius: 16,
          background: 'rgba(0,0,0,0.55)',
        }}
      >
        {group.map((w, i) => (
          <span key={i} style={{color: t >= w.start && t < w.end ? job.theme.accent : job.theme.fg}}>
            {w.text}{' '}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
};
