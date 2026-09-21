import {bundle} from '@remotion/bundler';
import {openBrowser, selectComposition, renderMedia, renderStill, makeCancelSignal} from '@remotion/renderer';
import {copyFile, mkdir, mkdtemp, readFile, realpath, rm, stat} from 'node:fs/promises';
import {dirname, extname, isAbsolute, join} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
export const CACHE_BYTES = 64 * 1024 * 1024;
const runtime = {bundle, openBrowser, selectComposition, renderMedia, renderStill, makeCancelSignal};

/** @param {unknown} value @returns {asserts value is import('./src/model.js').VideoProps} */
export function validateProps(value) {
  const p = /** @type {import('./src/model.js').VideoProps} */ (value);
  if (!p || !['quick_demo', 'problem_solution'].includes(p.template) || p.locale !== 'en'
      || !Number.isInteger(p.duration_seconds) || p.duration_seconds < 15 || p.duration_seconds > 30
      || typeof p.test_only !== 'boolean' || !Array.isArray(p.captions) || p.captions.length < 1 || p.captions.length > 12
      || typeof p.app_name !== 'string' || !p.app_name.trim() || p.app_name.length > 24
      || !Array.isArray(p.platforms) || p.platforms.length < 1 || p.platforms.length > 2
      || p.platforms.some((platform) => !['ios', 'android'].includes(platform))
      || new Set(p.platforms).size !== p.platforms.length) {
    throw new Error('Invalid rendering props');
  }
  const text = (/** @type {unknown} */ v) => typeof v === 'string' && v.trim().length > 0 && [...v].length <= 80
    && v.split('\n').length <= 2 && v.split('\n').every(line => line.trim() && [...line].reduce((n, c) => n + ((c.codePointAt(0) ?? 0) > 127 ? 2 : 1), 0) <= 80);
  if (!text(p.hook) || !text(p.cta)) throw new Error('Invalid caption text');
  let end = 0;
  for (const c of p.captions) {
    if (!Number.isFinite(c.start) || !Number.isFinite(c.end) || c.start < end || c.end - c.start < 1 || c.end > p.duration_seconds || !text(c.text)) throw new Error('Invalid caption timing/text');
    end = c.end;
  }
}

/**
 * Internal CLI protocol. Public callers use Python validation/locking/ffprobe.
 * @param {{brief: Omit<import('./src/model.js').VideoProps, 'app_name' | 'platforms' | 'recording' | 'narration'>, product: import('./src/model.js').ProductSnapshot, assets: {recording: string, narration?: string}, output: string, browser: string}} request
 * @param {typeof runtime} api
 */
export async function renderRequest(request, api = runtime) {
  if (!isAbsolute(request.output) || !isAbsolute(request.browser) || !(await stat(request.browser)).isFile()) throw new Error('Local output and installed browser required');
  const output = await realpath(request.output);
  const temp = await mkdtemp(join(output, '.remotion-'));
  let browser;
  const {cancelSignal, cancel} = api.makeCancelSignal();
  const timer = setTimeout(cancel, 900_000);
  const onSignal = () => cancel();
  process.once('SIGTERM', onSignal);
  process.once('SIGINT', onSignal);
  try {
    const publicDir = join(temp, 'public');
    await mkdir(publicDir);
    /** @type {{recording: string, narration?: string}} */
    const selected = {recording: ''};
    for (const kind of /** @type {const} */ (['recording', 'narration'])) {
      const source = request.assets[kind];
      if (kind === 'narration' && source === undefined) continue;
      if (!source || !isAbsolute(source)) throw new Error('Local asset path required');
      const file = await realpath(source);
      const metadata = await stat(file);
      const suffix = extname(file).toLowerCase();
      if (!metadata.isFile() || metadata.size <= 0 || metadata.size > 256 * 1024 * 1024 || !(kind === 'recording' ? ['.mp4', '.mov', '.webm'] : ['.wav', '.mp3', '.m4a']).includes(suffix)) throw new Error('Unsupported asset');
      selected[kind] = kind + suffix;
      await copyFile(file, join(publicDir, selected[kind]));
    }
    // Whitelist caller copy and trusted immutable product metadata. Never expose host paths/secrets.
    const b = request.brief;
    const product = request.product;
    const inputProps = {template: b.template, locale: b.locale, duration_seconds: b.duration_seconds,
      hook: b.hook, cta: b.cta, captions: b.captions.map(c => ({start: c.start, end: c.end, text: c.text})),
      test_only: b.test_only, app_name: product?.app_name, platforms: product?.platforms, ...selected};
    validateProps(inputProps);
    const serveUrl = await api.bundle({entryPoint: join(here, 'src/index.tsx'), outDir: join(temp, 'bundle'),
      publicDir, enableCaching: false, gitSource: null, askAIEnabled: false, webpackOverride: config => ({...config, devtool: false, resolve: {...config.resolve, extensionAlias: {'.js': ['.ts', '.tsx', '.js']}}})});
    browser = await api.openBrowser('chrome', {browserExecutable: request.browser,
      chromiumOptions: {headless: true}, logLevel: 'error'});
    const common = {serveUrl, inputProps, puppeteerInstance: browser, envVariables: {},
      timeoutInMilliseconds: 30_000, offthreadVideoCacheSizeInBytes: CACHE_BYTES, mediaCacheSizeInBytes: CACHE_BYTES, offthreadVideoThreads: 1, logLevel: /** @type {const} */ ('error')};
    const composition = await api.selectComposition({...common, id: b.template.replace('_', '-')});
    await api.renderMedia({...common, composition, codec: 'h264', pixelFormat: 'yuv420p',
      outputLocation: join(output, 'video.mp4'), concurrency: 1, disallowParallelEncoding: true,
      offthreadVideoCacheSizeInBytes: CACHE_BYTES, mediaCacheSizeInBytes: CACHE_BYTES,
      offthreadVideoThreads: 1, cancelSignal, overwrite: false, videoBitrate: '4M', audioBitrate: '128k'});
    await api.renderStill({...common, composition, output: join(output, 'preview.png'),
      frame: Math.min(60, composition.durationInFrames - 1), imageFormat: 'png',
      offthreadVideoCacheSizeInBytes: CACHE_BYTES, mediaCacheSizeInBytes: CACHE_BYTES, cancelSignal});
    return {schema_version: 1, video: 'video.mp4', preview: 'preview.png'};
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
    if (!path || (await stat(path)).size > 65536) throw new Error('Bounded request file required');
    const request = JSON.parse(await readFile(path, 'utf8'));
    console.log(JSON.stringify(await renderRequest(request)));
  } catch {
    console.error(JSON.stringify({error: 'Local Remotion render failed'}));
    process.exitCode = 1;
  }
}
