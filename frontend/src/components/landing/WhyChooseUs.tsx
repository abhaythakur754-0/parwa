'use client';

import { useState, useEffect, useRef } from 'react';

/**
 * WhyChooseUs Component
 * 
 * Dark premium cards showing WHAT Jarvis does.
 * Three feature cards with hover animations.
 * NO emojis - using SVG icons.
 * 
 * Features:
 * - Scroll-triggered stagger animations
 * - Touch-friendly hover states for mobile
 * - Responsive grid layout
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
      <svg className="w-6 h-6 sm:w-8 sm:h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
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
      <svg className="w-6 h-6 sm:w-8 sm:h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
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
      <svg className="w-6 h-6 sm:w-8 sm:h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
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
  const [isInView, setIsInView] = useState(false);
  const [visibleCards, setVisibleCards] = useState<number[]>([]);
  const sectionRef = useRef<HTMLElement>(null);

  // Intersection Observer for scroll-triggered animation
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsInView(entry.isIntersecting);
      },
      { threshold: 0.1 }
    );

    if (sectionRef.current) {
      observer.observe(sectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  // Stagger card animations
  useEffect(() => {
    if (!isInView) return;
    
    features.forEach((_, index) => {
      setTimeout(() => {
        setVisibleCards(prev => [...prev, index]);
      }, 150 * (index + 1));
    });
  }, [isInView]);

  return (
    <section 
      ref={sectionRef}
      className={`relative bg-gradient-to-b from-navy-900 to-background-secondary py-12 sm:py-16 md:py-20 lg:py-32 overflow-hidden transition-opacity duration-700 ${isInView ? 'opacity-100' : 'opacity-0'}`}
    >
      {/* Background Effect */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute bottom-0 left-1/3 w-64 sm:w-96 h-64 sm:h-96 bg-gold-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className={`text-center mb-10 sm:mb-16 transition-all duration-700 ${isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-4 sm:mb-6">
            Why Choose <span className="text-gradient">PARWA</span>?
          </h2>
          <p className="text-base sm:text-lg text-white/60 max-w-2xl mx-auto px-4">
            Discover what makes Jarvis different from traditional customer support solutions
          </p>
        </div>

        {/* Feature Cards - Responsive Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
          {features.map((feature, index) => {
            const colors = colorClasses[feature.color];
            const isVisible = visibleCards.includes(index);
            
            return (
              <div
                key={index}
                className={`card p-6 sm:p-8 transition-all duration-500 cursor-pointer hover-lift ${
                  hoveredIndex === index
                    ? `border ${colors.border} shadow-xl ${colors.glow} -translate-y-2`
                    : 'hover:border-white/20'
                } ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
                onTouchStart={() => setHoveredIndex(hoveredIndex === index ? null : index)}
                role="article"
                aria-label={feature.title}
              >
                {/* Icon */}
                <div className={`w-12 h-12 sm:w-14 sm:h-14 rounded-xl ${colors.bg} flex items-center justify-center mb-5 sm:mb-6 transition-transform duration-300 ${hoveredIndex === index ? 'scale-110' : ''}`}>
                  <span className={colors.text}>{feature.icon}</span>
                </div>

                {/* Title */}
                <h3 className="text-lg sm:text-xl font-bold text-white mb-2 sm:mb-3">
                  {feature.title}
                </h3>

                {/* Description */}
                <p className="text-sm sm:text-base text-white/60 mb-4 sm:mb-6">
                  {feature.description}
                </p>

                {/* Details (shown on hover/tap) */}
                <div
                  className={`overflow-hidden transition-all duration-500 ${
                    hoveredIndex === index ? 'max-h-48 opacity-100' : 'max-h-0 opacity-0'
                  }`}
                >
                  <ul className="space-y-2 sm:space-y-3 pt-4 sm:pt-6 border-t border-white/10">
                    {feature.details.map((detail, detailIndex) => (
                      <li key={detailIndex} className="flex items-center gap-2 sm:gap-3 text-xs sm:text-sm text-white/70">
                        <svg className={`w-3.5 h-3.5 sm:w-4 sm:h-4 ${colors.text} flex-shrink-0`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                        {detail}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Tap hint for mobile */}
                <div className="md:hidden text-center mt-4 text-xs text-white/30">
                  {hoveredIndex === index ? 'Tap to collapse' : 'Tap to expand'}
                </div>
              </div>
            );
          })}
        </div>

        {/* Industry Tags */}
        <div className={`mt-10 sm:mt-16 text-center transition-all duration-700 delay-500 ${isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <p className="text-white/50 mb-4 sm:mb-6 text-sm sm:text-base">
            Powered by advanced AI that learns and adapts to your business
          </p>
          <div className="flex justify-center gap-2 sm:gap-4 flex-wrap px-4">
            {industries.map((industry) => (
              <span
                key={industry.name}
                className={`px-3 sm:px-5 py-1.5 sm:py-2.5 rounded-full text-xs sm:text-sm font-semibold border transition-all duration-300 hover:scale-105 ${
                  industry.color === 'teal' ? 'bg-teal-500/10 text-teal-400 border-teal-500/20 hover:bg-teal-500/20' :
                  industry.color === 'navy' ? 'bg-navy-500/10 text-navy-300 border-navy-500/20 hover:bg-navy-500/20' :
                  industry.color === 'orange' ? 'bg-orange-500/10 text-orange-400 border-orange-500/20 hover:bg-orange-500/20' :
                  'bg-gold-500/10 text-gold-400 border-gold-500/20 hover:bg-gold-500/20'
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
