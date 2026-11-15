import * as Linking from 'expo-linking';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { establishAuthSession, isAuthCallbackUrl } from './authCallback';

export { isAuthCallbackUrl } from './authCallback';

export const AUTH_CALLBACK_URL = Linking.createURL('auth/callback');
const SUPABASE_STORAGE_KEY = 'sr-supabase-auth';
const PKCE_VERIFIER_KEY = `${SUPABASE_STORAGE_KEY}-code-verifier`;

const secureStorage = {
  getItem: (key: string) => SecureStore.getItemAsync(key),
  setItem: (key: string, value: string) => SecureStore.setItemAsync(key, value),
  removeItem: (key: string) => SecureStore.deleteItemAsync(key),
};

let client: SupabaseClient | undefined;

export function getSupabaseClient(): SupabaseClient {
  if (client) return client;
  const url = process.env.EXPO_PUBLIC_SUPABASE_URL;
  const key = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) throw new Error('Email verification is not configured. Set the Supabase URL and public key in the mobile environment.');
  client = createClient(url, key, {
    auth: {
      storage: secureStorage,
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: false,
      flowType: 'pkce',
      storageKey: SUPABASE_STORAGE_KEY,
    },
  });
  return client;
}

export async function prepareEmailSignupPKCE(): Promise<string> {
  const verifier = Array.from(Crypto.getRandomBytes(32), (byte) => byte.toString(16).padStart(2, '0')).join('');
  const digest = await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, verifier, {
    encoding: Crypto.CryptoEncoding.BASE64,
  });
  await SecureStore.setItemAsync(PKCE_VERIFIER_KEY, verifier);
  return digest.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export async function clearEmailSignupPKCE(): Promise<void> {
  await SecureStore.deleteItemAsync(PKCE_VERIFIER_KEY);
}

export async function completeEmailCallback(callbackUrl: string) {
  const supabase = getSupabaseClient();
  return establishAuthSession(callbackUrl, supabase.auth);
}
