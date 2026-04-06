'use client';

import { useState } from 'react';

/**
 * WhyChooseUs Component
 * 
 * Dark premium cards showing WHAT Jarvis does.
 * Three feature cards with hover animations.
 * NO emojis - using SVG icons.
 */

interface Feature {
  icon: React.ReactNode;
  title: string;
  description: string;
  details: string[];
  color: 'teal' | 'navy' | 'charcoal';
}

const features: Feature[] = [
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
      </svg>
    ),
    title: 'Smart Recommendations',
    description: 'Suggests best solutions, not just answers',
    color: 'teal',
    details: [
      'Analyzes customer context',
      'Suggests upsell opportunities',
      'Recommends best actions',
      'Learns from successful resolutions',
    ],
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
      </svg>
    ),
    title: 'Predictive Support',
    description: 'Anticipates customer needs before they ask',
    color: 'navy',
    details: [
      'Proactive issue detection',
      'Anticipates common questions',
      'Prevents problems before they occur',
      'Smart notification timing',
    ],
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
      </svg>
    ),
    title: 'Industry Specific',
    description: 'E-commerce, SaaS, Logistics & more - tailored for you',
    color: 'charcoal',
    details: [
      'Pre-built industry templates',
      'Specialized vocabulary',
      'Industry-specific workflows',
      'Custom variant selection',
    ],
  },
];

const colorClasses = {
  teal: {
    bg: 'bg-teal-500/10',
    text: 'text-teal-400',
    border: 'border-teal-500/30',
    glow: 'hover:shadow-teal-500/10',
    badge: 'bg-teal-500/20 text-teal-400',
  },
  navy: {
    bg: 'bg-navy-500/10',
    text: 'text-navy-300',
    border: 'border-navy-500/30',
    glow: 'hover:shadow-navy-500/10',
    badge: 'bg-navy-500/20 text-navy-300',
  },
  charcoal: {
    bg: 'bg-charcoal-500/10',
    text: 'text-charcoal-300',
    border: 'border-charcoal-500/30',
    glow: 'hover:shadow-charcoal-500/10',
    badge: 'bg-charcoal-500/20 text-charcoal-300',
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
    <section className="relative bg-gradient-to-b from-navy-900 to-background-secondary py-20 md:py-32 overflow-hidden">
      {/* Background Effect */}
      <div className="absolute inset-0">
        <div className="absolute bottom-0 left-1/3 w-96 h-96 bg-gold-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-5xl font-bold text-white mb-6">
            Why Choose <span className="text-gradient">PARWA</span>?
          </h2>
          <p className="text-lg text-white/60 max-w-2xl mx-auto">
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
                className={`card p-8 transition-all duration-500 cursor-pointer ${
                  hoveredIndex === index
                    ? `border ${colors.border} shadow-xl ${colors.glow} -translate-y-2`
                    : 'hover:border-white/20'
                }`}
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
              >
                {/* Icon */}
                <div className={`w-14 h-14 rounded-xl ${colors.bg} flex items-center justify-center mb-6 transition-transform duration-300 ${hoveredIndex === index ? 'scale-110' : ''}`}>
                  <span className={colors.text}>{feature.icon}</span>
                </div>

                {/* Title */}
                <h3 className="text-xl font-bold text-white mb-3">
                  {feature.title}
                </h3>

                {/* Description */}
                <p className="text-white/60 mb-6">
                  {feature.description}
                </p>

                {/* Details (shown on hover) */}
                <div
                  className={`overflow-hidden transition-all duration-500 ${
                    hoveredIndex === index ? 'max-h-48 opacity-100' : 'max-h-0 opacity-0'
                  }`}
                >
                  <ul className="space-y-3 pt-6 border-t border-white/10">
                    {feature.details.map((detail, detailIndex) => (
                      <li key={detailIndex} className="flex items-center gap-3 text-sm text-white/70">
                        <svg className={`w-4 h-4 ${colors.text} flex-shrink-0`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
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

        {/* Industry Tags */}
        <div className="mt-16 text-center">
          <p className="text-white/50 mb-6">
            Powered by advanced AI that learns and adapts to your business
          </p>
          <div className="flex justify-center gap-4 flex-wrap">
            {industries.map((industry) => (
              <span
                key={industry.name}
                className={`px-5 py-2.5 rounded-full text-sm font-semibold border ${
                  industry.color === 'teal' ? 'bg-teal-500/10 text-teal-400 border-teal-500/20' :
                  industry.color === 'navy' ? 'bg-navy-500/10 text-navy-300 border-navy-500/20' :
                  industry.color === 'orange' ? 'bg-orange-500/10 text-orange-400 border-orange-500/20' :
                  'bg-gold-500/10 text-gold-400 border-gold-500/20'
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
