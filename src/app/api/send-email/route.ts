import { NextRequest, NextResponse } from 'next/server';
import { sendEmail } from '@/lib/email';
import { requireAuth } from '@/lib/auth';

/**
 * M-28 FIX: Sanitize user-supplied content before passing to Brevo API.
 * Strips dangerous HTML tags and encodes control characters to prevent
 * XSS in email clients and HTML injection in email bodies.
 */
function sanitizeEmailContent(raw: string): string {
  // Remove script tags and their content (including event handlers)
  let sanitized = raw.replace(
    /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
    ''
  );
  // Remove inline event handlers (onclick, onerror, onload, etc.)
  sanitized = sanitized.replace(
    /\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi,
    ''
  );
  // Remove dangerous tags: iframe, object, embed, form, meta, link, base
  sanitized = sanitized.replace(
    /<(iframe|object|embed|form|meta|link|base)\b[^>]*\/?>/gi,
    ''
  );
  // Remove javascript: and data: URLs in href/src attributes
  sanitized = sanitized.replace(
    /(href|src)\s*=\s*["']?(javascript|data|vbscript):/gi,
    '$1="about:blank'
  );
  // Encode < and > that are not part of valid HTML tags to prevent injection
  // Keep basic formatting tags: p, br, div, span, a, b, i, u, ul, ol, li,
  // h1-h6, table, tr, td, th, strong, em, hr, img, blockquote
  const allowedTags = new Set([
    'p', 'br', 'div', 'span', 'a', 'b', 'i', 'u', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'tr', 'td', 'th',
    'strong', 'em', 'hr', 'img', 'blockquote', 'sup', 'sub',
  ]);
  sanitized = sanitized.replace(
    /<\/?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*\/?>/g,
    (match, tagName) => {
      const lower = tagName.toLowerCase();
      if (allowedTags.has(lower)) {
        return match;
      }
      // Replace disallowed tags with their escaped text content
      return match.replace(/[<>]/g, (ch) =>
        ch === '<' ? '&lt;' : '&gt;'
      );
    }
  );
  return sanitized;
}

export async function POST(request: NextRequest) {
  const authError = await requireAuth(request);
  if (authError) return authError;
  try {
    const body = await request.json();
    const { to, subject, htmlContent, textContent } = body;

    if (!to || !subject) {
      return NextResponse.json(
        { success: false, error: 'to and subject are required' },
        { status: 400 }
      );
    }

    // M-28 FIX: Sanitize all user-supplied content before Brevo API call
    const safeHtml = htmlContent
      ? sanitizeEmailContent(htmlContent)
      : sanitizeEmailContent(
          `<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;"><p>${textContent || subject}</p><hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" /><p style="color: #888; font-size: 12px;">Powered by PARWA AI Workforce Platform</p></div>`
        );

    const result = await sendEmail(to, subject, safeHtml);
    return NextResponse.json(result);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 }
    );
  }
}
