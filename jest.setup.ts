import '@testing-library/jest-dom';

// jsdom does not provide fetch in every supported Node/Jest combination.
// Store tests mock this function directly, so provide a stable Jest mock.
if (typeof globalThis.fetch !== 'function') {
  Object.defineProperty(globalThis, 'fetch', {
    configurable: true,
    writable: true,
    value: jest.fn(),
  });
}
