import { isLegacyJarvisGuestFlowEnabled } from '../legacy-guest-guard';

describe('isLegacyJarvisGuestFlowEnabled', () => {
  it('disables process-local guest sessions in production', () => {
    expect(isLegacyJarvisGuestFlowEnabled('production')).toBe(false);
  });

  it('keeps the legacy guest experience available in local development', () => {
    expect(isLegacyJarvisGuestFlowEnabled('development')).toBe(true);
  });

  it('keeps the legacy guest experience available in test environments', () => {
    expect(isLegacyJarvisGuestFlowEnabled('test')).toBe(true);
  });
});
