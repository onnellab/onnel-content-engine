/**
 * Verify that this host's installed Node packages actually match the committed
 * lockfile. npm install or partial host maintenance can leave older transitive
 * packages in node_modules even when the lockfile already contains fixes.
 *
 * Missing OS-specific optional dependencies are allowed. All other lockfile
 * packages are checked before a render or test can consume their code.
 */
import {readFileSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const restore = 'Run: npm --prefix video ci (from the repository root)';

/** @param {string} path */
function json(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

/** @param {string} root */
export function assertInstalledLock(root = here) {
  const packageFile = json(join(root, 'package.json'));
  const lock = json(join(root, 'package-lock.json'));
  if (lock.lockfileVersion !== 3 || !lock.packages || lock.packages['']?.name !== packageFile.name) {
    throw new Error('Invalid video package-lock.json. ' + restore);
  }
  for (const field of ['dependencies', 'devDependencies']) {
    if (JSON.stringify(lock.packages[''][field] ?? {}) !== JSON.stringify(packageFile[field] ?? {})) {
      throw new Error('Video package.json is out of sync with package-lock.json (' + field + '). ' + restore);
    }
  }
  // npm does not serialize overrides in packages['']. Check the pinned
  // resolved root packages instead of comparing a non-existent lockfile field.
  for (const [name, version] of Object.entries(packageFile.overrides ?? {})) {
    if (typeof version === 'string' && /^[0-9]+[.][0-9]+[.][0-9]+$/.test(version)
        && lock.packages['node_modules/' + name]?.version !== version) {
      throw new Error('Video override is out of sync with the lockfile: ' + name + '. ' + restore);
    }
  }
  let checked = 0;
  let skippedOptional = 0;
  for (const [location, expected] of Object.entries(lock.packages)) {
    if (!location || !location.startsWith('node_modules/') || !expected.version) continue;
    if (location.split('/').includes('..') || location.includes('\\')) {
      throw new Error('Unsafe lockfile path');
    }
    let actual;
    try {
      actual = json(join(root, location, 'package.json'));
    } catch (error) {
      if (error instanceof Error && 'code' in error && error.code === 'ENOENT' && expected.optional) {
        skippedOptional++;
        continue;
      }
      throw new Error('Video dependency missing/corrupt: ' + location + '. ' + restore, {cause: error});
    }
    if (actual.version !== expected.version) {
      throw new Error(
        'Video dependency version mismatch: ' + location
        + ' installed=' + String(actual.version)
        + ' locked=' + String(expected.version) + '. ' + restore,
      );
    }
    checked++;
  }
  if (checked === 0) throw new Error('No installed video dependencies were verified. ' + restore);
  return {checked, skippedOptional};
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    process.stdout.write(JSON.stringify(assertInstalledLock()) + '\n');
  } catch (error) {
    console.error(error instanceof Error ? error.message : 'Video dependency validation failed');
    process.exitCode = 1;
  }
}
