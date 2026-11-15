import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import {
  Activity, ArrowDownRight, ArrowRight, Bell, BriefcaseBusiness, Check, CheckCircle2, ChevronDown, ClipboardCheck,
  FileCheck2, FileText, Filter, Handshake, Languages, LayoutDashboard, LogOut, MapPin, MessageSquareText,
  Plus, RefreshCw, Search, ShieldCheck, Users, WalletCards, X,
} from 'lucide-react'
import { api, json, tokenStore, type Agreement, type AgreementVersion, type Application, type Complaint, type Job, type Profile, type Travel } from './api'
import { copy, type Language } from './i18n'
import { assertLiveApiAllowed, canUseDemo } from './demoMode'
import { createDemoWorkspace, demoApplications, demoAttendance, demoPayments } from './demoData'

type Page = 'overview' | 'jobs' | 'applicants' | 'agreements' | 'travel' | 'complaints' | 'profile'
type AuthMode = 'login' | 'register'
type JobForm = { title: string; occupation: string; skill: string; description: string; location: string; latitude: string; longitude: string; wage_amount: string; wage_period: string; working_hours: string; payment_terms: string; start_date: string }
const blankJob: JobForm = { title: '', occupation: '', skill: '', description: '', location: '', latitude: '', longitude: '', wage_amount: '', wage_period: 'day', working_hours: '', payment_terms: '', start_date: '' }
const nav: { id: Page; icon: typeof LayoutDashboard; label: keyof typeof copy.en }[] = [
  { id: 'overview', icon: LayoutDashboard, label: 'navOverview' }, { id: 'jobs', icon: BriefcaseBusiness, label: 'navJobs' },
  { id: 'applicants', icon: Users, label: 'navApplicants' }, { id: 'agreements', icon: FileCheck2, label: 'navAgreements' },
  { id: 'travel', icon: ClipboardCheck, label: 'navTravel' }, { id: 'complaints', icon: MessageSquareText, label: 'navComplaints' },
]

function App() {
  const [language, setLanguage] = useState<Language>('en')
  const t = copy[language]
  const [page, setPage] = useState<Page>('overview')
  const [selectedApplicantJob, setSelectedApplicantJob] = useState('all')
  const [profile, setProfile] = useState<Profile | null>(null)
  const [demoMode, setDemoMode] = useState(false)
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [jobs, setJobs] = useState<Job[]>([])
  const [agreements, setAgreements] = useState<Agreement[]>([])
  const [complaints, setComplaints] = useState<Complaint[]>([])
  const [applications, setApplications] = useState<Record<string, Application[]>>({})
  const [travelChecks, setTravelChecks] = useState<(Travel & { agreement: Agreement })[]>([])
  const [jobForm, setJobForm] = useState<JobForm>(blankJob)
  const [editingJob, setEditingJob] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [agreementForm, setAgreementForm] = useState<{ applicationId: string; job: Job } | null>(null)
  const [agreementCurrency, setAgreementCurrency] = useState('INR')
  const [versionDraft, setVersionDraft] = useState<{ agreement: Agreement; wage: string; hours: string } | null>(null)
  const [trustReport, setTrustReport] = useState<any>(null)
  const [authFields, setAuthFields] = useState({ email: '', password: '', full_name: '', business_name: '' })
  const [profileDraft, setProfileDraft] = useState({ full_name: '', business_name: '', phone: '', city: '', state: '' })

  const setMessage = (message: string) => { setSuccess(message); window.setTimeout(() => setSuccess(''), 3200) }

  const workspaceRequest = useCallback(<T,>(path: string, options?: RequestInit) => {
    assertLiveApiAllowed(demoMode)
    return api<T>(path, options)
  }, [demoMode])

  const loadWorkspace = useCallback(async () => {
    if (demoMode) {
      const sample = createDemoWorkspace()
      setProfile(sample.profile); setProfileDraft({ full_name: sample.profile.full_name, business_name: sample.profile.business_name || '', phone: sample.profile.phone || '', city: sample.profile.city || '', state: sample.profile.state || '' })
      setJobs(sample.jobs); setApplications(sample.applications); setAgreements(sample.agreements); setComplaints(sample.complaints); setTravelChecks(sample.travelChecks)
      setLoading(false); setError(''); return
    }
    setLoading(true); setError('')
    try {
      const [me, listed, signed, cases] = await Promise.all([
        workspaceRequest<Profile>('/api/v1/auth/profile'), workspaceRequest<Job[]>('/api/v1/jobs/mine'), workspaceRequest<Agreement[]>('/api/v1/agreements/mine'), workspaceRequest<Complaint[]>('/api/v1/complaints/mine'),
      ])
      if (me.role !== 'contractor') throw new Error('This workspace is for contractor accounts.')
      setProfile(me); setProfileDraft({ full_name: me.full_name, business_name: me.business_name || '', phone: me.phone || '', city: me.city || '', state: me.state || '' })
      setJobs(listed); setAgreements(signed); setComplaints(cases)
    } catch (e) { tokenStore.clear(); setProfile(null); setError((e as Error).message) }
    finally { setLoading(false) }
  }, [demoMode, workspaceRequest])

  useEffect(() => { if (!demoMode && tokenStore.get()) void loadWorkspace(); else if (!demoMode) setLoading(false) }, [demoMode, loadWorkspace])

  useEffect(() => {
    if (page !== 'applicants' || demoMode) return
    let active = true
    Promise.all(jobs.map(async job => [job.id, await workspaceRequest<Application[]>(`/api/v1/jobs/${job.id}/applications`)] as const))
      .then(entries => { if (active) setApplications(Object.fromEntries(entries)) })
      .catch(e => { if (active) setError((e as Error).message) })
    return () => { active = false }
  }, [page, jobs, demoMode, workspaceRequest])

  useEffect(() => {
    if (page !== 'travel' || demoMode) return
    let active = true
    Promise.all(agreements.map(async agreement => {
      try {
        const checks = await workspaceRequest<Travel[]>(`/api/v1/agreements/${agreement.id}/travel-confirmations`)
        return checks.map(check => ({ ...check, agreement }))
      } catch { return [] }
    })).then(groups => { if (active) setTravelChecks(groups.flat()) })
    return () => { active = false }
  }, [page, agreements, demoMode, workspaceRequest])

  const activeJobs = useMemo(() => jobs.filter(job => job.status === 'open'), [jobs])
  const filteredJobs = useMemo(() => jobs.filter(job => `${job.title} ${job.occupation} ${job.location}`.toLowerCase().includes(filter.toLowerCase())), [jobs, filter])
  const pendingComplaints = complaints.filter(item => !['resolved', 'dismissed'].includes(item.status))

  async function submitAuth(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      if (authMode === 'register') {
        const result = await api<{ message: string; requires_email_confirmation: boolean }>('/api/v1/auth/register', json({ ...authFields, role: 'contractor' }))
        setSuccess(result.requires_email_confirmation ? 'Account created. Confirm your email, then sign in.' : 'Account created. Sign in to open your workspace.')
        setAuthMode('login')
      } else {
        const session = await api<{ access_token: string; user: Profile }>('/api/v1/auth/login', json({ email: authFields.email, password: authFields.password }))
        tokenStore.set(session.access_token); await loadWorkspace()
      }
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  function startDemo() {
    if (!canUseDemo(import.meta.env.DEV)) return
    tokenStore.clear()
    const sample = createDemoWorkspace()
    setDemoMode(true); setLoading(false); setPage('overview'); setProfile(sample.profile)
    setProfileDraft({ full_name: sample.profile.full_name, business_name: sample.profile.business_name || '', phone: sample.profile.phone || '', city: sample.profile.city || '', state: sample.profile.state || '' })
    setJobs(sample.jobs); setApplications(sample.applications); setAgreements(sample.agreements); setComplaints(sample.complaints); setTravelChecks(sample.travelChecks)
    setTrustReport(null); setJobForm(blankJob); setEditingJob(null); setAgreementForm(null); setVersionDraft(null); setFilter(''); setSelectedApplicantJob('all')
    setError(''); setSuccess('Demo workspace opened. Any changes stay local and are not real.')
  }

  async function createOrUpdateJob(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const payload = { ...jobForm, skill: jobForm.skill || null, description: jobForm.description || null, latitude: jobForm.latitude ? Number(jobForm.latitude) : null, longitude: jobForm.longitude ? Number(jobForm.longitude) : null, wage_amount: Number(jobForm.wage_amount) }
      if (demoMode) {
        const item: Job = { ...payload, wage_amount: String(payload.wage_amount), id: editingJob || `demo-job-${Date.now()}`, contractor_id: profile!.id, status: 'open' }
        setJobs(current => editingJob ? current.map(job => job.id === editingJob ? item : job) : [item, ...current])
        setJobForm(blankJob); setEditingJob(null); setMessage('Demo listing saved locally. It is not real or visible to workers.'); return
      }
      if (editingJob) await workspaceRequest(`/api/v1/jobs/${editingJob}`, { method: 'PATCH', body: JSON.stringify(payload) })
      else await workspaceRequest('/api/v1/jobs', json(payload))
      setJobForm(blankJob); setEditingJob(null); await loadWorkspace(); setMessage(editingJob ? 'Listing updated.' : 'Listing published.')
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  function editJob(job: Job) {
    setEditingJob(job.id)
    setJobForm({ title: job.title, occupation: job.occupation, skill: job.skill || '', description: job.description || '', location: job.location, latitude: job.latitude == null ? '' : String(job.latitude), longitude: job.longitude == null ? '' : String(job.longitude), wage_amount: job.wage_amount, wage_period: job.wage_period, working_hours: job.working_hours, payment_terms: job.payment_terms, start_date: job.start_date })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function cancelJob(jobId: string) {
    if (!window.confirm('Cancel this listing? Workers will no longer see it, and its history will remain.')) return
    if (demoMode) { setJobs(current => current.map(job => job.id === jobId ? { ...job, status: 'cancelled' } : job)); setMessage('Demo listing cancelled locally. No real listing changed.'); return }
    try { await workspaceRequest(`/api/v1/jobs/${jobId}`, { method: 'DELETE' }); await loadWorkspace(); setMessage('Listing cancelled.') }
    catch (e) { setError((e as Error).message) }
  }

  async function updateApplication(jobId: string, applicationId: string, status: 'accepted' | 'rejected') {
    if (demoMode) {
      setApplications(current => ({ ...current, [jobId]: (current[jobId] || []).map(item => item.id === applicationId ? { ...item, status } : item) }))
      setMessage(`Demo application ${status} locally. No worker was notified.`); return
    }
    try {
      await workspaceRequest(`/api/v1/jobs/${jobId}/applications/${applicationId}`, { method: 'PATCH', body: JSON.stringify({ status }) })
      const updated = await workspaceRequest<Application[]>(`/api/v1/jobs/${jobId}/applications`)
      setApplications(current => ({ ...current, [jobId]: updated })); setMessage(status === 'accepted' ? 'Worker accepted.' : 'Application declined.')
    } catch (e) { setError((e as Error).message) }
  }

  async function createAgreement(event: FormEvent) {
    event.preventDefault(); if (!agreementForm) return
    setBusy(true)
    try {
      const { applicationId, job } = agreementForm
      if (demoMode) {
        const id = `demo-agreement-${Date.now()}`, proposedAt = new Date().toISOString()
        const worker = Object.values(demoApplications).flat().find(item => item.id === applicationId)
        const version: AgreementVersion = { id: `${id}-version-1`, agreement_id: id, version_number: 1, accepted_wage: String(job.wage_amount), currency: agreementCurrency, wage_period: job.wage_period, working_hours: job.working_hours, location: job.location, payment_terms: job.payment_terms, start_date: job.start_date, proposed_by: profile!.id, status: 'pending', proposed_at: proposedAt, worker_accepted_at: null, contractor_accepted_at: null }
        const agreement: Agreement = { id, application_id: applicationId, job_id: job.id, worker_id: worker?.worker_id || 'demo-worker-local', contractor_id: profile!.id, created_at: proposedAt, current_accepted_version: null, versions: [version] }
        setAgreements(current => [agreement, ...current]); setAgreementForm(null); setAgreementCurrency('INR'); setMessage('Demo agreement created locally. No worker received it.'); return
      }
      await workspaceRequest('/api/v1/agreements', json({ application_id: applicationId, accepted_wage: Number(job.wage_amount), currency: agreementCurrency, wage_period: job.wage_period, working_hours: job.working_hours, location: job.location, payment_terms: job.payment_terms, start_date: job.start_date }))
      setAgreementForm(null); setAgreementCurrency('INR'); await loadWorkspace(); setMessage('Agreement proposal sent to the worker.')
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  async function proposeVersion(event: FormEvent) {
    event.preventDefault(); if (!versionDraft) return
    const body: Record<string, string | number> = {}
    if (versionDraft.wage) body.accepted_wage = Number(versionDraft.wage)
    if (versionDraft.hours) body.working_hours = versionDraft.hours
    if (!Object.keys(body).length) { setError('Enter a changed wage or working-hours term.'); return }
    if (demoMode) {
      const agreementId = versionDraft.agreement.id, original = versionDraft.agreement.versions.at(-1)!
      const version: AgreementVersion = { ...original, id: `demo-version-${Date.now()}`, agreement_id: agreementId, version_number: original.version_number + 1, accepted_wage: String(body.accepted_wage ?? original.accepted_wage), working_hours: String(body.working_hours ?? original.working_hours), proposed_by: profile!.id, status: 'pending', proposed_at: new Date().toISOString(), worker_accepted_at: null, contractor_accepted_at: null }
      setAgreements(current => current.map(agreement => agreement.id === agreementId ? { ...agreement, versions: [...agreement.versions, version] } : agreement)); setVersionDraft(null); setMessage('Demo agreement version saved locally. No worker was notified.'); return
    }
    try {
      await workspaceRequest(`/api/v1/agreements/${versionDraft.agreement.id}/versions`, json(body))
      setVersionDraft(null); await loadWorkspace(); setMessage('New agreement version sent for worker acceptance.')
    } catch (e) { setError((e as Error).message) }
  }

  async function confirmTravel(check: Travel & { agreement: Agreement }) {
    if (demoMode) { setTravelChecks(current => current.map(item => item.id === check.id ? { ...item, status: 'confirmed' } : item)); setMessage('Demo job details reconfirmed locally. No worker was notified.'); return }
    try {
      const terms = check.agreed_terms
      const confirmed = await workspaceRequest<Travel>(`/api/v1/travel-confirmations/${check.id}/confirm`, json({ accepted_wage: Number(terms.accepted_wage), currency: terms.currency, wage_period: terms.wage_period, working_hours: terms.working_hours, location: terms.location, payment_terms: terms.payment_terms, start_date: terms.start_date }))
      const checks = await workspaceRequest<Travel[]>(`/api/v1/agreements/${check.agreement_id}/travel-confirmations`)
      setTravelChecks(current => current.map(item => item.id === check.id ? { ...checks.find(entry => entry.id === check.id)!, agreement: check.agreement } : item))
      setMessage(confirmed.status === 'confirmed' ? 'Accepted terms reconfirmed. The worker can now record departure.' : 'The accepted agreement changed. The worker needs an updated accepted version before travel.')
    } catch (e) { setError((e as Error).message) }
  }

  async function downloadEvidence(complaintId: string, evidenceId: string, fileName: string) {
    if (demoMode) { setMessage('Demo evidence is sample-only and is not stored as a downloadable file.'); return }
    try { const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/api/v1/complaints/${complaintId}/evidence/${evidenceId}`, { headers: { Authorization: `Bearer ${tokenStore.get()}` } }); if (!response.ok) throw new Error('Could not download evidence.'); const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = fileName; link.click(); URL.revokeObjectURL(url) } catch (e) { setError((e as Error).message) }
  }

  async function sendComplaintResponse(complaintId: string, message: string) {
    if (demoMode) { setComplaints(current => current.map(item => item.id === complaintId ? { ...item, responses: [...item.responses, { id: `demo-response-${Date.now()}`, message, author_id: profile!.id, created_at: new Date().toISOString() }], status: 'under_review' } : item)); setMessage('Demo response saved locally. No worker was notified.'); return }
    try { await workspaceRequest(`/api/v1/complaints/${complaintId}/responses`, json({ message })); await loadWorkspace(); setMessage('Response sent to the worker.') }
    catch (e) { setError((e as Error).message) }
  }

  async function saveProfile(event: FormEvent) {
    event.preventDefault()
    if (demoMode) { const updated = { ...profile!, ...profileDraft }; setProfile(updated); setProfileDraft({ full_name: updated.full_name, business_name: updated.business_name || '', phone: updated.phone || '', city: updated.city || '', state: updated.state || '' }); setMessage('Demo profile saved locally. No account was changed.'); return }
    try { const updated = await workspaceRequest<Profile>('/api/v1/auth/profile', { method: 'PATCH', body: JSON.stringify(profileDraft) }); setProfile(updated); setProfileDraft({ full_name: updated.full_name, business_name: updated.business_name || '', phone: updated.phone || '', city: updated.city || '', state: updated.state || '' }); setMessage('Profile saved.') }
    catch (e) { setError((e as Error).message) }
  }

  async function showTrust() {
    if (!profile) return
    setPage('overview'); setTrustReport(null)
    if (demoMode) { setTrustReport({ score: null, status: 'insufficient_data', confidence: { level: 'low', data_coverage_pct: 0, evidence_count: 0 }, reasons: ['Demo profile has no verified contractor history.'], components: [{ key: 'verification', label: 'Contractor verification', weight_pct: 20, score: null, reasons: ['Demo identity is not verified.'] }, { key: 'wage_consistency', label: 'Wage consistency', weight_pct: 25, score: null, reasons: ['No verified demo history.'] }, { key: 'completion', label: 'Previous completion', weight_pct: 20, score: null, reasons: ['No verified demo history.'] }, { key: 'feedback', label: 'Worker feedback', weight_pct: 20, score: null, reasons: ['No verified demo history.'] }, { key: 'completeness', label: 'Information completeness', weight_pct: 15, score: null, reasons: ['Sample data is excluded.'] }] }); return }
    try { setTrustReport(await workspaceRequest('/api/v1/contractors/' + profile.id + '/jobtrust-score')) }
    catch (e) { setError((e as Error).message) }
  }

  async function signOut() {
    if (demoMode) { setDemoMode(false); setProfile(null); setJobs([]); setAgreements([]); setComplaints([]); setApplications({}); setTravelChecks([]); setTrustReport(null); setPage('overview'); setSuccess(''); setLoading(false); return }
    try { await api('/api/v1/auth/logout', { method: 'POST' }) } catch { /* clear the local session even if the server cannot be reached */ }
    tokenStore.clear(); setProfile(null); setJobs([]); setAgreements([]); setComplaints([]); setPage('overview')
  }

  if (loading) return <div className="loading-page"><span className="brand-mark">S</span><p>{t.loading}</p></div>
  if (!profile) return <AuthScreen t={t} language={language} setLanguage={setLanguage} mode={authMode} setMode={setAuthMode} fields={authFields} setFields={setAuthFields} onSubmit={submitAuth} onDemo={startDemo} demoAllowed={canUseDemo(import.meta.env.DEV)} busy={busy} error={error} success={success} />

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup"><span className="brand-mark">S</span><div><strong>{t.product}</strong><small>{t.role}</small></div></div>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {nav.map(item => <button className={`nav-item ${page === item.id ? 'active' : ''}`} key={item.id} onClick={() => setPage(item.id)}><item.icon size={18} strokeWidth={1.8} /><span>{t[item.label]}</span>{item.id === 'complaints' && pendingComplaints.length > 0 && <b className="nav-count">{pendingComplaints.length}</b>}</button>)}
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-item" onClick={() => setPage('profile')}><ShieldCheck size={18} /><span>{t.navProfile}</span></button>
          <div className="profile-strip"><span className="avatar">{profile.full_name.slice(0, 1).toUpperCase()}</span><div className="profile-name"><strong>{profile.full_name}</strong><small>{profile.business_name || profile.email}</small></div><button className="icon-button" title={demoMode ? t.exitDemo : t.signOut} aria-label={demoMode ? t.exitDemo : t.signOut} onClick={() => void signOut()}><LogOut size={17} /></button></div>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar"><div className="breadcrumbs"><span>Workspace</span><ArrowRight size={13} /><strong>{page === 'profile' ? t.navProfile : t[nav.find(item => item.id === page)?.label || 'navOverview']}</strong></div><div className="top-actions"><button className="quiet-button language-toggle" onClick={() => setLanguage(language === 'en' ? 'hi' : 'en')}><Languages size={16} />{t.language}</button><button className="icon-button notification-button" aria-label="Refresh workspace" onClick={() => demoMode ? setMessage(language === 'en' ? 'Demo data is local; no server was contacted.' : 'डेमो डेटा स्थानीय है; सर्वर से संपर्क नहीं हुआ।') : void loadWorkspace()}><RefreshCw size={17} /></button><button className="mobile-profile" onClick={() => setPage('profile')}>{profile.full_name.slice(0, 1).toUpperCase()}</button></div></header>
        <div className="page-content">
          {demoMode && <div className="demo-banner" role="status"><ShieldCheck size={17} /><strong>{language === 'en' ? 'DEMO CONTRACTOR · SAMPLE DATA ONLY' : 'डेमो ठेकेदार · केवल नमूना डेटा'}</strong><span>{language === 'en' ? 'Changes stay in this browser and are not real.' : 'बदलाव इसी ब्राउज़र में रहेंगे और वास्तविक नहीं हैं।'}</span></div>}
          {error && <div className="alert error-alert"><span>{error}</span><button onClick={() => setError('')}><X size={16} /></button></div>}
          {success && <div className="alert success-alert"><CheckCircle2 size={17} /><span>{success}</span></div>}
          {page === 'overview' && <Overview t={t} profile={profile} activeJobs={activeJobs.length} applicants={Object.values(applications).flat().filter(app => app.status === 'pending').length} openCases={pendingComplaints.length} agreements={agreements.length} trustReport={trustReport} onTrust={showTrust} onNavigate={setPage} />}
          {page === 'overview' && demoMode && <DemoRecords language={language} />}
          {page === 'jobs' && <JobsPage t={t} jobs={filteredJobs} filter={filter} setFilter={setFilter} form={jobForm} setForm={setJobForm} editing={editingJob} setEditing={setEditingJob} onSave={createOrUpdateJob} onEdit={editJob} onCancel={cancelJob} onApplicants={(jobId: string) => { setSelectedApplicantJob(jobId); setPage('applicants') }} busy={busy} />}
          {page === 'applicants' && <ApplicantsPage t={t} jobs={jobs} applications={applications} initialJob={selectedApplicantJob} onUpdate={updateApplication} onCreateAgreement={(applicationId: string, job: Job) => setAgreementForm({ applicationId, job })} />}
          {page === 'agreements' && <AgreementsPage t={t} agreements={agreements} onPropose={(agreement: Agreement) => setVersionDraft({ agreement, wage: '', hours: '' })} />}
          {page === 'travel' && <TravelPage t={t} checks={travelChecks} onConfirm={confirmTravel} onOpenAgreements={() => setPage('agreements')} />}
          {page === 'complaints' && <ComplaintsPage t={t} complaints={complaints} onRespond={sendComplaintResponse} onDownload={downloadEvidence} />}
          {page === 'profile' && <ProfilePage t={t} draft={profileDraft} setDraft={setProfileDraft} profile={profile} onSave={saveProfile} />}
        </div>
      </main>
      {agreementForm && <Modal title={t.createAgreement} onClose={() => setAgreementForm(null)}><p className="modal-copy">{demoMode ? 'Demo only: this sample agreement stays in this browser. No worker will receive it.' : 'This sends the worker a version 1 wage agreement using the listing terms. Confirm the currency before sending.'}</p><form className="stack-form" onSubmit={createAgreement}><label>Currency code<input required minLength={3} maxLength={8} value={agreementCurrency} onChange={event => setAgreementCurrency(event.target.value.toUpperCase())} /></label><div className="terms-preview"><span>{agreementForm.job.title}</span><strong>₹{agreementForm.job.wage_amount} / {agreementForm.job.wage_period}</strong><small>{agreementForm.job.working_hours} · {agreementForm.job.location}</small></div><button className="primary-button" disabled={busy}>{demoMode ? 'Create demo agreement' : 'Send version 1'}</button></form></Modal>}
      {versionDraft && <Modal title="Propose updated terms" onClose={() => setVersionDraft(null)}><p className="modal-copy">{demoMode ? 'Demo only: this sample version stays in this browser. No worker will receive it.' : 'Only changed fields are sent. The current accepted version stays intact until the worker accepts this revision.'}</p><form className="stack-form" onSubmit={proposeVersion}><label>New wage (₹)<input inputMode="decimal" value={versionDraft.wage} onChange={event => setVersionDraft({ ...versionDraft, wage: event.target.value })} placeholder={versionDraft.agreement.versions.find(v => v.status === 'accepted')?.accepted_wage} /></label><label>New working hours<input value={versionDraft.hours} onChange={event => setVersionDraft({ ...versionDraft, hours: event.target.value })} placeholder={versionDraft.agreement.versions.find(v => v.status === 'accepted')?.working_hours} /></label><button className="primary-button">{demoMode ? 'Save demo version' : 'Send for acceptance'}</button></form></Modal>}
    </div>
  )
}

function AuthScreen({ t, language, setLanguage, mode, setMode, fields, setFields, onSubmit, onDemo, demoAllowed, busy, error, success }: any) {
  return <div className="auth-page"><div className="auth-brand"><span className="brand-mark">S</span><span>{t.product}<small>{t.role}</small></span><button onClick={() => setLanguage(language === 'en' ? 'hi' : 'en')}>{t.language}</button></div><div className="auth-card"><div className="eyebrow">TRUST BEGINS WITH CLEAR TERMS</div><h1>{mode === 'login' ? t.signIn : t.register}</h1><p>Manage listings, applications and accepted wage agreements from one workspace.</p>{error && <div className="alert error-alert">{error}</div>}{success && <div className="alert success-alert">{success}</div>}<form className="stack-form" onSubmit={onSubmit}>{mode === 'register' && <><label>{t.name}<input required autoComplete="name" value={fields.full_name} onChange={(e: any) => setFields({ ...fields, full_name: e.target.value })} /></label><label>{t.business}<input required value={fields.business_name} onChange={(e: any) => setFields({ ...fields, business_name: e.target.value })} /></label></>}<label>{t.email}<input type="email" required autoComplete="email" value={fields.email} onChange={(e: any) => setFields({ ...fields, email: e.target.value })} /></label><label>{t.password}<input type="password" required minLength={8} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={fields.password} onChange={(e: any) => setFields({ ...fields, password: e.target.value })} /></label><button className="primary-button full-width" disabled={busy}>{busy ? 'Please wait…' : t.continue}<ArrowRight size={16} /></button></form>{mode === 'login' && demoAllowed && <button className="demo-button full-width" type="button" onClick={onDemo}>{language === 'en' ? 'Continue as Demo Contractor · DEVELOPMENT ONLY' : 'डेमो ठेकेदार के रूप में जारी रखें · केवल विकास के लिए'}<ArrowRight size={16} /></button>}<button className="auth-switch" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>{mode === 'login' ? 'New to ShramRakshak? Create a contractor account' : 'Already registered? Sign in'}</button><div className="auth-note"><ShieldCheck size={16} />Account creation is protected by Supabase Auth.</div></div><footer>Clear work. Fair wages. Reliable records.</footer></div>
}

function DemoRecords({ language }: { language: Language }) {
  const en = language === 'en'
  return <div className="overview-grid demo-records">
    <section className="panel"><div className="panel-head"><div><div className="eyebrow">{en ? 'SAMPLE RECORDS' : 'नमूना रिकॉर्ड'}</div><h2>{en ? 'Attendance' : 'उपस्थिति'}</h2><p>{en ? 'Demo worker · not a real attendance register' : 'डेमो कर्मचारी · वास्तविक उपस्थिति रजिस्टर नहीं'}</p></div><ClipboardCheck size={20} /></div>{demoAttendance.map(row => <div className="demo-record-row" key={row.id}><strong>{row.worker}</strong><span>{row.date} · {row.hours}h</span><span className="status-pill accepted">{row.status}</span></div>)}</section>
    <section className="panel"><div className="panel-head"><div><div className="eyebrow">{en ? 'SAMPLE RECORDS' : 'नमूना रिकॉर्ड'}</div><h2>{en ? 'Payments' : 'भुगतान'}</h2><p>{en ? 'Illustrative amounts only · no money moved' : 'केवल उदाहरण राशि · कोई भुगतान नहीं हुआ'}</p></div><WalletCards size={20} /></div>{demoPayments.map(row => <div className="demo-record-row" key={row.id}><strong>{row.worker}</strong><span>{row.date} · ₹{row.amount} · {row.method}</span><span className={`status-pill ${row.status === 'paid' ? 'accepted' : 'pending'}`}>{row.status}</span></div>)}</section>
  </div>
}

function Overview({ t, profile, activeJobs, applicants, openCases, agreements, trustReport, onTrust, onNavigate }: any) {
  return <><div className="welcome-row"><div><div className="eyebrow">{new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</div><h1>{t.welcome}</h1><p>{t.subtitle}</p></div><button className="primary-button" onClick={() => onNavigate('jobs')}><Plus size={17} />{t.createJob}</button></div>
    <section className="metric-grid"><Metric icon={BriefcaseBusiness} label={t.jobs} value={activeJobs} tone="green" /><Metric icon={Users} label={t.applicants} value={applicants} tone="blue" /><Metric icon={MessageSquareText} label={t.openCases} value={openCases} tone="amber" /><Metric icon={Handshake} label={t.navAgreements} value={agreements} tone="violet" /></section>
    <div className="overview-grid"><section className="panel welcome-panel"><div className="panel-head"><div><div className="eyebrow">YOUR STANDARD</div><h2>Build trust into every offer</h2></div><span className="soft-icon"><ShieldCheck size={22} /></span></div><p>Clear wages, hours and payment terms help workers choose with confidence. Accepted terms are recorded as a versioned agreement.</p><div className="check-list"><span><Check size={15} />Post complete job details</span><span><Check size={15} />Review workers through your job listings</span><span><Check size={15} />Reconfirm before a worker travels</span></div><button className="text-action" onClick={() => onNavigate('jobs')}>Manage job listings <ArrowRight size={15} /></button></section>
      <section className="panel trust-panel"><div className="panel-head"><div><div className="eyebrow">CONTRACTOR PROFILE</div><h2>{t.trust}</h2></div><button className="quiet-button" onClick={onTrust}><Activity size={15} />View report</button></div>{trustReport ? <TrustSummary report={trustReport} /> : <div className="trust-placeholder"><span className="score-ghost"><ShieldCheck size={25} /></span><div><strong>Evidence-backed, not a guess</strong><p>Open your report to see available data, missing components, and score confidence.</p></div></div>}</section></div>
    <div className="bottom-note"><span className="note-dot" />Signed in as <strong>{profile.business_name || profile.full_name}</strong><span className="note-separator">·</span>{profile.city || 'Add your work location'}<button onClick={() => onNavigate('profile')}>Edit profile</button></div></>
}

function Metric({ icon: Icon, label, value, tone }: any) { return <div className="metric-card"><span className={`metric-icon ${tone}`}><Icon size={19} /></span><div><span className="metric-label">{label}</span><strong>{value}</strong></div><ArrowDownRight size={16} className="metric-arrow" /></div> }

function JobsPage({ t, jobs, filter, setFilter, form, setForm, editing, setEditing, onSave, onEdit, onCancel, onApplicants, busy }: any) {
  const update = (field: keyof JobForm, value: string) => setForm({ ...form, [field]: value })
  return <div className="content-page"><div className="section-heading"><div><div className="eyebrow">MARKETPLACE</div><h1>{t.navJobs}</h1><p>Keep every offer complete and easy to compare.</p></div><button className="quiet-button" onClick={() => { setEditing(null); setForm(blankJob) }}><Plus size={16} />{t.createJob}</button></div>
    <div className="two-column-layout"><section className="panel form-panel"><div className="panel-head"><h2>{editing ? 'Edit listing' : t.createJob}</h2>{editing && <button className="icon-button" onClick={() => { setEditing(null); setForm(blankJob) }}><X size={17} /></button>}</div><form className="job-form" onSubmit={onSave}><div className="form-grid"><label>{t.title}<input required minLength={2} value={form.title} onChange={e => update('title', e.target.value)} /></label><label>{t.occupation}<input required minLength={2} value={form.occupation} onChange={e => update('occupation', e.target.value)} /></label><label>{t.skill}<input value={form.skill} onChange={e => update('skill', e.target.value)} /></label><label>{t.location}<input required value={form.location} onChange={e => update('location', e.target.value)} /></label><label>Latitude (optional)<input type="number" min="-90" max="90" step="any" value={form.latitude} onChange={e => update('latitude', e.target.value)} /></label><label>Longitude (optional)<input type="number" min="-180" max="180" step="any" value={form.longitude} onChange={e => update('longitude', e.target.value)} /></label><label>{t.wage}<input required type="number" min="1" step="0.01" value={form.wage_amount} onChange={e => update('wage_amount', e.target.value)} /></label><label>{t.period}<select value={form.wage_period} onChange={e => update('wage_period', e.target.value)}><option value="hour">Per hour</option><option value="day">Per day</option><option value="week">Per week</option><option value="month">Per month</option><option value="fixed">Fixed</option></select></label><label>{t.hours}<input required placeholder="08:00–17:00, 1 hour break" value={form.working_hours} onChange={e => update('working_hours', e.target.value)} /></label><label>{t.startDate}<input required type="date" value={form.start_date} onChange={e => update('start_date', e.target.value)} /></label><label className="full-span">{t.payment}<input required value={form.payment_terms} onChange={e => update('payment_terms', e.target.value)} /></label><label className="full-span">{t.description}<textarea rows={3} value={form.description} onChange={e => update('description', e.target.value)} /></label></div><div className="form-footnote"><MapPin size={15} />Add coordinates with the work location to enable nearby matching within the worker’s default 5 km radius.</div><button className="primary-button" disabled={busy}>{busy ? 'Saving…' : editing ? t.save : t.createJob}<ArrowRight size={16} /></button></form></section>
      <section className="listing-column"><div className="listing-toolbar"><div><strong>{jobs.length} listings</strong><small>Sorted by status</small></div><label className="search-box"><Search size={16} /><input value={filter} onChange={e => setFilter(e.target.value)} placeholder={t.search} /></label></div>{jobs.length === 0 ? <Empty title={t.noJobs} /> : jobs.map((job: Job) => <article className="listing-card" key={job.id}><div className="listing-top"><div><span className={`status-pill ${job.status}`}>{job.status}</span><h3>{job.title}</h3><span className="muted-line">{job.occupation}{job.skill ? ` · ${job.skill}` : ''}</span></div><strong className="listing-wage">₹{Number(job.wage_amount).toLocaleString('en-IN')}<small> / {job.wage_period}</small></strong></div><div className="listing-facts"><span><MapPin size={14} />{job.location}</span><span><Activity size={14} />{job.working_hours}</span><span><FileText size={14} />{job.start_date}</span></div><div className="listing-payment"><WalletCards size={15} />{job.payment_terms}</div><div className="listing-actions"><button className="quiet-button" onClick={() => onEdit(job)}>Edit terms</button><button className="quiet-button" onClick={() => onApplicants(job.id)}>{t.viewApplicants}</button>{job.status === 'open' && <button className="danger-link" onClick={() => onCancel(job.id)}>Cancel listing</button>}</div></article>)}</section></div></div>
}

function ApplicantsPage({ t, jobs, applications, onUpdate, onCreateAgreement, initialJob }: any) {
  const [selected, setSelected] = useState<string>(initialJob)
  useEffect(() => setSelected(initialJob), [initialJob])
  const visible = jobs.filter((job: Job) => selected === 'all' || job.id === selected)
  return <div className="content-page"><div className="section-heading"><div><div className="eyebrow">WORKER APPLICATIONS</div><h1>{t.navApplicants}</h1><p>Review applications against the details on each listing.</p></div><label className="select-inline"><Filter size={15} /><select value={selected} onChange={e => setSelected(e.target.value)}><option value="all">All listings</option>{jobs.map((job: Job) => <option key={job.id} value={job.id}>{job.title}</option>)}</select><ChevronDown size={14} /></label></div>{visible.map((job: Job) => <section className="panel applicants-panel" key={job.id}><div className="panel-head"><div><h2>{job.title}</h2><p>{job.location} · ₹{job.wage_amount}/{job.wage_period}</p></div><span className="subtle-count">{(applications[job.id] || []).length} applications</span></div>{(applications[job.id] || []).length === 0 ? <Empty title={t.noApplicants} /> : <div className="applicant-list">{applications[job.id].map((app: Application) => <article className="applicant-row" key={app.id}><span className="avatar worker-avatar">{app.worker_name.slice(0, 1)}</span><div className="applicant-info"><strong>{app.worker_name}</strong><small>{app.worker_city || 'Location not listed'} · Applied {new Date(app.created_at).toLocaleDateString()}</small>{app.message && <p>“{app.message}”</p>}</div><span className={`status-pill ${app.status}`}>{app.status}</span><div className="row-actions">{app.status === 'pending' ? <><button className="small-primary" onClick={() => onUpdate(job.id, app.id, 'accepted')}>{t.accept}</button><button className="small-quiet" onClick={() => onUpdate(job.id, app.id, 'rejected')}>{t.reject}</button></> : app.status === 'accepted' ? <button className="small-quiet" onClick={() => onCreateAgreement(app.id, job)}>{t.createAgreement}</button> : null}</div></article>)}</div>}</section>)}</div>
}

function AgreementsPage({ t, agreements, onPropose }: any) { return <div className="content-page"><div className="section-heading"><div><div className="eyebrow">VERSIONED WAGE TERMS</div><h1>{t.navAgreements}</h1><p>Each revision is a new record. The original terms remain available in the history.</p></div></div>{agreements.length === 0 ? <Empty title={t.noAgreements} /> : <div className="card-stack">{agreements.map((agreement: Agreement) => { const effective = [...agreement.versions].reverse().find(v => v.status === 'accepted'); const pending = agreement.versions.find(v => v.status === 'pending'); return <section className="panel agreement-card" key={agreement.id}><div className="panel-head"><div><span className="eyebrow">AGREEMENT · {agreement.id.slice(0, 8).toUpperCase()}</span><h2>{effective ? `Version ${effective.version_number}` : 'Awaiting worker acceptance'}</h2></div><span className={`status-pill ${pending ? 'pending' : 'accepted'}`}>{pending ? 'worker acceptance pending' : 'accepted'}</span></div>{effective && <div className="terms-grid"><Term label="Accepted wage" value={`₹${effective.accepted_wage} / ${effective.wage_period}`} /><Term label={t.hours} value={effective.working_hours} /><Term label={t.location} value={effective.location} /><Term label={t.payment} value={effective.payment_terms} /><Term label={t.startDate} value={effective.start_date} /><Term label="Currency" value={effective.currency} /></div>}<div className="version-history"><strong>Version history</strong>{agreement.versions.map(version => <div className="version-row" key={version.id}><span>v{version.version_number}{version.version_number === 1 ? ' · original' : ''}</span><span>₹{version.accepted_wage} · {version.working_hours}</span><span className={`status-pill ${version.status}`}>{version.status}</span></div>)}</div>{effective && <button className="quiet-button" onClick={() => onPropose(agreement)}>Propose term change</button>}</section>})}</div>}</div> }

function TravelPage({ t, checks, onConfirm, onOpenAgreements }: any) { return <div className="content-page"><div className="section-heading"><div><div className="eyebrow">PRE-TRAVEL CHECK</div><h1>{t.navTravel}</h1><p>Compare every detail to the latest accepted agreement before the worker travels.</p></div></div>{checks.length === 0 ? <Empty title={t.noTravel} /> : checks.map((check: Travel & { agreement: Agreement }) => <section className="panel travel-card" key={check.id}><div className="panel-head"><div><span className="eyebrow">TRAVEL DATE · {check.travel_date}</span><h2>{check.agreed_terms.version_number ? `Agreement version ${check.agreed_terms.version_number}` : 'Agreement'}</h2></div><span className={`status-pill ${check.status}`}>{check.status.replace('_', ' ')}</span></div>{check.status === 'terms_changed' && <div className="alert warning-alert">{t.changed}<button className="text-action" onClick={onOpenAgreements}>Open agreement versions <ArrowRight size={14} /></button></div>}<div className="terms-grid"><Term label="Wage" value={`₹${check.agreed_terms.accepted_wage} / ${check.agreed_terms.wage_period}`} /><Term label={t.hours} value={check.agreed_terms.working_hours} /><Term label={t.location} value={check.agreed_terms.location} /><Term label={t.payment} value={check.agreed_terms.payment_terms} /><Term label={t.startDate} value={check.agreed_terms.start_date} /></div>{check.status === 'requested' && <button className="primary-button" onClick={() => onConfirm(check)}><CheckCircle2 size={16} />{t.reconfirm}</button>}{check.status === 'confirmed' && <p className="confirmed-note"><CheckCircle2 size={16} />Accepted terms match. The worker may record departure.</p>}</section>)}</div> }

function ComplaintsPage({ t, complaints, onRespond, onDownload }: any) { return <div className="content-page"><div className="section-heading"><div><div className="eyebrow">CASE MANAGEMENT</div><h1>{t.navComplaints}</h1><p>Review worker reports and reply with relevant information. Admins record the final decision.</p></div></div>{complaints.length === 0 ? <Empty title={t.noCases} /> : <div className="card-stack">{complaints.map((complaint: Complaint) => <ComplaintCard key={complaint.id} complaint={complaint} t={t} onRespond={onRespond} onDownload={onDownload} />)}</div>}</div> }

function ComplaintCard({ complaint, t, onRespond, onDownload }: any) { const [message, setMessage] = useState(''); const [sending, setSending] = useState(false); async function submit(e: FormEvent) { e.preventDefault(); setSending(true); await onRespond(complaint.id, message); setMessage(''); setSending(false) } return <section className="panel complaint-card"><div className="panel-head"><div><span className="eyebrow">{complaint.category.replace('_', ' ').toUpperCase()} · {new Date(complaint.created_at).toLocaleDateString()}</span><h2>{complaint.description}</h2></div><span className={`status-pill ${complaint.status}`}>{complaint.status.replace('_', ' ')}</span></div><div className="case-resources"><span>{complaint.evidence.length} evidence file(s)</span><span>{complaint.responses.length} response(s)</span></div>{complaint.evidence.map((evidence: Complaint['evidence'][number]) => <button type="button" className="evidence-link" key={evidence.id} onClick={() => onDownload(complaint.id, evidence.id, evidence.file_name)}><FileText size={15} />{evidence.file_name}<small>{Math.ceil(evidence.byte_size / 1024)} KB · download</small></button>)}{complaint.responses.map((response: Complaint['responses'][number]) => <blockquote key={response.id}>{response.message}<small>Contractor response · {new Date(response.created_at).toLocaleString()}</small></blockquote>)}{!['resolved', 'dismissed'].includes(complaint.status) && <form className="response-form" onSubmit={submit}><textarea required minLength={10} maxLength={10000} value={message} onChange={e => setMessage(e.target.value)} placeholder="Write a clear, factual response to the worker…" /><button className="primary-button" disabled={sending || !message.trim()}>{sending ? 'Sending…' : t.respond}<ArrowRight size={15} /></button></form>}</section> }

function ProfilePage({ t, draft, setDraft, profile, onSave }: any) { return <div className="content-page profile-page"><div className="section-heading"><div><div className="eyebrow">ACCOUNT DETAILS</div><h1>{t.navProfile}</h1><p>Keep your public contractor details current.</p></div></div><section className="panel profile-form-panel"><div className="profile-hero"><span className="avatar large-avatar">{profile.full_name.slice(0, 1)}</span><div><strong>{profile.business_name || profile.full_name}</strong><small>{profile.email}</small><span className={`status-pill ${profile.verification_status === 'verified' ? 'accepted' : 'pending'}`}>{profile.verification_status || 'unverified'}</span></div></div><form className="profile-form" onSubmit={onSave}><label>{t.name}<input required value={draft.full_name} onChange={e => setDraft({ ...draft, full_name: e.target.value })} /></label><label>{t.business}<input value={draft.business_name} onChange={e => setDraft({ ...draft, business_name: e.target.value })} /></label><label>{t.phone}<input type="tel" value={draft.phone} onChange={e => setDraft({ ...draft, phone: e.target.value })} /></label><label>{t.city}<input value={draft.city} onChange={e => setDraft({ ...draft, city: e.target.value })} /></label><label>{t.state}<input value={draft.state} onChange={e => setDraft({ ...draft, state: e.target.value })} /></label><div className="profile-email"><small>LOGIN EMAIL</small><strong>{profile.email}</strong><span>Email is managed by Supabase Auth.</span></div><button className="primary-button">{t.save}<Check size={16} /></button></form></section></div> }

function TrustSummary({ report }: any) { return <><div className="trust-result"><div className={`trust-score ${report.status === 'scored' ? '' : 'empty-score'}`}>{report.score ?? '—'}<small>{report.status === 'scored' ? '/ 100' : 'score'}</small></div><div><strong>{report.status === 'scored' ? `${report.confidence.level} confidence` : 'Insufficient verified data'}</strong><p>{report.confidence.data_coverage_pct}% evidence coverage · {report.confidence.evidence_count} evidence records</p></div></div><div className="trust-components">{report.components.map((component: any) => <div className="trust-component" key={component.key}><span>{component.label}<small>{component.weight_pct}% weight</small></span><div className="component-bar"><i style={{ width: `${component.score ?? 0}%` }} /></div><strong>{component.score ?? '—'}{component.score !== null ? '%' : ''}</strong></div>)}</div><div className="trust-reasons">{report.reasons.map((reason: string) => <p key={reason}>{reason}</p>)}</div>{report.components.map((component: any) => component.reasons.map((reason: string) => <div className="reason-line" key={component.key + reason}><CheckCircle2 size={13} />{reason}</div>))}</> }

function Term({ label, value }: { label: string; value: string }) { return <div className="term"><small>{label}</small><strong>{value}</strong></div> }
function Empty({ title }: { title: string }) { return <div className="empty-state"><span className="empty-icon"><BriefcaseBusiness size={22} /></span><strong>{title}</strong></div> }
function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) { return <div className="modal-backdrop" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}><section className="modal-card"><div className="panel-head"><h2>{title}</h2><button className="icon-button" onClick={onClose}><X size={18} /></button></div>{children}</section></div> }

export default App
