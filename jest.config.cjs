const nextJest = require('next/jest');

const createJestConfig = nextJest({
  dir: './',
});

/** @type {import('jest').Config} */
const config = {
  coverageProvider: 'v8',
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  testPathIgnorePatterns: ['<rootDir>/node_modules/', '<rootDir>/.next/'],
  transform: {
    '^.+\\.(ts|tsx)$': ['ts-jest', { tsconfig: '<rootDir>/tsconfig.json' }],
  },
  // Coverage configuration
  collectCoverageFrom: [
    'src/lib/**/*.ts',
    'src/hooks/**/*.ts',
    'src/components/**/*.{ts,tsx}',
    'src/contexts/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/components/ui/**',   // shadcn/ui — not our code
    '!src/types/**',
  ],
  coverageThreshold: {
    global: {
      branches: 10,
      functions: 30,
      lines: 10,
      statements: 10,
    },
  },
  // Test file patterns
  testMatch: [
    '<rootDir>/src/**/__tests__/**/*.{test,spec}.{ts,tsx}',
    '<rootDir>/src/**/*.{test,spec}.{ts,tsx}',
  ],
  // Max workers for parallel test execution
  maxWorkers: '50%',
};

module.exports = createJestConfig(config);
