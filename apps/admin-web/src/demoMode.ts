const demoSessionKey = 'sr_admin_demo_guest'
const demoSessionVersion = '1'

/** Demo guest access is a local UI session and is available in every build. */
export function canUseDemo(_isDevelopmentBuild?: boolean): boolean {
  return true
}

export const demoSession = {
  start(): void {
    sessionStorage.setItem(demoSessionKey, demoSessionVersion)
  },
  active(): boolean {
    return sessionStorage.getItem(demoSessionKey) === demoSessionVersion
  },
  clear(): void {
    sessionStorage.removeItem(demoSessionKey)
  },
}

/** Demo screens must never call admin APIs with the real browser session. */
export function assertLiveApiAllowed(isDemoMode: boolean): void {
  if (isDemoMode) throw new Error('Demo mode uses local sample data only; privileged API requests are disabled.')
}
