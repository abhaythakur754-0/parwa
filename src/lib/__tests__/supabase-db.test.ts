import { SupabaseClient } from '../supabase-db';

describe('SupabaseClient URL configuration', () => {
  const originalUrl = process.env.SUPABASE_URL;
  const originalPublicUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const originalServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const originalFetch = global.fetch;

  beforeEach(() => {
    process.env.SUPABASE_SERVICE_ROLE_KEY = 'test-service-role-key';
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
      text: async () => '',
    } as Response);
  });

  afterEach(() => {
    if (originalUrl === undefined) delete process.env.SUPABASE_URL;
    else process.env.SUPABASE_URL = originalUrl;

    if (originalPublicUrl === undefined) delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    else process.env.NEXT_PUBLIC_SUPABASE_URL = originalPublicUrl;

    if (originalServiceKey === undefined) delete process.env.SUPABASE_SERVICE_ROLE_KEY;
    else process.env.SUPABASE_SERVICE_ROLE_KEY = originalServiceKey;

    global.fetch = originalFetch;
  });

  it('uses the server-side SUPABASE_URL when configured', async () => {
    process.env.SUPABASE_URL = 'https://server-project.supabase.co/';
    process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://public-project.supabase.co';

    await new SupabaseClient().from('users').select();

    expect(global.fetch).toHaveBeenCalledWith(
      'https://server-project.supabase.co/rest/v1/users?select=*',
      expect.any(Object)
    );
  });

  it('falls back to NEXT_PUBLIC_SUPABASE_URL for existing deployments', async () => {
    delete process.env.SUPABASE_URL;
    process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://legacy-project.supabase.co';

    await new SupabaseClient().from('users').select();

    expect(global.fetch).toHaveBeenCalledWith(
      'https://legacy-project.supabase.co/rest/v1/users?select=*',
      expect.any(Object)
    );
  });

  it('fails clearly when no Supabase URL is configured', async () => {
    delete process.env.SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;

    expect(() => new SupabaseClient().from('users').select()).toThrow(
      'SUPABASE_URL is not set'
    );
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('rejects malformed Supabase URLs', async () => {
    process.env.SUPABASE_URL = 'not-a-url';

    expect(() => new SupabaseClient().from('users').select()).toThrow(
      'Supabase URL must be a valid absolute URL'
    );
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
