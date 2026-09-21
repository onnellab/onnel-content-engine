import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {Short} from './Short.js';
import {defaults} from './model.js';

const Root: React.FC = () => <>
  {(['quick_demo', 'problem_solution'] as const).map((template) => <Composition
    key={template} id={template.replace('_', '-')}
    component={Short} width={1080} height={1920} fps={30} durationInFrames={450}
    defaultProps={{...defaults, template}}
    calculateMetadata={({props}) => ({durationInFrames: props.duration_seconds * 30})}
  />)}
</>;
registerRoot(Root);
