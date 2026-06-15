/**
 * PARWA Paddle Price IDs — Pure Data Module
 *
 * Extracted from paddle.ts so components can import price IDs
 * WITHOUT triggering evaluation of the @paddle/paddle-js module.
 *
 * This is the ONLY safe import for components that need price IDs
 * but don't call Paddle functions directly.
 */

export const VARIANT_PRICE_IDS: Record<string, string> = {
  mini_parwa: 'pri_01ksamxdpw0kmh3qj9p1gdzgms',  // Active: Starter $999/mo
  parwa: 'pri_01ksamxf31qkmbekat2cgmqyef',        // Active: Growth $2,499/mo
  parwa_high: 'pri_01ksamxed6jkm7g7xz687ax3zy',    // Active: High $3,999/mo
};
