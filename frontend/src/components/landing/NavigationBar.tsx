'use client';

import { useState } from 'react';
import Link from 'next/link';

/**
 * NavigationBar Component
 * 
 * Top navigation bar with:
 * - Logo (PARWA)
 * - Navigation links: Home, Models, ROI, Jarvis Chatbot
 * - Login button (signup is inside login page)
 * 
 * Color scheme based on Frontend Docs:
 * - Teal accent for active/hover states
 * 
 * Based on ONBOARDING_SPEC.md v2.0 Section 2.3.1
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
    <nav className="sticky top-0 z-50 bg-white border-b border-secondary-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 group">
            <span className="text-2xl">🤖</span>
            <span className="text-xl font-bold text-secondary-900 group-hover:text-teal-600 transition-colors">
              PARWA
            </span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-8">
            {navLinks.map((link) => (
              link.onClick ? (
                <button
                  key={link.name}
                  onClick={link.onClick}
                  className="text-secondary-600 hover:text-teal-600 font-medium transition-colors"
                >
                  {link.name}
                </button>
              ) : (
                <Link
                  key={link.name}
                  href={link.href}
                  className="text-secondary-600 hover:text-teal-600 font-medium transition-colors"
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
              className="bg-teal-600 hover:bg-teal-700 text-white px-5 py-2.5 rounded-lg font-medium transition-colors"
            >
              Login
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="md:hidden p-2 rounded-lg text-secondary-600 hover:bg-secondary-100"
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
          <div className="md:hidden py-4 border-t border-secondary-200">
            <div className="flex flex-col gap-4">
              {navLinks.map((link) => (
                link.onClick ? (
                  <button
                    key={link.name}
                    onClick={() => {
                      link.onClick?.();
                      setIsMobileMenuOpen(false);
                    }}
                    className="text-left text-secondary-600 hover:text-teal-600 font-medium py-2"
                  >
                    {link.name}
                  </button>
                ) : (
                  <Link
                    key={link.name}
                    href={link.href}
                    className="text-secondary-600 hover:text-teal-600 font-medium py-2"
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    {link.name}
                  </Link>
                )
              ))}
              <Link
                href="/login"
                className="bg-teal-600 hover:bg-teal-700 text-white px-5 py-2.5 rounded-lg font-medium text-center mt-2 transition-colors"
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
