import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, writeFile, readdir, rm, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {renderRequest, validateProps, CACHE_BYTES} from '../render.mjs';

const brief = {
  template: 'quick_demo',
  locale: 'en',
  duration_seconds: 15,
  hook: 'Need to clean up a batch of files without guessing what will change?',
  cta: 'Try it on your own files.',
  captions: [{start: 0, end: 15, text: 'Preview the changes, then apply only the names you want.'}],
  test_only: true,
  app_name: 'Fixture App',
  platforms: ['ios', 'android'],
};
const {app_name: _ignoredApp, platforms: _ignoredPlatforms, ...callerBrief} = brief;

test('English-only props reject other locales and unsafe bounds before execution', () => {
  validateProps(brief);
  for (const change of [
    {locale: 'ko'},
    {locale: 'ja'},
    {locale: 'zh-Hans'},
    {template: 'javascript'},
    {duration_seconds: 31},
    {test_only: 'false'},
    {captions: [{start: 0, end: 16, text: 'too late'}]},
    {hook: 'x'.repeat(81)},    {platforms: ['web']},
    {app_name: ''},
  ]) {
    assert.throws(() => validateProps({...brief, ...change}));
  }
});

for (const fail of [false, true]) {
  test(`renderer stages only selected assets and closes resources; fail=${fail}`, async () => {
    const root = await mkdtemp(join(tmpdir(), 'video-unit-'));
    try {
      const asset = join(root, 'recording.mp4');
      const browserPath = join(root, 'headless');
      await writeFile(asset, 'fixture');
      await writeFile(browserPath, 'fixture');
      await writeFile(join(root, 'do-not-stage.txt'), 'private');
      let selected;
      let closed = 0;
      let media = 0;
      let preview = 0;
      const api = {
        makeCancelSignal: () => ({cancelSignal: () => {}, cancel: () => {}}),
        bundle: async (options) => {
          assert.deepEqual(await readdir(options.publicDir), ['recording.mp4']);
          assert.equal(options.enableCaching, false);
          assert.equal(options.gitSource, null);
          return options.outDir;
        },
        openBrowser: async () => ({close: async () => {closed++;}}),        selectComposition: async (options) => {
          selected = options;
          return {durationInFrames: 450};
        },
        renderMedia: async (options) => {
          media++;
          assert.equal(options.inputProps, selected.inputProps);
          assert.equal(options.inputProps.app_name, 'Fixture App');
          assert.deepEqual(options.inputProps.platforms, ['ios', 'android']);
          assert.equal(options.concurrency, 1);
          assert.equal(options.disallowParallelEncoding, true);
          assert.equal(options.offthreadVideoCacheSizeInBytes, CACHE_BYTES);
          assert.deepEqual(options.envVariables, {});
          if (fail) throw new Error('render failed');
        },
        renderStill: async (options) => {
          preview++;
          assert.equal(options.inputProps, selected.inputProps);
        },
      };
      const request = {
        brief: {...callerBrief, app_name: 'Caller Cannot Override', platforms: ['web']},
        product: {app_name: 'Fixture App', platforms: ['ios', 'android']},
        assets: {recording: asset},
        output: root,
        browser: browserPath,
      };
      if (fail) await assert.rejects(renderRequest(request, api));
      else assert.equal((await renderRequest(request, api)).video, 'video.mp4');
      assert.equal(closed, 1);      assert.equal(media, 1);
      assert.equal(preview, fail ? 0 : 1);
      assert.ok(!(await readdir(root)).some((name) => name.startsWith('.remotion-')));
    } finally {
      await rm(root, {recursive: true, force: true});
    }
  });
}

test('all installed Remotion packages have identical pinned version', async () => {
  const lock = JSON.parse(await readFile(new URL('../package-lock.json', import.meta.url), 'utf8'));
  const packages = Object.entries(lock.packages).filter(([key]) =>
    /node_modules\/(?:@remotion\/[^/]+|remotion)$/.test(key),
  );
  assert.ok(packages.length >= 3);
  for (const [key, pkg] of packages) assert.equal(pkg.version, '4.0.526', key);
});

test('natural English copy fits at most two lines without truncation', async () => {
  const {layoutText} = await import('../src/text-layout.mjs');
  const measure = (text, size) => [...text].length * size * 0.56;
  const samples = [
    'Preview every filename before you apply a batch rename to the files.',
    'Clean up title and artist tags before adding songs to your library.',
    'Keep the original file. Save a converted copy only when you need one.',
  ];
  for (const text of samples) {    const layout = layoutText(text, 880, 58, measure);
    assert.ok(layout.size >= 40);
    assert.ok(layout.text.split('\n').length <= 2);
    assert.ok(layout.text.split('\n').every((line) => measure(line, layout.size) <= 880));
    assert.equal(layout.text.replace(/\s/g, ''), text.replace(/\s/g, ''));
  }
  assert.throws(() => layoutText('W'.repeat(160), 880, 58, measure));
});
