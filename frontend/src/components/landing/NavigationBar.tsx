'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

/**
 * NavigationBar Component
 * 
 * Light premium navigation bar with green accents.
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
    { name: 'Pricing', href: '/pricing' },
    { name: 'ROI Calculator', href: '/roi-calculator' },
    { name: 'Try Jarvis', href: '/jarvis' },
  ];

  return (
    <nav 
      className={`sticky top-0 z-50 transition-all duration-500 ${
        isScrolled 
          ? 'bg-white/95 backdrop-blur-2xl shadow-lg shadow-gray-900/5 border-b border-gray-200' 
          : 'bg-white/70 backdrop-blur-xl border-b border-transparent'
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
            <div className="relative w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-br from-emerald-600 to-emerald-700 flex items-center justify-center shadow-lg shadow-emerald-600/25 group-hover:shadow-emerald-600/40 transition-all duration-500 group-hover:scale-105">
              <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-emerald-400/20 to-transparent opacity-0 group-hover:opacity:100 transition-opacity duration-500" />
              <svg className="w-5 h-5 sm:w-5 sm:h-5 text-white relative z-10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
              </svg>
            </div>
            <span className="text-lg sm:text-xl font-bold text-gray-900 group-hover:text-emerald-700 transition-colors duration-500 tracking-tight">
              PARWA
            </span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => (
              <Link
                key={link.name}
                href={link.href}
                className="px-3.5 lg:px-4 py-2 text-gray-600 hover:text-gray-900 text-sm font-medium transition-all duration-300 rounded-xl hover:bg-gray-100 focus-visible-ring"
              >
                {link.name}
              </Link>
            ))}
          </div>

          {/* Login + Social Proof - Desktop */}
          <div className="hidden md:flex items-center gap-4">
            <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-300/50">
              <div className="flex -space-x-1.5">
                <div className="w-5 h-5 rounded-full bg-emerald-300/50 border-2 border-white" />
                <div className="w-5 h-5 rounded-full bg-emerald-400/50 border-2 border-white" />
                <div className="w-5 h-5 rounded-full bg-emerald-200/50 border-2 border-white" />
              </div>
              <span className="text-xs text-gray-500 font-medium">2,400+ businesses trust us</span>
            </div>
            <Link
              href="/login"
              className="bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-500 shadow-lg shadow-emerald-600/25 hover:shadow-emerald-600/40 hover:-translate-y-0.5 focus-visible-ring badge-pulse"
            >
              🔥 Join 2,400+ businesses
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="md:hidden p-2.5 rounded-xl text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-all duration-300 focus-visible-ring"
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
          <div className="py-5 border-t border-gray-200">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2 px-4 py-2 mb-2">
                <div className="flex -space-x-1.5">
                  <div className="w-5 h-5 rounded-full bg-emerald-300/50 border-2 border-white" />
                  <div className="w-5 h-5 rounded-full bg-emerald-400/50 border-2 border-white" />
                  <div className="w-5 h-5 rounded-full bg-emerald-200/50 border-2 border-white" />
                </div>
                <span className="text-xs text-gray-500 font-medium">2,400+ businesses trust us</span>
              </div>
              {navLinks.map((link, index) => (
                  <Link
                    key={link.name}
                    href={link.href}
                    className={`px-4 py-3.5 text-gray-600 hover:text-gray-900 text-sm font-medium rounded-xl hover:bg-gray-100 transition-all duration-500 focus-visible-ring ${
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
                className={`mt-3 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white px-5 py-3.5 rounded-xl text-sm font-semibold text-center transition-all duration-500 focus-visible-ring ${
                  isMobileMenuOpen ? 'translate-x-0 opacity-100' : '-translate-x-6 opacity-0'
                }`}
                style={{ transitionDelay: isMobileMenuOpen ? '240ms' : '0ms' }}
                onClick={() => setIsMobileMenuOpen(false)}
              >
                Login
              </Link>
            </div>
          </div>
        </div>
      </div>

      {isMobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-gray-900/30 backdrop-blur-sm md:hidden z-[-1] transition-opacity duration-300"
          onClick={() => setIsMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}
    </nav>
  );
}
