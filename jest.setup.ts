import '@testing-library/jest-dom';
import { webcrypto } from 'node:crypto';
import { TextDecoder, TextEncoder } from 'node:util';

Object.assign(globalThis, { crypto: webcrypto, TextDecoder, TextEncoder });

// JSDOM does not provide Node's fetch API. Tests replace this spy with the
// response they need; the default prevents unrelated store tests from
// failing with ReferenceError when their best-effort API sync runs.
global.fetch = jest.fn();
