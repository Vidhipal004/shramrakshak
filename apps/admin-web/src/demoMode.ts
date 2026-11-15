export function canUseDemo(isDevelopmentBuild: boolean): boolean {
  return isDevelopmentBuild
}

/** Demo screens must never call admin APIs with the real browser session. */
export function assertLiveApiAllowed(isDemoMode: boolean): void {
  if (isDemoMode) throw new Error('Demo mode uses local sample data only; privileged API requests are disabled.')
}
