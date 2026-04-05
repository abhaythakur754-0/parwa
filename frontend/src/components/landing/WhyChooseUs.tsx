'use client';

import { useState } from 'react';

/**
 * WhyChooseUs Component
 * 
 * Shows WHAT Jarvis does (people care about WHAT before HOW).
 * Three feature cards with animations:
 * 1. Smart Recommendations - Suggests best solutions, not just answers
 * 2. Predictive Support - Anticipates customer needs before they ask
 * 3. Industry Specific - E-commerce, SaaS, Logistics & more - tailored for you
 * 
 * Color scheme based on Frontend Docs:
 * - E-commerce: Teal/Gold
 * - SaaS: Navy/Silver
 * - Logistics: Charcoal/Orange
 * 
 * Based on ONBOARDING_SPEC.md v2.0 Section 2.3.5
 */

interface Feature {
  icon: string;
  title: string;
  description: string;
  animation: string;
  details: string[];
  color: 'teal' | 'navy' | 'charcoal';
}

const features: Feature[] = [
  {
    icon: '💡',
    title: 'Smart Recommendations',
    description: 'Suggests best solutions, not just answers',
    animation: 'Card hover effect',
    color: 'teal',
    details: [
      'Analyzes customer context',
      'Suggests upsell opportunities',
      'Recommends best actions',
      'Learns from successful resolutions',
    ],
  },
  {
    icon: '🔮',
    title: 'Predictive Support',
    description: 'Anticipates customer needs before they ask',
    animation: 'Subtle glow effect',
    color: 'navy',
    details: [
      'Proactive issue detection',
      'Anticipates common questions',
      'Prevents problems before they occur',
      'Smart notification timing',
    ],
  },
  {
    icon: '🎯',
    title: 'Industry Specific',
    description: 'E-commerce, SaaS, Logistics & more - tailored for you',
    animation: 'Industry icons animation',
    color: 'charcoal',
    details: [
      'Pre-built industry templates',
      'Specialized vocabulary',
      'Industry-specific workflows',
      'Custom variant selection',
    ],
  },
];

// Color mapping for different industries
const colorClasses = {
  teal: {
    ring: 'ring-teal-500',
    icon: 'text-teal-600',
    check: 'text-teal-500',
    badge: 'bg-teal-100 text-teal-700',
  },
  navy: {
    ring: 'ring-navy-500',
    icon: 'text-navy-600',
    check: 'text-navy-500',
    badge: 'bg-navy-100 text-navy-700',
  },
  charcoal: {
    ring: 'ring-charcoal-500',
    icon: 'text-charcoal-600',
    check: 'text-charcoal-500',
    badge: 'bg-charcoal-100 text-charcoal-700',
  },
};

const industries = [
  { name: 'E-commerce', color: 'teal' },
  { name: 'SaaS', color: 'navy' },
  { name: 'Logistics', color: 'orange' },
  { name: 'Others', color: 'gold' },
] as const;

export default function WhyChooseUs() {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  return (
    <section className="py-16 md:py-24 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center mb-12 md:mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-secondary-900 mb-4">
            Why Choose <span className="text-teal-600">PARWA</span>?
          </h2>
          <p className="text-lg text-secondary-600 max-w-2xl mx-auto">
            Discover what makes Jarvis different from traditional customer support solutions
          </p>
        </div>

        {/* Feature Cards */}
        <div className="grid md:grid-cols-3 gap-8">
          {features.map((feature, index) => {
            const colors = colorClasses[feature.color];
            return (
              <div
                key={index}
                className={`card p-6 md:p-8 transition-all duration-300 cursor-pointer ${
                  hoveredIndex === index
                    ? `ring-2 ${colors.ring} shadow-lg transform -translate-y-1`
                    : 'hover:shadow-md'
                }`}
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
              >
                {/* Icon */}
                <div
                  className={`text-5xl mb-6 transition-transform duration-300 ${
                    hoveredIndex === index ? 'scale-110' : ''
                  }`}
                >
                  {feature.icon}
                </div>

                {/* Title */}
                <h3 className="text-xl font-bold text-secondary-900 mb-2">
                  {feature.title}
                </h3>

                {/* Description */}
                <p className="text-secondary-600 mb-6">
                  {feature.description}
                </p>

                {/* Details (shown on hover) */}
                <div
                  className={`overflow-hidden transition-all duration-300 ${
                    hoveredIndex === index ? 'max-h-40 opacity-100' : 'max-h-0 opacity-0'
                  }`}
                >
                  <ul className="space-y-2 pt-4 border-t border-secondary-200">
                    {feature.details.map((detail, detailIndex) => (
                      <li key={detailIndex} className="flex items-center gap-2 text-sm text-secondary-600">
                        <svg className={`w-4 h-4 ${colors.check} flex-shrink-0`} fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                        {detail}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>

        {/* Industry Tags with Colors */}
        <div className="mt-12 md:mt-16 text-center">
          <p className="text-secondary-600 mb-4">
            Powered by advanced AI that learns and adapts to your business
          </p>
          <div className="flex justify-center gap-4 flex-wrap">
            {industries.map((industry) => (
              <span
                key={industry.name}
                className={`px-4 py-2 rounded-full text-sm font-medium ${
                  industry.color === 'teal' ? 'bg-teal-100 text-teal-700' :
                  industry.color === 'navy' ? 'bg-navy-100 text-navy-700' :
                  industry.color === 'orange' ? 'bg-orange-100 text-orange-700' :
                  'bg-gold-100 text-gold-700'
                }`}
              >
                {industry.name}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
