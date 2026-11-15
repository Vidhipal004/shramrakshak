export const DEMO_USER = {
  id: 'demo-worker-local-only',
  email: 'demo.worker@example.test',
  full_name: 'Asha Kumari (Demo)',
  role: 'worker',
};

export const DEMO_PROFILE = {
  ...DEMO_USER,
  phone: '+91 90000 00000',
  city: 'Jaipur',
  state: 'Rajasthan',
  latitude: 26.9124,
  longitude: 75.7873,
};

export const DEMO_JOBS = [
  {
    id: 'demo-job-masonry', contractor_id: 'demo-contractor-masonry',
    title: 'Masonry helper', occupation: 'Construction', skill: 'Masonry',
    description: 'Help with brickwork at a residential site.', location: 'Mansarovar, Jaipur',
    wage_amount: '700', wage_period: 'day', working_hours: '8 hours',
    payment_terms: 'Paid daily by UPI or cash', start_date: '2026-11-18', status: 'open',
  },
  {
    id: 'demo-job-packing', contractor_id: 'demo-contractor-packing',
    title: 'Warehouse packing worker', occupation: 'Warehouse', skill: 'Packing',
    description: 'Pack and sort household goods.', location: 'Sanganer, Jaipur',
    wage_amount: '650', wage_period: 'day', working_hours: '7 hours',
    payment_terms: 'Payment every evening', start_date: '2026-11-20', status: 'open',
  },
];

export const DEMO_APPLICATIONS: any[] = [
  { id: 'demo-application-1', job_id: 'demo-job-packing', status: 'pending', job: DEMO_JOBS[1] },
];

export const DEMO_AGREEMENTS: any[] = [
  {
    id: 'demo-agreement-1', job_id: 'demo-job-masonry', current_accepted_version: 1,
    versions: [
      {
        id: 'demo-agreement-version-1', version_number: 1, status: 'accepted',
        accepted_wage: '700', wage_period: 'day', working_hours: '8 hours',
        location: 'Mansarovar, Jaipur', payment_terms: 'Paid daily by UPI or cash',
        start_date: '2026-11-18',
      },
    ],
  },
];

export const DEMO_TRAVEL_CHECKS: any[] = [
  { id: 'demo-travel-1', agreement_id: 'demo-agreement-1', travel_date: '2026-11-18', status: 'confirmed' },
];

export const DEMO_CASES: any[] = [
  {
    id: 'demo-case-1', category: 'payment', description: 'Sample complaint: payment was delayed by one day.',
    status: 'resolved', created_at: '2026-11-10T08:00:00Z', responses: [], evidence: [],
  },
];

export const DEMO_ATTENDANCE = [
  { id: 'demo-attendance-1', date: '2026-11-13', status: 'present', hours: 8, job: 'Masonry helper' },
  { id: 'demo-attendance-2', date: '2026-11-12', status: 'present', hours: 7.5, job: 'Masonry helper' },
];

export const DEMO_PAYMENTS = [
  { id: 'demo-payment-1', date: '2026-11-13', amount: 700, status: 'paid', method: 'UPI' },
  { id: 'demo-payment-2', date: '2026-11-12', amount: 700, status: 'paid', method: 'Cash' },
  { id: 'demo-payment-3', date: '2026-11-11', amount: 700, status: 'pending', method: '—' },
];

export const DEMO_OFFER = {
  contractor_name: 'Ramesh BuildWorks (Demo)', occupation: 'Masonry helper',
  wage_amount: 700, currency: 'INR', wage_period: 'day', working_hours: '8 hours',
  location: 'Mansarovar, Jaipur', payment_terms: 'Paid daily', start_date: '2026-11-18',
  notes: 'Sample extraction only. Review all details before relying on them.',
};

export function createDemoSnapshot() {
  return {
    profile: { ...DEMO_PROFILE },
    jobs: DEMO_JOBS.map((job) => ({ ...job })),
    applications: DEMO_APPLICATIONS.map((app) => ({ ...app, job: { ...app.job } })),
    agreements: DEMO_AGREEMENTS.map((agreement) => ({
      ...agreement,
      versions: agreement.versions.map((version: any) => ({ ...version })),
    })),
    travelChecks: DEMO_TRAVEL_CHECKS.map((check) => ({ ...check })),
    cases: DEMO_CASES.map((item) => ({ ...item, responses: [...item.responses], evidence: [...item.evidence] })),
  };
}
