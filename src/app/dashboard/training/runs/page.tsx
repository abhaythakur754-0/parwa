'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import {
  Loader2,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  Play,
  ArrowLeft,
} from 'lucide-react';
import Link from 'next/link';
import { listTrainingRuns, type TrainingRun } from '@/lib/training-api';
import { TrainingRunCard } from '@/components/training/TrainingRunCard';

export default function TrainingRunsPage() {
  const [loading, setLoading] = useState(true);
  const [runs, setRuns] = useState<TrainingRun[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const limit = 20;

  useEffect(() => {
    loadRuns();
  }, [page, statusFilter]);

  const loadRuns = async () => {
    try {
      setLoading(true);
      
      const data = await listTrainingRuns({
        status: statusFilter === 'all' ? undefined : statusFilter,
        limit,
        offset: page * limit,
      });

      setRuns(data.runs);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to load training runs:', err);
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="min-h-screen bg-[#0D0D0D] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard/training">
              <Button variant="ghost" size="icon" className="text-gray-400 hover:text-white">
                <ArrowLeft className="w-5 h-5" />
              </Button>
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-white">Training History</h1>
              <p className="text-gray-400 text-sm">
                View all training runs for your AI agents
              </p>
            </div>
          </div>
          <Link href="/dashboard/training/new">
            <Button className="bg-gradient-to-r from-[#FF7F11] to-orange-500">
              <Play className="w-4 h-4 mr-2" />
              New Training
            </Button>
          </Link>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search runs..."
              className="pl-9 bg-[#1A1A1A] border-white/[0.08] text-white placeholder:text-gray-500"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-40 bg-[#1A1A1A] border-white/[0.08] text-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#1A1A1A] border-white/[0.08]">
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="running">Running</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Runs List */}
        {loading ? (
          <div className="flex items-center justify-center p-12">
            <Loader2 className="w-8 h-8 animate-spin text-orange-400" />
          </div>
        ) : runs.length === 0 ? (
          <Card className="bg-[#1A1A1A] border-white/[0.08]">
            <CardContent className="p-12 text-center">
              <p className="text-gray-400">No training runs found.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {runs.map((run) => (
              <TrainingRunCard key={run.id} run={run} compact />
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="bg-[#1A1A1A] border-white/[0.08]"
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="text-sm text-gray-400">
              Page {page + 1} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="bg-[#1A1A1A] border-white/[0.08]"
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
