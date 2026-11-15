import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {Longform, longformDefaults} from './Longform.js';

const Root: React.FC = () => <Composition
  id="educational-longform"
  component={Longform}
  width={1920}
  height={1080}
  fps={30}
  durationInFrames={360}
  defaultProps={longformDefaults}
  calculateMetadata={({props}) => ({
    durationInFrames: props.scenes.reduce((total, scene) => total + scene.duration_seconds * 30, 0),
  })}
/>;

registerRoot(Root);
