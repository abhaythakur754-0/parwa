/**
 * Test: JarvisAIEngine is wired as the final fallback in /api/chat
 *
 * Context:
 *   src/lib/jarvis-ai-engine.ts is a 900-line knowledge-based AI engine
 *   that generates contextual responses when external providers (ZAI,
 *   Google, Groq, Cerebras) are unavailable. Previously it was NOT wired
 *   into the chat API — getAIResponse() returned null when all 4 external
 *   providers failed, and the user got a 503 error.
 *
 *   This test confirms the fallback is now wired: when all external
 *   providers are unavailable, the JarvisAIEngine.generateResponse()
 *   method is invoked.
 *
 * Per CLAUDE.md Rule #5: "Never say it works unless you have PROVEN it works."
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { POST } from '../route';

// Mock the external AI providers to all return null (simulate unavailable).
vi.mock('z-ai-web-dev-sdk', () => ({
  default: class {
    static async create() {
      return {
        chat: {
          completions: {
            create: vi.fn().mockResolvedValue({
              choices: [{ message: { content: '' } }],
            }),
          },
        },
      };
    }
  },
}));

// Mock fetch for Google/Cerebras/Groq (all return null).
global.fetch = vi.fn().mockImplementation(async () => ({
  ok: false,
  json: async () => ({}),
  text: async () => '',
})) as any;

// Mock the JarvisAIEngine so we can assert it gets called.
const { generateResponseMock, ensureLoadedMock } = vi.hoisted(() => ({
  generateResponseMock: vi.fn().mockResolvedValue(
    'Thanks for your question! PARWA handles customer support across email, chat, SMS, and voice. Pricing starts at $999/mo for Mini PARWA.'
  ),
  ensureLoadedMock: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('@/lib/jarvis-ai-engine', () => ({
  JarvisAIEngine: {
    getInstance: () => ({
      ensureLoaded: ensureLoadedMock,
      generateResponse: generateResponseMock,
    }),
  },
}));

// Mock JWT verification (vi.hoisted so the mocks are available to the hoisted vi.mock calls).
const { verifyTokenMock, getAccessTokenFromCookiesMock } = vi.hoisted(() => ({
  verifyTokenMock: vi.fn().mockResolvedValue({ sub: 'user-1', company_id: 'company-1' }),
  getAccessTokenFromCookiesMock: vi.fn().mockReturnValue('fake-token'),
}));

vi.mock('@/lib/jwt', () => ({
  verifyToken: verifyTokenMock,
  getAccessTokenFromCookies: getAccessTokenFromCookiesMock,
}));

describe('POST /api/chat — JarvisAIEngine fallback', () => {
  beforeEach(() => {
    // mockReset clears both call history AND one-time return value queues.
    verifyTokenMock.mockReset();
    getAccessTokenFromCookiesMock.mockReset();
    generateResponseMock.mockReset();
    ensureLoadedMock.mockReset();
    // Restore default return values.
    verifyTokenMock.mockResolvedValue({ sub: 'user-1', company_id: 'company-1' });
    getAccessTokenFromCookiesMock.mockReturnValue('fake-token');
    generateResponseMock.mockResolvedValue(
      'Thanks for your question! PARWA handles customer support across email, chat, SMS, and voice. Pricing starts at $999/mo for Mini PARWA.'
    );
    ensureLoadedMock.mockResolvedValue(undefined);
  });

  it('calls JarvisAIEngine.generateResponse when all external providers fail', async () => {
    const req = new Request('http://localhost:3000/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer fake-token',
      },
      body: JSON.stringify({
        message: 'What does PARWA cost?',
        industry: 'ecommerce',
      }),
    });

    const response = await POST(req as any);
    const data = await response.json();

    // The fallback engine should have been called.
    expect(ensureLoadedMock).toHaveBeenCalledTimes(1);
    expect(generateResponseMock).toHaveBeenCalledTimes(1);

    // The response should be successful with the fallback text.
    expect(response.status).toBe(200);
    expect(data.status).toBe('success');
    expect(data.reply).toContain('PARWA');
    expect(data.reply.length).toBeGreaterThan(10);
  });

  it('returns the fallback text containing PARWA pricing keywords', async () => {
    const req = new Request('http://localhost:3000/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer fake-token',
      },
      body: JSON.stringify({
        message: 'how much',
      }),
    });

    const response = await POST(req as any);
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.status).toBe('success');
    // The mocked JarvisAIEngine response mentions PARWA + pricing.
    expect(data.reply.toLowerCase()).toMatch(/parwa|\$|price|plan/);
  });

  it('requires authentication', async () => {
    // Simulate no token in cookie OR header.
    getAccessTokenFromCookiesMock.mockReturnValueOnce(null);
    verifyTokenMock.mockResolvedValueOnce(null);

    const req = new Request('http://localhost:3000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'hi' }),
    });

    const response = await POST(req as any);
    expect(response.status).toBe(401);
  });

  it('rejects empty messages', async () => {
    // Explicitly ensure auth passes for this test.
    verifyTokenMock.mockResolvedValue({ sub: 'user-1', company_id: 'company-1' });
    getAccessTokenFromCookiesMock.mockReturnValue('fake-token');

    const req = new Request('http://localhost:3000/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer fake-token',
      },
      body: JSON.stringify({ message: '' }),
    });

    const response = await POST(req as any);
    expect(response.status).toBe(400);
  });
});
