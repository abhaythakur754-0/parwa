/**
 * PARWA Tickets Query Hook
 *
 * Enhanced hook for ticket management using React Query.
 * Features pagination, filtering, real-time updates, and optimistic mutations.
 *
 * @module hooks/queries/useTicketsQuery
 */

"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
  useInfiniteQuery,
  type UseQueryOptions,
  type UseMutationOptions,
  type UseInfiniteQueryOptions,
  type InfiniteData,
} from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";
import { z } from "zod";
import { queryKeys } from "../../lib/react-query/query-client";
import { useOptimisticMutation } from "../../lib/react-query/mutation-helpers";

// ============================================================================
// Types & Schemas
// ============================================================================

/**
 * Ticket status enumeration.
 */
export const TicketStatusSchema = z.enum(["open", "in_progress", "resolved", "closed"]);
export type TicketStatus = z.infer<typeof TicketStatusSchema>;

/**
 * Ticket priority enumeration.
 */
export const TicketPrioritySchema = z.enum(["low", "medium", "high", "critical"]);
export type TicketPriority = z.infer<typeof TicketPrioritySchema>;

/**
 * Ticket source enumeration.
 */
export const TicketSourceSchema = z.enum(["email", "chat", "phone", "web", "api"]);
export type TicketSource = z.infer<typeof TicketSourceSchema>;

/**
 * Customer schema.
 */
export const TicketCustomerSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string().email(),
  phone: z.string().optional(),
});

export type TicketCustomer = z.infer<typeof TicketCustomerSchema>;

/**
 * Assignee schema.
 */
export const TicketAssigneeSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string().email(),
  avatar: z.string().optional(),
});

export type TicketAssignee = z.infer<typeof TicketAssigneeSchema>;

/**
 * Ticket message schema.
 */
export const TicketMessageSchema = z.object({
  id: z.string(),
  content: z.string(),
  sender: z.enum(["customer", "agent", "system"]),
  senderName: z.string(),
  createdAt: z.string(),
  attachments: z
    .array(
      z.object({
        id: z.string(),
        name: z.string(),
        url: z.string(),
        size: z.number(),
      })
    )
    .optional(),
});

export type TicketMessage = z.infer<typeof TicketMessageSchema>;

/**
 * Ticket schema.
 */
export const TicketSchema = z.object({
  id: z.string(),
  subject: z.string(),
  description: z.string(),
  status: TicketStatusSchema,
  priority: TicketPrioritySchema,
  source: TicketSourceSchema,
  customer: TicketCustomerSchema,
  assignee: TicketAssigneeSchema.optional(),
  messages: z.array(TicketMessageSchema),
  tags: z.array(z.string()),
  slaDueAt: z.string().optional(),
  resolvedAt: z.string().optional(),
  closedAt: z.string().optional(),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export type Ticket = z.infer<typeof TicketSchema>;

/**
 * Tickets list response schema.
 */
export const TicketsListResponseSchema = z.object({
  tickets: z.array(TicketSchema),
  total: z.number(),
  page: z.number(),
  pageSize: z.number(),
  hasMore: z.boolean().optional(),
});

export type TicketsListResponse = z.infer<typeof TicketsListResponseSchema>;

/**
 * Tickets filter options schema.
 */
export const TicketsFiltersSchema = z.object({
  status: TicketStatusSchema.optional(),
  priority: TicketPrioritySchema.optional(),
  source: TicketSourceSchema.optional(),
  assigneeId: z.string().optional(),
  customerId: z.string().optional(),
  startDate: z.string().optional(),
  endDate: z.string().optional(),
  search: z.string().optional(),
  tags: z.array(z.string()).optional(),
});

export type TicketsFilters = z.infer<typeof TicketsFiltersSchema>;

/**
 * Create ticket data schema.
 */
export const CreateTicketDataSchema = z.object({
  subject: z.string().min(1).max(200),
  description: z.string().min(1),
  priority: TicketPrioritySchema.optional().default("medium"),
  source: TicketSourceSchema.optional().default("web"),
  customerId: z.string(),
  tags: z.array(z.string()).optional(),
});

export type CreateTicketData = z.infer<typeof CreateTicketDataSchema>;

/**
 * Update ticket data schema.
 */
export const UpdateTicketDataSchema = z.object({
  status: TicketStatusSchema.optional(),
  priority: TicketPrioritySchema.optional(),
  assigneeId: z.string().optional(),
  tags: z.array(z.string()).optional(),
  resolution: z.string().optional(),
});

export type UpdateTicketData = z.infer<typeof UpdateTicketDataSchema>;

// ============================================================================
// API Functions
// ============================================================================

const API_BASE = "/api";

/**
 * Fetch tickets list with filters and pagination.
 */
async function fetchTickets(params: {
  page: number;
  pageSize: number;
  filters?: TicketsFilters;
}): Promise<TicketsListResponse> {
  const searchParams = new URLSearchParams({
    page: String(params.page),
    pageSize: String(params.pageSize),
  });

  if (params.filters) {
    const { filters } = params;
    if (filters.status) searchParams.set("status", filters.status);
    if (filters.priority) searchParams.set("priority", filters.priority);
    if (filters.source) searchParams.set("source", filters.source);
    if (filters.assigneeId) searchParams.set("assigneeId", filters.assigneeId);
    if (filters.customerId) searchParams.set("customerId", filters.customerId);
    if (filters.startDate) searchParams.set("startDate", filters.startDate);
    if (filters.endDate) searchParams.set("endDate", filters.endDate);
    if (filters.search) searchParams.set("search", filters.search);
    if (filters.tags?.length) searchParams.set("tags", filters.tags.join(","));
  }

  const response = await fetch(`${API_BASE}/tickets?${searchParams}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch tickets: ${response.statusText}`);
  }

  const data = await response.json();
  return TicketsListResponseSchema.parse(data);
}

/**
 * Fetch a single ticket by ID.
 */
async function fetchTicket(id: string): Promise<Ticket> {
  const response = await fetch(`${API_BASE}/tickets/${id}`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Ticket not found");
    }
    throw new Error(`Failed to fetch ticket: ${response.statusText}`);
  }

  const data = await response.json();
  return TicketSchema.parse(data);
}

/**
 * Create a new ticket.
 */
async function createTicket(data: CreateTicketData): Promise<Ticket> {
  const validatedData = CreateTicketDataSchema.parse(data);

  const response = await fetch(`${API_BASE}/tickets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(validatedData),
  });

  if (!response.ok) {
    throw new Error(`Failed to create ticket: ${response.statusText}`);
  }

  const ticket = await response.json();
  return TicketSchema.parse(ticket);
}

/**
 * Update a ticket.
 */
async function updateTicket(id: string, data: UpdateTicketData): Promise<Ticket> {
  const validatedData = UpdateTicketDataSchema.parse(data);

  const response = await fetch(`${API_BASE}/tickets/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(validatedData),
  });

  if (!response.ok) {
    throw new Error(`Failed to update ticket: ${response.statusText}`);
  }

  const ticket = await response.json();
  return TicketSchema.parse(ticket);
}

/**
 * Add a reply to a ticket.
 */
async function addTicketReply(ticketId: string, content: string): Promise<Ticket> {
  const response = await fetch(`${API_BASE}/tickets/${ticketId}/reply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });

  if (!response.ok) {
    throw new Error(`Failed to add reply: ${response.statusText}`);
  }

  const ticket = await response.json();
  return TicketSchema.parse(ticket);
}

/**
 * Search tickets.
 */
async function searchTickets(query: string): Promise<Ticket[]> {
  const response = await fetch(`${API_BASE}/tickets/search?q=${encodeURIComponent(query)}`);
  if (!response.ok) {
    throw new Error(`Search failed: ${response.statusText}`);
  }

  const data = await response.json();
  return z.array(TicketSchema).parse(data);
}

// ============================================================================
// Query Hooks
// ============================================================================

/**
 * Options for useTickets hook.
 */
export interface UseTicketsOptions
  extends Omit<UseQueryOptions<TicketsListResponse, Error>, "queryKey" | "queryFn"> {
  /** Initial filters */
  filters?: TicketsFilters;
  /** Page number */
  page?: number;
  /** Items per page */
  pageSize?: number;
  /** Enable real-time updates via WebSocket */
  realtime?: boolean;
}

/**
 * Hook to fetch tickets list with pagination and filtering.
 *
 * @param options - Query options
 * @returns Query result with tickets data
 *
 * @example
 * ```tsx
 * function TicketsList() {
 *   const { data, isLoading, refetch } = useTickets({
 *     filters: { status: 'open' },
 *     pageSize: 10,
 *   });
 *
 *   return (
 *     <div>
 *       {data?.tickets.map(ticket => (
 *         <TicketCard key={ticket.id} ticket={ticket} />
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
export function useTickets(options: UseTicketsOptions = {}) {
  const {
    filters = {},
    page = 1,
    pageSize = 20,
    realtime = false,
    ...queryOptions
  } = options;

  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);

  const query = useQuery({
    queryKey: queryKeys.tickets.list({ ...filters, page, pageSize }),
    queryFn: () => fetchTickets({ page, pageSize, filters }),
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...queryOptions,
  });

  // Setup real-time updates via WebSocket
  useEffect(() => {
    if (!realtime) return;

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:3001";
    wsRef.current = new WebSocket(`${wsUrl}/tickets`);

    wsRef.current.onmessage = (event) => {
      const update = JSON.parse(event.data);

      // Handle different update types
      if (update.type === "ticket_created") {
        queryClient.setQueryData<TicketsListResponse>(
          queryKeys.tickets.lists(),
          (old) => {
            if (!old) return old;
            return {
              ...old,
              tickets: [update.data, ...old.tickets],
              total: old.total + 1,
            };
          }
        );
      } else if (update.type === "ticket_updated") {
        // Update both list and detail caches
        queryClient.setQueryData(queryKeys.tickets.detail(update.data.id), update.data);

        queryClient.setQueryData<TicketsListResponse>(
          queryKeys.tickets.lists(),
          (old) => {
            if (!old) return old;
            return {
              ...old,
              tickets: old.tickets.map((t) =>
                t.id === update.data.id ? update.data : t
              ),
            };
          }
        );
      }
    };

    return () => {
      wsRef.current?.close();
    };
  }, [realtime, queryClient]);

  return query;
}

/**
 * Options for useTicket hook.
 */
export interface UseTicketOptions
  extends Omit<UseQueryOptions<Ticket, Error>, "queryKey" | "queryFn"> {
  /** Ticket ID */
  id: string;
}

/**
 * Hook to fetch a single ticket by ID.
 *
 * @param options - Query options including ticket ID
 * @returns Query result with ticket data
 */
export function useTicket(options: UseTicketOptions) {
  const { id, ...queryOptions } = options;

  return useQuery({
    queryKey: queryKeys.tickets.detail(id),
    queryFn: () => fetchTicket(id),
    enabled: !!id,
    staleTime: 2 * 60 * 1000, // 2 minutes
    ...queryOptions,
  });
}

/**
 * Options for infinite tickets scroll.
 */
export interface UseInfiniteTicketsOptions
  extends Omit<
    UseInfiniteQueryOptions<
      TicketsListResponse,
      Error,
      InfiniteData<TicketsListResponse>
    >,
    "queryKey" | "queryFn" | "getNextPageParam"
  > {
  /** Filters for tickets */
  filters?: TicketsFilters;
  /** Items per page */
  pageSize?: number;
}

/**
 * Hook for infinite scroll ticket loading.
 *
 * @param options - Infinite query options
 * @returns Infinite query result
 */
export function useInfiniteTickets(options: UseInfiniteTicketsOptions = {}) {
  const { filters = {}, pageSize = 20, ...queryOptions } = options;

  return useInfiniteQuery({
    queryKey: queryKeys.tickets.list({ ...filters, pageSize }),
    queryFn: ({ pageParam = 1 }) => fetchTickets({ page: pageParam, pageSize, filters }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const totalPages = Math.ceil(lastPage.total / lastPage.pageSize);
      return lastPage.page < totalPages ? lastPage.page + 1 : undefined;
    },
    staleTime: 5 * 60 * 1000,
    ...queryOptions,
  });
}

/**
 * Hook for ticket search.
 *
 * @param query - Search query string
 * @param options - Query options
 * @returns Query result with search results
 */
export function useTicketSearch(
  query: string,
  options: Omit<UseQueryOptions<Ticket[], Error>, "queryKey" | "queryFn"> = {}
) {
  return useQuery({
    queryKey: queryKeys.tickets.search(query),
    queryFn: () => searchTickets(query),
    enabled: query.length >= 2,
    staleTime: 60 * 1000, // 1 minute
    ...options,
  });
}

// ============================================================================
// Mutation Hooks
// ============================================================================

/**
 * Hook to create a new ticket with optimistic update.
 *
 * @param options - Mutation options
 * @returns Mutation result
 */
export function useCreateTicket(
  options: Omit<UseMutationOptions<Ticket, Error, CreateTicketData>, "mutationFn"> = {}
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createTicket,
    onMutate: async (newTicket) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.tickets.lists() });

      const previousData = queryClient.getQueriesData({ queryKey: queryKeys.tickets.lists() });

      // Optimistically add to all ticket lists
      queryClient.setQueriesData<TicketsListResponse>(
        { queryKey: queryKeys.tickets.lists() },
        (old) => {
          if (!old) return old;
          const optimisticTicket: Ticket = {
            id: `temp-${Date.now()}`,
            ...newTicket,
            status: "open",
            source: newTicket.source || "web",
            customer: { id: newTicket.customerId, name: "", email: "" },
            messages: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
          };
          return {
            ...old,
            tickets: [optimisticTicket, ...old.tickets],
            total: old.total + 1,
          };
        }
      );

      return { previousData };
    },
    onError: (error, variables, context) => {
      if (context?.previousData) {
        context.previousData.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data);
        });
      }
      options.onError?.(error, variables, context);
    },
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tickets.lists() });
      options.onSuccess?.(data, variables, context);
    },
  });
}

/**
 * Hook to update a ticket with optimistic update.
 *
 * @param options - Mutation options
 * @returns Mutation result
 */
export function useUpdateTicket(
  options: Omit<UseMutationOptions<Ticket, Error, { id: string; data: UpdateTicketData }>, "mutationFn"> = {}
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => updateTicket(id, data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.tickets.detail(id) });

      const previousTicket = queryClient.getQueryData<Ticket>(queryKeys.tickets.detail(id));

      // Optimistically update ticket detail
      if (previousTicket) {
        queryClient.setQueryData<Ticket>(queryKeys.tickets.detail(id), {
          ...previousTicket,
          ...data,
          updatedAt: new Date().toISOString(),
        });
      }

      return { previousTicket };
    },
    onError: (error, variables, context) => {
      if (context?.previousTicket) {
        queryClient.setQueryData(
          queryKeys.tickets.detail(variables.id),
          context.previousTicket
        );
      }
      options.onError?.(error, variables, context);
    },
    onSuccess: (data, variables, context) => {
      queryClient.setQueryData(queryKeys.tickets.detail(variables.id), data);
      queryClient.invalidateQueries({ queryKey: queryKeys.tickets.lists() });
      options.onSuccess?.(data, variables, context);
    },
  });
}

/**
 * Hook to add a reply to a ticket.
 *
 * @param options - Mutation options
 * @returns Mutation result
 */
export function useAddTicketReply(
  options: Omit<UseMutationOptions<Ticket, Error, { ticketId: string; content: string }>, "mutationFn"> = {}
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ticketId, content }) => addTicketReply(ticketId, content),
    onSuccess: (data, variables, context) => {
      queryClient.setQueryData(queryKeys.tickets.detail(variables.ticketId), data);
      queryClient.invalidateQueries({ queryKey: queryKeys.tickets.lists() });
      options.onSuccess?.(data, variables, context);
    },
  });
}

/**
 * Prefetch tickets for faster navigation.
 *
 * @param filters - Filter options
 * @param page - Page number
 */
export function usePrefetchTickets() {
  const queryClient = useQueryClient();

  return useCallback((filters?: TicketsFilters, page = 1, pageSize = 20) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.tickets.list({ ...filters, page, pageSize }),
      queryFn: () => fetchTickets({ page, pageSize, filters }),
    });
  }, [queryClient]);
}

/**
 * Prefetch a single ticket.
 *
 * @param id - Ticket ID
 */
export function usePrefetchTicket() {
  const queryClient = useQueryClient();

  return useCallback((id: string) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.tickets.detail(id),
      queryFn: () => fetchTicket(id),
    });
  }, [queryClient]);
}

export default useTickets;
