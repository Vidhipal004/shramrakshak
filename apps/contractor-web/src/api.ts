const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const TOKEN_KEY = 'sr_contractor_access_token'

export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = tokenStore.get()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${API}${path}`, { ...options, headers })
  if (response.status === 204) return undefined as T
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    const message = Array.isArray(detail) ? detail.map((entry: { msg?: string }) => entry.msg).join(' · ') : detail
    throw new Error(message || `Request failed (${response.status})`)
  }
  return body as T
}

export type Profile = { id: string; email: string; full_name: string; role: string; phone: string | null; city: string | null; state: string | null; business_name: string | null; verification_status: string | null }
export type Job = { id: string; contractor_id: string; title: string; occupation: string; skill: string | null; description: string | null; location: string; latitude: number | null; longitude: number | null; wage_amount: string; wage_period: string; working_hours: string; payment_terms: string; start_date: string; status: string }
export type Application = { id: string; job_id: string; worker_id: string; worker_name: string; worker_city: string | null; message: string | null; status: string; created_at: string }
export type AgreementVersion = { id: string; agreement_id: string; version_number: number; accepted_wage: string; currency: string; wage_period: string; working_hours: string; location: string; payment_terms: string; start_date: string; proposed_by: string; status: string; proposed_at: string; worker_accepted_at: string | null; contractor_accepted_at: string | null }
export type Agreement = { id: string; application_id: string; job_id: string; worker_id: string; contractor_id: string; created_at: string; current_accepted_version: number | null; versions: AgreementVersion[] }
export type Travel = { id: string; agreement_id: string; agreement_version_id: string; travel_date: string; status: string; reconfirmed_terms: Record<string, unknown> | null; agreed_terms: AgreementVersion }
export type Complaint = { id: string; worker_id: string; contractor_id: string; category: string; description: string; status: string; created_at: string; responses: { id: string; message: string; author_id: string; created_at: string }[]; evidence: { id: string; file_name: string; byte_size: number; content_type: string; created_at: string }[] }

export const json = (value: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(value) })
