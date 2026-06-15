"use client";

import { useState, useCallback } from "react";
import { Upload, FileText, Trash2, Search, Loader2, CheckCircle, XCircle, File } from "lucide-react";

interface KBDocument {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: string;
  error_message: string | null;
  created_at: string;
}

interface SearchResult {
  document_id: string;
  filename: string;
  relevance_score: number;
  preview: string;
}

/**
 * KBUploadWidget — GAP 7 Knowledge Base upload and management.
 */
export function KBUploadWidget() {
  const [documents, setDocuments] = useState<KBDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ success: boolean; message: string } | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [stats, setStats] = useState<{ total_documents: number; ready_documents: number; total_chunks: number; total_size_mb: number } | null>(null);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/kb/documents");
      const data = await res.json();
      setDocuments(data.documents || []);
    } catch { /* silently fail */ }
    finally { setLoading(false); }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch("/api/kb/stats");
      const data = await res.json();
      setStats(data);
    } catch { /* silently fail */ }
  }, []);

  const handleUpload = async (files: FileList) => {
    setUploading(true);
    setUploadResult(null);
    let successCount = 0;
    let failCount = 0;
    for (let i = 0; i < files.length; i++) {
      const formData = new FormData();
      formData.append("file", files[i]);
      try {
        const res = await fetch("/api/kb/upload", { method: "POST", body: formData });
        res.ok ? successCount++ : failCount++;
      } catch { failCount++; }
    }
    setUploadResult({ success: failCount === 0, message: `Uploaded ${successCount} file(s)${failCount > 0 ? `, ${failCount} failed` : ""}` });
    setUploading(false);
    fetchDocuments();
    fetchStats();
  };

  const handleDelete = async (documentId: string) => {
    try {
      await fetch(`/api/kb/documents/${documentId}`, { method: "DELETE" });
      fetchDocuments();
      fetchStats();
    } catch { /* silently fail */ }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const res = await fetch("/api/kb/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery, top_k: 5 }),
      });
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch { /* silently fail */ }
    finally { setSearching(false); }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "ready": return <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-green-700 bg-green-50 rounded-full"><CheckCircle className="h-3 w-3" /> Ready</span>;
      case "processing": return <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-yellow-700 bg-yellow-50 rounded-full"><Loader2 className="h-3 w-3 animate-spin" /> Processing</span>;
      case "error": return <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-red-700 bg-red-50 rounded-full"><XCircle className="h-3 w-3" /> Error</span>;
      default: return <span className="px-2 py-0.5 text-xs font-medium text-gray-700 bg-gray-50 rounded-full">{status}</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-3">Upload Documents</h3>
        <p className="text-sm text-gray-500 mb-3">Supported: PDF, DOCX, TXT, MD, CSV, HTML, JSON</p>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 cursor-pointer transition-colors">
            <Upload className="h-4 w-4" />
            {uploading ? "Uploading..." : "Choose Files"}
            <input type="file" multiple accept=".pdf,.docx,.txt,.md,.csv,.html,.htm,.json" className="hidden" onChange={(e) => e.target.files && handleUpload(e.target.files)} disabled={uploading} />
          </label>
          {uploadResult && <span className={`text-sm ${uploadResult.success ? "text-green-600" : "text-red-600"}`}>{uploadResult.message}</span>}
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Documents", value: stats.total_documents, color: "text-gray-900" },
            { label: "Ready", value: stats.ready_documents, color: "text-green-600" },
            { label: "Chunks", value: stats.total_chunks, color: "text-blue-600" },
            { label: "MB", value: stats.total_size_mb, color: "text-purple-600" },
          ].map((s) => (
            <div key={s.label} className="bg-gray-50 rounded-lg p-3 text-center">
              <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
              <p className="text-xs text-gray-500">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Search */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-3">Search Knowledge Base</h3>
        <div className="flex gap-2">
          <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleSearch()} placeholder="Search your knowledge base..." className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          <button onClick={handleSearch} disabled={searching || !searchQuery.trim()} className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50 text-sm">
            {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          </button>
        </div>
        {searchResults.length > 0 && (
          <div className="mt-3 space-y-2">
            {searchResults.map((r, i) => (
              <div key={i} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-gray-400" />
                  <span className="text-sm font-medium text-gray-900">{r.filename}</span>
                  <span className="text-xs text-gray-500">Score: {r.relevance_score}</span>
                </div>
                <p className="text-xs text-gray-600 mt-1">{r.preview}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Document List */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold text-gray-900">Documents</h3>
          <button onClick={() => { fetchDocuments(); fetchStats(); }} className="text-sm text-blue-600 hover:text-blue-800">Refresh</button>
        </div>
        {loading ? (
          <div className="text-center py-8"><Loader2 className="mx-auto h-6 w-6 animate-spin text-gray-400" /></div>
        ) : documents.length === 0 ? (
          <div className="text-center py-8 text-gray-500"><File className="mx-auto h-8 w-8 text-gray-300 mb-2" /><p className="text-sm">No documents uploaded yet</p></div>
        ) : (
          <div className="space-y-2">
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg">
                <div className="flex items-center gap-3">
                  <FileText className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">{doc.filename}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-gray-500">{formatFileSize(doc.file_size)}</span>
                      <span className="text-xs text-gray-300">|</span>
                      <span className="text-xs text-gray-500">{doc.chunk_count} chunks</span>
                      {getStatusBadge(doc.status)}
                    </div>
                    {doc.error_message && <p className="text-xs text-red-600 mt-1">{doc.error_message}</p>}
                  </div>
                </div>
                <button onClick={() => handleDelete(doc.id)} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors" title="Delete">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
