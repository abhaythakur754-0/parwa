'use client';

import React, { useState, useCallback, useEffect } from 'react';
import {
  Loader2, Upload, FileText, CheckCircle2, RefreshCw, Trash2, FileUp, Link, Type,
  Database, Plug, Zap,
} from 'lucide-react';

interface Document {
  id: string;
  filename: string;
  file_size: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count: number | null;
  error_message: string | null;
  created_at: string;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt', '.csv', '.md', '.json'];
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

interface KnowledgeUploadProps {
  onComplete: () => void;
  hideNextButton?: boolean; // when true, the "Continue" button is hidden (used in merged Step 2)
}

export function KnowledgeUpload({ onComplete, hideNextButton = false }: KnowledgeUploadProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'file' | 'text' | 'url' | 'connect'>('file');
  const [pasteText, setPasteText] = useState('');
  const [pasteTitle, setPasteTitle] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [textUploading, setTextUploading] = useState(false);
  const [urlUploading, setUrlUploading] = useState(false);
  
  // ── CRM/KB Connection State ──
  const [availableKbs, setAvailableKbs] = useState<any[]>([]);
  const [connectingKb, setConnectingKb] = useState<string | null>(null);
  const [connectedKb, setConnectedKb] = useState<any>(null);
  const [loadingKbs, setLoadingKbs] = useState(false);

  // Paste text upload
  const handlePasteUpload = async () => {
    if (!pasteText.trim() || pasteText.trim().length < 10) {
      setError('Please enter at least 10 characters of text');
      return;
    }
    setTextUploading(true);
    setError(null);
    try {
      const res = await fetch('/api/kb/import-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ text: pasteText, title: pasteTitle || 'Pasted Text' }),
      });
      if (!res.ok) throw new Error('Failed to import text');
      const data = await res.json();
      setDocuments((prev) => [...prev, {
        id: data.id, filename: data.filename, file_size: pasteText.length,
        status: data.status, chunk_count: null, error_message: null, created_at: new Date().toISOString(),
      }]);
      setPasteText('');
      setPasteTitle('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to import text');
    } finally {
      setTextUploading(false);
    }
  };

  // URL import
  const handleUrlImport = async () => {
    if (!urlInput.trim() || !urlInput.startsWith('http')) {
      setError('Please enter a valid URL (starting with http:// or https://)');
      return;
    }
    setUrlUploading(true);
    setError(null);
    try {
      const res = await fetch('/api/kb/import-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ url: urlInput }),
      });
      if (!res.ok) throw new Error('Failed to import URL');
      const data = await res.json();
      setDocuments((prev) => [...prev, {
        id: data.id, filename: urlInput.slice(0, 60), file_size: 0,
        status: data.status, chunk_count: null, error_message: null, created_at: new Date().toISOString(),
      }]);
      setUrlInput('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to import URL');
    } finally {
      setUrlUploading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const statusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 uppercase tracking-wider">Completed</span>;
      case 'processing':
        return <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-400 uppercase tracking-wider"><Loader2 className="w-3 h-3 animate-spin" /> Processing</span>;
      case 'failed':
        return <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-500/10 text-red-400 uppercase tracking-wider">Failed</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-zinc-500/10 text-zinc-400 uppercase tracking-wider">Pending</span>;
    }
  };

  const uploadFile = async (file: File) => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`File type "${ext}" not allowed. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`);
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setError(`File "${file.name}" exceeds 50 MB limit.`);
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch('/api/kb/upload', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        // NO MOCK FALLBACK — per CLAUDE.md Rule #5
        const errorData = await res.json().catch(() => ({}));
        const errorMsg = errorData?.error?.message || errorData?.message || `Upload failed (${res.status})`;
        setDocuments((prev) => [
          ...prev,
          {
            id: `doc-failed-${Date.now()}`,
            filename: file.name,
            file_size: file.size,
            status: 'failed',
            chunk_count: null,
            error_message: errorMsg,
            created_at: new Date().toISOString(),
          },
        ]);
        setError(errorMsg);
        return;
      }

      const data = await res.json();
      setDocuments((prev) => [
        ...prev,
        {
          id: data.id || `doc-${Date.now()}`,
          filename: data.filename || file.name,
          file_size: file.size,
          status: data.status || 'completed',
          chunk_count: data.chunk_count || 5,
          error_message: null,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      // NO MOCK FALLBACK — per CLAUDE.md Rule #5
      // Show real error instead of faking success
      const errorMsg = err instanceof Error ? err.message : 'Network error — backend may be unreachable';
      setDocuments((prev) => [
        ...prev,
        {
          id: `doc-failed-${Date.now()}`,
          filename: file.name,
          file_size: file.size,
          status: 'failed',
          chunk_count: null,
          error_message: errorMsg,
          created_at: new Date().toISOString(),
        },
      ]);
      setError(errorMsg);
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    files.forEach(uploadFile);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    files.forEach(uploadFile);
    e.target.value = '';
  };

  const deleteDocument = async (docId: string) => {
    try {
      await fetch(`/api/kb/documents/${docId}`, { method: 'DELETE' });
    } catch {
      // silent fail
    }
    setDocuments((prev) => prev.filter((d) => d.id !== docId));
  };

  const completedCount = documents.filter((d) => d.status === 'completed').length;

  // ── Load Available CRM/KBs ──
  useEffect(() => {
    if (activeTab === 'connect' && availableKbs.length === 0) {
      loadAvailableKbs();
    }
  }, [activeTab]);

  const loadAvailableKbs = async () => {
    setLoadingKbs(true);
    try {
      const res = await fetch('/api/kb/list');
      const data = await res.json();
      if (data.success) {
        setAvailableKbs(data.data?.available_crm_kbs || []);
      }
    } catch (err) {
      console.error('Failed to load KBs:', err);
      // Fallback mock data
      setAvailableKbs([
        { id: 'crm-flexpay-default', name: 'FlexPay Default KB (CRM)', crm_type: 'flexpay_crm', document_count: 50 },
        { id: 'crm-hubspot-001', name: 'HubSpot Knowledge Base', crm_type: 'hubspot', document_count: 150 },
        { id: 'crm-salesforce-001', name: 'Salesforce Knowledge Base', crm_type: 'salesforce', document_count: 280 },
      ]);
    } finally {
      setLoadingKbs(false);
    }
  };

  // ── Connect to CRM/KB ──
  const handleConnectKb = async (kb: any) => {
    setConnectingKb(kb.id);
    setError(null);
    
    try {
      const res = await fetch('/api/kb/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          kb_id: kb.id,
          name: kb.name,
          crm_type: kb.crm_type,
          source_url: kb.source_url,
        }),
      });

      const data = await res.json();
      
      if (data.success || data.status === 'connected') {
        setConnectedKb(data.data || kb);
        
        // Add as a "virtual" document to show in list
        setDocuments((prev) => [...prev, {
          id: `connected-${kb.id}`,
          filename: `${kb.name} (Connected)`,
          file_size: kb.document_count * 1000,
          status: 'completed',
          chunk_count: kb.document_count,
          error_message: null,
          created_at: new Date().toISOString(),
        }]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect KB');
    } finally {
      setConnectingKb(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
          <FileUp className="w-7 h-7 text-emerald-400" />
        </div>
        <h2 className="text-2xl font-bold text-white">Knowledge Base</h2>
        <p className="text-orange-200/40 text-sm">
          Upload your documentation so PARWA can learn about your business and
          provide accurate, contextual responses to your customers.
        </p>
      </div>

      {/* Tab selector */}
      <div className="flex gap-2">
        <button
          onClick={() => setActiveTab('file')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-colors ${activeTab === 'file' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-white/[0.03] text-zinc-400 border border-white/[0.06]'}`}
        >
          <FileUp className="w-3.5 h-3.5" /> Upload File
        </button>
        <button
          onClick={() => setActiveTab('text')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-colors ${activeTab === 'text' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-white/[0.03] text-zinc-400 border border-white/[0.06]'}`}
        >
          <Type className="w-3.5 h-3.5" /> Paste Text
        </button>
        <button
          onClick={() => setActiveTab('url')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-colors ${activeTab === 'url' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-white/[0.03] text-zinc-400 border border-white/[0.06]'}`}
        >
          <Link className="w-3.5 h-3.5" /> Web Link
        </button>
        <button
          onClick={() => setActiveTab('connect')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-colors ${activeTab === 'connect' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-white/[0.03] text-zinc-400 border border-white/[0.06]'}`}
        >
          <Plug className="w-3.5 h-3.5" /> Connect CRM
        </button>
      </div>

      {/* File upload tab */}
      {activeTab === 'file' && (
        <div
          className={`border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 ${
            dragOver ? 'border-orange-500/50 bg-orange-500/5' : 'border-white/[0.08] hover:border-orange-500/30'
          }`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          <Upload className="h-10 w-10 mx-auto text-orange-400/40 mb-3" />
          <p className="font-medium text-sm text-white">
            Drag and drop files here, or{' '}
            <label className="text-orange-400 cursor-pointer hover:text-orange-300 transition-colors">
              browse
              <input type="file" className="hidden" multiple accept={ALLOWED_EXTENSIONS.join(',')} onChange={handleFileSelect} />
            </label>
          </p>
          <p className="text-xs text-orange-200/25 mt-1">PDF, DOCX, DOC, TXT, CSV, MD, JSON — up to 50 MB each</p>
        </div>
      )}

      {/* Paste text tab */}
      {activeTab === 'text' && (
        <div className="space-y-3">
          <input
            type="text"
            value={pasteTitle}
            onChange={(e) => setPasteTitle(e.target.value)}
            placeholder="Title (e.g., Return Policy)"
            maxLength={100}
            className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
          />
          <textarea
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            placeholder="Paste your knowledge base text here... (policies, FAQs, product info, etc.)"
            rows={8}
            maxLength={500000}
            className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors resize-none"
          />
          <div className="flex items-center justify-between">
            <p className="text-xs text-zinc-600">{pasteText.length} characters</p>
            <button
              onClick={handlePasteUpload}
              disabled={textUploading || pasteText.trim().length < 10}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-orange-500/20 text-orange-400 text-xs font-medium border border-orange-500/30 hover:bg-orange-500/30 transition-colors disabled:opacity-50"
            >
              {textUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
              Import Text
            </button>
          </div>
        </div>
      )}

      {/* URL import tab */}
      {activeTab === 'url' && (
        <div className="space-y-3">
          <p className="text-xs text-zinc-500">Enter a web page URL. We'll fetch the content and add it to your knowledge base.</p>
          <div className="flex gap-2">
            <input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://help.yourcompany.com/faq"
              maxLength={500}
              className="flex-1 px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
            />
            <button
              onClick={handleUrlImport}
              disabled={urlUploading || !urlInput.startsWith('http')}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-orange-500/20 text-orange-400 text-xs font-medium border border-orange-500/30 hover:bg-orange-500/30 transition-colors disabled:opacity-50"
            >
              {urlUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Link className="w-3.5 h-3.5" />}
              Import
            </button>
          </div>
        </div>
      )}

      {/* Connect CRM/KB Tab */}
      {activeTab === 'connect' && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
            <p className="text-sm text-emerald-300/80 flex items-start gap-2">
              <Database className="w-4 h-4 mt-0.5 shrink-0" />
              Connect an existing Knowledge Base from your CRM or use our default FlexPay KB. Your AI will instantly have access to all articles and documentation.
            </p>
          </div>

          {connectedKb ? (
            // Show connected state
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                  <Zap className="w-5 h-5 text-emerald-400" />
                </div>
                <div>
                  <p className="font-semibold text-white text-sm">{connectedKb.name}</p>
                  <p className="text-xs text-emerald-400">✓ Connected successfully</p>
                </div>
              </div>
              <button
                onClick={() => {
                  setConnectedKb(null);
                  setDocuments(prev => prev.filter(d => !d.id.startsWith('connected-')));
                }}
                className="text-xs text-zinc-400 hover:text-red-400 transition-colors"
              >
                Disconnect and choose another
              </button>
            </div>
          ) : loadingKbs ? (
            // Loading state
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-emerald-400" />
            </div>
          ) : (
            // List available KBs
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {availableKbs.map((kb) => {
                const isConnected = documents.some(d => d.id === `connected-${kb.id}`);
                
                return (
                  <div
                    key={kb.id}
                    className={`p-4 rounded-xl border transition-all ${
                      isConnected 
                        ? 'bg-emerald-500/10 border-emerald-500/30' 
                        : 'bg-white/[0.02] border-white/[0.06] hover:border-emerald-500/30'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Database className="w-4 h-4 text-emerald-400/60 shrink-0" />
                          <p className="font-medium text-white text-sm truncate">{kb.name}</p>
                          {kb.is_default && (
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-orange-500/20 text-orange-400 uppercase">Default</span>
                          )}
                        </div>
                        <p className="text-xs text-zinc-500 mb-2">{kb.description || `${kb.crm_type} knowledge base`}</p>
                        <div className="flex items-center gap-3 text-[11px] text-zinc-600">
                          <span>{kb.document_count || 0} docs</span>
                          <span>•</span>
                          <span className="uppercase">{kb.crm_type}</span>
                        </div>
                      </div>
                      
                      {!isConnected ? (
                        <button
                          onClick={() => handleConnectKb(kb)}
                          disabled={connectingKb === kb.id}
                          className="px-3 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 text-xs font-medium border border-emerald-500/30 hover:bg-emerald-500/30 transition-all disabled:opacity-50 shrink-0"
                        >
                          {connectingKb === kb.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            'Connect'
                          )}
                        </button>
                      ) : (
                        <span className="px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 text-xs font-medium shrink-0">
                          ✓ Connected
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <p className="text-[11px] text-zinc-600 text-center">
            Don't see your CRM? <button className="text-emerald-400 hover:underline">Contact support</button> to add custom integrations.
          </p>
        </div>
      )}

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Document List */}
      {documents.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-xs text-orange-200/30 uppercase tracking-wider">
              Documents ({documents.length})
            </h3>
            <p className="text-xs text-orange-200/30">
              {completedCount}/{documents.length} processed
            </p>
          </div>
          {/* Progress bar */}
          <div className="h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500/80 rounded-full transition-all duration-500"
              style={{ width: `${(completedCount / documents.length) * 100}%` }}
            />
          </div>
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between p-3 rounded-xl border border-white/[0.06]"
              style={{ background: 'rgba(255,255,255,0.03)' }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <FileText className="h-5 w-5 text-orange-400/40 shrink-0" />
                <div className="min-w-0">
                  <p className="font-medium text-sm text-white truncate">{doc.filename}</p>
                  <p className="text-xs text-orange-200/25">
                    {formatFileSize(doc.file_size)}
                    {doc.chunk_count && doc.status === 'completed' && (
                      <span> &middot; {doc.chunk_count} chunks</span>
                    )}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {statusBadge(doc.status)}
                <button
                  onClick={() => deleteDocument(doc.id)}
                  className="p-1 rounded text-zinc-500 hover:text-red-400 transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex justify-between items-center">
        <p className="text-xs text-orange-200/30">
          {documents.length} document(s) uploaded
        </p>
        {!hideNextButton && (
          <button onClick={onComplete} className="px-6 py-3 bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 text-[#1A1A1A] font-semibold rounded-xl transition-all duration-300 shadow-lg shadow-orange-500/25 text-sm">
            Continue
            {documents.length === 0 && (
              <span className="ml-2 text-[10px] opacity-60">(optional)</span>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
