'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import {
  fetchKnowledgeDocuments, fetchSearchMetrics, uploadDocument, reindexDocument,
} from '@/lib/api';
import type { KnowledgeDocument, SearchMetrics } from '@/lib/types';
import {
  FileText, Upload, Search, RefreshCw, CheckCircle, Clock, AlertCircle, Loader2,
} from 'lucide-react';

const statusConfig: Record<string, { color: string; icon: React.ElementType }> = {
  indexed: { color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400', icon: CheckCircle },
  indexing: { color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400', icon: Loader2 },
  error: { color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400', icon: AlertCircle },
  pending: { color: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400', icon: Clock },
};

export function KnowledgeBasePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [metrics, setMetrics] = useState<SearchMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    Promise.all([fetchKnowledgeDocuments(), fetchSearchMetrics()]).then(([docs, m]) => {
      setDocuments(docs);
      setMetrics(m);
      setLoading(false);
    });
  }, []);

  const handleUpload = async () => {
    setUploading(true);
    const file = new File(['test content'], 'new-document.pdf', { type: 'application/pdf' });
    const doc = await uploadDocument(file);
    setDocuments(prev => [doc, ...prev]);
    setUploading(false);
  };

  const handleReindex = async (docId: string) => {
    await reindexDocument(docId);
    setDocuments(prev => prev.map(d => d.id === docId ? { ...d, status: 'indexing' as const } : d));
  };

  if (loading) {
    return <div className="space-y-6"><Skeleton className="h-48 w-full" /><Skeleton className="h-64 w-full" /></div>;
  }

  return (
    <div className="space-y-6">
      {/* Search Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        {metrics && [
          { label: 'Avg Relevance', value: `${(metrics.avgRelevanceScore * 100).toFixed(0)}%`, color: 'emerald' },
          { label: 'Retrieval Latency', value: `${metrics.retrievalLatency}ms`, color: 'amber' },
          { label: 'Hit Rate', value: `${metrics.hitRate}%`, color: 'emerald' },
          { label: 'Total Queries', value: metrics.totalQueries.toLocaleString(), color: 'blue' },
          { label: 'Failed Queries', value: metrics.failedQueries.toString(), color: 'red' },
        ].map(stat => (
          <Card key={stat.label}>
            <CardContent className="p-4 text-center">
              <p className="text-xs text-muted-foreground">{stat.label}</p>
              <p className="text-xl font-bold">{stat.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Upload Area */}
      <Card>
        <CardContent className="p-6">
          <div className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-emerald-400 transition-colors cursor-pointer" onClick={handleUpload}>
            <Upload className="h-8 w-8 mx-auto text-muted-foreground mb-3" />
            <p className="text-sm font-medium">Drop files here or click to upload</p>
            <p className="text-xs text-muted-foreground mt-1">Supports PDF, DOCX, TXT, CSV</p>
            {uploading && (
              <div className="mt-3 flex items-center justify-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-xs">Uploading...</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Document List */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Documents</CardTitle>
            <Badge variant="outline" className="border-0 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400">
              {documents.length} documents
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left font-medium text-muted-foreground pb-3">Name</th>
                  <th className="text-left font-medium text-muted-foreground pb-3">Type</th>
                  <th className="text-right font-medium text-muted-foreground pb-3">Chunks</th>
                  <th className="text-left font-medium text-muted-foreground pb-3">Status</th>
                  <th className="text-left font-medium text-muted-foreground pb-3">Last Indexed</th>
                  <th className="text-right font-medium text-muted-foreground pb-3"></th>
                </tr>
              </thead>
              <tbody>
                {documents.map(doc => {
                  const config = statusConfig[doc.status];
                  const Icon = config.icon;
                  return (
                    <tr key={doc.id} className="border-b border-border/50 hover:bg-muted/50">
                      <td className="py-3 flex items-center gap-2">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">{doc.name}</span>
                      </td>
                      <td className="py-3 text-xs uppercase">{doc.type}</td>
                      <td className="py-3 text-right font-mono text-xs">{doc.chunkCount}</td>
                      <td className="py-3">
                        <Badge variant="outline" className={`text-[10px] px-1.5 py-0 border-0 ${config.color}`}>
                          <Icon className={`h-3 w-3 mr-1 ${doc.status === 'indexing' ? 'animate-spin' : ''}`} />
                          {doc.status}
                        </Badge>
                      </td>
                      <td className="py-3 text-xs text-muted-foreground">
                        {new Date(doc.lastIndexed).toLocaleString()}
                      </td>
                      <td className="py-3 text-right">
                        <Button variant="ghost" size="sm" onClick={() => handleReindex(doc.id)}>
                          <RefreshCw className="h-3 w-3" />
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
