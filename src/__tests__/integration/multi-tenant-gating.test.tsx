/**
 * Integration coverage for the current two-tier model.
 *
 * Both tiers share the same AI capabilities. High changes capacity limits;
 * legacy tier names are normalized to the current Parwa tier.
 */
import React from 'react';
import { act, render, renderHook, screen } from '@testing-library/react';
import { useVariantStore } from '@/lib/variant-store';
import { useVariant } from '@/hooks/useVariant';
import { LockedFeature, TierBadge, InlineLock } from '@/components/LockedFeature';
import { normalizeTier } from '@/lib/pricing-config';

describe('Integration: current Parwa tier model', () => {
  beforeEach(() => {
    useVariantStore.getState().reset();
    // Avoid network side effects: this suite exercises store → hook → UI wiring.
    useVariantStore.setState({
      fetchTier: jest.fn().mockResolvedValue(undefined),
      fetchUsage: jest.fn().mockResolvedValue(undefined),
    });
  });

  it('keeps AI capabilities consistent across Parwa and High', () => {
    const parwa = useVariantStore.getState().getFeatureMap();
    expect(parwa.chatChannel).toBe(true);
    expect(parwa.emailChannel).toBe(true);
    expect(parwa.smsChannel).toBe(true);
    expect(parwa.voiceChannel).toBe(true);
    expect(parwa.videoChannel).toBe(true);
    expect(parwa.refundAgent).toBe(true);
    expect(parwa.fraudDetection).toBe(true);

    act(() => useVariantStore.getState().setTier('high'));
    const high = useVariantStore.getState().getFeatureMap();
    expect(high).toMatchObject({
      chatChannel: true,
      emailChannel: true,
      smsChannel: true,
      voiceChannel: true,
      videoChannel: true,
      refundAgent: true,
      fraudDetection: true,
    });
  });

  it('updates tier and capacity through the hook', () => {
    const { result } = renderHook(() => useVariant());
    expect(result.current.tier).toBe('parwa');
    expect(result.current.features.maxAgents).toBe(5);
    expect(result.current.features.maxKnowledgeDocs).toBe(500);

    act(() => useVariantStore.getState().setTier('high'));

    expect(result.current.tier).toBe('high');
    expect(result.current.features.maxAgents).toBe(8);
    expect(result.current.features.maxKnowledgeDocs).toBe(-1);
  });

  it('normalizes retired tier aliases to Parwa', () => {
    expect(normalizeTier('mini')).toBe('parwa');
    expect(normalizeTier('starter')).toBe('parwa');
    expect(normalizeTier('growth')).toBe('parwa');
    expect(normalizeTier('mini_parwa')).toBe('parwa');
    expect(normalizeTier('high')).toBe('high');
  });

  it('gates High-only capacity screens and unlocks them after upgrade', () => {
    const { rerender } = render(
      <LockedFeature requiredTier="high" featureName="High capacity">
        <div data-testid="high-capacity">High capacity controls</div>
      </LockedFeature>
    );

    expect(screen.getByText('High capacity')).toBeInTheDocument();
    expect(screen.getByText('Upgrade Now')).toBeInTheDocument();
    expect(screen.getByTestId('high-capacity')).toBeInTheDocument();
    expect(screen.getByTestId('high-capacity').parentElement).toHaveClass('blur-[6px]');

    act(() => useVariantStore.getState().setTier('high'));
    rerender(
      <LockedFeature requiredTier="high" featureName="High capacity">
        <div data-testid="high-capacity">High capacity controls</div>
      </LockedFeature>
    );

    expect(screen.getByTestId('high-capacity')).toBeInTheDocument();
    expect(screen.queryByText('Upgrade Now')).not.toBeInTheDocument();
  });

  it('shows tier indicators consistently for a Parwa account', () => {
    render(
      <div>
        <div data-testid="parwa-badge"><TierBadge requiredTier="parwa" /></div>
        <div data-testid="high-badge"><TierBadge requiredTier="high" /></div>
        <LockedFeature requiredTier="high" featureName="Advanced capacity">
          <div>Advanced capacity</div>
        </LockedFeature>
        <InlineLock requiredTier="high" />
      </div>
    );

    expect(screen.getByTestId('parwa-badge').querySelector('svg')).toBeNull();
    expect(screen.getByTestId('high-badge').querySelector('svg')).not.toBeNull();
    expect(screen.getByText('Upgrade Now')).toBeInTheDocument();
    expect(document.querySelectorAll('svg')).not.toHaveLength(0);
  });

  it('applies resource limits by tier without removing AI capabilities', () => {
    act(() => {
      useVariantStore.setState({
        usage: {
          agentsUsed: 5,
          docsUsed: 500,
          apiKeysUsed: 5,
          teamMembersUsed: 10,
          ticketsThisMonth: 0,
          messagesThisMonth: 0,
        },
      });
    });

    const { result } = renderHook(() => useVariant());
    expect(result.current.isAtLimit('agents')).toBe(true);
    expect(result.current.isAtLimit('docs')).toBe(true);
    expect(result.current.isFeatureAvailable('smsChannel')).toBe(true);

    act(() => useVariantStore.getState().setTier('high'));
    expect(result.current.isAtLimit('agents')).toBe(false);
    expect(result.current.isAtLimit('docs')).toBe(false);
    expect(result.current.isFeatureAvailable('smsChannel')).toBe(true);
  });

  it('re-locks High capacity controls after downgrading to Parwa', () => {
    act(() => useVariantStore.getState().setTier('high'));
    const { rerender } = render(
      <LockedFeature requiredTier="high" featureName="High capacity">
        <div data-testid="high-capacity">High capacity controls</div>
      </LockedFeature>
    );
    expect(screen.getByTestId('high-capacity')).toBeInTheDocument();

    act(() => useVariantStore.getState().setTier('parwa'));
    rerender(
      <LockedFeature requiredTier="high" featureName="High capacity">
        <div data-testid="high-capacity">High capacity controls</div>
      </LockedFeature>
    );
    expect(screen.getByText('Upgrade Now')).toBeInTheDocument();
    expect(screen.getByTestId('high-capacity')).toBeInTheDocument();
    expect(screen.getByTestId('high-capacity').parentElement).toHaveClass('blur-[6px]');
    expect(useVariantStore.getState().isFeatureAvailable('smsChannel')).toBe(true);
  });
});
