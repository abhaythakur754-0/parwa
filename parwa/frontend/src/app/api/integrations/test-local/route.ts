/**
 * PARWA Integrations — Local Test Connection
 *
 * POST /api/integrations/test-local
 *
 * Makes a real HTTP request to the third-party service to validate
 * the provided credentials. This runs server-side to avoid CORS issues.
 *
 * Supports the integration catalog's testConnection templates.
 */

import { NextRequest, NextResponse } from 'next/server';
import { INTEGRATION_CATALOG } from '@/lib/integration-catalog';

interface TestRequest {
  integration_type: string;
  auth_type: string;
  credentials: Record<string, string>;
  test_url?: string;
  test_method?: 'GET' | 'POST';
  test_headers?: Record<string, string>;
  success_check?: 'status_200' | 'json_ok_true' | 'status_200_or_201';
}

export async function POST(req: NextRequest) {
  let payload: TestRequest;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json(
      { success: false, message: 'Invalid request body' },
      { status: 400 }
    );
  }

  const { integration_type, credentials, test_url, test_method, test_headers, success_check } = payload;

  // Try to find a matching integration in the catalog for pre-built test
  const catalogEntry = INTEGRATION_CATALOG.find((i) => i.key === integration_type);

  let url = test_url || '';
  let method = test_method || 'GET';
  let headers: Record<string, string> = { ...test_headers };
  let check = success_check || 'status_200';

  if (catalogEntry?.testConnection) {
    const tc = catalogEntry.testConnection;
    url = tc.urlTemplate;
    method = tc.method;
    check = tc.successCheck;

    // Replace {field_name} placeholders in URL and headers
    for (const [key, value] of Object.entries(credentials)) {
      const placeholder = `{${key}}`;
      url = url.replace(placeholder, value);
      for (const [hKey, hVal] of Object.entries(headers)) {
        headers[hKey] = hVal.replace(placeholder, value);
      }
    }

    // Apply header template from catalog
    if (tc.headersTemplate) {
      for (const [hKey, hVal] of Object.entries(tc.headersTemplate)) {
        let resolved = hVal;
        for (const [key, value] of Object.entries(credentials)) {
          resolved = resolved.replace(`{${key}}`, value);
        }
        headers[hKey] = resolved;
      }
    }
  } else if (test_url) {
    // Custom integration — replace placeholders in provided URL/headers
    for (const [key, value] of Object.entries(credentials)) {
      const placeholder = `{${key}}`;
      url = url.replace(placeholder, value);
      for (const [hKey, hVal] of Object.entries(headers)) {
        headers[hKey] = hVal.replace(placeholder, value);
      }
    }
  } else {
    // No test URL and not in catalog — just validate that credentials are non-empty
    const hasValues = Object.values(credentials).some((v) => v.trim().length > 0);
    return NextResponse.json({
      success: hasValues,
      message: hasValues
        ? 'Credentials saved. Automated test not available for this platform — your integration will be verified when first used.'
        : 'No credentials provided.',
    });
  }

  if (!url) {
    return NextResponse.json({
      success: false,
      message: 'No test URL available for this integration type.',
    });
  }

  // Execute the test request
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000); // 10 second timeout

    const fetchOptions: RequestInit = {
      method,
      headers: Object.keys(headers).length > 0 ? headers : undefined,
      signal: controller.signal,
    };

    const res = await fetch(url, fetchOptions);
    clearTimeout(timeout);

    // Check success criteria
    let success = false;
    switch (check) {
      case 'status_200':
        success = res.status === 200;
        break;
      case 'status_200_or_201':
        success = res.status === 200 || res.status === 201;
        break;
      case 'json_ok_true':
        try {
          const data = await res.json();
          success = data.ok === true || data.success === true;
        } catch {
          success = false;
        }
        break;
      default:
        success = res.status >= 200 && res.status < 300;
    }

    return NextResponse.json({
      success,
      message: success
        ? `Successfully connected to ${integration_type}`
        : `Connection test returned status ${res.status}. Check your credentials.`,
      status: res.status,
    });
  } catch (err) {
    const message = err instanceof Error && err.name === 'AbortError'
      ? 'Connection timed out after 10 seconds.'
      : 'Could not reach the service. Check your credentials and try again.';

    return NextResponse.json({
      success: false,
      message,
    });
  }
}
