'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { FocusTrap } from './focus-trap';
import { useMediaQuery } from '@/hooks/useMediaQuery';

interface NavItem {
  label: string;
  href: string;
  icon?: React.ReactNode;
  children?: NavItem[];
}

interface MobileNavProps {
  items: NavItem[];
  logo?: React.ReactNode;
  onNavigate?: (href: string) => void;
  className?: string;
}

/**
 * MobileNav - Mobile-first responsive navigation
 * WCAG 2.1 compliant with proper focus management
 * Touch targets minimum 44x44px
 */
export const MobileNav: React.FC<MobileNavProps> = ({
  items,
  logo,
  onNavigate,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [expandedItems, setExpandedItems] = useState<string[]>([]);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  // Close menu on larger screens
  const isDesktop = useMediaQuery('(min-width: 1024px)');

  useEffect(() => {
    if (isDesktop && isOpen) {
      setIsOpen(false);
    }
  }, [isDesktop, isOpen]);

  // Prevent body scroll when menu is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const toggleMenu = useCallback(() => {
    setIsOpen(prev => !prev);
  }, []);

  const closeMenu = useCallback(() => {
    setIsOpen(false);
    menuButtonRef.current?.focus();
  }, []);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeMenu();
      }
    },
    [closeMenu]
  );

  const toggleSubmenu = useCallback((label: string) => {
    setExpandedItems(prev =>
      prev.includes(label)
        ? prev.filter(item => item !== label)
        : [...prev, label]
    );
  }, []);

  const handleNavigate = useCallback(
    (href: string) => {
      if (onNavigate) {
        onNavigate(href);
      }
      closeMenu();
    },
    [onNavigate, closeMenu]
  );

  return (
    <div className={`mobile-nav ${className}`}>
      {/* Menu button - 44px minimum touch target */}
      <button
        ref={menuButtonRef}
        type="button"
        onClick={toggleMenu}
        onKeyDown={handleKeyDown}
        className="
          flex items-center justify-center
          w-11 h-11
          rounded-md
          bg-transparent
          hover:bg-accent
          focus:outline-none
          focus:ring-2
          focus:ring-ring
          focus:ring-offset-2
          transition-colors
        "
        aria-expanded={isOpen}
        aria-controls="mobile-menu"
        aria-label={isOpen ? 'Close menu' : 'Open menu'}
      >
        {/* Hamburger/X icon */}
        <span className="relative w-6 h-6">
          <span
            className={`
              absolute left-0 w-6 h-0.5 bg-current transition-all duration-200
              ${isOpen ? 'top-[11px] rotate-45' : 'top-1'}
            `}
          />
          <span
            className={`
              absolute left-0 top-[11px] w-6 h-0.5 bg-current transition-all duration-200
              ${isOpen ? 'opacity-0' : 'opacity-100'}
            `}
          />
          <span
            className={`
              absolute left-0 w-6 h-0.5 bg-current transition-all duration-200
              ${isOpen ? 'top-[11px] -rotate-45' : 'top-[21px]'}
            `}
          />
        </span>
      </button>

      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={closeMenu}
          aria-hidden="true"
        />
      )}

      {/* Slide-out drawer */}
      <FocusTrap active={isOpen} onEscape={closeMenu}>
        <div
          id="mobile-menu"
          className={`
            fixed top-0 left-0 h-full w-80 max-w-[85vw]
            bg-background shadow-xl z-50
            transform transition-transform duration-300 ease-in-out
            ${isOpen ? 'translate-x-0' : '-translate-x-full'}
            lg:hidden
          `}
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
        >
          {/* Drawer header */}
          <div className="flex items-center justify-between p-4 border-b">
            {logo && <div className="logo">{logo}</div>}
            <button
              type="button"
              onClick={closeMenu}
              className="
                flex items-center justify-center
                w-11 h-11
                rounded-md
                hover:bg-accent
                focus:outline-none
                focus:ring-2
                focus:ring-ring
              "
              aria-label="Close menu"
            >
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Navigation items */}
          <nav className="p-4 overflow-y-auto h-[calc(100%-80px)]">
            <ul className="space-y-1" role="menu">
              {items.map(item => (
                <li key={item.label} role="none">
                  {item.children ? (
                    // Item with submenu
                    <div>
                      <button
                        type="button"
                        onClick={() => toggleSubmenu(item.label)}
                        className="
                          w-full flex items-center justify-between
                          min-h-[44px] px-4 py-3
                          rounded-md
                          hover:bg-accent
                          focus:outline-none
                          focus:ring-2
                          focus:ring-ring
                          focus:ring-offset-2
                          text-left
                        "
                        aria-expanded={expandedItems.includes(item.label)}
                        role="menuitem"
                      >
                        <span className="flex items-center gap-3">
                          {item.icon}
                          {item.label}
                        </span>
                        <svg
                          className={`
                            w-5 h-5 transition-transform duration-200
                            ${expandedItems.includes(item.label) ? 'rotate-180' : ''}
                          `}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M19 9l-7 7-7-7"
                          />
                        </svg>
                      </button>
                      {/* Submenu */}
                      {expandedItems.includes(item.label) && (
                        <ul className="ml-4 mt-1 space-y-1" role="menu">
                          {item.children.map(child => (
                            <li key={child.label} role="none">
                              <a
                                href={child.href}
                                onClick={e => {
                                  e.preventDefault();
                                  handleNavigate(child.href);
                                }}
                                className="
                                  block
                                  min-h-[44px] px-4 py-3
                                  rounded-md
                                  hover:bg-accent
                                  focus:outline-none
                                  focus:ring-2
                                  focus:ring-ring
                                  focus:ring-offset-2
                                "
                                role="menuitem"
                              >
                                <span className="flex items-center gap-3">
                                  {child.icon}
                                  {child.label}
                                </span>
                              </a>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ) : (
                    // Simple navigation item
                    <a
                      href={item.href}
                      onClick={e => {
                        e.preventDefault();
                        handleNavigate(item.href);
                      }}
                      className="
                        block
                        min-h-[44px] px-4 py-3
                        rounded-md
                        hover:bg-accent
                        focus:outline-none
                        focus:ring-2
                        focus:ring-ring
                        focus:ring-offset-2
                      "
                      role="menuitem"
                    >
                      <span className="flex items-center gap-3">
                        {item.icon}
                        {item.label}
                      </span>
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </FocusTrap>
    </div>
  );
};

export default MobileNav;
