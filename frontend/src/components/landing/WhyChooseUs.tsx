'use client';

import { useState, useEffect, useRef } from 'react';
import { Shield, HelpCircle, BookOpen, BarChart3, Languages, TrendingUp } from 'lucide-react';

/**
 * WhyChooseUs - Light green theme
 */

const features = [
  {
    icon: <Shield className="w-6 h-6 sm:w-7 sm:h-7" />,
    title: 'Bank-Grade Security',
    description: 'Your data is encrypted end-to-end. GDPR compliant. SOC 2 certified.',
    details: ['End-to-end encryption', 'GDPR compliant', 'SOC 2 Type II certified', 'Regular security audits'],
    color: 'green' as const,
  },
  {
    icon: <HelpCircle className="w-6 h-6 sm:w-7 sm:h-7" />,
    title: 'Asks You When Unsure',
    description: 'Jarvis never guesses wrong. It asks you before making uncertain decisions.',
    details: ['Human-in-the-loop fallback', 'Confidence scoring', 'Escalation protocols', 'Custom approval workflows'],
    color: 'amber' as const,
  },
  {
    icon: <BookOpen className="w-6 h-6 sm:w-7 sm:h-7" />,
    title: 'Learns Your Business',
    description: 'Upload your docs and Jarvis becomes an expert in hours, not months.',
    details: ['Knowledge base ingestion', 'Context-aware responses', 'Continuous learning', 'Multi-format document support'],
    color: 'emerald' as const,
  },
  {
    icon: <BarChart3 className="w-6 h-6 sm:w-7 sm:h-7" />,
    title: 'Real-Time Dashboard',
    description: 'Track ROI, resolution rates, and customer satisfaction live.',
    details: ['Live metrics dashboard', 'Custom report builder', 'CSAT tracking', 'Revenue impact analytics'],
    color: 'green' as const,
  },
  {
    icon: <Languages className="w-6 h-6 sm:w-7 sm:h-7" />,
    title: 'Multi-Language Support',
    description: 'Speak to customers in 50+ languages with native-level accuracy.',
    details: ['50+ languages supported', 'Automatic detection', 'Cultural context awareness', 'Translation quality scoring'],
    color: 'green' as const,
  },
  {
    icon: <TrendingUp className="w-6 h-6 sm:w-7 sm:h-7" />,
    title: 'Scales With You',
    description: '10 or 10,000 tickets — Jarvis handles it all without breaking a sweat.',
    details: ['Unlimited ticket capacity', 'Auto-scaling infrastructure', 'Peak load management', 'Zero downtime SLA'],
    color: 'green' as const,
  },
];

const colorClasses: Record<string, { bg: string; text: string; border: string; hoverBorder: string; glow: string; check: string }> = {
  green: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-gray-200', hoverBorder: 'border-emerald-300', glow: 'hover:shadow-emerald-600/10', check: 'text-emerald-600' },
  amber: { bg: 'bg-amber-50', text: 'text-amber-600', border: 'border-gray-200', hoverBorder: 'border-amber-300', glow: 'hover:shadow-amber-500/8', check: 'text-amber-500' },
  emerald: { bg: 'bg-emerald-50', text: 'text-emerald-600', border: 'border-gray-200', hoverBorder: 'border-emerald-300', glow: 'hover:shadow-emerald-500/8', check: 'text-emerald-500' },
};

export default function WhyChooseUs() {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [isInView, setIsInView] = useState(false);
  const [visibleCards, setVisibleCards] = useState<number[]>([]);
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setIsInView(true); },
      { threshold: 0.1 }
    );
    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!isInView) return;
    features.forEach((_, index) => {
      setTimeout(() => setVisibleCards((prev) => [...prev, index]), 120 * (index + 1));
    });
  }, [isInView]);

  return (
    <section ref={sectionRef} className="relative overflow-hidden bg-gradient-to-b from-white to-[#F0FDF4]">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute bottom-0 left-1/3 w-96 h-96 bg-emerald-200/25 rounded-full blur-[120px]" />
        <div className="absolute top-1/4 right-1/4 w-80 h-80 bg-emerald-200/20 rounded-full blur-[100px]" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div
          className={`text-center mb-8 sm:mb-10 lg:mb-12 transition-all duration-700 ${
            isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
          }`}
        >
          <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-gray-900 mb-4 sm:mb-5">
            Why Businesses Choose <span className="text-gradient">PARWA</span>
          </h2>
          <p className="text-base sm:text-lg text-gray-500 max-w-2xl mx-auto px-4">
            Built for businesses that demand reliability, security, and instant results.
          </p>
          {/* Trust indicators row */}
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2 sm:gap-3">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-300/50 text-xs sm:text-sm font-semibold text-emerald-700">
              💎 99.9% Uptime SLA
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-xs sm:text-sm font-semibold text-emerald-600">
              🔒 SOC 2 Certified
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-sky-50 border border-sky-200 text-xs sm:text-sm font-semibold text-sky-600">
              🛡️ GDPR Compliant
            </span>
            <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-xs sm:text-sm font-semibold text-amber-600">
              🔐 Bank-Grade Encryption
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 sm:gap-6">
          {features.map((feature, index) => {
            const colors = colorClasses[feature.color];
            const isVisible = visibleCards.includes(index);
            const isHovered = hoveredIndex === index;

            return (
              <div
                key={index}
                className={`rounded-xl border p-6 sm:p-7 transition-all duration-500 cursor-pointer group bg-white ${
                  isHovered
                    ? `${colors.hoverBorder} shadow-xl ${colors.glow} -translate-y-2`
                    : `${colors.border} hover:border-gray-300 hover:-translate-y-1.5 hover:shadow-lg hover:shadow-gray-900/5`
                } ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
                style={{ transitionDelay: isVisible ? '0ms' : `${index * 80}ms` }}
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
                onTouchStart={() => setHoveredIndex(hoveredIndex === index ? null : index)}
                role="article"
                aria-label={feature.title}
              >
                <div className={`w-12 h-12 sm:w-13 sm:h-13 rounded-xl ${colors.bg} flex items-center justify-center mb-5 transition-all duration-300 ${isHovered ? 'scale-110' : ''}`}>
                  <span className={colors.text}>{feature.icon}</span>
                </div>
                <h3 className="text-base sm:text-lg font-bold text-gray-900 mb-2">{feature.title}</h3>
                <p className="text-sm text-gray-500 mb-5 leading-relaxed">{feature.description}</p>
                <div className={`overflow-hidden transition-all duration-500 ${isHovered ? 'max-h-40 opacity-100' : 'max-h-0 opacity-0'}`}>
                  <ul className="space-y-2 pt-4 border-t border-gray-100">
                    {feature.details.map((detail, i) => (
                      <li key={i} className="flex items-center gap-2 text-xs sm:text-sm text-gray-600">
                        <div className={`w-1 h-1 rounded-full ${colors.check} flex-shrink-0`} />
                        {detail}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="sm:hidden text-center mt-4 text-xs text-gray-400">
                  {isHovered ? 'Tap to collapse' : 'Tap to learn more'}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
