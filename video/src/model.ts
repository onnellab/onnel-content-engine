export type Caption = {start: number; end: number; text: string};
export type VideoProps = {
  template: 'quick_demo' | 'problem_solution';
  locale: 'en' | 'ko';
  duration_seconds: number;
  hook: string;
  cta: string;
  captions: Caption[];
  recording: string;
  narration?: string;
  test_only: boolean;
};

export const defaults: VideoProps = {
  template: 'quick_demo', locale: 'en', duration_seconds: 15,
  hook: 'Your problem comes first', cta: 'Try the steps on your own file.',
  captions: [{start: 0, end: 15, text: 'Supply a real screen recording.'}],
  recording: 'MISSING-RECORDING.mp4', test_only: true,
};
