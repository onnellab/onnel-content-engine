import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, writeFile, readdir, rm, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {renderRequest, validateProps, CACHE_BYTES} from '../render.mjs';

const brief = {template: 'quick_demo', locale: 'ko', duration_seconds: 15,
  hook: '큰 파일 읽기가 어려운가요?', cta: '내 파일로 따라 해 보세요.',
  captions: [{start: 0, end: 15, text: '필요한 부분을 찾아 읽기'}], test_only: true};

test('reject invalid template, timing, duration and text without execution', () => {
  validateProps(brief);
  for (const change of [{template: 'javascript'}, {duration_seconds: 31}, {test_only: 'false'},
    {captions: [{start: 0, end: 16, text: 'too late'}]}, {hook: 'x'.repeat(100)}]) {
    assert.throws(() => validateProps({...brief, ...change}));
  }
});

for (const fail of [false, true]) test(`renderer selects only assets and always closes own resources; fail=${fail}`, async () => {
  const root = await mkdtemp(join(tmpdir(), 'video-unit-'));
  try {
    const asset = join(root, 'recording.mp4');
    const browserPath = join(root, 'headless');
    await writeFile(asset, 'fixture'); await writeFile(browserPath, 'fixture');
    await writeFile(join(root, 'do-not-stage.txt'), 'private');
    let selected, closed = 0, media = 0, preview = 0;
    const api = {
      makeCancelSignal: () => ({cancelSignal: () => {}, cancel: () => {}}),
      bundle: async options => {
        assert.deepEqual(await readdir(options.publicDir), ['recording.mp4']);
        assert.equal(options.enableCaching, false);
        assert.equal(options.gitSource, null);
        return options.outDir;
      },
      openBrowser: async () => ({close: async () => {closed++;}}),
      selectComposition: async options => {selected = options; return {durationInFrames: 450};},
      renderMedia: async options => {
        media++;
        assert.equal(options.inputProps, selected.inputProps);
        assert.equal(options.concurrency, 1);
        assert.equal(options.disallowParallelEncoding, true);
        assert.equal(options.offthreadVideoCacheSizeInBytes, CACHE_BYTES);
        assert.deepEqual(options.envVariables, {});
        assert.equal(options.inputProps.secret, undefined);
        if (fail) throw new Error('render failed');
      },
      renderStill: async options => {preview++; assert.equal(options.inputProps, selected.inputProps);},
    };
    const request = {brief: {...brief, secret: 'not-in-browser'}, assets: {recording: asset}, output: root, browser: browserPath};
    if (fail) await assert.rejects(renderRequest(request, api));
    else assert.equal((await renderRequest(request, api)).video, 'video.mp4');
    assert.equal(closed, 1); assert.equal(media, 1); assert.equal(preview, fail ? 0 : 1);
    assert.ok(!(await readdir(root)).some(name => name.startsWith('.remotion-')));
  } finally {await rm(root, {recursive: true, force: true});}
});

test('all installed Remotion packages have identical pinned version', async () => {
  const lock = JSON.parse(await readFile(new URL('../package-lock.json', import.meta.url), 'utf8'));
  const packages = Object.entries(lock.packages).filter(([key]) => /node_modules\/(?:@remotion\/[^/]+|remotion)$/.test(key));
  assert.ok(packages.length >= 3);
  for (const [key, pkg] of packages) assert.equal(pkg.version, '4.0.526', key);
});
