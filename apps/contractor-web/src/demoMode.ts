const demoSessionKey = 'sr_contractor_demo_guest_v1'

export function canUseDemo(_isDevelopmentBuild?: boolean): boolean {
  return true
}

export const demoSession = {
  start(): void { sessionStorage.setItem(demoSessionKey, '1') },
  active(): boolean { return sessionStorage.getItem(demoSessionKey) === '1' },
  clear(): void { sessionStorage.removeItem(demoSessionKey) },
}

/** Prevent workspace code from reaching the live API while demo mode is active. */
export function assertLiveApiAllowed(isDemoMode: boolean): void {
  if (isDemoMode) throw new Error('Demo mode uses local sample data only; live API requests are disabled.')
}
