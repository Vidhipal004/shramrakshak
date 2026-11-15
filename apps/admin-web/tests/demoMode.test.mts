import assert from 'node:assert/strict'
import test from 'node:test'
import { assertLiveApiAllowed, canUseDemo } from '../src/demoMode.ts'
import { createDemoSnapshot, demoAttendance } from '../src/demoData.ts'

test('demo admin entry is allowed only for development builds', () => {
  assert.equal(canUseDemo(true), true)
  assert.equal(canUseDemo(false), false)
})

test('demo dataset is isolated and cannot authenticate as a production admin', () => {
  const sample = createDemoSnapshot()
  assert.equal(sample.profile.role, 'demo_admin')
  assert.match(sample.profile.id, /^demo-/)
  assert.equal('access_token' in sample.profile, false)
  assert.ok(sample.workers.every(row => row.id.startsWith('demo-')))
  assert.ok(sample.contractors.every(row => row.id.startsWith('demo-')))
  assert.ok(sample.jobs.every(row => row.id.startsWith('demo-')))
  assert.ok(sample.payments.every(row => row.id.startsWith('demo-')))
  assert.ok(sample.agreements.every(row => row.id.startsWith('demo-')))
  assert.ok(sample.cases.every(row => row.id.startsWith('demo-')))
  assert.ok(demoAttendance.every(row => row.id.startsWith('demo-')))
})

test('privileged workspace API calls are blocked in demo mode only', () => {
  assert.throws(() => assertLiveApiAllowed(true), /privileged API requests are disabled/)
  assert.doesNotThrow(() => assertLiveApiAllowed(false))
})
