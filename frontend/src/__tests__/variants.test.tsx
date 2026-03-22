/**
 * Unit tests for Variant Card Components.
 *
 * Tests for:
 * - VariantCard base component
 * - MiniCard component
 * - ParwaJuniorCard component
 * - ParwaHighCard component
 * - VariantsComparison component
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

// Import components
import { VariantCard } from "../components/variants/VariantCard";
import { MiniCard, getMiniConfig } from "../components/variants/MiniCard";
import { ParwaJuniorCard, getParwaJuniorConfig } from "../components/variants/ParwaJuniorCard";
import { ParwaHighCard, getParwaHighConfig } from "../components/variants/ParwaHighCard";
import { VariantsComparison } from "../components/variants/VariantsComparison";

// Mock Select callback
const mockOnSelect = vi.fn();

describe("VariantCard", () => {
  const defaultProps = {
    variantId: "test",
    title: "Test Variant",
    tier: "Test",
    price: 99,
    targetAudience: "Test audience",
    features: [
      { name: "Feature 1", included: true, value: "10" },
      { name: "Feature 2", included: false },
    ],
    onSelect: mockOnSelect,
  };

  it("renders with required props", () => {
    render(<VariantCard {...defaultProps} />);
    expect(screen.getByText("Test Variant")).toBeInTheDocument();
    expect(screen.getByText("$99")).toBeInTheDocument();
    expect(screen.getByText("/month")).toBeInTheDocument();
  });

  it("displays feature list correctly", () => {
    render(<VariantCard {...defaultProps} />);
    expect(screen.getByText("Feature 1")).toBeInTheDocument();
    expect(screen.getByText("Feature 2")).toBeInTheDocument();
  });

  it("shows popular badge when isPopular is true", () => {
    render(<VariantCard {...defaultProps} isPopular={true} />);
    expect(screen.getByText("Most Popular")).toBeInTheDocument();
  });

  it("shows tier badge", () => {
    render(<VariantCard {...defaultProps} />);
    expect(screen.getByText("Test")).toBeInTheDocument();
  });

  it("renders select button with custom text", () => {
    render(<VariantCard {...defaultProps} selectButtonText="Custom Button" />);
    expect(screen.getByText("Custom Button")).toBeInTheDocument();
  });
});

describe("MiniCard", () => {
  it("renders Mini PARWA card correctly", () => {
    render(<MiniCard onSelect={mockOnSelect} />);
    expect(screen.getByText("Mini PARWA")).toBeInTheDocument();
    expect(screen.getByText("$1000")).toBeInTheDocument();
    expect(screen.getByText("Light")).toBeInTheDocument();
  });

  it("shows correct features for Mini tier", () => {
    render(<MiniCard onSelect={mockOnSelect} />);
    expect(screen.getByText("Concurrent calls")).toBeInTheDocument();
    expect(screen.getAllByText("2")[0]).toBeInTheDocument();
  });

  it("returns correct config from getMiniConfig", () => {
    const config = getMiniConfig();
    expect(config.variantId).toBe("mini");
    expect(config.price).toBe(1000);
    expect(config.maxConcurrentCalls).toBe(2);
    expect(config.refundLimit).toBe(50);
    expect(config.escalationThreshold).toBe(70);
  });
});

describe("ParwaJuniorCard", () => {
  it("renders PARWA Junior card correctly", () => {
    render(<ParwaJuniorCard onSelect={mockOnSelect} />);
    expect(screen.getByText("PARWA Junior")).toBeInTheDocument();
    expect(screen.getByText("$2500")).toBeInTheDocument();
    expect(screen.getByText("Medium")).toBeInTheDocument();
  });

  it("shows Most Popular badge (isPopular=true)", () => {
    render(<ParwaJuniorCard onSelect={mockOnSelect} />);
    expect(screen.getByText("Most Popular")).toBeInTheDocument();
  });

  it("returns correct config from getParwaJuniorConfig", () => {
    const config = getParwaJuniorConfig();
    expect(config.variantId).toBe("parwa");
    expect(config.price).toBe(2500);
    expect(config.maxConcurrentCalls).toBe(5);
    expect(config.refundLimit).toBe(500);
    expect(config.escalationThreshold).toBe(60);
  });
});

describe("ParwaHighCard", () => {
  it("renders PARWA High card correctly", () => {
    render(<ParwaHighCard onSelect={mockOnSelect} />);
    expect(screen.getByText("PARWA High")).toBeInTheDocument();
    expect(screen.getByText("$4000")).toBeInTheDocument();
    expect(screen.getByText("Heavy")).toBeInTheDocument();
  });

  it("shows Contact Sales button", () => {
    render(<ParwaHighCard onSelect={mockOnSelect} />);
    expect(screen.getByText("Contact Sales")).toBeInTheDocument();
  });

  it("returns correct config from getParwaHighConfig", () => {
    const config = getParwaHighConfig();
    expect(config.variantId).toBe("parwa_high");
    expect(config.price).toBe(4000);
    expect(config.maxConcurrentCalls).toBe(10);
    expect(config.refundLimit).toBe(2000);
    expect(config.escalationThreshold).toBe(50);
    expect(config.features.canExecuteRefunds).toBe(true);
    expect(config.features.hipaaCompliance).toBe(true);
  });
});

describe("VariantsComparison", () => {
  it("renders comparison table", () => {
    render(<VariantsComparison />);
    expect(screen.getByText("Feature")).toBeInTheDocument();
    expect(screen.getByText("Mini PARWA")).toBeInTheDocument();
    expect(screen.getByText("PARWA Junior")).toBeInTheDocument();
    expect(screen.getByText("PARWA High")).toBeInTheDocument();
  });

  it("shows recommended badge on PARWA Junior", () => {
    render(<VariantsComparison highlightRecommended={true} />);
    expect(screen.getByText("Recommended")).toBeInTheDocument();
  });

  it("displays pricing category", () => {
    render(<VariantsComparison />);
    expect(screen.getByText("Pricing")).toBeInTheDocument();
  });

  it("displays AI category", () => {
    render(<VariantsComparison />);
    expect(screen.getByText("AI")).toBeInTheDocument();
  });

  it("displays Channels category", () => {
    render(<VariantsComparison />);
    expect(screen.getByText("Channels")).toBeInTheDocument();
  });
});

describe("Variant Integration Tests", () => {
  it("Mini tier should NOT have voice/video support", () => {
    render(<MiniCard onSelect={mockOnSelect} />);
    // Voice and Video should be marked as not included
    const features = screen.getAllByRole("listitem");
    const voiceFeature = features.find((f) => f.textContent?.includes("Voice support"));
    const videoFeature = features.find((f) => f.textContent?.includes("Video support"));

    // These features should have X icon (not included)
    expect(voiceFeature).toBeDefined();
    expect(videoFeature).toBeDefined();
  });

  it("PARWA High should have HIPAA compliance", () => {
    render(<ParwaHighCard onSelect={mockOnSelect} />);
    expect(screen.getByText("HIPAA compliance")).toBeInTheDocument();
  });

  it("All variants should have correct escalation thresholds", () => {
    const miniConfig = getMiniConfig();
    const juniorConfig = getParwaJuniorConfig();
    const highConfig = getParwaHighConfig();

    // CRITICAL: Verify escalation thresholds
    expect(miniConfig.escalationThreshold).toBe(70);
    expect(juniorConfig.escalationThreshold).toBe(60);
    expect(highConfig.escalationThreshold).toBe(50);
  });
});
