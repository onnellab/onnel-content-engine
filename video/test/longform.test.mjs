import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, writeFile, readdir, readFile, rm, symlink} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {checkedAsset, relativeAssetName, renderLongform, validateBrief} from '../render-longform.mjs';

const brief = {schema_version: 1, locale: 'en', test_only: true, scenes: [
  {kind: 'opening', duration_seconds: 3, heading: 'A useful explanation'},
  {kind: 'demonstration', duration_seconds: 4, heading: 'See the real screen', body: 'Observe the control, then its result.', recording: 'demo.mp4'},
]};
const inspected = {streams: [{codec_type: 'video', codec_name: 'h264', width: 1920, height: 1080, pix_fmt: 'yuv420p', avg_frame_rate: '30/1'}], format: {duration: '7.00'}};

test('longform keeps inputs bounded and production minimum separate from test smoke', () => {
  assert.equal(validateBrief(brief), 7);
  for (const change of [
    {locale: 'ko'}, {test_only: 'true'}, {schema_version: 2},
    {scenes: Array(17).fill(brief.scenes[0])},
    {scenes: [{...brief.scenes[0], kind: 'arbitrary'}]},
    {scenes: [{...brief.scenes[1], recording: undefined}]},
    {scenes: [{...brief.scenes[0], body: '<x>'.repeat(50)}]},
    {scenes: [{...brief.scenes[0], body: 'abc', points: ['duplicate layout']}]},
    {test_only: false},
    {scenes: [{...brief.scenes[0], duration_seconds: 91}]},
    {unexpected: 'javascript'},
  ]) assert.throws(() => validateBrief({...brief, ...change}));
  assert.equal(validateBrief({...brief, test_only: false, scenes: [
    {kind: 'opening', duration_seconds: 60, heading: 'Useful lesson'},
  ]}), 60);
  for (const path of ['../secret.mp4', '/tmp/file.mp4', './file.mp4', 'a//file.mp4', 'http://x', 'a\\b.mp4']) {
    assert.throws(() => relativeAssetName(path), path);
  }
});

test('private asset paths cannot escape through a symbolic link', async () => {
  const root = await mkdtemp(join(tmpdir(), 'longform-assets-'));
  try {
    await mkdir(join(root, 'trusted'));
    await writeFile(join(root, 'secret.mp4'), 'video');
    await symlink(join(root, 'secret.mp4'), join(root, 'trusted', 'out.mp4'));
    await assert.rejects(checkedAsset(join(root, 'trusted'), 'out.mp4', ['.mp4']));
  } finally { await rm(root, {recursive: true, force: true}); }
});

for (const fail of [false, true]) {
  test(`longform stages only trusted files, verifies MP4, closes browser, and publishes atomically; fail=${fail}`, async () => {
    const root = await mkdtemp(join(tmpdir(), 'longform-render-'));
    try {
      const assets = join(root, 'assets'), output = join(root, 'final');
      await mkdir(assets);
      await writeFile(join(assets, 'demo.mp4'), 'real-production-asset-stub');
      await writeFile(join(assets, 'secret.txt'), 'must not be staged');
      const browser = join(root, 'headless-browser');
      await writeFile(browser, 'stub');
      let closed = 0, finished = 0;
      const api = {
        makeCancelSignal: () => ({cancelSignal: () => {}, cancel: () => {}}),
        bundle: async ({publicDir, enableCaching, gitSource}) => {
          assert.deepEqual(await readdir(publicDir), ['recording-1.mp4']);
          assert.equal(enableCaching, false);
          assert.equal(gitSource, null);
          return 'mock-bundle';
        },
        openBrowser: async () => ({close: async () => {closed++;}}),
        selectComposition: async ({id, inputProps}) => {
          assert.equal(id, 'educational-longform');
          assert.equal(inputProps.scenes[1].recording, 'recording-1.mp4');
          return {width: 1920, height: 1080, fps: 30, durationInFrames: 210};
        },
        renderMedia: async ({outputLocation, disallowParallelEncoding, concurrency, envVariables, colorSpace, imageFormat, pixelFormat}) => {
          // Stable BT.709 PNG input avoids the previous yuvj420p ffprobe failure.
          assert.equal(colorSpace, 'bt709');
          assert.equal(imageFormat, 'png');
          assert.equal(pixelFormat, 'yuv420p');
          assert.equal(disallowParallelEncoding, true);
          assert.equal(concurrency, 1);
          assert.deepEqual(envVariables, {});
          if (fail) throw new Error('renderer failure');
          await writeFile(outputLocation, 'h264-from-remotion');
        },
        renderStill: async ({output: imagePath, frame}) => {
          assert.equal(frame, 45); // First scene midpoint, never a blank transition boundary.
          await writeFile(imagePath, 'thumbnail');
        },
      };
      const system = {
        probe: async (path) => path.endsWith('demo.mp4')
          ? {streams: [{codec_type: 'video', width: 720, height: 1280}], format: {duration: '4.1'}}
          : inspected,
        finish: async (_raw, final) => {finished++; await writeFile(final, 'ffmpeg-faststart');},
      };
      const request = {brief, asset_root: assets, output, browser};
      if (fail) {
        await assert.rejects(renderLongform(request, api, system));
        await assert.rejects(readdir(output));
      } else {
        const result = await renderLongform(request, api, system);
        assert.equal(result.upload_eligible, false);
        assert.equal(result.publication_review_required, true);
        assert.equal(result.duration_seconds, 7);
        assert.equal(finished, 1);
        assert.deepEqual((await readdir(output)).sort(), ['manifest.json', 'preview.png', 'video.mp4']);
        assert.equal(JSON.parse(await readFile(join(output, 'manifest.json'), 'utf8')).input_sha256.length, 64);
        await assert.rejects(renderLongform(request, api, system));
      }
      assert.equal(closed, 1);
      assert.ok(!(await readdir(root)).some((name) => name.startsWith('.longform-')));
    } finally {await rm(root, {recursive: true, force: true});}
  });
}

test('longform uses a separate Remotion entry and leaves the Shorts fingerprint inputs unchanged', async () => {
  const shortEntry = await readFile(new URL('../src/index.tsx', import.meta.url), 'utf8');
  const longEntry = await readFile(new URL('../longform/index.tsx', import.meta.url), 'utf8');
  const shortTypecheck = await readFile(new URL('../tsconfig.json', import.meta.url), 'utf8');
  assert.doesNotMatch(shortEntry, /Longform|educational-longform/);
  assert.match(longEntry, /educational-longform/);
  assert.doesNotMatch(shortTypecheck, /longform/i);
});
