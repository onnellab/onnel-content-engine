import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdir, mkdtemp, readFile, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {assertInstalledLock} from '../verify-install.mjs';

const here = dirname(fileURLToPath(import.meta.url));

async function setup() {
  const root = await mkdtemp(join(tmpdir(), 'video-install-integrity-'));
  const pkg = {name: '@onnellab/test', dependencies: {a: '2.0.0'}, overrides: {zod: '4.6.6'}};
  const lock = {lockfileVersion: 3, packages: {
    '': {name: pkg.name, dependencies: pkg.dependencies},
    'node_modules/a': {version: '2.0.0'},
    'node_modules/zod': {version: '4.6.6'},
    'node_modules/@other/linux': {version: '1.0.0', optional: true},
  }};
  await writeFile(join(root, 'package.json'), JSON.stringify(pkg));
  await writeFile(join(root, 'package-lock.json'), JSON.stringify(lock));
  for (const [name, version] of [['a', '2.0.0'], ['zod', '4.6.6']]) {
    await mkdir(join(root, 'node_modules', name), {recursive: true});
    await writeFile(join(root, 'node_modules', name, 'package.json'), JSON.stringify({name, version}));
  }
  return root;
}

test('current video dependencies precisely match pinned lockfile', () => {
  const result = assertInstalledLock(join(here, '..'));
  assert.ok(result.checked > 10);
  assert.ok(result.skippedOptional >= 0);
});

test('lock verification permits only missing host-optional dependencies', async () => {
  const root = await setup();
  try {
    assert.deepEqual(assertInstalledLock(root), {checked: 2, skippedOptional: 1});
  } finally {await rm(root, {recursive: true, force: true});}
});

test('lock verification rejects stale transitive packages before rendering', async () => {
  const root = await setup();
  try {
    const manifest = join(root, 'node_modules/a/package.json');
    await writeFile(manifest, JSON.stringify({name: 'a', version: '1.9.9'}));
    assert.throws(() => assertInstalledLock(root), /version mismatch.*installed=1.9.9.*locked=2.0.0/);
    await rm(join(root, 'node_modules/a'), {recursive: true});
    assert.throws(() => assertInstalledLock(root), /dependency missing\/corrupt.*node_modules\/a/i);
  } finally {await rm(root, {recursive: true, force: true});}
});

test('lock verification rejects inconsistent package and override versions', async () => {
  const root = await setup();
  try {
    const packagePath = join(root, 'package.json');
    const pkg = JSON.parse(await readFile(packagePath, 'utf8'));
    pkg.overrides.zod = '4.5.4';
    await writeFile(packagePath, JSON.stringify(pkg));
    assert.throws(() => assertInstalledLock(root), /override is out of sync/);
    pkg.overrides.zod = '4.6.6';
    pkg.dependencies.a = '1.0.0';
    await writeFile(packagePath, JSON.stringify(pkg));
    assert.throws(() => assertInstalledLock(root), /out of sync.*dependencies/);
  } finally {await rm(root, {recursive: true, force: true});}
});
