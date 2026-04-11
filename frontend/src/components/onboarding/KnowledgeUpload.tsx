'use client';

import React, { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Loader2, Upload, FileText, CheckCircle2, XCircle, RefreshCw, Trash2, FileUp,
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
}

export function KnowledgeUpload({ onComplete }: KnowledgeUploadProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const statusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge className="bg-green-100 text-green-800">Completed</Badge>;
      case 'processing':
        return <Badge className="bg-blue-100 text-blue-800">
          <Loader2 className="h-3 w-3 mr-1 animate-spin" /> Processing
        </Badge>;
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>;
      default:
        return <Badge variant="secondary">Pending</Badge>;
    }
  };

  const uploadFile = async (file: File) => {
    const ext = '.' + file.name.rsplit('.', 1).pop()?.toLowerCase();
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
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || data?.error?.message || 'Upload failed');
      }

      const data = await res.json();
      setDocuments((prev) => [
        ...prev,
        {
          id: data.id,
          filename: data.filename,
          file_size: file.size,
          status: data.status,
          chunk_count: null,
          error_message: null,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
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

  const retryDocument = async (docId: string) => {
    try {
      setDocuments((prev) =>
        prev.map((d) => (d.id === docId ? { ...d, status: 'processing' as const } : d))
      );
      const res = await fetch(`/api/kb/documents/${docId}/retry`, { method: 'POST' });
      if (!res.ok) throw new Error('Retry failed');
    } catch {
      setDocuments((prev) =>
        prev.map((d) => (d.id === docId ? { ...d, status: 'failed' as const } : d))
      );
    }
  };

  const deleteDocument = async (docId: string) => {
    try {
      await fetch(`/api/kb/documents/${docId}`, { method: 'DELETE' });
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch {
      // silent fail
    }
  };

  const completedCount = documents.filter((d) => d.status === 'completed').length;

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <FileUp className="h-12 w-12 mx-auto text-emerald-600" />
        <h2 className="text-2xl font-bold">Knowledge Base</h2>
        <p className="text-muted-foreground">
          Upload your documentation so PARWA can learn about your business and
          provide accurate, contextual responses to your customers.
        </p>
      </div>

      {/* Drop Zone */}
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          dragOver
            ? 'border-primary bg-primary/5'
            : 'border-muted-foreground/25 hover:border-primary/50'
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <Upload className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
        <p className="font-medium">
          Drag and drop files here, or{' '}
          <label className="text-primary cursor-pointer hover:underline">
            browse
            <input
              type="file"
              className="hidden"
              multiple
              accept={ALLOWED_EXTENSIONS.join(',')}
              onChange={handleFileSelect}
            />
          </label>
        </p>
        <p className="text-sm text-muted-foreground mt-1">
          PDF, DOCX, DOC, TXT, CSV, MD, JSON — up to 50 MB each
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Document List */}
      {documents.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm">
              Documents ({documents.length})
            </h3>
            <p className="text-sm text-muted-foreground">
              {completedCount}/{documents.length} processed
            </p>
          </div>
          <Progress value={(completedCount / documents.length) * 100} className="h-2" />
          {documents.map((doc) => (
            <Card key={doc.id}>
              <CardContent className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3 min-w-0">
                  <FileText className="h-5 w-5 text-muted-foreground shrink-0" />
                  <div className="min-w-0">
                    <p className="font-medium truncate">{doc.filename}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatFileSize(doc.file_size)}
                      {doc.chunk_count && doc.status === 'completed' && (
                        <span> &middot; {doc.chunk_count} chunks</span>
                      )}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {statusBadge(doc.status)}
                  {doc.status === 'failed' && (
                    <Button variant="ghost" size="sm" onClick={() => retryDocument(doc.id)}>
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => deleteDocument(doc.id)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <div className="flex justify-between">
        <p className="text-sm text-muted-foreground">
          {documents.length} document(s) uploaded
        </p>
        <Button onClick={onComplete} size="lg">
          Continue
          {documents.length === 0 && (
            <span className="ml-2 text-xs text-muted-foreground">(optional)</span>
          )}
        </Button>
      </div>
    </div>
  );
}
