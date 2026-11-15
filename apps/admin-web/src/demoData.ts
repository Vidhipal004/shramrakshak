import type { Complaint, Contractor } from './api'

export type DemoWorker = { id: string; full_name: string; email: string; city: string; skill: string; status: string; joined: string }
export type DemoJob = { id: string; title: string; contractor: string; location: string; wage: number; period: string; status: string; applicants: number }
export type DemoPayment = { id: string; worker: string; contractor: string; job: string; amount: number; status: string; date: string; method: string }

export const demoAdminProfile = { id: 'demo-admin-local', email: 'demo.admin@example.test', full_name: 'ShramRakshak Admin (Demo)', role: 'demo_admin' }

export const demoWorkers: DemoWorker[] = [
  { id: 'demo-worker-1', full_name: 'Sita Devi', email: 'sita.worker@example.test', city: 'Jaipur', skill: 'Masonry', status: 'active', joined: '2026-10-02' },
  { id: 'demo-worker-2', full_name: 'Imran Khan', email: 'imran.worker@example.test', city: 'Sanganer', skill: 'Painting', status: 'active', joined: '2026-10-11' },
  { id: 'demo-worker-3', full_name: 'Meena Kumari', email: 'meena.worker@example.test', city: 'Ajmer', skill: 'Packing', status: 'pending verification', joined: '2026-11-01' },
]

export const demoContractors: Contractor[] = [
  { id: 'demo-contractor-1', full_name: 'Ramesh Sharma', email: 'ramesh.contractor@example.test', business_name: 'Sharma BuildWorks · Demo', city: 'Jaipur', state: 'Rajasthan', verification_status: 'verified', verification_updated_at: '2026-10-20T08:00:00Z' },
  { id: 'demo-contractor-2', full_name: 'Farida Khan', email: 'farida.contractor@example.test', business_name: 'Khan Home Services · Demo', city: 'Ajmer', state: 'Rajasthan', verification_status: 'unverified', verification_updated_at: null },
]

export const demoJobs: DemoJob[] = [
  { id: 'demo-job-1', title: 'Masonry helper', contractor: 'Sharma BuildWorks · Demo', location: 'Mansarovar, Jaipur', wage: 700, period: 'day', status: 'open', applicants: 4 },
  { id: 'demo-job-2', title: 'Assistant painter', contractor: 'Khan Home Services · Demo', location: 'Ajmer Road, Jaipur', wage: 650, period: 'day', status: 'filled', applicants: 3 },
  { id: 'demo-job-3', title: 'Warehouse packer', contractor: 'Sharma BuildWorks · Demo', location: 'Sanganer, Jaipur', wage: 600, period: 'day', status: 'open', applicants: 2 },
]

export const demoPayments: DemoPayment[] = [
  { id: 'demo-payment-1', worker: 'Sita Devi', contractor: 'Ramesh Sharma', job: 'Masonry helper', amount: 700, status: 'paid', date: '2026-11-13', method: 'UPI' },
  { id: 'demo-payment-2', worker: 'Imran Khan', contractor: 'Ramesh Sharma', job: 'Assistant painter', amount: 650, status: 'pending', date: '2026-11-14', method: '—' },
  { id: 'demo-payment-3', worker: 'Meena Kumari', contractor: 'Farida Khan', job: 'Warehouse packer', amount: 600, status: 'under review', date: '2026-11-12', method: 'Cash' },
]

export const demoAttendance = [
  { id: 'demo-attendance-1', worker: 'Sita Devi', job: 'Masonry helper', date: '2026-11-13', hours: 8, status: 'present' },
  { id: 'demo-attendance-2', worker: 'Imran Khan', job: 'Assistant painter', date: '2026-11-13', hours: 7.5, status: 'present' },
]

export const demoCases: Complaint[] = [
  { id: 'demo-case-1', worker_id: 'demo-worker-2', contractor_id: 'demo-contractor-1', category: 'payment', description: 'Sample dispute: daily wages were delayed after the painting shift.', status: 'submitted', created_at: '2026-11-14T09:00:00Z', responses: [{ id: 'demo-response-1', message: 'I will check the attendance record and reply.', author_id: 'demo-contractor-1', created_at: '2026-11-14T11:00:00Z' }], evidence: [{ id: 'demo-evidence-1', file_name: 'sample-shift-record.jpg', byte_size: 12000, content_type: 'image/jpeg' }], reviews: [] },
  { id: 'demo-case-2', worker_id: 'demo-worker-1', contractor_id: 'demo-contractor-2', category: 'hours', description: 'Sample dispute: actual working hours differed from the accepted agreement.', status: 'under_review', created_at: '2026-11-10T07:30:00Z', responses: [], evidence: [], reviews: [{ status: 'under_review', outcome: null, notes: 'Sample review note: compare the accepted terms with both accounts.', created_at: '2026-11-11T10:00:00Z' }] },
]

export const demoAgreements = [
  { id: 'demo-agreement-1', worker: 'Sita Devi', contractor: 'Ramesh Sharma', wage: 700, period: 'day', hours: '8 hours', status: 'accepted', version: 1 },
  { id: 'demo-agreement-2', worker: 'Imran Khan', contractor: 'Ramesh Sharma', wage: 650, period: 'day', hours: '7.5 hours', status: 'pending worker acceptance', version: 2 },
]

export function createDemoSnapshot() {
  return {
    profile: { ...demoAdminProfile }, workers: demoWorkers.map(row => ({ ...row })), contractors: demoContractors.map(row => ({ ...row })),
    jobs: demoJobs.map(row => ({ ...row })), payments: demoPayments.map(row => ({ ...row })), agreements: demoAgreements.map(row => ({ ...row })),
    cases: demoCases.map(row => ({ ...row, responses: row.responses.map(item => ({ ...item })), evidence: row.evidence.map(item => ({ ...item })), reviews: row.reviews?.map(item => ({ ...item })) })),
  }
}
