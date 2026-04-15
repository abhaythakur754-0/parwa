'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Brain,
  Play,
  RefreshCw,
  CheckCircle,
  Clock,
  Snowflake,
  ChevronRight,
  Loader2,
} from 'lucide-react';
import Link from 'next/link';

import { TrainingRunCard } from '@/components/training/TrainingRunCard';
import { ColdStartCard } from '@/components/training/ColdStartCard';
import { RetrainingScheduleCard } from '@/components/training/RetrainingScheduleCard';
import {
  getTrainingStats,
  listTrainingRuns,
  getAgentsNeedingColdStart,
  getAgentsDueForRetraining,
  type TrainingStats,
  type TrainingRun,
  type ColdStartStatus,
} from '@/lib/training-api';

export default function TrainingDashboardPage() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<TrainingStats | null>(null);
  const [runs, setRuns] = useState<TrainingRun[]>([]);
  const [coldStartAgents, setColdStartAgents] = useState<ColdStartStatus[]>([]);
  const [retrainingDue, setRetrainingDue] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [statsData, runsData, coldStartData, retrainingData] = await Promise.all([
        getTrainingStats(),
        listTrainingRuns({ limit: 10 }),
        getAgentsNeedingColdStart(),
        getAgentsDueForRetraining(),
      ]);

      setStats(statsData);
      setRuns(runsData.runs);
      setColdStartAgents(coldStartData.agents);
      setRetrainingDue(retrainingData.due_count);
    } catch (err) {
      console.error('Failed to load training dashboard:', err);
      setError('Failed to load training data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const activeRuns = runs.filter((r) =>
    ['queued', 'preparing', 'running', 'validating'].includes(r.status)
  );
  const recentRuns = runs.filter((r) =>
    ['completed', 'failed', 'cancelled'].includes(r.status)
  );

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-orange-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0D0D0D] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">Training Pipeline</h1>
            <p className="text-gray-400 mt-1">
              Manage AI agent training, retraining, and cold start initialization
            </p>
          </div>
          <div className="flex gap-3">
            <Link href="/dashboard/training/runs">
              <Button
                variant="outline"
                className="bg-[#1A1A1A] border-white/[0.1] text-gray-300 hover:text-white"
              >
                View All Runs
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </Link>
            <Link href="/dashboard/training/new">
              <Button className="bg-gradient-to-r from-[#FF7F11] to-orange-500 hover:from-orange-500 hover:to-orange-400 text-white">
                <Play className="w-4 h-4 mr-2" />
                Start Training
              </Button>
            </Link>
          </div>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/25 rounded-lg p-4 text-red-400">
            {error}
          </div>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <Card className="bg-[#1A1A1A] border-white/[0.08]">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-500/15 flex items-center justify-center">
                  <Brain className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">{stats?.total_runs || 0}</p>
                  <p className="text-xs text-gray-400">Total Runs</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#1A1A1A] border-white/[0.08]">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-green-500/15 flex items-center justify-center">
                  <CheckCircle className="w-5 h-5 text-green-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">{stats?.completed || 0}</p>
                  <p className="text-xs text-gray-400">Completed</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#1A1A1A] border-white/[0.08]">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-orange-500/15 flex items-center justify-center">
                  <RefreshCw className="w-5 h-5 text-orange-400 animate-spin" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">{stats?.running || 0}</p>
                  <p className="text-xs text-gray-400">Running</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#1A1A1A] border-white/[0.08]">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-purple-500/15 flex items-center justify-center">
                  <Snowflake className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">{coldStartAgents.length}</p>
                  <p className="text-xs text-gray-400">Cold Start</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#1A1A1A] border-white/[0.08]">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-yellow-500/15 flex items-center justify-center">
                  <Clock className="w-5 h-5 text-yellow-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">{retrainingDue}</p>
                  <p className="text-xs text-gray-400">Due Retraining</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content Tabs */}
        <Tabs defaultValue="active" className="space-y-6">
          <TabsList className="bg-[#1A1A1A] border border-white/[0.08]">
            <TabsTrigger
              value="active"
              className="data-[state=active]:bg-[#FF7F11] data-[state=active]:text-white"
            >
              Active Training
              {activeRuns.length > 0 && (
                <Badge className="ml-2 bg-orange-500/20 text-orange-400">
                  {activeRuns.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger
              value="history"
              className="data-[state=active]:bg-[#FF7F11] data-[state=active]:text-white"
            >
              History
            </TabsTrigger>
            <TabsTrigger
              value="cold-start"
              className="data-[state=active]:bg-[#FF7F11] data-[state=active]:text-white"
            >
              Cold Start
              {coldStartAgents.length > 0 && (
                <Badge className="ml-2 bg-purple-500/20 text-purple-400">
                  {coldStartAgents.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger
              value="retraining"
              className="data-[state=active]:bg-[#FF7F11] data-[state=active]:text-white"
            >
              Retraining
              {retrainingDue > 0 && (
                <Badge className="ml-2 bg-yellow-500/20 text-yellow-400">
                  {retrainingDue}
                </Badge>
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="active" className="space-y-4">
            {activeRuns.length === 0 ? (
              <Card className="bg-[#1A1A1A] border-white/[0.08]">
                <CardContent className="p-8 text-center">
                  <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-4">
                    <Play className="w-8 h-8 text-gray-500" />
                  </div>
                  <h3 className="text-lg font-medium text-white mb-2">No Active Training</h3>
                  <p className="text-gray-400 mb-4">
                    Start a new training run or wait for scheduled retraining.
                  </p>
                  <Link href="/dashboard/training/new">
                    <Button className="bg-gradient-to-r from-[#FF7F11] to-orange-500">
                      Start Training
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {activeRuns.map((run) => (
                  <TrainingRunCard key={run.id} run={run} onUpdate={loadDashboardData} />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="history" className="space-y-4">
            {recentRuns.length === 0 ? (
              <Card className="bg-[#1A1A1A] border-white/[0.08]">
                <CardContent className="p-8 text-center">
                  <p className="text-gray-400">No training history yet.</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {recentRuns.slice(0, 10).map((run) => (
                  <TrainingRunCard key={run.id} run={run} compact />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="cold-start" className="space-y-4">
            <ColdStartCard agents={coldStartAgents} onUpdate={loadDashboardData} />
          </TabsContent>

          <TabsContent value="retraining" className="space-y-4">
            <RetrainingScheduleCard onUpdate={loadDashboardData} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
