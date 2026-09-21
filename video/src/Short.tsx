import React from 'react';
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import type {VideoProps} from './model.js';
import {CaptionText, fontFamily} from './CaptionText.js';

const ink = '#242335';
const label = {fontSize: 27, letterSpacing: 1.8, fontWeight: 650} as const;

const platformLabel = (platforms: VideoProps['platforms']) =>
  platforms.map((platform) => (platform === 'ios' ? 'iOS' : 'Android')).join(' · ');

export const Short: React.FC<VideoProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const second = frame / fps;
  const caption = props.captions.find((item) => second >= item.start && second < item.end);
  const closingStart = durationInFrames - 3 * fps;
  const closing = frame >= closingStart;
  const problem = props.template === 'problem_solution';
  const problemPhase = second < 4;
  const step = Math.max(0, props.captions.findIndex((item) => item === caption));
  const phase = closing
    ? 'TRY IT'
    : problem
      ? (problemPhase ? 'PROBLEM' : 'SOLUTION')
      : `QUICK DEMO · ${step + 1}/${props.captions.length}`;
  const fade = interpolate(
    frame,
    [0, 10, durationInFrames - 10, durationInFrames - 1],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );
  const captionFade = caption
    ? interpolate(frame - caption.start * fps, [0, 7], [0, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      })
    : 0;
  const closingFade = interpolate(frame, [closingStart, closingStart + 8], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: problem ? '#FFFCF5' : '#FFFFFF',
        color: ink,
        fontFamily,
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: -130,
          right: -140,
          width: 580,
          height: 580,
          borderRadius: '50%',
          background: '#EEE7FF',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: -180,
          left: -130,
          width: 650,
          height: 650,
          borderRadius: '50%',
          background: '#E2F0FC',
        }}
      />
      <AbsoluteFill style={{padding: '78px 72px 90px', opacity: fade}}>
        <div
          style={{
            ...label,
            alignSelf: 'flex-start',
            padding: '14px 24px',
            borderRadius: 22,
            background: problem ? '#FFE8DC' : '#EEE7FF',
          }}
        >
          {phase}
        </div>

        <div
          style={{
            marginTop: 26,
            height: 156,
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <CaptionText text={props.hook} width={924} size={58} weight={760} />
        </div>

        <div
          style={{
            height: 1060,
            width: '100%',
            marginTop: 22,
            border: '3px solid #E4E2EA',
            borderRadius: 30,
            overflow: 'hidden',
            background: '#F6F5F8',
            display: 'flex',
            justifyContent: 'center',
          }}
        >
          <OffthreadVideo
            src={staticFile(props.recording)}
            muted
            style={{width: '100%', height: '100%', objectFit: 'contain'}}
          />
        </div>

        <div
          style={{
            marginTop: 24,
            minHeight: 162,
            borderRadius: 26,
            padding: '18px 22px',
            background: problem ? '#FFE8DC' : '#EEE7FF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              fontSize: 46,
              lineHeight: 1.32,
              fontWeight: 700,
              textAlign: 'center',
              whiteSpace: 'pre',
              opacity: captionFade,
            }}
          >
            {caption && <CaptionText text={caption.text} width={880} size={46} weight={700} />}
          </div>
        </div>

        <div
          style={{
            marginTop: 24,
            minHeight: 172,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
          }}
        >
          {closing ? (
            <div style={{opacity: closingFade, width: '100%'}}>
              <div style={{fontSize: 23, letterSpacing: 2.4, fontWeight: 650, color: '#77718A'}}>
                ONNELLAB
              </div>
              <div style={{fontSize: 50, lineHeight: 1.14, fontWeight: 780, marginTop: 6}}>
                {props.app_name}
              </div>
              <div style={{fontSize: 24, lineHeight: 1.25, fontWeight: 600, color: '#77718A', marginTop: 5}}>
                {platformLabel(props.platforms)}
              </div>
              <div style={{marginTop: 9}}>
                <CaptionText text={props.cta} width={924} size={40} weight={600} />
              </div>
            </div>
          ) : (
            <div style={{fontSize: 21, letterSpacing: 2.2, fontWeight: 650, color: '#8B87A3'}}>
              ONNELLAB
            </div>
          )}
        </div>

        {props.test_only && (
          <div
            style={{
              position: 'absolute',
              top: 26,
              right: 36,
              ...label,
              color: '#8A263D',
              fontWeight: 800,
            }}
          >
            TEST ONLY · NOT FOR UPLOAD
          </div>
        )}
      </AbsoluteFill>
      {props.narration && <Audio src={staticFile(props.narration)} />}
    </AbsoluteFill>
  );
};
