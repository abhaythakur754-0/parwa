/** @type {import('jest').Config} */
const config = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  roots: ['<rootDir>/src'],
  testMatch: ['**/__tests__/**/*.test.{ts,tsx}', '**/*.test.{ts,tsx}', '**/*.spec.{ts,tsx}'],
  transform: {
    '^.+\\.[tj]sx?$': ['ts-jest', {
      tsconfig: {
        jsx: 'react-jsx',
        allowJs: true,
        esModuleInterop: true,
        module: 'commonjs',
        target: 'es2017',
        strict: false,
        moduleResolution: 'node16',
        rootDir: '..',
        ignoreDeprecations: '6.0',
      },
    }],
  },
  moduleNameMapper: {
    '^server-only$': '<rootDir>/src/test-mocks/server-only.ts',
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  transformIgnorePatterns: ['/node_modules/(?!jose/)'],
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  // This regression is authored with Vitest APIs and is executed by the dedicated Vitest step.
  testPathIgnorePatterns: ['/node_modules/', '<rootDir>/src/app/api/chat/__tests__/jarvis-fallback.test.ts'],
  testTimeout: 10000,
  verbose: true,
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/*.test.ts',
    '!src/**/*.spec.ts',
    '!src/__tests__/**',
  ],
};

module.exports = config;
