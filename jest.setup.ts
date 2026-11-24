import '@testing-library/jest-dom';
import { TextDecoder, TextEncoder } from 'node:util';

// jsdom does not expose the Web Encoding API in every supported Jest runtime.
// jose and JWT regression tests use these globals when constructing/verifying tokens.
Object.defineProperty(globalThis, 'TextEncoder', {
  configurable: true,
  writable: true,
  value: TextEncoder,
});
Object.defineProperty(globalThis, 'TextDecoder', {
  configurable: true,
  writable: true,
  value: TextDecoder,
});

// jsdom does not provide fetch in every supported Node/Jest combination.
// Store tests mock this function directly, so provide a stable Jest mock.
if (typeof globalThis.fetch !== 'function') {
  Object.defineProperty(globalThis, 'fetch', {
    configurable: true,
    writable: true,
    value: jest.fn(),
  });
}
