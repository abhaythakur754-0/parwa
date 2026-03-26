"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Search,
  X,
  Ticket,
  User,
  Bot,
  Clock,
  ArrowUp,
  ArrowDown,
  Loader2,
} from "lucide-react";

/**
 * Search result type.
 */
export type SearchResultType = "ticket" | "customer" | "agent";

/**
 * Search result data structure.
 */
export interface SearchResult {
  /** Unique result ID */
  id: string;
  /** Result type */
  type: SearchResultType;
  /** Result title */
  title: string;
  /** Result description */
  description?: string;
  /** Additional metadata */
  metadata?: {
    status?: string;
    priority?: string;
    variant?: string;
  };
}

/**
 * Search bar props.
 */
export interface SearchBarProps {
  /** Placeholder text */
  placeholder?: string;
  /** Search handler */
  onSearch?: (query: string) => Promise<SearchResult[]>;
  /** Callback when result is selected */
  onResultSelect?: (result: SearchResult) => void;
  /** Recent searches */
  recentSearches?: string[];
  /** Callback to save search to recent */
  onSaveRecentSearch?: (query: string) => void;
  /** Additional CSS classes */
  className?: string;
}

// Result type config
const resultTypeConfig: Record<
  SearchResultType,
  { icon: React.ReactNode; label: string; color: string }
> = {
  ticket: {
    icon: <Ticket className="h-4 w-4" />,
    label: "Ticket",
    color: "text-blue-600",
  },
  customer: {
    icon: <User className="h-4 w-4" />,
    label: "Customer",
    color: "text-green-600",
  },
  agent: {
    icon: <Bot className="h-4 w-4" />,
    label: "Agent",
    color: "text-purple-600",
  },
};

/**
 * Global Search Bar Component
 *
 * A search bar with autocomplete suggestions, keyboard navigation,
 * and recent searches. Supports searching across tickets, customers, and agents.
 *
 * @example
 * ```tsx
 * <SearchBar
 *   onSearch={async (query) => searchAPI(query)}
 *   onResultSelect={(result) => router.push(`/${result.type}/${result.id}`)}
 *   recentSearches={recentSearches}
 * />
 * ```
 */
export function SearchBar({
  placeholder = "Search tickets, customers, agents...",
  onSearch,
  onResultSelect,
  recentSearches = [],
  onSaveRecentSearch,
  className,
}: SearchBarProps) {
  const [query, setQuery] = React.useState("");
  const [results, setResults] = React.useState<SearchResult[]>([]);
  const [isOpen, setIsOpen] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(false);
  const [selectedIndex, setSelectedIndex] = React.useState(-1);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);

  // Debounced search
  const searchTimeout = React.useRef<NodeJS.Timeout | null>(null);

  React.useEffect(() => {
    if (searchTimeout.current) {
      clearTimeout(searchTimeout.current);
    }

    if (query.trim().length < 2) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    searchTimeout.current = setTimeout(async () => {
      if (onSearch) {
        try {
          const searchResults = await onSearch(query);
          setResults(searchResults);
        } catch {
          setResults([]);
        } finally {
          setIsLoading(false);
        }
      }
      setIsOpen(true);
    }, 300);

    return () => {
      if (searchTimeout.current) {
        clearTimeout(searchTimeout.current);
      }
    };
  }, [query, onSearch]);

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    const totalItems = results.length + (recentSearches.length > 0 && query.length < 2 ? recentSearches.length : 0);

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, totalItems - 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, -1));
        break;
      case "Enter":
        e.preventDefault();
        if (selectedIndex >= 0 && selectedIndex < results.length) {
          handleResultSelect(results[selectedIndex]);
        } else if (selectedIndex >= results.length && query.length < 2) {
          const recentIndex = selectedIndex - results.length;
          if (recentSearches[recentIndex]) {
            setQuery(recentSearches[recentIndex]);
          }
        } else if (query.trim()) {
          onSaveRecentSearch?.(query);
          setIsOpen(false);
        }
        break;
      case "Escape":
        setIsOpen(false);
        inputRef.current?.blur();
        break;
    }
  };

  const handleResultSelect = (result: SearchResult) => {
    onResultSelect?.(result);
    onSaveRecentSearch?.(query);
    setQuery("");
    setResults([]);
    setIsOpen(false);
    setSelectedIndex(-1);
  };

  const handleRecentSearchClick = (search: string) => {
    setQuery(search);
    inputRef.current?.focus();
  };

  const clearSearch = () => {
    setQuery("");
    setResults([]);
    setSelectedIndex(-1);
    inputRef.current?.focus();
  };

  const showRecent = query.length < 2 && recentSearches.length > 0;
  const showDropdown = isOpen && (results.length > 0 || showRecent || isLoading);

  return (
    <div ref={containerRef} className={cn("relative w-full max-w-md", className)}>
      {/* Search input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setSelectedIndex(-1);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="pl-10 pr-10"
          aria-label="Global search"
          aria-expanded={showDropdown}
          aria-haspopup="listbox"
        />
        {query && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
            onClick={clearSearch}
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <div
          className="absolute top-full left-0 right-0 mt-1 bg-background border rounded-lg shadow-lg z-50"
          role="listbox"
        >
          {/* Loading state */}
          {isLoading && (
            <div className="flex items-center justify-center p-4">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">Searching...</span>
            </div>
          )}

          {/* Search results */}
          {!isLoading && results.length > 0 && (
            <div className="p-2">
              <p className="text-xs text-muted-foreground px-2 py-1">Results</p>
              {results.map((result, index) => {
                const config = resultTypeConfig[result.type];
                return (
                  <button
                    key={result.id}
                    className={cn(
                      "w-full flex items-center gap-3 p-2 rounded-md text-left transition-colors",
                      selectedIndex === index && "bg-muted"
                    )}
                    onClick={() => handleResultSelect(result)}
                    onMouseEnter={() => setSelectedIndex(index)}
                    role="option"
                    aria-selected={selectedIndex === index}
                  >
                    <div
                      className={cn(
                        "w-8 h-8 rounded-full flex items-center justify-center bg-muted"
                      )}
                    >
                      <span className={config.color}>{config.icon}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{result.title}</p>
                      {result.description && (
                        <p className="text-xs text-muted-foreground truncate">
                          {result.description}
                        </p>
                      )}
                    </div>
                    <Badge variant="outline" className="text-xs">
                      {config.label}
                    </Badge>
                  </button>
                );
              })}
            </div>
          )}

          {/* Recent searches */}
          {showRecent && !isLoading && (
            <div className="p-2 border-t">
              <p className="text-xs text-muted-foreground px-2 py-1">Recent Searches</p>
              {recentSearches.map((search, index) => (
                <button
                  key={search}
                  className={cn(
                    "w-full flex items-center gap-3 p-2 rounded-md text-left transition-colors",
                    selectedIndex === results.length + index && "bg-muted"
                  )}
                  onClick={() => handleRecentSearchClick(search)}
                  onMouseEnter={() => setSelectedIndex(results.length + index)}
                >
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">{search}</span>
                </button>
              ))}
            </div>
          )}

          {/* No results */}
          {!isLoading && results.length === 0 && query.length >= 2 && (
            <div className="flex flex-col items-center justify-center p-6 text-center">
              <Search className="h-8 w-8 text-muted-foreground mb-2" />
              <p className="text-muted-foreground">No results found</p>
              <p className="text-xs text-muted-foreground mt-1">
                Try a different search term
              </p>
            </div>
          )}

          {/* Keyboard hints */}
          {showDropdown && (
            <div className="border-t p-2 flex items-center justify-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">
                  <ArrowUp className="h-3 w-3 inline" />
                </kbd>
                <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">
                  <ArrowDown className="h-3 w-3 inline" />
                </kbd>
                Navigate
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">Enter</kbd>
                Select
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">Esc</kbd>
                Close
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default SearchBar;
