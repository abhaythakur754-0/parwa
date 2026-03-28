'use client';

import { useState, useEffect, useCallback } from 'react';
import { breakpoints, Breakpoint } from '@/lib/responsive';

/**
 * Hook for responsive media queries
 */
export const useMediaQuery = (query: string): boolean => {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const media = window.matchMedia(query);

    // Set initial value
    setMatches(media.matches);

    // Define listener
    const listener = (event: MediaQueryListEvent) => {
      setMatches(event.matches);
    };

    // Add listener
    media.addEventListener('change', listener);

    return () => {
      media.removeEventListener('change', listener);
    };
  }, [query]);

  return matches;
};

/**
 * Hook for breakpoint queries
 */
export const useBreakpoint = (breakpoint: Breakpoint): boolean => {
  const query = `(min-width: ${breakpoints[breakpoint]}px)`;
  return useMediaQuery(query);
};

/**
 * Hook for breakpoint range queries
 */
export const useBreakpointRange = (
  min: Breakpoint,
  max: Breakpoint
): boolean => {
  const query = `(min-width: ${breakpoints[min]}px) and (max-width: ${breakpoints[max] - 1}px)`;
  return useMediaQuery(query);
};

/**
 * Hook for touch device detection
 */
export const useTouchDevice = (): boolean => {
  const [isTouch, setIsTouch] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const checkTouch = () => {
      setIsTouch(
        'ontouchstart' in window ||
        navigator.maxTouchPoints > 0
      );
    };

    checkTouch();
    window.addEventListener('touchstart', checkTouch, { once: true });

    return () => {
      window.removeEventListener('touchstart', checkTouch);
    };
  }, []);

  return isTouch;
};

/**
 * Hook for reduced motion preference
 */
export const usePrefersReducedMotion = (): boolean => {
  return useMediaQuery('(prefers-reduced-motion: reduce)');
};

/**
 * Hook for dark mode preference
 */
export const usePrefersDarkMode = (): boolean => {
  return useMediaQuery('(prefers-color-scheme: dark)');
};

/**
 * Hook for current breakpoint
 */
export const useCurrentBreakpoint = (): Breakpoint => {
  const [breakpoint, setBreakpoint] = useState<Breakpoint>('sm');

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const updateBreakpoint = () => {
      const width = window.innerWidth;

      if (width >= breakpoints['2xl']) {
        setBreakpoint('2xl');
      } else if (width >= breakpoints.xl) {
        setBreakpoint('xl');
      } else if (width >= breakpoints.lg) {
        setBreakpoint('lg');
      } else if (width >= breakpoints.md) {
        setBreakpoint('md');
      } else {
        setBreakpoint('sm');
      }
    };

    updateBreakpoint();
    window.addEventListener('resize', updateBreakpoint);

    return () => {
      window.removeEventListener('resize', updateBreakpoint);
    };
  }, []);

  return breakpoint;
};

/**
 * Hook for viewport dimensions
 */
export const useViewport = (): { width: number; height: number } => {
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const updateDimensions = () => {
      setDimensions({
        width: window.innerWidth,
        height: window.innerHeight,
      });
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);

    return () => {
      window.removeEventListener('resize', updateDimensions);
    };
  }, []);

  return dimensions;
};

/**
 * Hook for orientation
 */
export const useOrientation = (): 'portrait' | 'landscape' => {
  const isPortrait = useMediaQuery('(orientation: portrait)');
  return isPortrait ? 'portrait' : 'landscape';
};

/**
 * Hook for responsive value selection
 */
export const useResponsiveValue = <T>(
  values: Partial<Record<Breakpoint, T>>,
  defaultValue: T
): T => {
  const current = useCurrentBreakpoint();

  const getValue = useCallback(() => {
    const breakpointOrder: Breakpoint[] = ['sm', 'md', 'lg', 'xl', '2xl'];
    const currentIndex = breakpointOrder.indexOf(current);

    for (let i = currentIndex; i >= 0; i--) {
      if (values[breakpointOrder[i]] !== undefined) {
        return values[breakpointOrder[i]] as T;
      }
    }

    return defaultValue;
  }, [current, values, defaultValue]);

  return getValue();
};

/**
 * Hook for device type detection
 */
export const useDeviceType = (): 'mobile' | 'tablet' | 'desktop' => {
  const isMobile = useMediaQuery(`(max-width: ${breakpoints.md - 1}px)`);
  const isTablet = useMediaQuery(
    `(min-width: ${breakpoints.md}px) and (max-width: ${breakpoints.lg - 1}px)`
  );
  const isTouch = useTouchDevice();

  if (isMobile) return 'mobile';
  if (isTablet && isTouch) return 'tablet';
  return 'desktop';
};

export default useMediaQuery;
