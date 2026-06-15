/**
 * Empty stub for @paddle/paddle-js
 *
 * This module replaces the real @paddle/paddle-js npm package in the
 * Turbopack/Webpack bundle. The real package has TDZ errors when bundled
 * by Next.js ("Cannot access 'ea' before initialization").
 *
 * We load Paddle.js from CDN instead (see src/lib/paddle.ts).
 * This stub ensures that if any code somehow statically imports
 * @paddle/paddle-js, it won't crash the bundle.
 */

export function initializePaddle() {
  console.warn(
    '[paddle] Stub: @paddle/paddle-js is not bundled. ' +
    'Paddle.js is loaded from CDN. See src/lib/paddle.ts.'
  );
  return Promise.resolve(undefined);
}

export const Paddle = undefined;

export default { initializePaddle, Paddle };
