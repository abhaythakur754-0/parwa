'use client';

import React from 'react';

interface SkipLinkProps {
  targetId: string;
  label?: string;
  className?: string;
}

/**
 * SkipLink component for keyboard navigation accessibility.
 * Allows users to skip directly to main content, bypassing navigation.
 * WCAG 2.1 Requirement: Bypass Blocks (Level A)
 */
export const SkipLink: React.FC<SkipLinkProps> = ({
  targetId,
  label = 'Skip to main content',
  className = '',
}) => {
  const handleClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    const target = document.getElementById(targetId);

    if (target) {
      // Set tabindex to make it focusable if not already
      if (!target.hasAttribute('tabindex')) {
        target.setAttribute('tabindex', '-1');
      }

      // Focus the target element
      target.focus();

      // Smooth scroll to the element
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLAnchorElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      const target = document.getElementById(targetId);

      if (target) {
        if (!target.hasAttribute('tabindex')) {
          target.setAttribute('tabindex', '-1');
        }
        target.focus();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  };

  return (
    <a
      href={`#${targetId}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={`
        skip-link
        sr-only
        focus:not-sr-only
        focus:absolute
        focus:top-4
        focus:left-4
        focus:z-[9999]
        focus:px-4
        focus:py-2
        focus:bg-primary
        focus:text-primary-foreground
        focus:rounded-md
        focus:shadow-lg
        focus:outline-none
        focus:ring-2
        focus:ring-ring
        focus:ring-offset-2
        ${className}
      `}
      data-skip-link="true"
    >
      {label}
    </a>
  );
};

/**
 * SkipLinkContainer - Renders multiple skip links
 */
interface SkipLinkItem {
  targetId: string;
  label: string;
}

interface SkipLinkContainerProps {
  links: SkipLinkItem[];
  className?: string;
}

export const SkipLinkContainer: React.FC<SkipLinkContainerProps> = ({
  links,
  className = '',
}) => {
  return (
    <div className={`skip-links-container ${className}`}>
      {links.map((link, index) => (
        <SkipLink
          key={index}
          targetId={link.targetId}
          label={link.label}
        />
      ))}
    </div>
  );
};

export default SkipLink;
