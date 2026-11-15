import assert from 'node:assert/strict';
import test from 'node:test';
import { assertNotDemoRequest, canUseDemo } from '../demoMode.ts';
import { createDemoSnapshot, DEMO_ATTENDANCE, DEMO_PAYMENTS, DEMO_USER } from '../demoData.ts';

test('demo access is available only in development builds', () => {
  assert.equal(canUseDemo(true), true);
  assert.equal(canUseDemo(false), false);
});

test('demo identity is explicitly worker-only and sample data is separate', () => {
  const snapshot = createDemoSnapshot();
  assert.equal(DEMO_USER.role, 'worker');
  assert.match(DEMO_USER.id, /^demo-/);
  assert.ok(snapshot.jobs.every((job) => job.id.startsWith('demo-')));
  assert.ok(snapshot.agreements.every((agreement) => agreement.id.startsWith('demo-')));
  assert.ok(DEMO_ATTENDANCE.every((item) => item.id.startsWith('demo-')));
  assert.ok(DEMO_PAYMENTS.every((item) => item.id.startsWith('demo-')));
});

test('demo mode cannot issue backend API requests', () => {
  assert.throws(() => assertNotDemoRequest(true), /cannot access backend APIs/);
  assert.doesNotThrow(() => assertNotDemoRequest(false));
});
