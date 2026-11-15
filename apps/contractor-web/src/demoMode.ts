export function canUseDemo(isDevelopmentBuild: boolean): boolean {
  return isDevelopmentBuild
}

/** Prevent workspace code from reaching the live API while demo mode is active. */
export function assertLiveApiAllowed(isDemoMode: boolean): void {
  if (isDemoMode) throw new Error('Demo mode uses local sample data only; live API requests are disabled.')
}
