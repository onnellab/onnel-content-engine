export type Caption = {start: number; end: number; text: string};
export type ProductSnapshot = {
  app_name: string;
  platforms: Array<'ios' | 'android'>;
};
export type VideoProps = {
  template: 'quick_demo' | 'problem_solution';
  locale: 'en';
  duration_seconds: number;
  recording_duration_seconds: number;
  hook: string;
  cta: string;
  captions: Caption[];
  recording: string;
  narration?: string;
  test_only: boolean;
  app_name: string;
  platforms: Array<'ios' | 'android'>;
};

export const defaults: VideoProps = {
  template: 'quick_demo',
  locale: 'en',
  duration_seconds: 15,
  recording_duration_seconds: 15,
  hook: 'Your problem comes first',
  cta: 'Try it on your own file.',
  captions: [{start: 0, end: 15, text: 'Use a real app screen recording.'}],
  recording: 'MISSING-RECORDING.mp4',
  test_only: true,
  app_name: 'ONNELLAB App',
  platforms: ['ios', 'android'],
};
