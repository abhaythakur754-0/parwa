'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Theme,
  getSystemTheme,
  getStoredTheme,
  setStoredTheme,
  getEffectiveTheme,
  applyTheme,
  subscribeToSystemTheme,
} from '@/lib/theme';

interface UseThemeReturn {
  theme: Theme;
  effectiveTheme: 'light' | 'dark';
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  isDark: boolean;
  isLight: boolean;
  isSystem: boolean;
}

/**
 * Hook for managing theme state
 * Handles system preference sync and local storage persistence
 */
export const useTheme = (): UseThemeReturn => {
  // User's preference (light, dark, or system)
  const [theme, setThemeState] = useState<Theme>('system');

  // Effective theme (always light or dark)
  const [effectiveTheme, setEffectiveTheme] = useState<'light' | 'dark'>('light');

  // Initialize on mount
  useEffect(() => {
    const storedTheme = getStoredTheme();
    const initialTheme = storedTheme || 'system';
    const initialEffectiveTheme = getEffectiveTheme(initialTheme);

    setThemeState(initialTheme);
    setEffectiveTheme(initialEffectiveTheme);
    applyTheme(initialEffectiveTheme);
  }, []);

  // Subscribe to system theme changes
  useEffect(() => {
    if (theme !== 'system') return;

    const unsubscribe = subscribeToSystemTheme((systemTheme) => {
      setEffectiveTheme(systemTheme);
      applyTheme(systemTheme);
    });

    return unsubscribe;
  }, [theme]);

  // Set theme
  const setTheme = useCallback((newTheme: Theme) => {
    setThemeState(newTheme);
    setStoredTheme(newTheme);

    const effective = getEffectiveTheme(newTheme);
    setEffectiveTheme(effective);
    applyTheme(effective);
  }, []);

  // Toggle between light and dark
  const toggleTheme = useCallback(() => {
    const newTheme = effectiveTheme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
  }, [effectiveTheme, setTheme]);

  return {
    theme,
    effectiveTheme,
    setTheme,
    toggleTheme,
    isDark: effectiveTheme === 'dark',
    isLight: effectiveTheme === 'light',
    isSystem: theme === 'system',
  };
};

export default useTheme;
