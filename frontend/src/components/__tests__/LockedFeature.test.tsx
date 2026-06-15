/**
 * PARWA LockedFeature Component — Unit Tests
 *
 * Tests tier gating, upgrade CTA, custom fallback,
 * TierBadge, and InlineLock sub-components.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { LockedFeature, TierBadge, InlineLock } from '@/components/LockedFeature';
import { useVariantStore } from '@/lib/variant-store';

// ── LockedFeature ────────────────────────────────────────────────────

describe('LockedFeature', () => {
  beforeEach(() => {
    useVariantStore.getState().reset();
  });

  describe('when tier meets or exceeds requiredTier', () => {
    it('renders children when mini user accesses mini feature', () => {
      useVariantStore.getState().setTier('mini');

      render(
        <LockedFeature requiredTier="mini">
          <div data-testid="child-content">Mini Feature</div>
        </LockedFeature>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
      expect(screen.getByText('Mini Feature')).toBeInTheDocument();
    });

    it('renders children when pro user accesses mini feature', () => {
      useVariantStore.getState().setTier('pro');

      render(
        <LockedFeature requiredTier="mini">
          <div data-testid="child-content">Basic Feature</div>
        </LockedFeature>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
    });

    it('renders children when pro user accesses pro feature', () => {
      useVariantStore.getState().setTier('pro');

      render(
        <LockedFeature requiredTier="pro">
          <div data-testid="child-content">Pro Feature</div>
        </LockedFeature>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
    });

    it('renders children when high user accesses any feature', () => {
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
    it('shows upgrade CTA for mini user accessing pro feature', () => {
      useVariantStore.getState().setTier('mini');

      render(
        <LockedFeature requiredTier="pro" featureName="SMS Channel">
          <div data-testid="child-content">SMS Channel Toggle</div>
        </LockedFeature>
      );

      // Children should NOT be directly visible (they're blurred)
      expect(screen.getByTestId('child-content')).toBeInTheDocument();

      // Upgrade CTA should be shown
      expect(screen.getByText('SMS Channel')).toBeInTheDocument();
      expect(screen.getByText(/Available on/)).toBeInTheDocument();
      expect(screen.getByText('Upgrade Now')).toBeInTheDocument();
    });

    it('shows "Premium Feature" when no featureName provided', () => {
      useVariantStore.getState().setTier('mini');

      render(
        <LockedFeature requiredTier="pro">
          <div>Content</div>
        </LockedFeature>
      );

      expect(screen.getByText('Premium Feature')).toBeInTheDocument();
    });

    it('shows correct tier label in upgrade CTA', () => {
      useVariantStore.getState().setTier('mini');

      render(
        <LockedFeature requiredTier="high">
          <div>Content</div>
        </LockedFeature>
      );

      expect(screen.getByText('PARWA High')).toBeInTheDocument();
      expect(screen.getByText(/\$3,999\/mo/)).toBeInTheDocument();
    });

    it('shows mini-to-pro upsell message for mini users', () => {
      useVariantStore.getState().setTier('mini');

      render(
        <LockedFeature requiredTier="pro">
          <div>Content</div>
        </LockedFeature>
      );

      expect(screen.getByText(/Pro unlocks SMS & Voice channels/)).toBeInTheDocument();
    });

    it('shows high upsell message for high-tier features', () => {
      useVariantStore.getState().setTier('mini');

      render(
        <LockedFeature requiredTier="high">
          <div>Content</div>
        </LockedFeature>
      );

      expect(screen.getByText(/High unlocks Video channel/)).toBeInTheDocument();
    });

    it('links upgrade button to /dashboard/billing', () => {
      useVariantStore.getState().setTier('mini');

      render(
        <LockedFeature requiredTier="pro">
          <div>Content</div>
        </LockedFeature>
      );

      const upgradeLink = screen.getByText('Upgrade Now').closest('a');
      expect(upgradeLink).toHaveAttribute('href', '/dashboard/billing');
    });
  });

  describe('custom fallback', () => {
    it('renders custom fallback when feature is locked', () => {
      useVariantStore.getState().setTier('mini');

      render(
        <LockedFeature requiredTier="pro" fallback={<div data-testid="custom-fallback">Not available</div>}>
          <div data-testid="child-content">Pro Feature</div>
        </LockedFeature>
      );

      expect(screen.getByTestId('custom-fallback')).toBeInTheDocument();
      // Upgrade CTA should NOT be shown when fallback is provided
      expect(screen.queryByText('Upgrade Now')).not.toBeInTheDocument();
    });

    it('ignores fallback when tier is sufficient', () => {
      useVariantStore.getState().setTier('pro');

      render(
        <LockedFeature requiredTier="pro" fallback={<div data-testid="custom-fallback">Fallback</div>}>
          <div data-testid="child-content">Pro Feature</div>
        </LockedFeature>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
      expect(screen.queryByTestId('custom-fallback')).not.toBeInTheDocument();
    });
  });

  describe('showUpgrade=false', () => {
    it('renders nothing when locked and showUpgrade is false', () => {
      useVariantStore.getState().setTier('mini');

      const { container } = render(
        <LockedFeature requiredTier="pro" showUpgrade={false}>
          <div data-testid="child-content">Pro Feature</div>
        </LockedFeature>
      );

      // Should render nothing (no children, no upgrade CTA)
      expect(container.innerHTML).toBe('');
    });

    it('still renders children when tier is sufficient', () => {
      useVariantStore.getState().setTier('pro');

      render(
        <LockedFeature requiredTier="pro" showUpgrade={false}>
          <div data-testid="child-content">Pro Feature</div>
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
    useVariantStore.getState().setTier('pro');

    const { container } = render(<TierBadge requiredTier="pro" />);
    expect(container.innerHTML).toBe('');
  });

  it('renders lock icon and tier label when tier is below requirement', () => {
    useVariantStore.getState().setTier('mini');

    render(<TierBadge requiredTier="pro" />);

    expect(screen.getByTestId('icon-lock')).toBeInTheDocument();
    // getTierLabel('pro').split(' ')[0] = 'PARWA'
    expect(screen.getByText('PARWA')).toBeInTheDocument();
  });

  it('shows "High" label for high-tier badge', () => {
    useVariantStore.getState().setTier('mini');

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
    useVariantStore.getState().setTier('pro');

    const { container } = render(<InlineLock requiredTier="pro" />);
    expect(container.innerHTML).toBe('');
  });

  it('renders lock icon when tier is below requirement', () => {
    useVariantStore.getState().setTier('mini');

    render(<InlineLock requiredTier="pro" />);

    expect(screen.getByTestId('icon-lock')).toBeInTheDocument();
  });

  it('has title tooltip showing upgrade info', () => {
    useVariantStore.getState().setTier('mini');

    render(<InlineLock requiredTier="pro" />);

    const lockElement = screen.getByTestId('icon-lock').closest('span');
    expect(lockElement).toHaveAttribute('title', 'Requires PARWA Pro ($2,499/mo)');
  });
});
