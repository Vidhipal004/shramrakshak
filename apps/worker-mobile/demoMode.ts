/** Demo access is a local UI mode only; it never authenticates to the API. */
export function canUseDemo(isDevelopmentBuild: boolean): boolean {
  return isDevelopmentBuild;
}

export function assertNotDemoRequest(isDemoMode: boolean): void {
  if (isDemoMode) {
    throw new Error('Demo mode uses sample data and cannot access backend APIs.');
  }
}
