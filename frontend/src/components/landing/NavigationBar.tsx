'use client';

import { useState } from 'react';
import Link from 'next/link';

/**
 * NavigationBar Component
 * 
 * Dark transparent navigation bar with:
 * - PARWA logo (SVG icon, NO emoji)
 * - Navigation links: Home, Models, ROI, Jarvis Chatbot
 * - Login button
 */

interface NavigationBarProps {
  onOpenJarvis?: () => void;
}

export default function NavigationBar({ onOpenJarvis }: NavigationBarProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const navLinks = [
    { name: 'Home', href: '/' },
    { name: 'Models', href: '/models' },
    { name: 'ROI', href: '/roi' },
    { name: 'Jarvis Chatbot', href: '#', onClick: onOpenJarvis },
  ];

  return (
    <nav className="sticky top-0 z-50 bg-navy-900/80 backdrop-blur-xl border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-teal-500 to-teal-600 flex items-center justify-center shadow-lg shadow-teal-500/20 group-hover:shadow-teal-500/40 transition-shadow">
              <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <span className="text-xl font-bold text-white group-hover:text-teal-400 transition-colors">
              PARWA
            </span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => (
              link.onClick ? (
                <button
                  key={link.name}
                  onClick={link.onClick}
                  className="px-4 py-2 text-white/70 hover:text-white font-medium transition-colors rounded-lg hover:bg-white/5"
                >
                  {link.name}
                </button>
              ) : (
                <Link
                  key={link.name}
                  href={link.href}
                  className="px-4 py-2 text-white/70 hover:text-white font-medium transition-colors rounded-lg hover:bg-white/5"
                >
                  {link.name}
                </Link>
              )
            ))}
          </div>

          {/* Login Button */}
          <div className="hidden md:flex items-center gap-4">
            <Link
              href="/login"
              className="bg-teal-600 hover:bg-teal-500 text-white px-5 py-2.5 rounded-lg font-semibold transition-all duration-300 shadow-lg shadow-teal-500/20 hover:shadow-teal-500/40 hover:-translate-y-0.5"
            >
              Login
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="md:hidden p-2 rounded-lg text-white/70 hover:text-white hover:bg-white/5 transition-colors"
            aria-label="Toggle menu"
          >
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              {isMobileMenuOpen ? (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              ) : (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <div className="md:hidden py-4 border-t border-white/10">
            <div className="flex flex-col gap-1">
              {navLinks.map((link) => (
                link.onClick ? (
                  <button
                    key={link.name}
                    onClick={() => {
                      link.onClick?.();
                      setIsMobileMenuOpen(false);
                    }}
                    className="text-left px-4 py-3 text-white/70 hover:text-white font-medium rounded-lg hover:bg-white/5 transition-colors"
                  >
                    {link.name}
                  </button>
                ) : (
                  <Link
                    key={link.name}
                    href={link.href}
                    className="px-4 py-3 text-white/70 hover:text-white font-medium rounded-lg hover:bg-white/5 transition-colors"
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    {link.name}
                  </Link>
                )
              ))}
              <Link
                href="/login"
                className="mt-4 bg-teal-600 hover:bg-teal-500 text-white px-5 py-3 rounded-lg font-semibold text-center transition-all duration-300"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                Login
              </Link>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
