import assert from 'node:assert/strict';
import test from 'node:test';
import { establishAuthSession, isAuthCallbackUrl, parseAuthCallbackUrl } from '../authCallback.ts';

test('accepts an Expo Go callback URL with the runtime host and port', () => {
  const url = 'exp://192.168.1.44:8081/--/auth/callback?code=single-use-code';
  assert.equal(isAuthCallbackUrl(url), true);
  assert.deepEqual(parseAuthCallbackUrl(url), {
    code: 'single-use-code',
    tokenHash: null,
    type: null,
    accessToken: null,
    refreshToken: null,
    error: null,
  });
});

test('reads callback errors without logging or requiring token fields', () => {
  const url = 'exp://192.168.1.44:8081/--/auth/callback#error=access_denied&error_code=otp_expired';
  assert.deepEqual(parseAuthCallbackUrl(url), {
    code: null,
    tokenHash: null,
    type: null,
    accessToken: null,
    refreshToken: null,
    error: 'This confirmation link has expired or was already used. Enter your email and choose Resend confirmation email for a fresh link.',
  });
});

test('rejects redirects to the old localhost site URL', () => {
  assert.equal(isAuthCallbackUrl('http://localhost:3000/#code=anything'), false);
  assert.throws(() => parseAuthCallbackUrl('http://localhost:3000/#code=anything'));
});

test('exchanges the Supabase PKCE code and returns the secure session', async () => {
  const session = { access_token: 'test-access-token', refresh_token: 'test-refresh-token' };
  const calls: string[] = [];
  const auth = {
    exchangeCodeForSession: async (code: string) => {
      calls.push(code);
      return { data: { session }, error: null };
    },
    verifyOtp: async () => { throw new Error('Unexpected token hash verification'); },
    setSession: async () => {
      throw new Error('PKCE callback should exchange the code');
    },
  };

  const result = await establishAuthSession(
    'exp://192.168.1.44:8081/--/auth/callback?code=single-use-code',
    auth,
  );
  assert.deepEqual(calls, ['single-use-code']);
  assert.equal(result, session);
});

test('does not exchange expired or denied callbacks', async () => {
  let called = false;
  const auth = {
    exchangeCodeForSession: async () => { called = true; return { data: { session: null }, error: null }; },
    verifyOtp: async () => { called = true; return { data: { session: null }, error: null }; },
    setSession: async () => { called = true; return { data: { session: null }, error: null }; },
  };
  await assert.rejects(
    establishAuthSession(
      'exp://192.168.1.44:8081/--/auth/callback#error=access_denied&error_code=otp_expired',
      auth,
    ),
    /expired or was already used/,
  );
  assert.equal(called, false);
});

test('verifies a Supabase token_hash confirmation when supplied by the email template', async () => {
  let verified: { token_hash: string; type: 'signup' } | null = null;
  const session = { access_token: 'test-session', refresh_token: 'test-refresh' };
  const auth = {
    exchangeCodeForSession: async () => { throw new Error('Unexpected code exchange'); },
    verifyOtp: async (params: { token_hash: string; type: 'signup' }) => {
      verified = params;
      return { data: { session }, error: null };
    },
    setSession: async () => { throw new Error('Unexpected implicit session'); },
  };
  const result = await establishAuthSession(
    'exp://192.168.1.44:8081/--/auth/callback?token_hash=mock-token-hash&type=signup',
    auth,
  );
  assert.deepEqual(verified, { token_hash: 'mock-token-hash', type: 'signup' });
  assert.equal(result, session);
});
