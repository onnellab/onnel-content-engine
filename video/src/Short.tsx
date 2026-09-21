import React from 'react';
import {AbsoluteFill, Audio, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {VideoProps} from './model.js';

const ink = '#242335';
const fontFamily = '"Noto Sans KR", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
const label = {fontSize: 28, letterSpacing: 2, fontWeight: 650} as const;

export const Short: React.FC<VideoProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const second = frame / fps;
  const caption = props.captions.find((c) => second >= c.start && second < c.end);
  const closing = frame >= durationInFrames - 3 * fps;
  const problem = props.template === 'problem_solution';
  const problemPhase = second < 4;
  const phase = problem
    ? (props.locale === 'ko' ? (problemPhase ? '문제' : '해결 단계') : (problemPhase ? 'THE PROBLEM' : 'TRY THESE STEPS'))
    : (props.locale === 'ko' ? '따라 해 보기' : 'QUICK WALKTHROUGH');
  const fade = interpolate(frame, [0, 10, durationInFrames - 10, durationInFrames - 1], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const captionFade = caption ? interpolate(frame - caption.start * fps, [0, 7], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0;
  return <AbsoluteFill style={{backgroundColor: problem ? '#FFFCF5' : '#FFFFFF', color: ink, fontFamily}}>
    <div style={{position: 'absolute', top: -130, right: -140, width: 580, height: 580, borderRadius: '50%', background: '#EEE7FF'}} />
    <div style={{position: 'absolute', bottom: -180, left: -130, width: 650, height: 650, borderRadius: '50%', background: '#E2F0FC'}} />
    <AbsoluteFill style={{padding: '78px 72px 110px', opacity: fade}}>
      <div style={{...label, alignSelf: 'flex-start', padding: '14px 24px', borderRadius: 22, background: problem && problemPhase ? '#FFE8DC' : '#EEE7FF'}}>{phase}</div>
      <div style={{fontSize: 58, lineHeight: 1.22, fontWeight: 760, whiteSpace: 'pre', marginTop: 28, height: 156, display: 'flex', alignItems: 'center'}}>{props.hook}</div>
      <div style={{height: 1080, width: '100%', marginTop: 25, border: '3px solid #E4E2EA', borderRadius: 30, overflow: 'hidden', background: '#F6F5F8', display: 'flex', justifyContent: 'center'}}>
        <OffthreadVideo src={staticFile(props.recording)} muted style={{width: '100%', height: '100%', objectFit: 'contain'}} />
      </div>
      <div style={{marginTop: 26, minHeight: 170, borderRadius: 26, padding: '20px 22px', background: problem ? '#FFE8DC' : '#EEE7FF', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <div style={{fontSize: 46, lineHeight: 1.32, fontWeight: 700, textAlign: 'center', whiteSpace: 'pre', opacity: captionFade}}>{caption?.text ?? ''}</div>
      </div>
      <div style={{fontSize: 36, lineHeight: 1.3, fontWeight: 600, whiteSpace: 'pre', textAlign: 'center', marginTop: 30, opacity: closing ? 1 : 0}}>{props.cta}</div>
      {props.test_only && <div style={{position: 'absolute', top: 26, right: 36, ...label, color: '#8A263D'}}>TEST ONLY · NOT FOR UPLOAD</div>}
    </AbsoluteFill>
    {props.narration && <Audio src={staticFile(props.narration)} />}
  </AbsoluteFill>;
};
