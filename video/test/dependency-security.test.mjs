import {test} from 'node:test';
import assert from 'node:assert/strict';
import uri from 'fast-uri';
import {z} from 'zod';

// Upstream GHSA regressions: retain bounded examples, never exhaustion payloads.
test('encoded URI schemes remain invalid instead of becoming executable schemes', () => {
  const input = '%6Aavascript:alert(1)';
  assert.ok(uri.parse(input).error);
  assert.notEqual(uri.normalize(input), 'javascript:alert(1)');
});
test('malformed authorities are rejected rather than silently rewritten', () => {
  assert.ok(uri.parse('http://a@b@evil.example/').error);
});
test('relative references preserve parent paths and suffix colons stay escaped', () => {
  assert.equal(uri.normalize('../x'), '../x');
  assert.equal(uri.serialize({path: 'javascript:alert(1)'}, {reference: 'suffix'}), 'javascript%3Aalert(1)');
});
test('bounded Zod arrays reject oversize before accumulating per-element issues', () => {
  const schema = z.array(z.string()).max(10);
  assert.deepEqual(schema.parse(['valid']), ['valid']);
  const result = schema.safeParse(Array(1000).fill(1));
  assert.equal(result.success, false);
  assert.equal(result.error.issues.length, 1);
  assert.equal(result.error.issues[0].code, 'too_big');
});
