/**
 * PARWA Integration Test: Multi-Tenant Tier Gating Flow
 *
 * Tests the complete flow:
 * variant-store → useVariant hook → LockedFeature component
 *
 * Validates that tier changes in the store correctly propagate
 * through the hook to the component, gating/ungating features.
 */

import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import { useVariantStore } from '@/lib/variant-store';
import { useVariant } from '@/hooks/useVariant';
import { LockedFeature, TierBadge, InlineLock } from '@/components/LockedFeature';

describe('Integration: Multi-Tenant Tier Gating Flow', () => {
  beforeEach(() => {
    useVariantStore.getState().reset();
  });

  describe('Store → Hook → Component propagation', () => {
    it('changing tier in store updates LockedFeature rendering', () => {
      // Start at mini tier
      useVariantStore.getState().setTier('mini');

      const { rerender } = render(
        <LockedFeature requiredTier="pro" featureName="SMS Channel">
          <div data-testid="sms-toggle">SMS Channel Toggle</div>
        </LockedFeature>
      );

      // Mini user should see upgrade CTA
      expect(screen.getByText('SMS Channel')).toBeInTheDocument();
      expect(screen.getByText('Upgrade Now')).toBeInTheDocument();

      // Upgrade to pro
      act(() => {
        useVariantStore.getState().setTier('pro');
      });

      // Re-render to pick up store change
      rerender(
        <LockedFeature requiredTier="pro" featureName="SMS Channel">
          <div data-testid="sms-toggle">SMS Channel Toggle</div>
        </LockedFeature>
      );

      // Pro user should see the actual content
      expect(screen.getByTestId('sms-toggle')).toBeInTheDocument();
      expect(screen.queryByText('Upgrade Now')).not.toBeInTheDocument();
    });

    it('hook reflects store tier changes', () => {
      const { result } = renderHook(() => useVariant());

      // Initially mini
      expect(result.current.tier).toBe('mini');
      expect(result.current.isFeatureAvailable('smsChannel')).toBe(false);

      // Upgrade to pro
      act(() => {
        useVariantStore.getState().setTier('pro');
      });

      expect(result.current.tier).toBe('pro');
      expect(result.current.isFeatureAvailable('smsChannel')).toBe(true);
    });
  });

  describe('Complete tier upgrade scenario', () => {
    it('mini → pro: unlocks SMS, Voice, Refund, Technical, Complaint agents', () => {
      useVariantStore.getState().setTier('mini');

      const { result } = renderHook(() => useVariant());

      // Mini tier limitations
      expect(result.current.isFeatureAvailable('smsChannel')).toBe(false);
      expect(result.current.isFeatureAvailable('voiceChannel')).toBe(false);
      expect(result.current.isFeatureAvailable('videoChannel')).toBe(false);
      expect(result.current.isFeatureAvailable('refundAgent')).toBe(false);
      expect(result.current.isFeatureAvailable('technicalAgent')).toBe(false);
      expect(result.current.isFeatureAvailable('fraudDetection')).toBe(false);

      // Upgrade to pro
      act(() => {
        useVariantStore.getState().setTier('pro');
      });

      // Pro tier unlocks
      expect(result.current.isFeatureAvailable('smsChannel')).toBe(true);
      expect(result.current.isFeatureAvailable('voiceChannel')).toBe(true);
      expect(result.current.isFeatureAvailable('refundAgent')).toBe(true);
      expect(result.current.isFeatureAvailable('technicalAgent')).toBe(true);
      expect(result.current.isFeatureAvailable('complaintAgent')).toBe(true);

      // Still locked on pro
      expect(result.current.isFeatureAvailable('videoChannel')).toBe(false);
      expect(result.current.isFeatureAvailable('fraudDetection')).toBe(false);
      expect(result.current.isFeatureAvailable('qualityCoach')).toBe(false);
    });

    it('pro → high: unlocks Video, Fraud, Quality, Churn', () => {
      useVariantStore.getState().setTier('pro');

      const { result } = renderHook(() => useVariant());

      // Pro tier - video and high features still locked
      expect(result.current.isFeatureAvailable('videoChannel')).toBe(false);
      expect(result.current.isFeatureAvailable('fraudDetection')).toBe(false);
      expect(result.current.isFeatureAvailable('qualityCoach')).toBe(false);
      expect(result.current.isFeatureAvailable('churnPrediction')).toBe(false);

      // Upgrade to high
      act(() => {
        useVariantStore.getState().setTier('high');
      });

      // All features unlocked
      expect(result.current.isFeatureAvailable('videoChannel')).toBe(true);
      expect(result.current.isFeatureAvailable('fraudDetection')).toBe(true);
      expect(result.current.isFeatureAvailable('qualityCoach')).toBe(true);
      expect(result.current.isFeatureAvailable('churnPrediction')).toBe(true);
    });
  });

  describe('Usage limits integration', () => {
    it('isAtLimit correctly reflects usage vs tier limits', () => {
      useVariantStore.getState().setTier('mini');

      const { result } = renderHook(() => useVariant());

      // Under limit
      expect(result.current.isAtLimit('agents')).toBe(false);
      expect(result.current.isAtLimit('docs')).toBe(false);

      // Hit limit
      act(() => {
        useVariantStore.setState({
          usage: {
            agentsUsed: 5,
            docsUsed: 50,
            apiKeysUsed: 1,
            teamMembersUsed: 1,
            ticketsThisMonth: 0,
            messagesThisMonth: 0,
          },
        });
      });

      expect(result.current.isAtLimit('agents')).toBe(true);
      expect(result.current.isAtLimit('docs')).toBe(true);

      // Upgrade to pro (higher limits)
      act(() => {
        useVariantStore.getState().setTier('pro');
      });

      // Now under limit again (pro allows 15 agents, 500 docs)
      expect(result.current.isAtLimit('agents')).toBe(false);
      expect(result.current.isAtLimit('docs')).toBe(false);
    });
  });

  describe('TierBadge + LockedFeature consistency', () => {
    it('TierBadge and LockedFeature agree on feature availability', () => {
      useVariantStore.getState().setTier('mini');

      render(
        <div>
          <div data-testid="tier-badge-area"><TierBadge requiredTier="pro" /></div>
          <LockedFeature requiredTier="pro">
            <div data-testid="content">Pro Feature</div>
          </LockedFeature>
        </div>
      );

      // TierBadge should show lock icon
      const badgeArea = screen.getByTestId('tier-badge-area');
      expect(badgeArea.querySelector('[data-testid="icon-lock"]')).toBeInTheDocument();
      // LockedFeature should show upgrade CTA
      expect(screen.getByText('Upgrade Now')).toBeInTheDocument();
    });
  });

  describe('Multiple LockedFeature components', () => {
    it('correctly gates multiple features simultaneously', () => {
      useVariantStore.getState().setTier('mini');

      render(
        <div>
          <LockedFeature requiredTier="mini" featureName="Chat">
            <div data-testid="chat">Chat Channel</div>
          </LockedFeature>
          <LockedFeature requiredTier="pro" featureName="SMS">
            <div data-testid="sms">SMS Channel</div>
          </LockedFeature>
          <LockedFeature requiredTier="high" featureName="Video">
            <div data-testid="video">Video Channel</div>
          </LockedFeature>
        </div>
      );

      // Mini feature: accessible
      expect(screen.getByTestId('chat')).toBeInTheDocument();

      // Pro feature: locked (shows upgrade)
      expect(screen.getByText('SMS')).toBeInTheDocument();

      // High feature: locked (shows upgrade)
      expect(screen.getByText('Video')).toBeInTheDocument();

      // Two upgrade CTAs
      const upgradeButtons = screen.getAllByText('Upgrade Now');
      expect(upgradeButtons).toHaveLength(2);
    });
  });

  describe('Tier downgrade scenario', () => {
    it('downgrading from high to mini re-locks all features', () => {
      // Start at high
      useVariantStore.getState().setTier('high');

      const { result } = renderHook(() => useVariant());

      expect(result.current.isFeatureAvailable('videoChannel')).toBe(true);
      expect(result.current.isFeatureAvailable('fraudDetection')).toBe(true);

      // Downgrade to mini
      act(() => {
        useVariantStore.getState().setTier('mini');
      });

      expect(result.current.isFeatureAvailable('videoChannel')).toBe(false);
      expect(result.current.isFeatureAvailable('fraudDetection')).toBe(false);
      expect(result.current.isFeatureAvailable('smsChannel')).toBe(false);
    });
  });
});
