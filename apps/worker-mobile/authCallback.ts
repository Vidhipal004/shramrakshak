export type AuthCallbackParams = {
  code: string | null;
  tokenHash: string | null;
  type: string | null;
  accessToken: string | null;
  refreshToken: string | null;
  error: string | null;
};

export function isAuthCallbackUrl(callbackUrl: string): boolean {
  try {
    const parsed = new URL(callbackUrl);
    return parsed.protocol === 'exp:' && !!parsed.hostname && parsed.pathname === '/--/auth/callback';
  } catch {
    return false;
  }
}

export function parseAuthCallbackUrl(callbackUrl: string): AuthCallbackParams {
  if (!isAuthCallbackUrl(callbackUrl)) {
    throw new Error('This link is not a ShramRakshak Expo Go confirmation link.');
  }
  const parsed = new URL(callbackUrl);
  const fragment = new URLSearchParams(parsed.hash.replace(/^#/, ''));
  const value = (key: string) => parsed.searchParams.get(key) ?? fragment.get(key);
  const errorCode = value('error_code');
  const error = errorCode === 'otp_expired'
    ? 'This confirmation link has expired or was already used. Enter your email and choose Resend confirmation email for a fresh link.'
    : value('error_description') ?? errorCode ?? value('error');
  return {
    code: value('code'),
    tokenHash: value('token_hash'),
    type: value('type'),
    accessToken: value('access_token'),
    refreshToken: value('refresh_token'),
    error: error?.replace(/\+/g, ' ') ?? null,
  };
}

type AuthSessionClient = {
  exchangeCodeForSession: (code: string) => Promise<any>;
  verifyOtp: (params: { token_hash: string; type: 'signup' }) => Promise<any>;
  setSession: (tokens: { access_token: string; refresh_token: string }) => Promise<any>;
};

export async function establishAuthSession(callbackUrl: string, auth: AuthSessionClient) {
  const callback = parseAuthCallbackUrl(callbackUrl);
  if (callback.error) throw new Error(callback.error);

  const result = callback.code
    ? await auth.exchangeCodeForSession(callback.code)
    : callback.tokenHash && callback.type === 'signup'
      ? await auth.verifyOtp({ token_hash: callback.tokenHash, type: 'signup' })
    : callback.accessToken && callback.refreshToken
      ? await auth.setSession({ access_token: callback.accessToken, refresh_token: callback.refreshToken })
      : null;
  if (!result) throw new Error('The confirmation link is missing its session code. Request a new email and try again.');
  if (result.error) throw new Error(result.error.message);
  if (!result.data?.session) throw new Error('The confirmation link did not return a valid session. Request a new email and try again.');
  return result.data.session;
}
