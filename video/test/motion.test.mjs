import {test} from 'node:test';
import assert from 'node:assert/strict';
import {reveal} from '../src/motion.mjs';

test('motion is deterministic, bounded and settles without overshoot', () => {
  assert.deepEqual(reveal(0, 10), {opacity: 0, transform: 'translateY(20px)'});
  assert.deepEqual(reveal(20, 10), {opacity: 1, transform: 'translateY(0px)'});
  assert.deepEqual(reveal(300, 10), reveal(20, 10));
  const middle = reveal(15, 10);
  assert.ok(middle.opacity > 0 && middle.opacity < 1);
  assert.ok(Number.parseFloat(middle.transform.slice(11)) > 0);
  assert.throws(() => reveal(0, 0, 0));
});
