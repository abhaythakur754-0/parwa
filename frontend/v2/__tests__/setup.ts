/**
 * PARWA v2 - Test Setup
 *
 * Global test configuration and setup.
 */

import "@testing-library/jest-dom";
import { vi } from "vitest";

// Mock IntersectionObserver
class MockIntersectionObserver {
  observe = vi.fn();
  disconnect = vi.fn();
  unobserve = vi.fn();
}

Object.defineProperty(window, "IntersectionObserver", {
  writable: true,
  configurable: true,
  value: MockIntersectionObserver,
});

// Mock ResizeObserver
class MockResizeObserver {
  observe = vi.fn();
  disconnect = vi.fn();
  unobserve = vi.fn();
}

Object.defineProperty(window, "ResizeObserver", {
  writable: true,
  configurable: true,
  value: MockResizeObserver,
});

// Mock matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock IndexedDB
const mockIndexedDB = {
  open: vi.fn().mockReturnValue({
    result: {
      createObjectStore: vi.fn(),
      transaction: vi.fn().mockReturnValue({
        objectStore: vi.fn().mockReturnValue({
          add: vi.fn(),
          get: vi.fn(),
          put: vi.fn(),
          delete: vi.fn(),
          getAll: vi.fn(),
          clear: vi.fn(),
        }),
      }),
    },
    onsuccess: null,
    onerror: null,
  }),
};

Object.defineProperty(window, "indexedDB", {
  value: mockIndexedDB,
});

// Mock Service Worker
Object.defineProperty(navigator, "serviceWorker", {
  value: {
    register: vi.fn().mockResolvedValue({
      active: {},
      waiting: null,
      installing: null,
    }),
    ready: Promise.resolve({
      showNotification: vi.fn(),
      getNotifications: vi.fn().mockResolvedValue([]),
      update: vi.fn(),
    }),
    controller: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  },
});

// Mock Notification API
Object.defineProperty(window, "Notification", {
  value: class MockNotification {
    static permission = "default";
    static requestPermission = vi.fn().mockResolvedValue("granted");
    constructor(title, options) {
      this.title = title;
      this.options = options;
    }
    close = vi.fn();
  },
  writable: true,
});

// Mock fetch
global.fetch = vi.fn();

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
Object.defineProperty(window, "localStorage", { value: localStorageMock });

// Mock sessionStorage
const sessionStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
Object.defineProperty(window, "sessionStorage", { value: sessionStorageMock });

// Clean up after each test
afterEach(() => {
  vi.clearAllMocks();
  localStorageMock.getItem.mockReset();
  localStorageMock.setItem.mockReset();
  localStorageMock.removeItem.mockReset();
  localStorageMock.clear.mockReset();
});
