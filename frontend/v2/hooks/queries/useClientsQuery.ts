/**
 * PARWA Clients Query Hook
 *
 * Enhanced hook for client data management using React Query.
 * Features prefetching, caching strategies, and health monitoring.
 *
 * @module hooks/queries/useClientsQuery
 */

"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import { useCallback } from "react";
import { z } from "zod";
import { queryKeys } from "../../lib/react-query/query-client";

// ============================================================================
// Types & Schemas
// ============================================================================

/**
 * Client industry enumeration.
 */
export const ClientIndustrySchema = z.enum([
  "ecommerce",
  "saas",
  "healthcare",
  "financial",
  "logistics",
  "retail",
  "education",
  "other",
]);
export type ClientIndustry = z.infer<typeof ClientIndustrySchema>;

/**
 * Client status enumeration.
 */
export const ClientStatusSchema = z.enum(["trial", "active", "paused", "churned"]);
export type ClientStatus = z.infer<typeof ClientStatusSchema>;

/**
 * Client subscription tier.
 */
export const SubscriptionTierSchema = z.enum(["starter", "professional", "enterprise", "custom"]);
export type SubscriptionTier = z.infer<typeof SubscriptionTierSchema>;

/**
 * Client schema.
 */
export const ClientSchema = z.object({
  id: z.string(),
  name: z.string(),
  domain: z.string(),
  industry: ClientIndustrySchema,
  status: ClientStatusSchema,
  subscriptionTier: SubscriptionTierSchema,
  logo: z.string().optional(),
  primaryContact: z.object({
    name: z.string(),
    email: z.string().email(),
    phone: z.string().optional(),
  }),
  settings: z.object({
    timezone: z.string(),
    language: z.string(),
    currency: z.string(),
    notifications: z.object({
      email: z.boolean(),
      slack: z.boolean(),
      webhook: z.boolean(),
    }),
  }),
  integrations: z.array(
    z.object({
      type: z.string(),
      name: z.string(),
      status: z.enum(["connected", "disconnected", "error"]),
      lastSync: z.string().optional(),
    })
  ),
  usage: z.object({
    ticketsThisMonth: z.number(),
    ticketsLimit: z.number(),
    storageUsed: z.number(),
    storageLimit: z.number(),
    apiCallsThisMonth: z.number(),
    apiCallsLimit: z.number(),
  }),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export type Client = z.infer<typeof ClientSchema>;

/**
 * Client health metrics schema.
 */
export const ClientHealthSchema = z.object({
  clientId: z.string(),
  healthScore: z.number().min(0).max(100),
  engagementScore: z.number().min(0).max(100),
  adoptionScore: z.number().min(0).max(100),
  riskLevel: z.enum(["low", "medium", "high", "critical"]),
  riskFactors: z.array(
    z.object({
      factor: z.string(),
      severity: z.enum(["low", "medium", "high"]),
      recommendation: z.string(),
    })
  ),
  lastActive: z.string(),
  trends: z.object({
    ticketVolume: z.enum(["increasing", "stable", "decreasing"]),
    responseTime: z.enum(["improving", "stable", "degrading"]),
    satisfaction: z.enum(["improving", "stable", "declining"]),
  }),
  milestones: z.array(
    z.object({
      name: z.string(),
      status: z.enum(["completed", "in_progress", "pending", "at_risk"]),
      dueDate: z.string().optional(),
    })
  ),
});

export type ClientHealth = z.infer<typeof ClientHealthSchema>;

/**
 * Clients list response schema.
 */
export const ClientsListResponseSchema = z.object({
  clients: z.array(ClientSchema),
  total: z.number(),
  page: z.number(),
  pageSize: z.number(),
});

export type ClientsListResponse = z.infer<typeof ClientsListResponseSchema>;

/**
 * Clients filter options schema.
 */
export const ClientsFiltersSchema = z.object({
  industry: ClientIndustrySchema.optional(),
  status: ClientStatusSchema.optional(),
  tier: SubscriptionTierSchema.optional(),
  search: z.string().optional(),
  sortBy: z.enum(["name", "createdAt", "usage", "health"]).optional(),
  sortOrder: z.enum(["asc", "desc"]).optional(),
});

export type ClientsFilters = z.infer<typeof ClientsFiltersSchema>;

/**
 * Create client data schema.
 */
export const CreateClientDataSchema = z.object({
  name: z.string().min(1).max(100),
  domain: z.string().min(1),
  industry: ClientIndustrySchema,
  primaryContact: z.object({
    name: z.string(),
    email: z.string().email(),
    phone: z.string().optional(),
  }),
  settings: z
    .object({
      timezone: z.string().optional(),
      language: z.string().optional(),
      currency: z.string().optional(),
    })
    .optional(),
});

export type CreateClientData = z.infer<typeof CreateClientDataSchema>;

/**
 * Update client data schema.
 */
export const UpdateClientDataSchema = z.object({
  name: z.string().min(1).max(100).optional(),
  status: ClientStatusSchema.optional(),
  settings: z
    .object({
      timezone: z.string().optional(),
      language: z.string().optional(),
      currency: z.string().optional(),
      notifications: z
        .object({
          email: z.boolean().optional(),
          slack: z.boolean().optional(),
          webhook: z.boolean().optional(),
        })
        .optional(),
    })
    .optional(),
});

export type UpdateClientData = z.infer<typeof UpdateClientDataSchema>;

/**
 * Client stats schema.
 */
export const ClientStatsSchema = z.object({
  totalClients: z.number(),
  activeClients: z.number(),
  trialClients: z.number(),
  churnedClients: z.number(),
  byIndustry: z.record(z.number()),
  byTier: z.record(z.number()),
  averageHealthScore: z.number(),
});

export type ClientStats = z.infer<typeof ClientStatsSchema>;

// ============================================================================
// API Functions
// ============================================================================

const API_BASE = "/api";

/**
 * Fetch clients list with filters and pagination.
 */
async function fetchClients(params: {
  page: number;
  pageSize: number;
  filters?: ClientsFilters;
}): Promise<ClientsListResponse> {
  const searchParams = new URLSearchParams({
    page: String(params.page),
    pageSize: String(params.pageSize),
  });

  if (params.filters) {
    const { filters } = params;
    if (filters.industry) searchParams.set("industry", filters.industry);
    if (filters.status) searchParams.set("status", filters.status);
    if (filters.tier) searchParams.set("tier", filters.tier);
    if (filters.search) searchParams.set("search", filters.search);
    if (filters.sortBy) searchParams.set("sortBy", filters.sortBy);
    if (filters.sortOrder) searchParams.set("sortOrder", filters.sortOrder);
  }

  const response = await fetch(`${API_BASE}/clients?${searchParams}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch clients: ${response.statusText}`);
  }

  const data = await response.json();
  return ClientsListResponseSchema.parse(data);
}

/**
 * Fetch a single client by ID.
 */
async function fetchClient(id: string): Promise<Client> {
  const response = await fetch(`${API_BASE}/clients/${id}`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Client not found");
    }
    throw new Error(`Failed to fetch client: ${response.statusText}`);
  }

  const data = await response.json();
  return ClientSchema.parse(data);
}

/**
 * Fetch client health metrics.
 */
async function fetchClientHealth(id: string): Promise<ClientHealth> {
  const response = await fetch(`${API_BASE}/clients/${id}/health`);
  if (!response.ok) {
    throw new Error(`Failed to fetch client health: ${response.statusText}`);
  }

  const data = await response.json();
  return ClientHealthSchema.parse(data);
}

/**
 * Create a new client.
 */
async function createClient(data: CreateClientData): Promise<Client> {
  const validatedData = CreateClientDataSchema.parse(data);

  const response = await fetch(`${API_BASE}/clients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(validatedData),
  });

  if (!response.ok) {
    throw new Error(`Failed to create client: ${response.statusText}`);
  }

  const client = await response.json();
  return ClientSchema.parse(client);
}

/**
 * Update a client.
 */
async function updateClient(id: string, data: UpdateClientData): Promise<Client> {
  const validatedData = UpdateClientDataSchema.parse(data);

  const response = await fetch(`${API_BASE}/clients/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(validatedData),
  });

  if (!response.ok) {
    throw new Error(`Failed to update client: ${response.statusText}`);
  }

  const client = await response.json();
  return ClientSchema.parse(client);
}

/**
 * Fetch client statistics.
 */
async function fetchClientStats(): Promise<ClientStats> {
  const response = await fetch(`${API_BASE}/clients/stats`);
  if (!response.ok) {
    throw new Error(`Failed to fetch client stats: ${response.statusText}`);
  }

  const data = await response.json();
  return ClientStatsSchema.parse(data);
}

// ============================================================================
// Query Hooks
// ============================================================================

/**
 * Options for useClients hook.
 */
export interface UseClientsOptions
  extends Omit<UseQueryOptions<ClientsListResponse, Error>, "queryKey" | "queryFn"> {
  /** Initial filters */
  filters?: ClientsFilters;
  /** Page number */
  page?: number;
  /** Items per page */
  pageSize?: number;
}

/**
 * Hook to fetch clients list with pagination and filtering.
 *
 * @param options - Query options
 * @returns Query result with clients data
 *
 * @example
 * ```tsx
 * function ClientsList() {
 *   const { data, isLoading } = useClients({
 *     filters: { status: 'active' },
 *   });
 *
 *   return (
 *     <div>
 *       {data?.clients.map(client => (
 *         <ClientCard key={client.id} client={client} />
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
export function useClients(options: UseClientsOptions = {}) {
  const { filters = {}, page = 1, pageSize = 20, ...queryOptions } = options;

  return useQuery({
    queryKey: queryKeys.clients.list({ ...filters, page, pageSize }),
    queryFn: () => fetchClients({ page, pageSize, filters }),
    staleTime: 10 * 60 * 1000, // 10 minutes
    ...queryOptions,
  });
}

/**
 * Options for useClient hook.
 */
export interface UseClientOptions
  extends Omit<UseQueryOptions<Client, Error>, "queryKey" | "queryFn"> {
  /** Client ID */
  id: string;
}

/**
 * Hook to fetch a single client by ID.
 *
 * @param options - Query options including client ID
 * @returns Query result with client data
 */
export function useClient(options: UseClientOptions) {
  const { id, ...queryOptions } = options;

  return useQuery({
    queryKey: queryKeys.clients.detail(id),
    queryFn: () => fetchClient(id),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
    ...queryOptions,
  });
}

/**
 * Options for useClientHealth hook.
 */
export interface UseClientHealthOptions
  extends Omit<UseQueryOptions<ClientHealth, Error>, "queryKey" | "queryFn"> {
  /** Client ID */
  clientId: string;
  /** Auto-refresh interval */
  refetchInterval?: number;
}

/**
 * Hook to fetch client health metrics.
 *
 * @param options - Query options including client ID
 * @returns Query result with health data
 */
export function useClientHealth(options: UseClientHealthOptions) {
  const { clientId, refetchInterval = 60000, ...queryOptions } = options;

  return useQuery({
    queryKey: queryKeys.clients.health(clientId),
    queryFn: () => fetchClientHealth(clientId),
    enabled: !!clientId,
    staleTime: 5 * 60 * 1000,
    refetchInterval,
    ...queryOptions,
  });
}

/**
 * Hook to fetch client statistics.
 *
 * @param options - Query options
 * @returns Query result with client stats
 */
export function useClientStats(
  options: Omit<UseQueryOptions<ClientStats, Error>, "queryKey" | "queryFn"> = {}
) {
  return useQuery({
    queryKey: ["clients", "stats"],
    queryFn: fetchClientStats,
    staleTime: 10 * 60 * 1000,
    ...options,
  });
}

// ============================================================================
// Mutation Hooks
// ============================================================================

/**
 * Hook to create a new client.
 *
 * @param options - Mutation options
 * @returns Mutation result
 */
export function useCreateClient(
  options: Omit<UseMutationOptions<Client, Error, CreateClientData>, "mutationFn"> = {}
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createClient,
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.clients.lists() });
      queryClient.setQueryData(queryKeys.clients.detail(data.id), data);
      options.onSuccess?.(data, variables, context);
    },
  });
}

/**
 * Hook to update a client.
 *
 * @param options - Mutation options
 * @returns Mutation result
 */
export function useUpdateClient(
  options: Omit<UseMutationOptions<Client, Error, { id: string; data: UpdateClientData }>, "mutationFn"> = {}
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => updateClient(id, data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.clients.detail(id) });

      const previousClient = queryClient.getQueryData<Client>(queryKeys.clients.detail(id));

      if (previousClient) {
        queryClient.setQueryData<Client>(queryKeys.clients.detail(id), {
          ...previousClient,
          ...data,
          updatedAt: new Date().toISOString(),
        });
      }

      return { previousClient };
    },
    onError: (error, variables, context) => {
      if (context?.previousClient) {
        queryClient.setQueryData(queryKeys.clients.detail(variables.id), context.previousClient);
      }
      options.onError?.(error, variables, context);
    },
    onSuccess: (data, variables, context) => {
      queryClient.setQueryData(queryKeys.clients.detail(variables.id), data);
      queryClient.invalidateQueries({ queryKey: queryKeys.clients.lists() });
      options.onSuccess?.(data, variables, context);
    },
  });
}

// ============================================================================
// Prefetch Hooks
// ============================================================================

/**
 * Prefetch clients for faster navigation.
 */
export function usePrefetchClients() {
  const queryClient = useQueryClient();

  return useCallback((filters?: ClientsFilters, page = 1, pageSize = 20) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.clients.list({ ...filters, page, pageSize }),
      queryFn: () => fetchClients({ page, pageSize, filters }),
    });
  }, [queryClient]);
}

/**
 * Prefetch a single client.
 */
export function usePrefetchClient() {
  const queryClient = useQueryClient();

  return useCallback((id: string) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.clients.detail(id),
      queryFn: () => fetchClient(id),
    });
  }, [queryClient]);
}

/**
 * Prefetch client health data.
 */
export function usePrefetchClientHealth() {
  const queryClient = useQueryClient();

  return useCallback((clientId: string) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.clients.health(clientId),
      queryFn: () => fetchClientHealth(clientId),
    });
  }, [queryClient]);
}

/**
 * Hook to prefetch all related client data.
 */
export function usePrefetchClientDetails() {
  const prefetchClient = usePrefetchClient();
  const prefetchHealth = usePrefetchClientHealth();

  return useCallback(
    (clientId: string) => {
      prefetchClient(clientId);
      prefetchHealth(clientId);
    },
    [prefetchClient, prefetchHealth]
  );
}

export default useClients;
