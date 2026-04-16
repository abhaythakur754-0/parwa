/**
 * PARWA Knowledge Base API Client
 *
 * Typed client for all KB and RAG endpoints consumed by the Knowledge Base dashboard.
 * Uses the shared apiClient (axios instance with httpOnly cookie auth + CSRF).
 */

import { get, post, del } from '@/lib/api';
import apiClient from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────────

export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface KBDocument {
  id: string;
  filename: string;
  file_type?: string;
  file_size?: number;
  status: DocumentStatus;
  chunk_count?: number;
  error_message?: string;
  retry_count?: number;
  created_at?: string;
  category?: string;
}

export interface KBDocumentListResponse {
  documents: KBDocument[];
  total: number;
}

export interface KBDocumentUploadResponse {
  id: string;
  filename: string;
  status: DocumentStatus;
  message: string;
}

export interface KBStats {
  total_documents: number;
  total_chunks: number;
  completed: number;
  processing: number;
  failed: number;
  pending: number;
}

export interface RAGSearchRequest {
  query: string;
  top_k?: number;
  company_id?: string;
}

export interface RAGSearchResult {
  content: string;
  source: string;
  score: number;
  page?: number;
  metadata?: Record<string, unknown>;
}

export interface RAGSearchResponse {
  results: RAGSearchResult[];
  query: string;
  total: number;
}

export interface ReindexStatus {
  company_id: string;
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  total: number;
}

export interface RAGHealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  embedding_model?: string;
  vector_store?: string;
  documents_indexed?: number;
  message?: string;
}

// ── KB API Client ──────────────────────────────────────────────────────────

export const kbApi = {
  /** K2: Upload document with progress tracking */
  upload: async (
    file: File,
    onProgress?: (progress: number) => void,
    category?: string,
  ): Promise<KBDocumentUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (category) formData.append('category', category);

    const response = await apiClient.post<KBDocumentUploadResponse>('/api/kb/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    });

    return response.data;
  },

  /** K1: List all documents with optional status filter */
  listDocuments: (params?: { status?: DocumentStatus; category?: string }) =>
    get<KBDocumentListResponse>('/api/kb/documents', { params }),

  /** Get single document details */
  getDocument: (id: string) =>
    get<KBDocument>(`/api/kb/documents/${id}`),

  /** K3: Delete document and associated chunks */
  deleteDocument: (id: string) =>
    del<{ message: string }>(`/api/kb/documents/${id}`),

  /** K3: Retry a failed document */
  retryDocument: (id: string) =>
    post<{ message: string; status: DocumentStatus }>(`/api/kb/documents/${id}/retry`),

  /** K3: Re-index a completed document */
  reindexDocument: (id: string) =>
    post<{ message: string; status: DocumentStatus }>(`/api/kb/documents/${id}/reindex`),

  /** K5: Get KB statistics */
  getStats: () => get<KBStats>('/api/kb/stats'),

  // ── RAG / Search Endpoints ──────────────────────────────────────────────

  /** K4/K8: Semantic search across knowledge base */
  search: (data: RAGSearchRequest) =>
    post<RAGSearchResponse>('/api/rag/search', data),

  /** Trigger full reindexing of all documents */
  triggerReindex: (companyId?: string) =>
    post<{ message: string; task_id?: string }>('/api/rag/reindex', {
      company_id: companyId,
    }),

  /** Get reindex queue status */
  getReindexStatus: (companyId: string) =>
    get<ReindexStatus>(`/api/rag/reindex/status/${companyId}`),

  /** RAG health check */
  getHealth: () => get<RAGHealthResponse>('/api/rag/health'),
};
