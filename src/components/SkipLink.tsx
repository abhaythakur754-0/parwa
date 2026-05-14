/**
 * PARWA SkipLink Component
 *
 * WCAG 2.1 (2.4.1 Bypass Blocks) requires a mechanism to bypass
 * repeated content (navigation, sidebar, etc.). SkipLink provides
 * an invisible link that becomes visible on focus, allowing keyboard
 * users to jump directly to the main content area.
 *
 * Usage:
 *   <SkipLink />
 *   <nav>...sidebar...</nav>
 *   <main id="main-content">...content...</main>
 */

'use client';

import React from 'react';

interface SkipLinkProps {
  /** The ID of the main content element to skip to (default: "main-content") */
  targetId?: string;
  /** The label text (default: "Skip to main content") */
  label?: string;
}

export function SkipLink({ targetId = 'main-content', label = 'Skip to main content' }: SkipLinkProps) {
  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    const target = document.getElementById(targetId);
    if (target) {
      target.focus();
      target.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLAnchorElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const target = document.getElementById(targetId);
      if (target) {
        target.focus();
        target.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  return (
    <a
      href={`#${targetId}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      data-testid="skip-link"
      className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[9999] focus:px-4 focus:py-2 focus:rounded-lg focus:bg-orange-500 focus:text-[#1A1A1A] focus:font-semibold focus:text-sm focus:shadow-lg focus:shadow-orange-500/25 focus:outline-none focus:ring-2 focus:ring-orange-400 focus:ring-offset-2 focus:ring-offset-[#0A0A0A] transition-all duration-200"
    >
      {label}
    </a>
  );
}

export default SkipLink;
