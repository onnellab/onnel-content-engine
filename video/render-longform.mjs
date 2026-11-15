import {bundle} from '@remotion/bundler';
import {openBrowser, selectComposition, renderMedia, renderStill, makeCancelSignal} from '@remotion/renderer';
import {copyFile, lstat, mkdir, mkdtemp, readFile, realpath, rename, rm, stat, writeFile} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {basename, dirname, extname, isAbsolute, join, relative, sep} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const exec = promisify(execFile);
const MAX_MEDIA = 256 * 1024 * 1024;
const CACHE_BYTES = 64 * 1024 * 1024;
const runtime = {bundle, openBrowser, selectComposition, renderMedia, renderStill, makeCancelSignal};
/** @param {Record<string, unknown>} object @param {string[]} names */
const onlyKeys = (object, names) => Object.keys(object).every((key) => names.includes(key));
/** @param {unknown} value @param {number} max */
const isText = (value, max) => typeof value === 'string' && value.trim().length > 0 && [...value].length <= max && !/[\u0000-\u001f]/u.test(value);

/** @param {any} brief */
export function validateBrief(brief) {
  if (!brief || typeof brief !== 'object' || Array.isArray(brief)
      || !onlyKeys(brief, ['schema_version', 'locale', 'test_only', 'scenes', 'narration'])
      || brief.schema_version !== 1 || brief.locale !== 'en' || typeof brief.test_only !== 'boolean'
      || !Array.isArray(brief.scenes) || brief.scenes.length < 1 || brief.scenes.length > 16) {
    throw new Error('Invalid longform brief');
  }
  const total = brief.scenes.reduce((/** @type {number} */ seconds, /** @type {any} */ scene) => {
    if (!scene || typeof scene !== 'object' || Array.isArray(scene)
        || !onlyKeys(scene, ['kind', 'duration_seconds', 'heading', 'body', 'points', 'recording'])
        || !['opening', 'explanation', 'demonstration', 'closing'].includes(scene.kind)
        || !Number.isInteger(scene.duration_seconds) || scene.duration_seconds < 3 || scene.duration_seconds > 90
        || !isText(scene.heading, 70)
        || (scene.body !== undefined && !isText(scene.body, 135))
        || (scene.points !== undefined && (!Array.isArray(scene.points) || scene.points.length < 1
          || scene.points.length > 3 || !scene.points.every((/** @type {unknown} */ point) => isText(point, 95))))
        || (scene.body !== undefined && scene.points !== undefined)
        || (scene.kind === 'demonstration' && (scene.recording === undefined || scene.points !== undefined))
        || (scene.kind !== 'demonstration' && scene.recording !== undefined)) {
      throw new Error('Invalid longform scene');
    }
    return seconds + scene.duration_seconds;
  }, 0);
  if (total > 600 || (!brief.test_only && total < 60)) throw new Error('Longform duration outside bounds');
  if (brief.narration !== undefined && !isText(brief.narration, 240)) throw new Error('Invalid narration');
  return total;
}

/** @param {unknown} value */
export function relativeAssetName(value) {
  if (typeof value !== 'string' || value.length < 1 || value.length > 240 || isAbsolute(value)
      || value.includes('\\') || value.includes(':') || value.includes('\0')
      || value.split('/').some((part) => !part || part === '.' || part === '..')) {
    throw new Error('Only local relative assets are supported');
  }
  return value;
}

/** @param {string} path */
async function hashFile(path) {
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest('hex');
}

/** @param {string} root @param {string} name @param {string[]} extensions */
export async function checkedAsset(root, name, extensions) {
  const src = await realpath(join(root, relativeAssetName(name)));
  const rel = relative(root, src);
  if (rel.startsWith('..' + sep) || rel === '..' || isAbsolute(rel) || !rel) throw new Error('Asset escaped private root');
  if (!extensions.includes(extname(src).toLowerCase())) throw new Error('Unsupported media type');
  const info = await stat(src);
  if (!info.isFile() || info.size < 1 || info.size > MAX_MEDIA) throw new Error('Media size outside bounds');
  return src;
}

/** @param {string} path */
async function ffprobe(path) {
  const {stdout} = await exec('ffprobe', [
    '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_entries',
    'format=duration:stream=codec_type,codec_name,width,height,pix_fmt,avg_frame_rate',
    '-of', 'json', path,
  ], {timeout: 30000, maxBuffer: 262144, encoding: 'utf8'});
  return JSON.parse(stdout);
}

/** @param {string} input @param {string} output */
async function ffmpegFinish(input, output) {
  await exec('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
    '-i', input, '-map', '0:v:0', '-map', '0:a?', '-c', 'copy', '-movflags', '+faststart', output],
  {timeout: 120000, maxBuffer: 262144});
}

/**
 * Longform is separate from the Shorts publication queue. It stages only
 * whitelisted local assets and emits a review-required private render.
 * @param {{brief: unknown, asset_root: string, browser: string, output: string}} request
 * @param {typeof runtime} api
 * @param {{probe: typeof ffprobe, finish: typeof ffmpegFinish}} system
 */
export async function renderLongform(request, api = runtime, system = {probe: ffprobe, finish: ffmpegFinish}) {
  const brief = /** @type {import('./longform/Longform.js').LongformProps & {schema_version: number}} */ (request.brief);
  const total = validateBrief(brief);
  if (!isAbsolute(request.asset_root) || !isAbsolute(request.browser) || !isAbsolute(request.output)
      || !(await stat(request.browser)).isFile()) throw new Error('Local browser, asset root and output required');
  const assetRoot = await realpath(request.asset_root);
  if (!(await stat(assetRoot)).isDirectory()) throw new Error('Invalid asset root');
  const parent = await realpath(dirname(request.output));
  const output = join(parent, basename(request.output));
  if (output === parent || basename(output).startsWith('.') || (await lstat(output).then(() => true, () => false))) {
    throw new Error('Output directory must be a new, visible path');
  }
  const temp = await mkdtemp(join(parent, '.longform-'));
  let browser;
  const {cancelSignal, cancel} = api.makeCancelSignal();
  const timer = setTimeout(cancel, 900000);
  const onSignal = () => cancel();
  process.once('SIGTERM', onSignal);
  process.once('SIGINT', onSignal);
  try {
    const publicDir = join(temp, 'public');
    const deliver = join(temp, 'deliver');
    await mkdir(publicDir);
    await mkdir(deliver);
    /** @type {Record<string, string>} */
    const hashes = {};
    const stagedScenes = [];
    for (const [index, scene] of brief.scenes.entries()) {
      if (scene.kind === 'demonstration' && scene.recording) {
        const source = await checkedAsset(assetRoot, scene.recording, ['.mp4', '.mov', '.webm']);
        const meta = await system.probe(source);
        const video = meta.streams?.filter((/** @type {any} */ item) => item.codec_type === 'video') ?? [];
        const seconds = Number(meta.format?.duration);
        if (video.length !== 1 || !Number.isFinite(seconds) || seconds < scene.duration_seconds - 0.05
            || !(video[0].width >= 240 && video[0].width <= 4096)
            || !(video[0].height >= 240 && video[0].height <= 4096)) {
          throw new Error('Recording does not cover demonstrated scene');
        }
        const name = 'recording-' + index + extname(source).toLowerCase();
        const digest = await hashFile(source);
        await copyFile(source, join(publicDir, name));
        if (await hashFile(join(publicDir, name)) !== digest) throw new Error('Recording changed while staging');
        hashes[name] = digest;
        stagedScenes.push({...scene, recording: name});
      } else stagedScenes.push({...scene});
    }
    let narration;
    if (brief.narration) {
      const source = await checkedAsset(assetRoot, brief.narration, ['.mp3', '.m4a', '.wav']);
      const meta = await system.probe(source);
      const audio = meta.streams?.filter((/** @type {any} */ item) => item.codec_type === 'audio') ?? [];
      const seconds = Number(meta.format?.duration);
      if (audio.length < 1 || !Number.isFinite(seconds) || seconds <= 0 || seconds > total + 0.1) {
        throw new Error('Narration length outside video bounds');
      }
      narration = 'narration' + extname(source).toLowerCase();
      const digest = await hashFile(source);
      await copyFile(source, join(publicDir, narration));
      if (await hashFile(join(publicDir, narration)) !== digest) throw new Error('Narration changed while staging');
      hashes[narration] = digest;
    }
    const inputProps = {locale: brief.locale, scenes: stagedScenes, test_only: brief.test_only, ...(narration ? {narration} : {})};
    const serveUrl = await api.bundle({entryPoint: join(here, 'longform/index.tsx'), outDir: join(temp, 'bundle'),
      publicDir, enableCaching: false, gitSource: null, askAIEnabled: false,
      webpackOverride: (config) => ({...config, devtool: false,
        resolve: {...config.resolve, extensionAlias: {'.js': ['.ts', '.tsx', '.js']}}})});
    browser = await api.openBrowser('chrome', {browserExecutable: request.browser,
      chromiumOptions: {headless: true}, logLevel: 'error'});
    const common = {serveUrl, inputProps, puppeteerInstance: browser, envVariables: {},
      timeoutInMilliseconds: 30000, offthreadVideoCacheSizeInBytes: CACHE_BYTES,
      mediaCacheSizeInBytes: CACHE_BYTES, offthreadVideoThreads: 1, logLevel: /** @type {const} */ ('error')};
    const composition = await api.selectComposition({...common, id: 'educational-longform'});
    if (composition.width !== 1920 || composition.height !== 1080 || composition.fps !== 30
        || composition.durationInFrames !== total * 30) throw new Error('Unexpected longform composition');
    const raw = join(temp, 'render.mp4');
    await api.renderMedia({...common, composition, codec: 'h264', pixelFormat: 'yuv420p',
      colorSpace: 'bt709', imageFormat: 'png', outputLocation: raw, concurrency: 1, disallowParallelEncoding: true,
      videoBitrate: '4M', audioBitrate: '160k', cancelSignal, overwrite: false});
    await system.finish(raw, join(deliver, 'video.mp4'));
    const inspected = await system.probe(join(deliver, 'video.mp4'));
    const streams = inspected.streams ?? [];
    const v = streams.find((/** @type {any} */ item) => item.codec_type === 'video');
    const duration = Number(inspected.format?.duration);
    if (!v || v.codec_name !== 'h264' || v.width !== 1920 || v.height !== 1080
        || v.pix_fmt !== 'yuv420p' || !['30/1', '30'].includes(v.avg_frame_rate)
        || !Number.isFinite(duration) || Math.abs(duration - total) > 0.3) throw new Error('Final video format verification failed: ' + JSON.stringify({video: v, duration, expected: total}));
    await api.renderStill({...common, composition, output: join(deliver, 'preview.png'),
      frame: Math.min(Math.floor(brief.scenes[0].duration_seconds * 15), composition.durationInFrames - 1), imageFormat: 'png',
      cancelSignal});
    const digest = createHash('sha256').update(JSON.stringify({brief, asset_hashes: hashes})).digest('hex');
    const manifest = {schema_version: 1, format: 'youtube-longform', test_only: brief.test_only,
      upload_eligible: false, publication_review_required: true,
      duration_seconds: total, width: 1920, height: 1080, fps: 30, input_sha256: digest,
      sha256: {'video.mp4': await hashFile(join(deliver, 'video.mp4')),
        'preview.png': await hashFile(join(deliver, 'preview.png'))}};
    await writeFile(join(deliver, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
    await rename(deliver, output);
    return manifest;
  } finally {
    clearTimeout(timer);
    process.removeListener('SIGTERM', onSignal);
    process.removeListener('SIGINT', onSignal);
    try { if (browser) await browser.close({silent: true}); }
    finally { await rm(temp, {recursive: true, force: true}); }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const path = process.argv[2];
    if (!path || (await stat(path)).size > 65536) throw new Error('Bounded request required');
    const request = JSON.parse(await readFile(path, 'utf8'));
    console.log(JSON.stringify(await renderLongform(request)));
  } catch {
    console.error(JSON.stringify({error: 'Longform render/verification failed; output was not published'}));
    process.exitCode = 1;
  }
}
