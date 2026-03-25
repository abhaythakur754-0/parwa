'use client';

import React from 'react';
import { useTheme } from '@/hooks/useTheme';
import { Theme } from '@/lib/theme';

interface ThemeToggleProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

/**
 * ThemeToggle - Button to switch between light, dark, and system themes
 * WCAG 2.1 compliant with keyboard accessibility and ARIA labels
 */
export const ThemeToggle: React.FC<ThemeToggleProps> = ({
  className = '',
  size = 'md',
  showLabel = false,
}) => {
  const { theme, effectiveTheme, setTheme, toggleTheme } = useTheme();

  const sizeClasses = {
    sm: 'w-8 h-8',
    md: 'w-11 h-11',
    lg: 'w-14 h-14',
  };

  const iconSizes = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6',
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      toggleTheme();
    }
  };

  const cycleTheme = () => {
    const themes: Theme[] = ['light', 'dark', 'system'];
    const currentIndex = themes.indexOf(theme);
    const nextIndex = (currentIndex + 1) % themes.length;
    setTheme(themes[nextIndex]);
  };

  const getThemeLabel = () => {
    switch (theme) {
      case 'light':
        return 'Light theme';
      case 'dark':
        return 'Dark theme';
      case 'system':
        return 'System theme';
    }
  };

  return (
    <button
      type="button"
      onClick={cycleTheme}
      onKeyDown={handleKeyDown}
      className={`
        inline-flex items-center justify-center gap-2
        ${sizeClasses[size]}
        rounded-md
        bg-transparent
        hover:bg-accent
        focus:outline-none
        focus:ring-2
        focus:ring-ring
        focus:ring-offset-2
        focus:ring-offset-background
        transition-colors
        ${className}
      `}
      aria-label={`Current: ${getThemeLabel()}. Click to change theme.`}
      title={getThemeLabel()}
    >
      {/* Sun icon (light mode) */}
      <span
        className={`
          ${iconSizes[size]}
          transition-all duration-300
          ${
            effectiveTheme === 'dark'
              ? 'rotate-90 scale-0 opacity-0 absolute'
              : 'rotate-0 scale-100 opacity-100'
          }
        `}
      >
        <svg
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          className={iconSizes[size]}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
          />
        </svg>
      </span>

      {/* Moon icon (dark mode) */}
      <span
        className={`
          ${iconSizes[size]}
          transition-all duration-300
          ${
            effectiveTheme === 'dark'
              ? 'rotate-0 scale-100 opacity-100'
              : '-rotate-90 scale-0 opacity-0 absolute'
          }
        `}
      >
        <svg
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          className={iconSizes[size]}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
          />
        </svg>
      </span>

      {/* System indicator */}
      {theme === 'system' && (
        <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-blue-500 rounded-full border border-background" />
      )}

      {/* Optional label */}
      {showLabel && (
        <span className="ml-1 text-sm font-medium">
          {effectiveTheme === 'dark' ? 'Dark' : 'Light'}
        </span>
      )}
    </button>
  );
};

/**
 * ThemeToggleCompact - Minimal toggle without system option
 */
export const ThemeToggleCompact: React.FC<Omit<ThemeToggleProps, 'showLabel'>> = ({
  className = '',
  size = 'md',
}) => {
  const { effectiveTheme, toggleTheme } = useTheme();

  const sizeClasses = {
    sm: 'w-8 h-8',
    md: 'w-11 h-11',
    lg: 'w-14 h-14',
  };

  const iconSizes = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6',
  };

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`
        inline-flex items-center justify-center
        ${sizeClasses[size]}
        rounded-md
        bg-transparent
        hover:bg-accent
        focus:outline-none
        focus:ring-2
        focus:ring-ring
        focus:ring-offset-2
        focus:ring-offset-background
        transition-all
        ${className}
      `}
      aria-label={`Switch to ${effectiveTheme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {effectiveTheme === 'dark' ? (
        <svg
          className={iconSizes[size]}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
          />
        </svg>
      ) : (
        <svg
          className={iconSizes[size]}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
          />
        </svg>
      )}
    </button>
  );
};

export default ThemeToggle;
