// Jest Global Setup
// Configured for PARWA Frontend Testing (Day 2+3)

import '@testing-library/jest-dom';
import React from 'react';

// ── Mock localStorage with a working implementation ──────────────────
const localStorageStore: Record<string, string> = {};
const localStorageMock = {
  getItem: jest.fn((key: string) => localStorageStore[key] ?? null),
  setItem: jest.fn((key: string, value: string) => {
    localStorageStore[key] = value;
  }),
  removeItem: jest.fn((key: string) => {
    delete localStorageStore[key];
  }),
  clear: jest.fn(() => {
    Object.keys(localStorageStore).forEach((k) => delete localStorageStore[k]);
  }),
  get length() {
    return Object.keys(localStorageStore).length;
  },
  key: jest.fn((index: number) => Object.keys(localStorageStore)[index] ?? null),
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// ── Mock fetch ──────────────────────────────────────────────────────
global.fetch = jest.fn();

// ── Polyfill Node crypto for jsdom ──────────────────────────────────
const nodeCrypto = require('crypto');

// TextEncoder/TextDecoder polyfill for jsdom
if (typeof TextEncoder === 'undefined') {
  const { TextEncoder, TextDecoder } = require('util');
  global.TextEncoder = TextEncoder;
  global.TextDecoder = TextDecoder;
}

if (!globalThis.crypto?.subtle) {
  Object.defineProperty(globalThis, 'crypto', {
    value: {
      ...nodeCrypto,
      subtle: nodeCrypto.webcrypto?.subtle || {
        digest: jest.fn(),
        importKey: jest.fn(),
        sign: jest.fn(),
        verify: jest.fn(),
      },
      getRandomValues: (arr: any) => nodeCrypto.randomFillSync(arr),
    },
    writable: true,
  });
}

// ── Mock Next.js router ─────────────────────────────────────────────
jest.mock('next/navigation', () => ({
  useRouter() {
    return {
      push: jest.fn(),
      replace: jest.fn(),
      prefetch: jest.fn(),
      back: jest.fn(),
      pathname: '/',
      query: {},
      asPath: '/',
    };
  },
  useSearchParams() {
    return {
      get: jest.fn(),
    };
  },
  usePathname() {
    return '/';
  },
}));

// ── Mock next/link ──────────────────────────────────────────────────
jest.mock('next/link', () => {
  return function MockLink(props: Record<string, unknown>) {
    return React.createElement('a', { href: props.href as string }, props.children);
  };
});

// ── Mock next/server (ESM, not available in jsdom) ──────────────────
jest.mock('next/server', () => ({
  NextResponse: {
    json: (body: any, init?: any) => ({ body, ...init }),
    redirect: (url: string) => ({ redirect: url }),
  },
  NextRequest: class NextRequest {
    url: string;
    headers: Map<string, string>;
    constructor(url: string) {
      this.url = url;
      this.headers = new Map();
    }
  },
}));

// ── Mock jose (pure ESM, can't be transformed by Jest) ─────────────
jest.mock('jose', () => {
  const crypto = require('crypto');
  const SECRET = process.env.JWT_SECRET_KEY || 'dev-jwt-secret-key-change-in-prod-32c';
  const b64url = {
    encode: (str: string) => Buffer.from(str).toString('base64url'),
    decode: (str: string) => Buffer.from(str, 'base64url').toString(),
  };
  function sign(payload: Record<string, unknown>): string {
    const header = b64url.encode(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
    const body = b64url.encode(JSON.stringify(payload));
    const sig = crypto.createHmac('sha256', SECRET).update(`${header}.${body}`).digest('base64url');
    return `${header}.${body}.${sig}`;
  }
  function verify(token: string): Record<string, unknown> | null {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const [, body, sig] = parts;
    const expected = crypto.createHmac('sha256', SECRET).update(`${parts[0]}.${body}`).digest('base64url');
    if (sig !== expected) return null;
    try {
      const payload = JSON.parse(b64url.decode(body));
      if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) return null;
      return payload;
    } catch { return null; }
  }
  return {
    SignJWT: class SignJWT {
      private p: Record<string, unknown>; private h: Record<string, unknown> = {};
      constructor(p: Record<string, unknown>) { this.p = { ...p }; }
      setProtectedHeader(h: Record<string, unknown>) { this.h = h; return this; }
      setIssuedAt() { this.p = { ...this.p, iat: Math.floor(Date.now() / 1000) }; return this; }
      setIssuer(iss: string) { this.p = { ...this.p, iss }; return this; }
      setAudience(aud: string) { this.p = { ...this.p, aud }; return this; }
      setExpirationTime(exp: string) {
        const now = Math.floor(Date.now() / 1000);
        const m = exp.match(/^(-?\d+)(s|m|h|d)$/);
        if (m) { const u: Record<string, number> = { s:1, m:60, h:3600, d:86400 }; this.p = { ...this.p, exp: now + parseInt(m[1]) * (u[m[2]] || 1) }; }
        return this;
      }
      async sign(_s: any) { return sign(this.p); }
    },
    jwtVerify: async (token: string, _s: any) => {
      const payload = verify(token);
      if (!payload) throw new Error('Invalid token');
      return { payload, protectedHeader: { alg: 'HS256' } };
    },
    importSPKI: jest.fn().mockResolvedValue({}),
    jwtDecrypt: jest.fn().mockRejectedValue(new Error('Not implemented in mock')),
    compactDecrypt: jest.fn().mockRejectedValue(new Error('Not implemented in mock')),
  };
});

// ── Mock lucide-react icons ─────────────────────────────────────────
jest.mock('lucide-react', () => {
  return new Proxy({}, {
    get: function(_target: Record<string, unknown>, prop: string) {
      return (props: Record<string, unknown>) =>
        React.createElement('svg', { 'data-testid': `icon-${prop.toLowerCase()}`, ...props });
    },
  });
});

// ── Suppress console errors in tests ────────────────────────────────
const originalError = console.error;
beforeAll(() => {
  console.error = (...args: unknown[]) => {
    if (
      typeof args[0] === 'string' &&
      (args[0].includes('Warning: ReactDOM.render') ||
        args[0].includes('Not implemented: navigation') ||
        args[0].includes('act(') ||
        args[0].includes('Warning: An update to'))
    ) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});

// ── Reset mocks between tests ───────────────────────────────────────
afterEach(() => {
  jest.clearAllMocks();
});
