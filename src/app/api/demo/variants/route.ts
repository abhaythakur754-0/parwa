/**
 * PARWA Demo Variants API — GET /api/demo/variants
 *
 * Returns all available demo variants and industries for the $1 Demo Pack.
 */

import { NextResponse } from 'next/server';
import { DEMO_VARIANTS, DEMO_INDUSTRIES } from '@/lib/demo-store';

export async function GET() {
  try {
    return NextResponse.json({
      variants: DEMO_VARIANTS,
      industries: DEMO_INDUSTRIES.map((i) => i.id),
    });
  } catch (error) {
    return NextResponse.json(
      { error: { code: 'VARIANT_LIST_ERROR', message: 'Failed to load variants' } },
      { status: 500 },
    );
  }
}
