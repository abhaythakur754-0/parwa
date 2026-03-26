/**
 * PARWA useSearch Hook
 *
 * Custom hook for global search functionality.
 * Handles search, autocomplete suggestions, and search history.
 *
 * Features:
 * - Global search across tickets, customers, agents
 * - Autocomplete suggestions
 * - Search history management
 * - Debounced search
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { apiClient } from "../services/api/client";

/**
 * Search result type enumeration.
 */
export type SearchResultType = "ticket" | "customer" | "agent" | "article" | "conversation";

/**
 * Search result interface.
 */
export interface SearchResult {
  id: string;
  type: SearchResultType;
  title: string;
  description?: string;
  url: string;
  metadata?: Record<string, unknown>;
  score: number;
}

/**
 * Search suggestion interface.
 */
export interface SearchSuggestion {
  text: string;
  type: SearchResultType;
  count?: number;
}

/**
 * Search history item interface.
 */
export interface SearchHistoryItem {
  id: string;
  query: string;
  timestamp: string;
  resultsCount: number;
}

/**
 * Search response interface.
 */
export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
  took: number;
}

/**
 * useSearch hook return type.
 */
export interface UseSearchReturn {
  /** Search results */
  results: SearchResult[];
  /** Autocomplete suggestions */
  suggestions: SearchSuggestion[];
  /** Recent search history */
  recentSearches: SearchHistoryItem[];
  /** Total results count */
  total: number;
  /** Search query */
  query: string;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: string | null;

  // Actions
  /** Perform search */
  search: (query: string) => Promise<void>;
  /** Fetch autocomplete suggestions */
  fetchSuggestions: (query: string) => Promise<void>;
  /** Clear search results */
  clearResults: () => void;
  /** Clear search history */
  clearHistory: () => void;
  /** Remove item from history */
  removeFromHistory: (id: string) => void;
  /** Clear error */
  clearError: () => void;
}

/** Storage key for search history */
const HISTORY_STORAGE_KEY = "parwa-search-history";
const MAX_HISTORY_ITEMS = 10;
const DEBOUNCE_MS = 300;

/**
 * Generate unique ID for history items.
 */
function generateId(): string {
  return `search-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Load search history from localStorage.
 */
function loadHistory(): SearchHistoryItem[] {
  if (typeof window === "undefined") return [];

  try {
    const stored = localStorage.getItem(HISTORY_STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

/**
 * Save search history to localStorage.
 */
function saveHistory(history: SearchHistoryItem[]): void {
  if (typeof window === "undefined") return;

  try {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history));
  } catch {
    // Storage might be full or disabled
  }
}

/**
 * Custom hook for global search functionality.
 *
 * @returns Search state and actions
 *
 * @example
 * ```tsx
 * function GlobalSearch() {
 *   const {
 *     results,
 *     suggestions,
 *     search,
 *     fetchSuggestions,
 *     isLoading
 *   } = useSearch();
 *
 *   const handleInputChange = (value: string) => {
 *     fetchSuggestions(value);
 *   };
 *
 *   const handleSearch = (query: string) => {
 *     search(query);
 *   };
 *
 *   return (
 *     <div>
 *       <SearchInput
 *         onChange={handleInputChange}
 *         onSearch={handleSearch}
 *         suggestions={suggestions}
 *       />
 *       <SearchResults results={results} isLoading={isLoading} />
 *     </div>
 *   );
 * }
 * ```
 */
export function useSearch(): UseSearchReturn {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [recentSearches, setRecentSearches] = useState<SearchHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * Load history on mount.
   */
  useEffect(() => {
    setRecentSearches(loadHistory());
  }, []);

  /**
   * Add search to history.
   */
  const addToHistory = useCallback((searchQuery: string, resultsCount: number): void => {
    const item: SearchHistoryItem = {
      id: generateId(),
      query: searchQuery,
      timestamp: new Date().toISOString(),
      resultsCount,
    };

    setRecentSearches((prev) => {
      const filtered = prev.filter((h) => h.query !== searchQuery);
      const updated = [item, ...filtered].slice(0, MAX_HISTORY_ITEMS);
      saveHistory(updated);
      return updated;
    });
  }, []);

  /**
   * Perform search.
   */
  const search = useCallback(
    async (searchQuery: string): Promise<void> => {
      if (!searchQuery.trim()) {
        setResults([]);
        setTotal(0);
        return;
      }

      setIsLoading(true);
      setError(null);
      setQuery(searchQuery);

      try {
        const response = await apiClient.get<SearchResponse>("/search", {
          q: searchQuery,
        });

        setResults(response.data.results);
        setTotal(response.data.total);

        // Add to history
        addToHistory(searchQuery, response.data.total);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Search failed";
        setError(message);
        setResults([]);
        setTotal(0);
      } finally {
        setIsLoading(false);
      }
    },
    [addToHistory]
  );

  /**
   * Fetch autocomplete suggestions with debounce.
   */
  const fetchSuggestions = useCallback(
    async (input: string): Promise<void> => {
      if (!input.trim()) {
        setSuggestions([]);
        return;
      }

      // Clear previous timeout
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }

      // Debounce the API call
      debounceRef.current = setTimeout(async () => {
        try {
          const response = await apiClient.get<SearchSuggestion[]>("/search/suggestions", {
            q: input,
          });

          setSuggestions(response.data);
        } catch {
          // Silently fail for suggestions
          setSuggestions([]);
        }
      }, DEBOUNCE_MS);
    },
    []
  );

  /**
   * Clear search results.
   */
  const clearResults = useCallback((): void => {
    setResults([]);
    setTotal(0);
    setQuery("");
    setSuggestions([]);
  }, []);

  /**
   * Clear search history.
   */
  const clearHistory = useCallback((): void => {
    setRecentSearches([]);
    saveHistory([]);
  }, []);

  /**
   * Remove item from history.
   */
  const removeFromHistory = useCallback((id: string): void => {
    setRecentSearches((prev) => {
      const updated = prev.filter((h) => h.id !== id);
      saveHistory(updated);
      return updated;
    });
  }, []);

  /**
   * Clear error.
   */
  const clearError = useCallback((): void => {
    setError(null);
  }, []);

  /**
   * Cleanup debounce on unmount.
   */
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  return {
    results,
    suggestions,
    recentSearches,
    total,
    query,
    isLoading,
    error,
    search,
    fetchSuggestions,
    clearResults,
    clearHistory,
    removeFromHistory,
    clearError,
  };
}

export default useSearch;
