/**
 * PARWA LockedFeature Component — Unit Tests
 *
 * Tests tier gating, upgrade CTA, custom fallback,
 * TierBadge, and InlineLock sub-components.
 *
 * Tier model: parwa ($2,499/mo) | high ($3,999/mo)
 * Mini PARWA was removed — legacy 'mini' values auto-upgrade to 'parwa'.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { LockedFeature, TierBadge, InlineLock } from '@/components/LockedFeature';
import { useVariantStore } from '@/lib/variant-store';

// ── LockedFeature ────────────────────────────────────────────────────

describe('LockedFeature', () => {
  beforeEach(() => {
    useVariantStore.getState().reset();
  });

  describe('when tier meets or exceeds requiredTier', () => {
    it('renders children when parwa user accesses parwa feature', () => {
      useVariantStore.getState().setTier('parwa');

      render(
        <LockedFeature requiredTier="parwa">
          <div data-testid="child-content">Parwa Feature</div>
        </LockedFeature>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
      expect(screen.getByText('Parwa Feature')).toBeInTheDocument();
    });

    it('renders children when high user accesses parwa feature', () => {
      useVariantStore.getState().setTier('high');

      render(
        <LockedFeature requiredTier="parwa">
          <div data-testid="child-content">Basic Feature</div>
        </LockedFeature>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
    });

    it('renders children when high user accesses high feature', () => {
      useVariantStore.getState().setTier('high');

      render(
        <LockedFeature requiredTier="high">
          <div data-testid="child-content">High Feature</div>
        </LockedFeature>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
    });
  });

  describe('when tier is below requiredTier', () => {
    it('shows upgrade CTA for parwa user accessing high feature', () => {
      useVariantStore.getState().setTier('parwa');

      render(
        <LockedFeature requiredTier="high" featureName="Video Channel">
          <div data-testid="child-content">Video Channel Toggle</div>
        </LockedFeature>
      );

      // Children should NOT be directly visible (they're blurred)
      expect(screen.getByTestId('child-content')).toBeInTheDocument();

      // Upgrade CTA should be shown
      expect(screen.getByText('Video Channel')).toBeInTheDocument();
      expect(screen.getByText(/Available on/)).toBeInTheDocument();
      expect(screen.getByText('Upgrade Now')).toBeInTheDocument();
    });

    it('shows "Premium Feature" when no featureName provided', () => {
      useVariantStore.getState().setTier('parwa');

      render(
        <LockedFeature requiredTier="high">
          <div>Content</div>
        </LockedFeature>
      );

      expect(screen.getByText('Premium Feature')).toBeInTheDocument();
    });

    it('shows correct tier label in upgrade CTA', () => {
      useVariantStore.getState().setTier('parwa');

      render(
        <LockedFeature requiredTier="high">
          <div>Content</div>
        </LockedFeature>
      );

      expect(screen.getByText('PARWA High')).toBeInTheDocument();
      expect(screen.getByText(/\$3,999\/mo/)).toBeInTheDocument();
    });

    it('shows parwa-to-high upsell message for parwa users accessing high features', () => {
      useVariantStore.getState().setTier('parwa');

      render(
        <LockedFeature requiredTier="high">
          <div>Content</div>
        </LockedFeature>
      );

      expect(screen.getByText(/Upgrade for 5 AI agents and 2,499 tickets\/month/)).toBeInTheDocument();
    });

    it('shows high upsell message for high-tier features', () => {
      useVariantStore.getState().setTier('parwa');

      render(
        <LockedFeature requiredTier="high">
          <div>Content</div>
        </LockedFeature>
      );

      expect(screen.getByText(/Upgrade for 8 AI agents/)).toBeInTheDocument();
    });

    it('links upgrade button to /dashboard/billing', () => {
      useVariantStore.getState().setTier('parwa');

      render(
        <LockedFeature requiredTier="high">
          <div>Content</div>
        </LockedFeature>
      );

      const upgradeLink = screen.getByText('Upgrade Now').closest('a');
      expect(upgradeLink).toHaveAttribute('href', '/dashboard/billing');
    });
  });

  describe('custom fallback', () => {
    it('renders custom fallback when feature is locked', () => {
      useVariantStore.getState().setTier('parwa');

      render(
        <LockedFeature requiredTier="high" fallback={<div data-testid="custom-fallback">Not available</div>}>
          <div data-testid="child-content">High Feature</div>
        </LockedFeature>
      );

      expect(screen.getByTestId('custom-fallback')).toBeInTheDocument();
      // Upgrade CTA should NOT be shown when fallback is provided
      expect(screen.queryByText('Upgrade Now')).not.toBeInTheDocument();
    });

    it('ignores fallback when tier is sufficient', () => {
      useVariantStore.getState().setTier('high');

      render(
        <LockedFeature requiredTier="parwa" fallback={<div data-testid="custom-fallback">Fallback</div>}>
          <div data-testid="child-content">Parwa Feature</div>
        </LockedFeature>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
      expect(screen.queryByTestId('custom-fallback')).not.toBeInTheDocument();
    });
  });

  describe('showUpgrade=false', () => {
    it('renders nothing when locked and showUpgrade is false', () => {
      useVariantStore.getState().setTier('parwa');

      const { container } = render(
        <LockedFeature requiredTier="high" showUpgrade={false}>
          <div data-testid="child-content">High Feature</div>
        </LockedFeature>
      );

      // Should render nothing (no children, no upgrade CTA)
      expect(container.innerHTML).toBe('');
    });

    it('still renders children when tier is sufficient', () => {
      useVariantStore.getState().setTier('high');

      render(
        <LockedFeature requiredTier="parwa" showUpgrade={false}>
          <div data-testid="child-content">Parwa Feature</div>
        </LockedFeature>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
    });
  });
});

// ── TierBadge ─────────────────────────────────────────────────────────

describe('TierBadge', () => {
  beforeEach(() => {
    useVariantStore.getState().reset();
  });

  it('renders nothing when tier meets requirement', () => {
    useVariantStore.getState().setTier('high');

    const { container } = render(<TierBadge requiredTier="parwa" />);
    expect(container.innerHTML).toBe('');
  });

  it('renders lock icon and tier label when tier is below requirement', () => {
    useVariantStore.getState().setTier('parwa');

    const { container } = render(<TierBadge requiredTier="high" />);

    expect(container.querySelector('svg.lucide-lock')).toBeInTheDocument();
    // getTierLabel('high').split(' ')[0] = 'PARWA'
    expect(screen.getByText('PARWA')).toBeInTheDocument();
  });

  it('shows "PARWA" label for high-tier badge', () => {
    useVariantStore.getState().setTier('parwa');

    render(<TierBadge requiredTier="high" />);

    // getTierLabel('high').split(' ')[0] = 'PARWA'
    expect(screen.getByText('PARWA')).toBeInTheDocument();
  });
});

// ── InlineLock ────────────────────────────────────────────────────────

describe('InlineLock', () => {
  beforeEach(() => {
    useVariantStore.getState().reset();
  });

  it('renders nothing when tier meets requirement', () => {
    useVariantStore.getState().setTier('high');

    const { container } = render(<InlineLock requiredTier="parwa" />);
    expect(container.innerHTML).toBe('');
  });

  it('renders lock icon when tier is below requirement', () => {
    useVariantStore.getState().setTier('parwa');

    const { container } = render(<InlineLock requiredTier="high" />);

    expect(container.querySelector('svg.lucide-lock')).toBeInTheDocument();
  });

  it('has title tooltip showing upgrade info', () => {
    useVariantStore.getState().setTier('parwa');

    const { container } = render(<InlineLock requiredTier="high" />);

    const lockElement = container.querySelector('svg.lucide-lock')?.closest('span');
    expect(lockElement).toHaveAttribute('title', 'Requires PARWA High ($3,999/mo)');
  });
});
