'use client';

import { useState, useEffect, useRef } from 'react';
import { Shield, HelpCircle, BookOpen, BarChart3, Languages, TrendingUp } from 'lucide-react';

/**
 * WhyChooseUs - Dark premium emerald theme
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
  green: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-white/10', hoverBorder: 'border-emerald-500/30', glow: 'hover:shadow-emerald-500/20', check: 'bg-emerald-400' },
  amber: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-white/10', hoverBorder: 'border-amber-500/30', glow: 'hover:shadow-amber-500/15', check: 'bg-amber-400' },
  emerald: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-white/10', hoverBorder: 'border-emerald-500/30', glow: 'hover:shadow-emerald-500/15', check: 'bg-emerald-400' },
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
    <section ref={sectionRef} className="relative overflow-hidden bg-gradient-to-b from-[#064E3B] to-[#022C22]">
      {/* Ambient glow orbs */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute bottom-0 left-1/3 w-96 h-96 bg-emerald-500/12 rounded-full blur-[140px]" />
        <div className="absolute top-1/4 right-1/4 w-80 h-80 bg-emerald-600/10 rounded-full blur-[120px]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[28rem] h-[28rem] bg-emerald-500/6 rounded-full blur-[160px]" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div
          className={`text-center mb-8 sm:mb-10 lg:mb-12 transition-all duration-700 ${
            isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
          }`}
        >
          <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-4 sm:mb-5">
            Why Businesses Choose <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">PARWA</span>
          </h2>
          <p className="text-base sm:text-lg text-gray-400 max-w-2xl mx-auto px-4">
            Built for businesses that demand reliability, security, and instant results.
          </p>
          {/* Trust indicators row */}
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2 sm:gap-3">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-xs sm:text-sm font-semibold text-emerald-300">
              💎 99.9% Uptime SLA
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/25 text-xs sm:text-sm font-semibold text-emerald-300">
              🔒 SOC 2 Certified
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-sky-500/10 border border-sky-500/30 text-xs sm:text-sm font-semibold text-sky-300">
              🛡️ GDPR Compliant
            </span>
            <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-xs sm:text-sm font-semibold text-amber-300">
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
                className={`rounded-xl border p-6 sm:p-7 transition-all duration-500 cursor-pointer group bg-white/[0.05] backdrop-blur-sm ${
                  isHovered
                    ? `${colors.hoverBorder} shadow-xl ${colors.glow} -translate-y-2`
                    : `${colors.border} hover:border-white/20 hover:-translate-y-1.5 hover:shadow-lg hover:shadow-black/20`
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
                <h3 className="text-base sm:text-lg font-bold text-white mb-2">{feature.title}</h3>
                <p className="text-sm text-gray-400 mb-5 leading-relaxed">{feature.description}</p>
                <div className={`overflow-hidden transition-all duration-500 ${isHovered ? 'max-h-40 opacity-100' : 'max-h-0 opacity-0'}`}>
                  <ul className="space-y-2 pt-4 border-t border-white/10">
                    {feature.details.map((detail, i) => (
                      <li key={i} className="flex items-center gap-2 text-xs sm:text-sm text-gray-300">
                        <div className={`w-1 h-1 rounded-full ${colors.check} flex-shrink-0`} />
                        {detail}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="sm:hidden text-center mt-4 text-xs text-gray-500">
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
