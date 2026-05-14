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
