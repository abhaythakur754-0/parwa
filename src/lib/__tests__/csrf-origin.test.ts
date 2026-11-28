import { describe, expect, it } from 'vitest';
import { isValidCookieAuthOrigin } from '../csrf-origin';

describe('cookie-auth CSRF origin validation', () => {
  const requestUrl = 'https://parwa.vercel.app/api/chat';

  it('accepts the exact same origin', () => {
    expect(isValidCookieAuthOrigin(requestUrl, 'https://parwa.vercel.app', null)).toBe(true);
  });

  it('rejects a hostile sibling Vercel subdomain', () => {
    expect(isValidCookieAuthOrigin(requestUrl, 'https://attacker.vercel.app', null)).toBe(false);
  });

  it('accepts a same-origin Referer when Origin is absent', () => {
    expect(isValidCookieAuthOrigin(requestUrl, null, 'https://parwa.vercel.app/settings/profile')).toBe(true);
  });

  it('rejects missing or malformed origin metadata', () => {
    expect(isValidCookieAuthOrigin(requestUrl, null, null)).toBe(false);
    expect(isValidCookieAuthOrigin(requestUrl, 'null', null)).toBe(false);
    expect(isValidCookieAuthOrigin(requestUrl, 'not a url', null)).toBe(false);
  });

  it('rejects lookalike hostnames and different ports', () => {
    expect(isValidCookieAuthOrigin(requestUrl, 'https://parwa.vercel.app.attacker.com', null)).toBe(false);
    expect(isValidCookieAuthOrigin(requestUrl, 'https://parwa.vercel.app:444', null)).toBe(false);
  });
});
