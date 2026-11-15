import type { Agreement, Application, Complaint, Job, Profile, Travel } from './api'

export const demoProfile: Profile = {
  id: 'demo-contractor-001', email: 'demo.contractor@example.test', full_name: 'Ramesh Sharma (Demo)',
  role: 'contractor', phone: '+91 90000 10001', city: 'Jaipur', state: 'Rajasthan',
  business_name: 'Sharma BuildWorks · Demo', verification_status: 'unverified',
}

export const demoJobs: Job[] = [
  {
    id: 'demo-job-masonry', contractor_id: demoProfile.id, title: 'Masonry helper', occupation: 'Construction',
    skill: 'Masonry', description: 'Support brickwork and site preparation for a residential project.',
    location: 'Mansarovar, Jaipur', latitude: 26.854, longitude: 75.764, wage_amount: '700', wage_period: 'day',
    working_hours: '8 hours · 9:00 AM–5:00 PM', payment_terms: 'Paid daily by UPI or cash', start_date: '2026-11-20', status: 'open',
  },
  {
    id: 'demo-job-painting', contractor_id: demoProfile.id, title: 'Assistant painter', occupation: 'Painting',
    skill: 'Wall painting', description: 'Prepare surfaces and assist with interior painting.',
    location: 'Vaishali Nagar, Jaipur', latitude: 26.912, longitude: 75.741, wage_amount: '650', wage_period: 'day',
    working_hours: '7.5 hours · 9:30 AM–5:30 PM', payment_terms: 'Paid every evening', start_date: '2026-11-22', status: 'open',
  },
]

export const demoApplications: Record<string, Application[]> = {
  'demo-job-masonry': [
    { id: 'demo-application-1', job_id: 'demo-job-masonry', worker_id: 'demo-worker-1', worker_name: 'Sita Devi', worker_city: 'Jaipur', message: 'I have three years of masonry experience.', status: 'pending', created_at: '2026-11-15T08:30:00Z' },
    { id: 'demo-application-2', job_id: 'demo-job-masonry', worker_id: 'demo-worker-2', worker_name: 'Imran Khan', worker_city: 'Sanganer', message: 'Available from the listed start date.', status: 'accepted', created_at: '2026-11-14T10:15:00Z' },
  ],
  'demo-job-painting': [
    { id: 'demo-application-3', job_id: 'demo-job-painting', worker_id: 'demo-worker-3', worker_name: 'Meena Kumari', worker_city: 'Vaishali Nagar', message: 'Experienced with interior painting.', status: 'pending', created_at: '2026-11-15T11:10:00Z' },
  ],
}

export const demoAgreements: Agreement[] = [
  {
    id: 'demo-agreement-1', application_id: 'demo-application-2', job_id: 'demo-job-masonry', worker_id: 'demo-worker-2',
    contractor_id: demoProfile.id, created_at: '2026-11-14T12:00:00Z', current_accepted_version: 1,
    versions: [{
      id: 'demo-agreement-version-1', agreement_id: 'demo-agreement-1', version_number: 1,
      accepted_wage: '700', currency: 'INR', wage_period: 'day', working_hours: '8 hours · 9:00 AM–5:00 PM',
      location: 'Mansarovar, Jaipur', payment_terms: 'Paid daily by UPI or cash', start_date: '2026-11-20',
      proposed_by: demoProfile.id, status: 'accepted', proposed_at: '2026-11-14T12:00:00Z',
      worker_accepted_at: '2026-11-14T13:00:00Z', contractor_accepted_at: '2026-11-14T13:05:00Z',
    }],
  },
]

export const demoTravelChecks: (Travel & { agreement: Agreement })[] = [
  {
    id: 'demo-travel-1', agreement_id: 'demo-agreement-1', agreement_version_id: 'demo-agreement-version-1',
    travel_date: '2026-11-20', status: 'confirmed', reconfirmed_terms: null, agreement: demoAgreements[0],
    agreed_terms: demoAgreements[0].versions[0],
  },
]

export const demoComplaints: Complaint[] = [
  {
    id: 'demo-complaint-1', worker_id: 'demo-worker-2', contractor_id: demoProfile.id, category: 'payment',
    description: 'Sample case: one daily payment was delayed and then settled.', status: 'resolved',
    created_at: '2026-11-12T09:00:00Z', responses: [], evidence: [],
  },
]

export const demoAttendance = [
  { id: 'demo-attendance-1', worker: 'Imran Khan', job: 'Masonry helper', date: '2026-11-14', hours: 8, status: 'present' },
  { id: 'demo-attendance-2', worker: 'Imran Khan', job: 'Masonry helper', date: '2026-11-13', hours: 7.5, status: 'present' },
]

export const demoPayments = [
  { id: 'demo-payment-1', worker: 'Imran Khan', date: '2026-11-14', amount: 700, status: 'paid', method: 'UPI' },
  { id: 'demo-payment-2', worker: 'Imran Khan', date: '2026-11-13', amount: 700, status: 'paid', method: 'Cash' },
  { id: 'demo-payment-3', worker: 'Imran Khan', date: '2026-11-12', amount: 700, status: 'pending', method: '—' },
]

export function createDemoWorkspace() {
  return {
    profile: { ...demoProfile }, jobs: demoJobs.map(job => ({ ...job })),
    applications: Object.fromEntries(Object.entries(demoApplications).map(([jobId, entries]) => [jobId, entries.map(entry => ({ ...entry }))])),
    agreements: demoAgreements.map(agreement => ({ ...agreement, versions: agreement.versions.map(version => ({ ...version })) })),
    complaints: demoComplaints.map(complaint => ({ ...complaint, responses: [...complaint.responses], evidence: [...complaint.evidence] })),
    travelChecks: demoTravelChecks.map(check => ({ ...check, agreement: { ...check.agreement }, agreed_terms: { ...check.agreed_terms } })),
  }
}
