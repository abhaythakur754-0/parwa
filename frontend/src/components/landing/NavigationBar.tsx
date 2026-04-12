'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

/**
 * NavigationBar Component
 *
 * Dark premium navigation bar with orange accents — matches the
 * PARWA dark theme (#0D0D0D/#1A1A1A + #FF7F11 orange).
 */

export default function NavigationBar() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isMobileMenuOpen) setIsMobileMenuOpen(false);
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isMobileMenuOpen]);

  useEffect(() => {
    if (isMobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isMobileMenuOpen]);

  const navLinks = [
    { name: 'Home', href: '/' },
    { name: 'Models', href: '/models' },
    { name: 'ROI Calculator', href: '/roi-calculator' },
    { name: 'Try Jarvis', href: '/jarvis' },
  ];

  return (
    <nav
      className={`sticky top-0 z-50 transition-all duration-500 ${
        isScrolled
          ? 'bg-[#0D0D0D]/95 backdrop-blur-2xl shadow-lg shadow-black/30 border-b border-white/[0.06]'
          : 'bg-[#0D0D0D]/70 backdrop-blur-xl border-b border-transparent'
      }`}
      role="navigation"
      aria-label="Main navigation"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16 sm:h-18">
          {/* Logo */}
          <Link
            href="/"
            className="flex items-center gap-2.5 sm:gap-3 group focus-visible-ring rounded-xl px-2 py-1.5 -ml-2"
            aria-label="PARWA home"
          >
            <div className="relative w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-500/25 group-hover:shadow-orange-500/40 transition-all duration-500 group-hover:scale-105">
              <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-orange-400/20 to-transparent opacity-0 group-hover:opacity:100 transition-opacity duration-500" />
              <svg className="w-5 h-5 sm:w-5 sm:h-5 text-white relative z-10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
              </svg>
            </div>
            <span className="text-lg sm:text-xl font-bold text-white group-hover:text-orange-400 transition-colors duration-500 tracking-tight">
              PARWA
            </span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => (
              <Link
                key={link.name}
                href={link.href}
                className="px-3.5 lg:px-4 py-2 text-gray-400 hover:text-white text-sm font-medium transition-all duration-300 rounded-xl hover:bg-white/[0.06] focus-visible-ring"
              >
                {link.name}
              </Link>
            ))}
          </div>

          {/* Login + Social Proof - Desktop */}
          <div className="hidden md:flex items-center gap-4">
            <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/20">
              <div className="flex -space-x-1.5">
                <div className="w-5 h-5 rounded-full bg-orange-400/30 border-2 border-[#0D0D0D]" />
                <div className="w-5 h-5 rounded-full bg-orange-500/30 border-2 border-[#0D0D0D]" />
                <div className="w-5 h-5 rounded-full bg-orange-300/30 border-2 border-[#0D0D0D]" />
              </div>
              <span className="text-xs text-gray-400 font-medium">2,400+ businesses trust us</span>
            </div>
            <Link
              href="/login"
              className="bg-gradient-to-r from-orange-600 to-orange-500 hover:from-orange-500 hover:to-orange-400 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-500 shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40 hover:-translate-y-0.5 focus-visible-ring"
            >
              Get Started
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="md:hidden p-2.5 rounded-xl text-gray-400 hover:text-white hover:bg-white/[0.06] transition-all duration-300 focus-visible-ring"
            aria-label={isMobileMenuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={isMobileMenuOpen}
            aria-controls="mobile-menu"
          >
            <svg className="w-5 h-5 transition-transform duration-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {isMobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile Menu */}
        <div
          id="mobile-menu"
          className={`md:hidden overflow-hidden transition-all duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] ${
            isMobileMenuOpen ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'
          }`}
          aria-hidden={!isMobileMenuOpen}
        >
          <div className="py-5 border-t border-white/[0.06]">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2 px-4 py-2 mb-2">
                <div className="flex -space-x-1.5">
                  <div className="w-5 h-5 rounded-full bg-orange-400/30 border-2 border-[#0D0D0D]" />
                  <div className="w-5 h-5 rounded-full bg-orange-500/30 border-2 border-[#0D0D0D]" />
                  <div className="w-5 h-5 rounded-full bg-orange-300/30 border-2 border-[#0D0D0D]" />
                </div>
                <span className="text-xs text-gray-500 font-medium">2,400+ businesses trust us</span>
              </div>
              {navLinks.map((link, index) => (
                  <Link
                    key={link.name}
                    href={link.href}
                    className={`px-4 py-3.5 text-gray-400 hover:text-white text-sm font-medium rounded-xl hover:bg-white/[0.06] transition-all duration-500 focus-visible-ring ${
                      isMobileMenuOpen ? 'translate-x-0 opacity-100' : '-translate-x-6 opacity-0'
                    }`}
                    style={{ transitionDelay: isMobileMenuOpen ? `${index * 60}ms` : '0ms' }}
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    {link.name}
                  </Link>
              ))}
              <Link
                href="/login"
                className={`mt-3 bg-gradient-to-r from-orange-600 to-orange-500 hover:from-orange-500 hover:to-orange-400 text-white px-5 py-3.5 rounded-xl text-sm font-semibold text-center transition-all duration-500 focus-visible-ring ${
                  isMobileMenuOpen ? 'translate-x-0 opacity-100' : '-translate-x-6 opacity-0'
                }`}
                style={{ transitionDelay: isMobileMenuOpen ? '240ms' : '0ms' }}
                onClick={() => setIsMobileMenuOpen(false)}
              >
                Get Started
              </Link>
            </div>
          </div>
        </div>
      </div>

      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm md:hidden z-[-1] transition-opacity duration-300"
          onClick={() => setIsMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}
    </nav>
  );
}
