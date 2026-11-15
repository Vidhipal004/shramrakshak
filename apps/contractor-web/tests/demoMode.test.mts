import assert from 'node:assert/strict'
import test from 'node:test'
import { assertLiveApiAllowed, canUseDemo } from '../src/demoMode.ts'
import { createDemoWorkspace, demoAttendance, demoPayments } from '../src/demoData.ts'

test('demo guest entry is available in development and production builds', () => {
  assert.equal(canUseDemo(true), true)
  assert.equal(canUseDemo(false), true)
})

test('fixture is a contractor identity with isolated sample records', () => {
  const data = createDemoWorkspace()
  assert.equal(data.profile.role, 'contractor')
  assert.match(data.profile.id, /^demo-/)
  assert.equal(data.profile.verification_status, 'unverified')
  assert.ok(data.jobs.every(job => job.id.startsWith('demo-')))
  assert.ok(Object.values(data.applications).flat().every(app => app.id.startsWith('demo-')))
  assert.ok(data.agreements.every(agreement => agreement.id.startsWith('demo-')))
  assert.ok(data.complaints.every(complaint => complaint.id.startsWith('demo-')))
  assert.ok(data.travelChecks.every(check => check.id.startsWith('demo-')))
  assert.ok(demoAttendance.every(record => record.id.startsWith('demo-')))
  assert.ok(demoPayments.every(record => record.id.startsWith('demo-')))
})

test('demo workspace requests are blocked; real workspace requests remain allowed', () => {
  assert.throws(() => assertLiveApiAllowed(true), /local sample data only/)
  assert.doesNotThrow(() => assertLiveApiAllowed(false))
})
