"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import { Button } from "@/components/ui/button";
import { MiniCard } from "@/components/variants/MiniCard";
import { ParwaJuniorCard } from "@/components/variants/ParwaJuniorCard";
import { ParwaHighCard } from "@/components/variants/ParwaHighCard";
import { VariantsComparison } from "@/components/variants/VariantsComparison";

/**
 * Variant ID type.
 */
type VariantId = "mini" | "parwa" | "parwa_high";

/**
 * Variants selection page component.
 *
 * Displays all PARWA variants with:
 * - Header section with title and description
 * - Three variant cards in a responsive grid
 * - Side-by-side comparison table
 * - Call-to-action section
 *
 * CRITICAL: All 3 variant cards must render correctly.
 */
export default function Home() {
  const [selectedVariant, setSelectedVariant] = React.useState<VariantId | null>(null);
  const [isLoading, setIsLoading] = React.useState<VariantId | null>(null);

  const handleSelect = React.useCallback((variantId: VariantId) => {
    setIsLoading(variantId);

    // Simulate API call
    setTimeout(() => {
      setSelectedVariant(variantId);
      setIsLoading(null);
      console.log(`Selected variant: ${variantId}`);
    }, 500);
  }, []);

  const handleVariantClick = React.useCallback((variantId: string) => {
    handleSelect(variantId as VariantId);
  }, [handleSelect]);

  return (
    <main
      className={cn(
        "min-h-screen bg-background",
        "flex flex-col"
      )}
      data-testid="variants-page"
    >
      {/* Hero Section */}
      <section className="py-16 px-4 text-center bg-gradient-to-b from-primary/5 to-background">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            Choose Your PARWA Plan
          </h1>
          <p className="text-lg text-muted-foreground mb-8 max-w-2xl mx-auto">
            From small businesses to enterprise teams, PARWA has a plan that fits
            your needs. All plans include AI-powered customer support with our
            unique escalation ladder and quality coaching.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Button variant="outline" size="lg">
              Compare Plans
            </Button>
            <Button size="lg">
              Start Free Trial
            </Button>
          </div>
        </div>
      </section>

      {/* Variant Cards Grid */}
      <section className="py-12 px-4" aria-labelledby="pricing-heading">
        <h2 id="pricing-heading" className="sr-only">
          Pricing Plans
        </h2>
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
            {/* Mini PARWA Card */}
            <MiniCard
              isSelected={selectedVariant === "mini"}
              onSelect={() => handleSelect("mini")}
              isLoading={isLoading === "mini"}
            />

            {/* PARWA Junior Card (Recommended) */}
            <ParwaJuniorCard
              isSelected={selectedVariant === "parwa"}
              onSelect={() => handleSelect("parwa")}
              isLoading={isLoading === "parwa"}
            />

            {/* PARWA High Card */}
            <ParwaHighCard
              isSelected={selectedVariant === "parwa_high"}
              onSelect={() => handleSelect("parwa_high")}
              isLoading={isLoading === "parwa_high"}
            />
          </div>
        </div>
      </section>

      {/* Comparison Section */}
      <section className="py-12 px-4 bg-muted/30" aria-labelledby="comparison-heading">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-8">
            <h2
              id="comparison-heading"
              className="text-2xl md:text-3xl font-bold mb-2"
            >
              Compare All Features
            </h2>
            <p className="text-muted-foreground">
              See how each plan stacks up against your requirements
            </p>
          </div>
          <VariantsComparison
            highlightRecommended={true}
            onVariantClick={handleVariantClick}
          />
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-12 px-4" aria-labelledby="faq-heading">
        <div className="max-w-3xl mx-auto">
          <h2
            id="faq-heading"
            className="text-2xl md:text-3xl font-bold text-center mb-8"
          >
            Frequently Asked Questions
          </h2>
          <div className="space-y-6">
            <div className="border rounded-lg p-6">
              <h3 className="font-semibold mb-2">
                Can I switch plans at any time?
              </h3>
              <p className="text-muted-foreground">
                Yes! You can upgrade or downgrade your plan at any time. Changes
                take effect immediately, and we&apos;ll prorate any differences.
              </p>
            </div>
            <div className="border rounded-lg p-6">
              <h3 className="font-semibold mb-2">
                What happens if I exceed my concurrent call limit?
              </h3>
              <p className="text-muted-foreground">
                Additional calls are queued and processed as capacity becomes
                available. You can also upgrade your plan for higher limits.
              </p>
            </div>
            <div className="border rounded-lg p-6">
              <h3 className="font-semibold mb-2">
                Is there a free trial?
              </h3>
              <p className="text-muted-foreground">
                Yes! All plans include a 14-day free trial. No credit card
                required to start.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 px-4 bg-primary text-primary-foreground">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-2xl md:text-3xl font-bold mb-4">
            Ready to Transform Your Customer Support?
          </h2>
          <p className="text-lg mb-8 opacity-90">
            Join thousands of businesses using PARWA to deliver exceptional
            AI-powered customer experiences.
          </p>
          <Button
            variant="secondary"
            size="lg"
            className="bg-white text-primary hover:bg-white/90"
          >
            Start Your Free Trial
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-4 border-t bg-muted/30 mt-auto">
        <div className="max-w-6xl mx-auto text-center text-muted-foreground text-sm">
          <p>
            &copy; {new Date().getFullYear()} PARWA. AI Customer Support That
            Actually Works.
          </p>
        </div>
      </footer>
    </main>
  );
}
