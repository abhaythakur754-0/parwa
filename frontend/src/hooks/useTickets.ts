/**
 * PARWA useTickets Hook
 *
 * Custom hook for ticket management.
 * Handles fetching, creating, updating, and searching tickets.
 *
 * Features:
 * - Fetch tickets list with filters and pagination
 * - Get single ticket detail
 * - Create new ticket
 * - Update ticket status
 * - Search tickets
 */

import { useState, useCallback, useEffect } from "react";
import { apiClient } from "../services/api/client";
import { useUIStore } from "../stores/uiStore";

/**
 * Ticket status enumeration.
 */
export type TicketStatus = "open" | "in_progress" | "resolved" | "closed";

/**
 * Ticket priority enumeration.
 */
export type TicketPriority = "low" | "medium" | "high" | "critical";

/**
 * Ticket source enumeration.
 */
export type TicketSource = "email" | "chat" | "phone" | "web" | "api";

/**
 * Customer interface.
 */
export interface TicketCustomer {
  id: string;
  name: string;
  email: string;
  phone?: string;
}

/**
 * Assignee interface.
 */
export interface TicketAssignee {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}

/**
 * Ticket message interface.
 */
export interface TicketMessage {
  id: string;
  content: string;
  sender: "customer" | "agent" | "system";
  senderName: string;
  createdAt: string;
  attachments?: Array<{
    id: string;
    name: string;
    url: string;
    size: number;
  }>;
}

/**
 * Ticket interface.
 */
export interface Ticket {
  id: string;
  subject: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  source: TicketSource;
  customer: TicketCustomer;
  assignee?: TicketAssignee;
  messages: TicketMessage[];
  tags: string[];
  slaDueAt?: string;
  resolvedAt?: string;
  closedAt?: string;
  createdAt: string;
  updatedAt: string;
}

/**
 * Tickets list response.
 */
export interface TicketsListResponse {
  tickets: Ticket[];
  total: number;
  page: number;
  pageSize: number;
}

/**
 * Tickets filter options.
 */
export interface TicketsFilters {
  status?: TicketStatus;
  priority?: TicketPriority;
  source?: TicketSource;
  assigneeId?: string;
  customerId?: string;
  startDate?: string;
  endDate?: string;
  search?: string;
  tags?: string[];
}

/**
 * Create ticket data.
 */
export interface CreateTicketData {
  subject: string;
  description: string;
  priority?: TicketPriority;
  source?: TicketSource;
  customerId: string;
  tags?: string[];
}

/**
 * Update ticket data.
 */
export interface UpdateTicketData {
  status?: TicketStatus;
  priority?: TicketPriority;
  assigneeId?: string;
  tags?: string[];
  resolution?: string;
}

/**
 * useTickets hook return type.
 */
export interface UseTicketsReturn {
  /** List of tickets */
  tickets: Ticket[];
  /** Single ticket detail */
  ticket: Ticket | null;
  /** Total count for pagination */
  total: number;
  /** Current page */
  page: number;
  /** Page size */
  pageSize: number;
  /** Current filters */
  filters: TicketsFilters;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: string | null;

  // Actions
  /** Fetch tickets list */
  fetchTickets: (filters?: TicketsFilters, page?: number) => Promise<void>;
  /** Fetch single ticket detail */
  fetchTicket: (id: string) => Promise<void>;
  /** Create new ticket */
  createTicket: (data: CreateTicketData) => Promise<Ticket>;
  /** Update ticket */
  updateTicket: (id: string, data: UpdateTicketData) => Promise<void>;
  /** Search tickets */
  searchTickets: (query: string) => Promise<Ticket[]>;
  /** Add reply to ticket */
  addReply: (ticketId: string, content: string) => Promise<void>;
  /** Refresh current list */
  refresh: () => Promise<void>;
  /** Set filters */
  setFilters: (filters: TicketsFilters) => void;
  /** Clear single ticket */
  clearTicket: () => void;
  /** Clear error */
  clearError: () => void;
}

/**
 * Custom hook for ticket management.
 *
 * @returns Tickets state and actions
 *
 * @example
 * ```tsx
 * function TicketsList() {
 *   const {
 *     tickets,
 *     isLoading,
 *     filters,
 *     setFilters,
 *     fetchTickets
 *   } = useTickets();
 *
 *   useEffect(() => {
 *     fetchTickets({ status: 'open' });
 *   }, []);
 *
 *   return (
 *     <div>
 *       {tickets.map(ticket => (
 *         <TicketCard key={ticket.id} ticket={ticket} />
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
export function useTickets(): UseTicketsReturn {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFiltersState] = useState<TicketsFilters>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { addToast } = useUIStore();

  /**
   * Fetch tickets list from API.
   */
  const fetchTickets = useCallback(
    async (newFilters?: TicketsFilters, newPage?: number): Promise<void> => {
      setIsLoading(true);
      setError(null);

      const currentPage = newPage ?? page;
      const currentFilters = newFilters ?? filters;

      try {
        const params: Record<string, string> = {
          page: String(currentPage),
          pageSize: String(pageSize),
        };

        if (currentFilters.status) params.status = currentFilters.status;
        if (currentFilters.priority) params.priority = currentFilters.priority;
        if (currentFilters.source) params.source = currentFilters.source;
        if (currentFilters.assigneeId) params.assigneeId = currentFilters.assigneeId;
        if (currentFilters.customerId) params.customerId = currentFilters.customerId;
        if (currentFilters.startDate) params.startDate = currentFilters.startDate;
        if (currentFilters.endDate) params.endDate = currentFilters.endDate;
        if (currentFilters.search) params.search = currentFilters.search;
        if (currentFilters.tags?.length) params.tags = currentFilters.tags.join(",");

        const response = await apiClient.get<TicketsListResponse>("/tickets", params);

        setTickets(response.data.tickets);
        setTotal(response.data.total);
        setPage(response.data.page);
        setPageSize(response.data.pageSize);

        if (newFilters) {
          setFiltersState(newFilters);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to fetch tickets";
        setError(message);
        addToast({
          title: "Error",
          description: message,
          variant: "error",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [page, pageSize, filters, addToast]
  );

  /**
   * Fetch single ticket detail.
   */
  const fetchTicket = useCallback(
    async (id: string): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiClient.get<Ticket>(`/tickets/${id}`);
        setTicket(response.data);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to fetch ticket";
        setError(message);
        addToast({
          title: "Error",
          description: message,
          variant: "error",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [addToast]
  );

  /**
   * Create new ticket.
   */
  const createTicket = useCallback(
    async (data: CreateTicketData): Promise<Ticket> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiClient.post<Ticket>("/tickets", data);
        const newTicket = response.data;

        // Add to local list
        setTickets((prev) => [newTicket, ...prev]);
        setTotal((prev) => prev + 1);

        addToast({
          title: "Ticket created",
          description: `Ticket #${newTicket.id} has been created.`,
          variant: "success",
        });

        return newTicket;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to create ticket";
        setError(message);
        addToast({
          title: "Error",
          description: message,
          variant: "error",
        });
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [addToast]
  );

  /**
   * Update ticket.
   */
  const updateTicket = useCallback(
    async (id: string, data: UpdateTicketData): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiClient.patch<Ticket>(`/tickets/${id}`, data);
        const updatedTicket = response.data;

        // Update in local list
        setTickets((prev) =>
          prev.map((t) => (t.id === id ? updatedTicket : t))
        );

        // Update single ticket if it's loaded
        if (ticket?.id === id) {
          setTicket(updatedTicket);
        }

        addToast({
          title: "Ticket updated",
          description: `Ticket #${id} has been updated.`,
          variant: "success",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to update ticket";
        setError(message);
        addToast({
          title: "Error",
          description: message,
          variant: "error",
        });
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [ticket, addToast]
  );

  /**
   * Search tickets.
   */
  const searchTickets = useCallback(
    async (query: string): Promise<Ticket[]> => {
      if (!query.trim()) {
        return [];
      }

      setIsLoading(true);

      try {
        const response = await apiClient.get<Ticket[]>("/tickets/search", {
          q: query,
        });
        return response.data;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Search failed";
        addToast({
          title: "Search error",
          description: message,
          variant: "error",
        });
        return [];
      } finally {
        setIsLoading(false);
      }
    },
    [addToast]
  );

  /**
   * Add reply to ticket.
   */
  const addReply = useCallback(
    async (ticketId: string, content: string): Promise<void> => {
      if (!content.trim()) {
        throw new Error("Reply content is required");
      }

      setIsLoading(true);

      try {
        const response = await apiClient.post<Ticket>(
          `/tickets/${ticketId}/reply`,
          { content }
        );

        const updatedTicket = response.data;

        // Update single ticket if it's loaded
        if (ticket?.id === ticketId) {
          setTicket(updatedTicket);
        }

        addToast({
          title: "Reply added",
          description: "Your reply has been added to the ticket.",
          variant: "success",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to add reply";
        addToast({
          title: "Error",
          description: message,
          variant: "error",
        });
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [ticket, addToast]
  );

  /**
   * Refresh current list.
   */
  const refresh = useCallback(async (): Promise<void> => {
    await fetchTickets(filters, page);
  }, [fetchTickets, filters, page]);

  /**
   * Set filters and refetch.
   */
  const setFilters = useCallback((newFilters: TicketsFilters): void => {
    setFiltersState(newFilters);
    setPage(1);
  }, []);

  /**
   * Clear single ticket.
   */
  const clearTicket = useCallback((): void => {
    setTicket(null);
  }, []);

  /**
   * Clear error.
   */
  const clearError = useCallback((): void => {
    setError(null);
  }, []);

  /**
   * Auto-fetch on mount.
   */
  useEffect(() => {
    fetchTickets();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    tickets,
    ticket,
    total,
    page,
    pageSize,
    filters,
    isLoading,
    error,
    fetchTickets,
    fetchTicket,
    createTicket,
    updateTicket,
    searchTickets,
    addReply,
    refresh,
    setFilters,
    clearTicket,
    clearError,
  };
}

export default useTickets;
