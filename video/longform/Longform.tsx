import React from 'react';
import {AbsoluteFill, Audio, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {CaptionText, fontFamily} from '../src/CaptionText.js';
import {reveal} from '../src/motion.mjs';

export type LongformScene = {
  kind: 'opening' | 'explanation' | 'demonstration' | 'closing';
  duration_seconds: number;
  heading: string;
  body?: string;
  points?: string[];
  recording?: string;
};

export type LongformProps = {
  locale: 'en';
  test_only: boolean;
  scenes: LongformScene[];
  narration?: string;
};

export const longformDefaults: LongformProps = {
  locale: 'en',
  test_only: true,
  scenes: [
    {kind: 'opening', duration_seconds: 4, heading: 'A practical guide', body: 'Start with the problem, not the product.'},
    {kind: 'explanation', duration_seconds: 4, heading: 'Three clear steps', points: ['Understand the task', 'See a real example', 'Verify the result']},
    {kind: 'closing', duration_seconds: 4, heading: 'Keep the useful part', body: 'Apply the workflow only when it helps.'},
  ],
};

const ink = '#292735';
const muted = '#706C7D';
const accent = {opening: '#EEE7FF', explanation: '#E3F0FD', demonstration: '#FBE8DF', closing: '#EEE7FF'};

const Scene: React.FC<{scene: LongformScene; chapter: number; total: number; segmentFrames: number}> = ({scene, chapter, total, segmentFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const isDemo = scene.kind === 'demonstration';
  const sceneOpacity = Math.min(1, Math.max(0, frame / 9), Math.max(0, (segmentFrames - 1 - frame) / 9));

  return <AbsoluteFill style={{backgroundColor: '#FFFEFC', fontFamily, color: ink, opacity: sceneOpacity}}>
    <div style={{position: 'absolute', inset: '0 0 auto auto', width: 390, height: 175, background: accent[scene.kind], borderBottomLeftRadius: 90}} />
    <div style={{position: 'absolute', top: 122, left: 114, width: 86, height: 5, background: accent[scene.kind], borderRadius: 3}} />
    <div style={{position: 'absolute', top: 76, left: 114, fontSize: 24, fontWeight: 680, letterSpacing: 2.5, color: muted}}>
      {scene.kind === 'opening' ? 'THE QUESTION' : scene.kind === 'explanation' ? 'THE EXPLANATION' : scene.kind === 'demonstration' ? 'REAL WORKFLOW' : 'THE TAKEAWAY'}
    </div>
    <div style={{position: 'absolute', top: 77, right: 112, fontSize: 23, color: muted, fontWeight: 650}}>
      {String(chapter).padStart(2, '0')} / {String(total).padStart(2, '0')}
    </div>
    <div style={{position: 'absolute', left: 114, right: isDemo ? 1180 : 130, top: isDemo ? 178 : 250}}>
      <div style={{...reveal(frame, 4, 20, 22), fontSize: isDemo ? 54 : 76, lineHeight: 1.18, fontWeight: 740}}>
        <CaptionText text={scene.heading} width={isDemo ? 570 : 1620} size={isDemo ? 54 : 76} weight={740} />
      </div>
      {scene.body && <div style={{...reveal(frame, 14, 18, 18), marginTop: 36, fontSize: isDemo ? 34 : 42, lineHeight: 1.5, color: '#494653'}}>
        <CaptionText text={scene.body} width={isDemo ? 570 : 1570} size={isDemo ? 34 : 42} weight={450} />
      </div>}
      {scene.points && <div style={{marginTop: 68, display: 'flex', flexDirection: 'column', gap: 30}}>
        {scene.points.map((point, index) => <div key={index} style={{...reveal(frame, 22 + index * 11, 16, 16), display: 'flex', alignItems: 'center', gap: 24, fontSize: 37}}>
          <div style={{width: 55, height: 55, background: accent[scene.kind], borderRadius: 16, textAlign: 'center', paddingTop: 7, flexShrink: 0, fontWeight: 680}}>{index + 1}</div>
          <CaptionText text={point} width={1470} size={37} weight={540} />
        </div>)}
      </div>}
    </div>
    {isDemo && scene.recording && <div style={{position: 'absolute', left: 788, right: 112, top: 174, bottom: 138, borderRadius: 24, overflow: 'hidden', border: '3px solid #DFDCE7', backgroundColor: '#F7F7F8'}}>
      <OffthreadVideo src={staticFile(scene.recording)} muted style={{width: '100%', height: '100%', objectFit: 'contain'}} />
    </div>}
    <div style={{position: 'absolute', bottom: 75, left: 114, fontSize: 21, fontWeight: 650, letterSpacing: 2.4, color: muted}}>ONNELLAB · PRACTICAL GUIDES</div>
    <div style={{position: 'absolute', bottom: 80, right: 114, fontSize: 22, color: muted}}>{Math.max(0, Math.ceil((segmentFrames - frame) / fps))}s</div>
  </AbsoluteFill>;
};

export const Longform: React.FC<LongformProps> = ({scenes, narration, test_only}) => {
  const {fps} = useVideoConfig();
  let offset = 0;
  return <AbsoluteFill style={{backgroundColor: '#FFFEFC'}}>
    {scenes.map((scene, index) => {
      const start = offset;
      const frames = Math.round(scene.duration_seconds * fps);
      offset += frames;
      return <Sequence key={index} from={start} durationInFrames={frames}>
        <Scene scene={scene} chapter={index + 1} total={scenes.length} segmentFrames={frames} />
      </Sequence>;
    })}
    {narration && <Audio src={staticFile(narration)} />}
    {test_only && <div style={{position: 'absolute', right: 40, top: 20, padding: '8px 12px', fontSize: 22, fontWeight: 800, background: '#FBE8DF', color: '#77253B'}}>TEST ONLY · NOT FOR UPLOAD</div>}
  </AbsoluteFill>;
};
