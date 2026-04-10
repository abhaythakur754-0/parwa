/**
 * Day 6: Pricing Components Tests
 *
 * Tests for:
 * - IndustrySelector
 * - QuantitySelector
 * - VariantCard
 * - TotalSummary
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

import { IndustrySelector } from '../IndustrySelector';
import { QuantitySelector } from '../QuantitySelector';
import { VariantCard, type PricingVariant } from '../VariantCard';
import { TotalSummary } from '../TotalSummary';

// ── IndustrySelector Tests ──────────────────────────────────────────

describe('IndustrySelector', () => {
  const mockOnSelect = jest.fn();

  beforeEach(() => {
    mockOnSelect.mockClear();
  });

  it('renders all 4 industries', () => {
    render(
      <IndustrySelector
        selectedIndustry={null}
        onSelect={mockOnSelect}
      />
    );

    expect(screen.getByText('E-commerce')).toBeInTheDocument();
    expect(screen.getByText('SaaS')).toBeInTheDocument();
    expect(screen.getByText('Logistics')).toBeInTheDocument();
    expect(screen.getByText('Others')).toBeInTheDocument();
  });

  it('calls onSelect when industry is clicked', () => {
    render(
      <IndustrySelector
        selectedIndustry={null}
        onSelect={mockOnSelect}
      />
    );

    fireEvent.click(screen.getByText('E-commerce'));
    expect(mockOnSelect).toHaveBeenCalledWith('ecommerce');
  });

  it('shows selected state for selected industry', () => {
    render(
      <IndustrySelector
        selectedIndustry="saas"
        onSelect={mockOnSelect}
      />
    );

    // SaaS button should have different styling when selected
    const saasButton = screen.getByText('SaaS').closest('button');
    expect(saasButton).toHaveAttribute('aria-pressed', 'true');
  });

  it('disables all buttons when disabled prop is true', () => {
    render(
      <IndustrySelector
        selectedIndustry={null}
        onSelect={mockOnSelect}
        disabled={true}
      />
    );

    const buttons = screen.getAllByRole('button');
    buttons.forEach(button => {
      expect(button).toBeDisabled();
    });
  });

  it('displays industry descriptions', () => {
    render(
      <IndustrySelector
        selectedIndustry={null}
        onSelect={mockOnSelect}
      />
    );

    expect(screen.getByText('Online retail, marketplaces, D2C brands')).toBeInTheDocument();
    expect(screen.getByText('Software companies, tech startups')).toBeInTheDocument();
  });
});


// ── QuantitySelector Tests ──────────────────────────────────────────

describe('QuantitySelector', () => {
  const mockOnChange = jest.fn();

  beforeEach(() => {
    mockOnChange.mockClear();
  });

  it('renders with initial value', () => {
    render(
      <QuantitySelector
        value={5}
        onChange={mockOnChange}
      />
    );

    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('increments value when plus is clicked', () => {
    render(
      <QuantitySelector
        value={5}
        onChange={mockOnChange}
      />
    );

    const incrementButton = screen.getByLabelText('Increase quantity');
    fireEvent.click(incrementButton);

    expect(mockOnChange).toHaveBeenCalledWith(6);
  });

  it('decrements value when minus is clicked', () => {
    render(
      <QuantitySelector
        value={5}
        onChange={mockOnChange}
      />
    );

    const decrementButton = screen.getByLabelText('Decrease quantity');
    fireEvent.click(decrementButton);

    expect(mockOnChange).toHaveBeenCalledWith(4);
  });

  it('does not decrement below minimum', () => {
    render(
      <QuantitySelector
        value={0}
        onChange={mockOnChange}
        min={0}
      />
    );

    const decrementButton = screen.getByLabelText('Decrease quantity');
    fireEvent.click(decrementButton);

    expect(mockOnChange).not.toHaveBeenCalled();
    expect(decrementButton).toBeDisabled();
  });

  it('does not increment above maximum', () => {
    render(
      <QuantitySelector
        value={10}
        onChange={mockOnChange}
        max={10}
      />
    );

    const incrementButton = screen.getByLabelText('Increase quantity');
    fireEvent.click(incrementButton);

    expect(mockOnChange).not.toHaveBeenCalled();
    expect(incrementButton).toBeDisabled();
  });

  it('disables all buttons when disabled prop is true', () => {
    render(
      <QuantitySelector
        value={5}
        onChange={mockOnChange}
        disabled={true}
      />
    );

    expect(screen.getByLabelText('Decrease quantity')).toBeDisabled();
    expect(screen.getByLabelText('Increase quantity')).toBeDisabled();
  });
});


// ── VariantCard Tests ───────────────────────────────────────────────

describe('VariantCard', () => {
  const mockVariant: PricingVariant = {
    id: 'test-variant',
    name: 'Test Variant',
    description: 'A test variant for testing',
    ticketsPerMonth: 500,
    pricePerMonth: 99,
    features: ['Feature 1', 'Feature 2', 'Feature 3'],
    popular: false,
  };

  const mockOnQuantityChange = jest.fn();

  beforeEach(() => {
    mockOnQuantityChange.mockClear();
  });

  it('renders variant information', () => {
    render(
      <VariantCard
        variant={mockVariant}
        quantity={1}
        onQuantityChange={mockOnQuantityChange}
      />
    );

    expect(screen.getByText('Test Variant')).toBeInTheDocument();
    expect(screen.getByText('A test variant for testing')).toBeInTheDocument();
    // With quantity=1, shows 500 tickets and $99
    expect(screen.getByText('500')).toBeInTheDocument();
    expect(screen.getByText('$99')).toBeInTheDocument();
  });

  it('displays features list', () => {
    render(
      <VariantCard
        variant={mockVariant}
        quantity={0}
        onQuantityChange={mockOnQuantityChange}
      />
    );

    expect(screen.getByText('Feature 1')).toBeInTheDocument();
    expect(screen.getByText('Feature 2')).toBeInTheDocument();
    expect(screen.getByText('Feature 3')).toBeInTheDocument();
  });

  it('shows popular badge when variant is popular', () => {
    const popularVariant = { ...mockVariant, popular: true };

    render(
      <VariantCard
        variant={popularVariant}
        quantity={0}
        onQuantityChange={mockOnQuantityChange}
      />
    );

    expect(screen.getByText('Most Popular')).toBeInTheDocument();
  });

  it('calculates total based on quantity', () => {
    render(
      <VariantCard
        variant={mockVariant}
        quantity={3}
        onQuantityChange={mockOnQuantityChange}
      />
    );

    // 99 * 3 = 297
    expect(screen.getByText('$297')).toBeInTheDocument();
    // 500 * 3 = 1500
    expect(screen.getByText('1,500')).toBeInTheDocument();
  });

  it('calls onQuantityChange when quantity changes', () => {
    render(
      <VariantCard
        variant={mockVariant}
        quantity={0}
        onQuantityChange={mockOnQuantityChange}
      />
    );

    const incrementButton = screen.getByLabelText('Increase quantity');
    fireEvent.click(incrementButton);

    expect(mockOnQuantityChange).toHaveBeenCalledWith('test-variant', 1);
  });
});


// ── TotalSummary Tests ───────────────────────────────────────────────

describe('TotalSummary', () => {
  const mockVariants: PricingVariant[] = [
    {
      id: 'variant-1',
      name: 'Variant One',
      description: 'First variant',
      ticketsPerMonth: 500,
      pricePerMonth: 99,
      features: ['Feature 1'],
      popular: true,
    },
    {
      id: 'variant-2',
      name: 'Variant Two',
      description: 'Second variant',
      ticketsPerMonth: 200,
      pricePerMonth: 49,
      features: ['Feature 2'],
      popular: false,
    },
  ];

  const mockOnContinue = jest.fn();

  beforeEach(() => {
    mockOnContinue.mockClear();
  });

  it('shows empty state when no variants selected', () => {
    render(
      <TotalSummary
        selectedVariants={[]}
        onContinue={mockOnContinue}
      />
    );

    expect(screen.getByText('Select variants to see your bill summary')).toBeInTheDocument();
  });

  it('displays selected variants breakdown', () => {
    const selectedVariants = [
      { variant: mockVariants[0], quantity: 2 },
    ];

    render(
      <TotalSummary
        selectedVariants={selectedVariants}
        onContinue={mockOnContinue}
      />
    );

    expect(screen.getByText('Variant One')).toBeInTheDocument();
    expect(screen.getByText('1,000 tickets/month')).toBeInTheDocument(); // 500 * 2
    expect(screen.getByText('$198/mo')).toBeInTheDocument(); // 99 * 2
  });

  it('calculates total tickets correctly', () => {
    const selectedVariants = [
      { variant: mockVariants[0], quantity: 2 }, // 500 * 2 = 1000
      { variant: mockVariants[1], quantity: 1 }, // 200 * 1 = 200
    ];

    render(
      <TotalSummary
        selectedVariants={selectedVariants}
        onContinue={mockOnContinue}
      />
    );

    // Total: 1000 + 200 = 1200
    expect(screen.getByText('1,200/month')).toBeInTheDocument();
  });

  it('calculates total monthly cost correctly', () => {
    const selectedVariants = [
      { variant: mockVariants[0], quantity: 2 }, // 99 * 2 = 198
      { variant: mockVariants[1], quantity: 1 }, // 49 * 1 = 49
    ];

    render(
      <TotalSummary
        selectedVariants={selectedVariants}
        onContinue={mockOnContinue}
      />
    );

    // Total: 198 + 49 = 247
    expect(screen.getByText('$247')).toBeInTheDocument();
  });

  it('shows annual savings message', () => {
    const selectedVariants = [
      { variant: mockVariants[0], quantity: 1 },
    ];

    render(
      <TotalSummary
        selectedVariants={selectedVariants}
        onContinue={mockOnContinue}
      />
    );

    // 99 * 2 = 198 savings
    expect(screen.getByText(/Save \$198\/year with annual billing/)).toBeInTheDocument();
  });

  it('calls onContinue when continue button is clicked', () => {
    const selectedVariants = [
      { variant: mockVariants[0], quantity: 1 },
    ];

    render(
      <TotalSummary
        selectedVariants={selectedVariants}
        onContinue={mockOnContinue}
      />
    );

    fireEvent.click(screen.getByText('Continue to Checkout'));
    expect(mockOnContinue).toHaveBeenCalled();
  });

  it('disables continue button when no variants selected', () => {
    render(
      <TotalSummary
        selectedVariants={[]}
        onContinue={mockOnContinue}
      />
    );

    // Continue button should not be rendered in empty state
    expect(screen.queryByText('Continue to Checkout')).not.toBeInTheDocument();
  });
});
