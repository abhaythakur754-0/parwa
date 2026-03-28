'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

interface UseLazyLoadOptions {
  threshold?: number;
  rootMargin?: string;
  triggerOnce?: boolean;
}

/**
 * Hook for lazy loading elements using Intersection Observer
 */
export const useLazyLoad = <T extends HTMLElement = HTMLDivElement>(
  options: UseLazyLoadOptions = {}
) => {
  const { threshold = 0.1, rootMargin = '200px', triggerOnce = true } = options;

  const [isIntersecting, setIsIntersecting] = useState(false);
  const [hasIntersected, setHasIntersected] = useState(false);
  const ref = useRef<T>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        const intersecting = entry.isIntersecting;
        setIsIntersecting(intersecting);

        if (intersecting) {
          setHasIntersected(true);
          if (triggerOnce) {
            observer.unobserve(element);
          }
        }
      },
      { threshold, rootMargin }
    );

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, [threshold, rootMargin, triggerOnce]);

  const isVisible = triggerOnce ? hasIntersected : isIntersecting;

  return { ref, isVisible, isIntersecting };
};

/**
 * Hook for lazy loading images
 */
export const useLazyImage = (src: string, placeholder?: string) => {
  const [imageSrc, setImageSrc] = useState(placeholder || '');
  const [isLoaded, setIsLoaded] = useState(false);
  const [hasError, setHasError] = useState(false);
  const { ref, isVisible } = useLazyLoad<HTMLImageElement>();

  useEffect(() => {
    if (isVisible && src) {
      const img = new Image();
      img.src = src;

      img.onload = () => {
        setImageSrc(src);
        setIsLoaded(true);
      };

      img.onerror = () => {
        setHasError(true);
      };
    }
  }, [isVisible, src]);

  return { ref, imageSrc, isLoaded, hasError, isVisible };
};

/**
 * Hook for lazy loading multiple images with priority
 */
export const useLazyImages = (
  images: Array<{ src: string; priority?: boolean }>,
  options: UseLazyLoadOptions = {}
) => {
  const [loadedImages, setLoadedImages] = useState<Set<string>>(new Set());
  const { ref, isVisible } = useLazyLoad<HTMLDivElement>(options);

  useEffect(() => {
    if (!isVisible) return;

    // Load priority images first
    const priorityImages = images.filter(img => img.priority);
    const normalImages = images.filter(img => !img.priority);

    const loadImages = async (imageList: typeof images) => {
      for (const { src } of imageList) {
        try {
          await new Promise<void>((resolve, reject) => {
            const img = new Image();
            img.src = src;
            img.onload = () => resolve();
            img.onerror = reject;
          });
          setLoadedImages(prev => new Set(prev).add(src));
        } catch (e) {
          console.warn(`Failed to load image: ${src}`);
        }
      }
    };

    loadImages([...priorityImages, ...normalImages]);
  }, [isVisible, images]);

  return { ref, loadedImages, isVisible };
};

/**
 * Hook for lazy loading components with suspense-like behavior
 */
export const useLazyComponent = <T,>(
  loader: () => Promise<{ default: T }>,
  options: UseLazyLoadOptions = {}
) => {
  const [Component, setComponent] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const { ref, isVisible } = useLazyLoad<HTMLDivElement>(options);

  useEffect(() => {
    if (!isVisible || Component || isLoading) return;

    setIsLoading(true);
    loader()
      .then(module => {
        setComponent(module.default);
        setError(null);
      })
      .catch(err => {
        setError(err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [isVisible, loader, Component, isLoading]);

  return { ref, Component, isLoading, error, isVisible };
};

/**
 * Hook for infinite scroll / lazy loading more content
 */
export const useInfiniteScroll = (
  onLoadMore: () => void,
  options: UseLazyLoadOptions & { hasMore?: boolean } = {}
) => {
  const { hasMore = true, ...lazyOptions } = options;
  const [isLoading, setIsLoading] = useState(false);
  const { ref, isIntersecting } = useLazyLoad<HTMLDivElement>({
    ...lazyOptions,
    triggerOnce: false,
  });

  useEffect(() => {
    if (isIntersecting && hasMore && !isLoading) {
      setIsLoading(true);
      Promise.resolve(onLoadMore()).finally(() => {
        setIsLoading(false);
      });
    }
  }, [isIntersecting, hasMore, isLoading, onLoadMore]);

  return { ref, isLoading, isIntersecting };
};

/**
 * Hook for preloading content on idle
 */
export const useIdlePreload = (
  preloadFn: () => void,
  options: { timeout?: number } = {}
) => {
  const { timeout = 2000 } = options;
  const hasPreloaded = useRef(false);

  useEffect(() => {
    if (hasPreloaded.current) return;

    if ('requestIdleCallback' in window) {
      const id = requestIdleCallback(
        () => {
          preloadFn();
          hasPreloaded.current = true;
        },
        { timeout }
      );
      return () => cancelIdleCallback(id);
    } else {
      const id = setTimeout(() => {
        preloadFn();
        hasPreloaded.current = true;
      }, timeout);
      return () => clearTimeout(id);
    }
  }, [preloadFn, timeout]);
};

export default useLazyLoad;
