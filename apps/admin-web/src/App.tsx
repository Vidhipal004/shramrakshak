import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { BriefcaseBusiness, FileText, Languages, LayoutDashboard, LogOut, MapPin, RefreshCw, Search, ShieldCheck, Users, WalletCards, X } from 'lucide-react'
import { api, session, type Profile, type Contractor, type Complaint } from './api'
import { words, type Lang } from './i18n'
import { assertLiveApiAllowed, canUseDemo } from './demoMode'
import { createDemoSnapshot, demoAgreements, demoAttendance, type DemoJob, type DemoPayment, type DemoWorker } from './demoData'

type Page = 'overview' | 'workers' | 'contractors' | 'jobs' | 'payments' | 'cases'
type Score = { status: string; score: number | null; confidence: { level: string; data_coverage_pct: number; evidence_count: number }; components: { key: string; label: string; weight_pct: number; score: number | null; reasons: string[] }[]; reasons: string[] }

export default function App() {
  const [lang, setLang] = useState<Lang>('en'), t = words[lang]
  const [profile, setProfile] = useState<Profile | null>(null)
  const [demoMode, setDemoMode] = useState(false)
  const [page, setPage] = useState<Page>('overview')
  const [contractors, setContractors] = useState<Contractor[]>([])
  const [workers, setWorkers] = useState<DemoWorker[]>([])
  const [jobs, setJobs] = useState<DemoJob[]>([])
  const [payments, setPayments] = useState<DemoPayment[]>([])
  const [agreements, setAgreements] = useState(createDemoSnapshot().agreements)
  const [cases, setCases] = useState<Complaint[]>([])
  const [filter, setFilter] = useState(''), [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [success, setSuccess] = useState('')
  const [email, setEmail] = useState(''), [password, setPassword] = useState(''), [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState<Complaint | null>(null), [reviewStatus, setReviewStatus] = useState('under_review')
  const [outcome, setOutcome] = useState('inconclusive'), [notes, setNotes] = useState(''), [score, setScore] = useState<Score | null>(null)

  const workspaceApi = useCallback(<T,>(path: string, init?: RequestInit) => {
    assertLiveApiAllowed(demoMode)
    return api<T>(path, init)
  }, [demoMode])

  const load = useCallback(async () => {
    if (demoMode) return
    setLoading(true); setError('')
    try {
      const me = await workspaceApi<Profile>('/api/v1/auth/profile')
      if (me.role !== 'admin') throw new Error('Admin account required.')
      setProfile(me)
      const [cs, ps] = await Promise.all([
        workspaceApi<Contractor[]>('/api/v1/admin/contractors'),
        workspaceApi<Complaint[]>('/api/v1/admin/complaints' + (status ? '?status=' + status : '')),
      ])
      setContractors(cs); setCases(ps)
    } catch (e) { session.clear(); setProfile(null); setError((e as Error).message) }
    finally { setLoading(false) }
  }, [status, demoMode, workspaceApi])

  useEffect(() => { if (!demoMode && session.get()) void load(); else if (!demoMode) setLoading(false) }, [demoMode, load])

  async function login(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      const res = await api<{ access_token: string }>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
      session.set(res.access_token); await load()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  function startDemo() {
    if (!canUseDemo(import.meta.env.DEV)) return
    session.clear()
    const sample = createDemoSnapshot()
    setDemoMode(true); setProfile(sample.profile as Profile); setWorkers(sample.workers); setContractors(sample.contractors)
    setJobs(sample.jobs); setPayments(sample.payments); setAgreements(sample.agreements); setCases(sample.cases)
    setPage('overview'); setFilter(''); setStatus(''); setScore(null); setSelected(null); setNotes(''); setError('')
    setSuccess(lang === 'en' ? 'Demo admin workspace opened. All displayed records are samples.' : 'डेमो एडमिन कार्यक्षेत्र खुला। सभी रिकॉर्ड नमूना हैं।')
    setLoading(false)
  }

  async function verify(c: Contractor) {
    if (demoMode) {
      setContractors(current => current.map(item => item.id === c.id ? { ...item, verification_status: item.verification_status === 'verified' ? 'unverified' : 'verified' } : item))
      setSuccess(lang === 'en' ? 'Demo verification updated locally. No real profile changed.' : 'डेमो सत्यापन स्थानीय रूप से बदला। कोई वास्तविक प्रोफ़ाइल नहीं बदली।'); return
    }
    try { await workspaceApi(`/api/v1/admin/contractors/${c.id}/verification`, { method: 'PUT', body: JSON.stringify({ verification_status: c.verification_status === 'verified' ? 'unverified' : 'verified' }) }); setContractors(await workspaceApi<Contractor[]>('/api/v1/admin/contractors')) }
    catch (e) { setError((e as Error).message) }
  }

  function toggleDemoWorker(workerId: string) {
    if (!demoMode) return
    setWorkers(current => current.map(worker => worker.id === workerId ? { ...worker, status: worker.status === 'active' ? 'paused (demo)' : 'active' } : worker))
    setSuccess(lang === 'en' ? 'Demo worker status changed locally. No real account was affected.' : 'डेमो कर्मचारी की स्थिति स्थानीय रूप से बदली। कोई वास्तविक खाता प्रभावित नहीं हुआ।')
  }

  async function showScore(c: Contractor) {
    if (demoMode) {
      setScore({ status: 'insufficient_data', score: null, confidence: { level: 'low', data_coverage_pct: 0, evidence_count: 0 }, components: [], reasons: ['Sample contractor data is not verified evidence.'] }); setPage('contractors'); return
    }
    try { setScore(await workspaceApi(`/api/v1/contractors/${c.id}/jobtrust-score`)); setPage('contractors') }
    catch (e) { setError((e as Error).message) }
  }

  async function submitReview(e: FormEvent) {
    e.preventDefault(); if (!selected) return
    if (demoMode) {
      const caseId = selected.id
      const review = { status: reviewStatus, outcome: reviewStatus === 'under_review' ? null : outcome, notes: notes.trim(), created_at: new Date().toISOString() }
      setCases(current => current.map(item => item.id === caseId ? { ...item, status: reviewStatus, reviews: [...(item.reviews || []), review] } : item))
      setSelected(null); setNotes(''); setSuccess(lang === 'en' ? 'Demo dispute review saved locally. No real case changed.' : 'डेमो विवाद समीक्षा स्थानीय रूप से सहेजी। कोई वास्तविक मामला नहीं बदला।'); return
    }
    setBusy(true)
    try { await workspaceApi(`/api/v1/admin/complaints/${selected.id}/review`, { method: 'PATCH', body: JSON.stringify({ status: reviewStatus, outcome: reviewStatus === 'under_review' ? null : outcome, notes }) }); setSelected(null); setNotes(''); await load() }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  async function download(c: Complaint, id: string, name: string) {
    if (demoMode) { setSuccess(lang === 'en' ? 'Sample evidence is illustrative and has no downloadable file.' : 'नमूना साक्ष्य उदाहरण के लिए है; डाउनलोड फ़ाइल नहीं है।'); return }
    try { const res = await fetch((import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000') + `/api/v1/complaints/${c.id}/evidence/${id}`, { headers: { Authorization: `Bearer ${session.get()}` } }); if (!res.ok) throw new Error('Could not download evidence'); const blob = await res.blob(), url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url) }
    catch (e) { setError((e as Error).message) }
  }

  async function logout() {
    if (demoMode) { setDemoMode(false); setProfile(null); setWorkers([]); setContractors([]); setJobs([]); setPayments([]); setAgreements([]); setCases([]); setScore(null); setSuccess(''); setPage('overview'); setLoading(false); return }
    try { await api('/api/v1/auth/logout', { method: 'POST' }) } catch { /* clear the local session even if the server cannot reach */ }
    session.clear(); setProfile(null)
  }

  if (loading) return <div className="center"><b>SR</b><p>{t.load}</p></div>
  if (!profile) return <div className="auth"><form onSubmit={login}><div className="mark">S</div><small>SHRAMRAKSHAK · ADMIN</small><h1>{t.signin}</h1><p>Access is restricted to assigned admin accounts.</p>{error && <div className="error">{error}</div>}<label>{t.email}<input type="email" required value={email} onChange={e => setEmail(e.target.value)} /></label><label>{t.password}<input type="password" required value={password} onChange={e => setPassword(e.target.value)} /></label><button className="primary" disabled={busy}>{busy ? '…' : t.login}</button>{canUseDemo(import.meta.env.DEV) && <button type="button" className="demo-login" onClick={startDemo}>{lang === 'en' ? 'Continue as Demo Admin · DEVELOPMENT ONLY' : 'डेमो एडमिन के रूप में जारी रखें · केवल विकास के लिए'}</button>}<button type="button" className="lang" onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}><Languages size={15} />{t.language}</button></form></div>

  const navPages: Page[] = demoMode ? ['overview', 'workers', 'contractors', 'jobs', 'payments', 'cases'] : ['overview', 'contractors', 'cases']
  const openCases = cases.filter(c => !['resolved', 'dismissed'].includes(c.status)).length
  const pageLabel = t[page] || page
  const setDemoMessage = () => setSuccess(lang === 'en' ? 'Demo-only action: this change is local and is not real.' : 'केवल डेमो कार्रवाई: यह बदलाव स्थानीय है और वास्तविक नहीं है।')

  return <div className="shell">
    <aside><div className="brand"><span className="mark">S</span><div><strong>{t.brand}</strong><small>{t.role}</small></div></div><div className="label">{lang === 'en' ? 'ADMINISTRATION' : 'प्रशासन'}</div>
      {navPages.map((p, i) => <button className={page === p ? 'active' : ''} onClick={() => setPage(p)} key={p}>{p === 'overview' ? <LayoutDashboard /> : p === 'workers' ? <Users /> : p === 'contractors' ? <ShieldCheck /> : p === 'jobs' ? <BriefcaseBusiness /> : p === 'payments' ? <WalletCards /> : <FileText />}{t[p]}</button>)}
      <div className="aside-foot"><span>{profile.full_name}</span><small>{profile.email}</small>{demoMode && <small className="demo-role">{lang === 'en' ? 'DEMO ROLE · NO BACKEND ACCESS' : 'डेमो भूमिका · बैकएंड पहुँच नहीं'}</small>}<button onClick={() => void logout()}><LogOut size={16} />{demoMode ? t.exitDemo : t.logout}</button></div>
    </aside>
    <main><header><span>{t.role} / <b>{pageLabel}</b></span><div><button onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}><Languages size={16} />{t.language}</button><button aria-label={t.refresh} onClick={() => demoMode ? setDemoMessage() : void load()}><RefreshCw size={16} /></button></div></header>
      <section className="content">{demoMode && <div className="demo-banner"><ShieldCheck size={17} /><strong>{lang === 'en' ? 'DEMO ADMIN · SAMPLE DATA ONLY' : 'डेमो एडमिन · केवल नमूना डेटा'}</strong><span>{lang === 'en' ? 'All changes stay in this browser. No real users or records are accessed.' : 'सभी बदलाव इसी ब्राउज़र में रहेंगे। वास्तविक उपयोगकर्ता या रिकॉर्ड नहीं खुलते।'}</span></div>}{error && <div className="error">{error}<button onClick={() => setError('')}><X size={15} /></button></div>}{success && <div className="success-banner">{success}<button onClick={() => setSuccess('')}><X size={14} /></button></div>}
        {page === 'overview' && <><div className="intro"><div><small>SHRAMRAKSHAK · TRUST OPERATIONS</small><h1>{t.overview}</h1><p>{demoMode ? (lang === 'en' ? 'Sample platform analytics for the local demo workspace.' : 'स्थानीय डेमो कार्यक्षेत्र के नमूना प्लेटफ़ॉर्म आँकड़े।') : t.description}</p></div></div><div className="stats">{demoMode ? <><div><Users /><span>{t.workers}</span><b>{workers.length}</b></div><div><ShieldCheck /><span>{t.contractors}</span><b>{contractors.length}</b></div><div><BriefcaseBusiness /><span>{t.jobs}</span><b>{jobs.length}</b></div><div><WalletCards /><span>{t.pendingPayments}</span><b>{payments.filter(p => p.status !== 'paid').length}</b></div></> : <><div><Users /><span>{t.contractors}</span><b>{contractors.length}</b></div><div><FileText /><span>{t.cases}</span><b>{openCases}</b></div><div><ShieldCheck /><span>{lang === 'en' ? 'Verified' : 'सत्यापित'}</span><b>{contractors.filter(c => c.verification_status === 'verified').length}</b></div><div><FileText /><span>{lang === 'en' ? 'Awaiting review' : 'समीक्षा लंबित'}</span><b>{openCases}</b></div></>}</div><div className="panel intro-panel"><ShieldCheck /><div><h2>{t.workers}</h2><p>{demoMode ? t.demoAnalytics : t.description}</p></div><button onClick={() => setPage('cases')}>{t.cases} →</button></div>{demoMode && <><div className="demo-metric-note">{lang === 'en' ? `Sample dispute queue: ${openCases} open · ${cases.length} total. No production analytics are queried.` : `नमूना विवाद सूची: ${openCases} खुले · कुल ${cases.length}। उत्पादन आँकड़े नहीं पढ़े जाते।`}</div><DemoRecords language={lang} /></>}</>}
        {page === 'workers' && demoMode && <WorkersPage rows={workers} language={lang} filter={filter} setFilter={setFilter} onToggle={toggleDemoWorker} />}
        {page === 'contractors' && <ContractorsPage t={t} rows={contractors} filter={filter} setFilter={setFilter} score={score} setScore={setScore} onScore={showScore} onVerify={verify} demoMode={demoMode} />}
        {page === 'jobs' && demoMode && <JobsPage rows={jobs} language={lang} />}
        {page === 'payments' && demoMode && <PaymentsPage rows={payments} language={lang} />}
        {page === 'cases' && <CasesPage t={t} cases={cases} status={status} setStatus={setStatus} onReview={(c: Complaint) => { setSelected(c); setReviewStatus('under_review'); setOutcome('inconclusive') }} onDownload={download} demoMode={demoMode} />}
      </section>
    </main>
    {selected && <div className="backdrop" onMouseDown={e => { if (e.target === e.currentTarget) setSelected(null) }}><form className="modal" onSubmit={submitReview}><header><h2>{t.review}</h2><button type="button" onClick={() => setSelected(null)}>×</button></header>{demoMode && <p className="modal-demo-note">{lang === 'en' ? 'Demo-only review. This will not affect a real dispute.' : 'केवल डेमो समीक्षा। इससे वास्तविक विवाद प्रभावित नहीं होगा।'}</p>}<p>{selected.description}</p><label>{t.status}<select value={reviewStatus} onChange={e => setReviewStatus(e.target.value)}><option value="under_review">{t.under}</option><option value="resolved">{t.resolved}</option><option value="dismissed">{t.dismissed}</option></select></label>{reviewStatus !== 'under_review' && <label>{t.outcome}<select value={outcome} onChange={e => setOutcome(e.target.value)}><option value="worker_upheld">{t.worker}</option><option value="contractor_upheld">{t.contractor}</option><option value="inconclusive">{t.inconclusive}</option></select></label>}<label>{t.notes}<textarea minLength={5} required value={notes} onChange={e => setNotes(e.target.value)} /></label><button disabled={busy}>{busy ? '…' : demoMode ? t.saveDemo : t.save}</button></form></div>}
  </div>
}

function WorkersPage({ rows, language, filter, setFilter, onToggle }: { rows: DemoWorker[]; language: Lang; filter: string; setFilter: (value: string) => void; onToggle: (workerId: string) => void }) {
  const en = language === 'en'
  return <><div className="intro"><div><small>{en ? 'SAMPLE DIRECTORY' : 'नमूना निर्देशिका'}</small><h1>{en ? 'Workers' : 'कर्मचारी'}</h1><p>{en ? 'Mock worker records for interface review only.' : 'केवल इंटरफ़ेस समीक्षा के लिए नमूना कर्मचारी रिकॉर्ड।'}</p></div><label className="search"><Search /><input value={filter} onChange={event => setFilter(event.target.value)} placeholder={en ? 'Search sample workers' : 'नमूना कर्मचारी खोजें'} /></label></div><div className="table panel">{rows.filter(row => `${row.full_name} ${row.city} ${row.skill}`.toLowerCase().includes(filter.toLowerCase())).map(row => <article key={row.id}><span className="avatar">{row.full_name[0]}</span><div className="identity"><b>{row.full_name}</b><small>{row.email} · {row.skill}</small></div><div className="place"><MapPin />{row.city}</div><span className={`pill ${row.status === 'active' ? 'verified' : 'unverified'}`}>{row.status}</span><span className="mock-label">{en ? 'SAMPLE' : 'नमूना'}</span><button onClick={() => onToggle(row.id)}>{row.status === 'active' ? (en ? 'Pause demo' : 'डेमो रोकें') : (en ? 'Set active (demo)' : 'डेमो सक्रिय करें')}</button></article>)}</div></>
}

function DemoRecords({ language }: { language: Lang }) {
  const en = language === 'en'
  return <div className="demo-records">
    <section className="panel"><div className="record-head"><h2>{en ? 'Wage agreements · sample' : 'वेतन समझौते · नमूना'}</h2><span className="mock-label">{en ? 'DEMO ONLY' : 'केवल डेमो'}</span></div>{demoAgreements.map(item => <article className="record-line" key={item.id}><strong>{item.worker} · {item.contractor}</strong><span>₹{item.wage}/{item.period} · {item.hours} · v{item.version}</span><span className="pill submitted">{item.status}</span></article>)}</section>
    <section className="panel"><div className="record-head"><h2>{en ? 'Attendance · sample' : 'उपस्थिति · नमूना'}</h2><span className="mock-label">{en ? 'DEMO ONLY' : 'केवल डेमो'}</span></div>{demoAttendance.map(item => <article className="record-line" key={item.id}><strong>{item.worker} · {item.job}</strong><span>{item.date} · {item.hours}h</span><span className="pill verified">{item.status}</span></article>)}</section>
  </div>
}

function ContractorsPage({ t, rows, filter, setFilter, score, setScore, onScore, onVerify, demoMode }: any) {
  return <><div className="intro"><div><small>IDENTITY & EVIDENCE</small><h1>{t.contractors}</h1><p>{demoMode ? t.demoRecords : 'Verification is an identity signal; JobTrust shows evidence coverage and missing data.'}</p></div><label className="search"><Search /><input placeholder={t.search} value={filter} onChange={e => setFilter(e.target.value)} /></label></div>{score && <div className="panel score"><button className="close" onClick={() => setScore(null)}>×</button><div><small>{t.trust}</small><h2>{score.score ?? '—'} <small>/100</small></h2><p>{score.status === 'scored' ? `${score.confidence.level} confidence · ${score.confidence.data_coverage_pct}% coverage` : t.insufficient}</p></div><div className="components">{score.components.map((x: any) => <div key={x.key}><span>{x.label}<small>{x.weight_pct}%</small></span><i><b style={{ width: `${x.score ?? 0}%` }} /></i><strong>{x.score ?? '—'}</strong></div>)}</div>{score.reasons.map((r: string) => <small key={r}>{r}<br /></small>)}</div>}<div className="table panel">{rows.filter((c: Contractor) => `${c.full_name} ${c.business_name || ''} ${c.city || ''}`.toLowerCase().includes(filter.toLowerCase())).map((c: Contractor) => <article key={c.id}><span className="avatar">{c.full_name[0]}</span><div className="identity"><b>{c.business_name || c.full_name}</b><small>{c.full_name} · {c.email}</small></div><div className="place"><MapPin />{[c.city, c.state].filter(Boolean).join(', ') || '—'}</div><span className={`pill ${c.verification_status}`}>{c.verification_status}</span>{demoMode && <span className="mock-label">SAMPLE</span>}<button onClick={() => void onScore(c)}>{t.trust}</button><button className="verify" onClick={() => void onVerify(c)}>{c.verification_status === 'verified' ? t.unverify : t.verify}</button></article>)}{rows.length === 0 && <p className="empty">{t.noContractors}</p>}</div></>
}

function JobsPage({ rows, language }: { rows: DemoJob[]; language: Lang }) { const en = language === 'en'; return <><div className="intro"><div><small>{en ? 'SAMPLE MONITORING' : 'नमूना निगरानी'}</small><h1>{en ? 'Job monitoring' : 'काम की निगरानी'}</h1><p>{en ? 'Illustrative listings and application counts. No production jobs are queried.' : 'उदाहरण काम और आवेदन संख्या। उत्पादन के काम नहीं पढ़े जाते।'}</p></div></div><div className="table panel">{rows.map(row => <article key={row.id}><span className="avatar"><BriefcaseBusiness size={16} /></span><div className="identity"><b>{row.title}</b><small>{row.contractor} · ₹{row.wage}/{row.period}</small></div><div className="place"><MapPin />{row.location}</div><span>{row.applicants} {en ? 'applicants' : 'आवेदन'}</span><span className={`pill ${row.status}`}>{row.status}</span><span className="mock-label">{en ? 'SAMPLE' : 'नमूना'}</span></article>)}</div></> }

function PaymentsPage({ rows, language }: { rows: DemoPayment[]; language: Lang }) { const en = language === 'en'; return <><div className="intro"><div><small>{en ? 'SAMPLE LEDGER' : 'नमूना लेजर'}</small><h1>{en ? 'Payment monitoring' : 'भुगतान निगरानी'}</h1><p>{en ? 'Sample payment statuses only. No transfers or ledger records are real.' : 'केवल नमूना भुगतान स्थिति। कोई वास्तविक हस्तांतरण या लेजर रिकॉर्ड नहीं।'}</p></div></div><div className="table panel">{rows.map(row => <article key={row.id}><span className="avatar"><WalletCards size={16} /></span><div className="identity"><b>{row.worker} · ₹{row.amount}</b><small>{row.job} · {row.contractor}</small></div><div className="place">{row.date}</div><span>{row.method}</span><span className={`pill ${row.status === 'paid' ? 'verified' : 'submitted'}`}>{row.status}</span><span className="mock-label">{en ? 'SAMPLE' : 'नमूना'}</span></article>)}</div></> }

function CasesPage({ t, cases, status, setStatus, onReview, onDownload, demoMode }: any) {
  const visible = cases.filter((c: Complaint) => !status || c.status === status)
  return <><div className="intro"><div><small>WORKER PROTECTION</small><h1>{t.cases}</h1><p>{demoMode ? t.demoRecords : 'Evidence and contractor responses remain attached to each case.'}</p></div><select value={status} onChange={e => setStatus(e.target.value)}><option value="">{t.all}</option><option value="submitted">Submitted</option><option value="contractor_responded">Contractor responded</option><option value="under_review">{t.under}</option><option value="resolved">{t.resolved}</option><option value="dismissed">{t.dismissed}</option></select></div><div className="cases">{visible.map((c: Complaint) => <article className="panel case" key={c.id}><div className="case-head"><span className="pill">{c.category.replace('_', ' ')}</span><span className={`pill ${c.status}`}>{c.status.replace('_', ' ')}</span><small>{new Date(c.created_at).toLocaleDateString()}</small>{demoMode && <span className="mock-label">SAMPLE</span>}</div><h2>{c.description}</h2><p>{c.evidence.length} evidence files · {c.responses.length} contractor responses</p><div className="attachments">{c.evidence.map(e => <button key={e.id} onClick={() => void onDownload(c, e.id, e.file_name)}><FileText size={15} />{e.file_name}</button>)}</div>{c.responses.map(r => <blockquote key={r.id}>{r.message}<small>Contractor response · {new Date(r.created_at).toLocaleString()}</small></blockquote>)}{c.reviews?.map((r, i) => <blockquote key={i}>{r.notes}<small>Admin review · {r.outcome || r.status}</small></blockquote>)}{!['resolved', 'dismissed'].includes(c.status) && <button className="primary" onClick={() => onReview(c)}>{t.review}</button>}</article>)}{visible.length === 0 && <div className="panel empty">{t.noCases}</div>}</div></>
}
