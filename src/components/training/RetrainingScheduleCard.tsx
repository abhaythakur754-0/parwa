'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Clock,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  Loader2,
  Calendar,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  getRetrainingSchedule,
  getAgentsDueForRetraining,
  scheduleRetraining,
  scheduleAllRetraining,
  getTrainingEffectiveness,
} from '@/lib/training-api';

interface RetrainingScheduleCardProps {
  onUpdate?: () => void;
}

interface ScheduleItem {
  agent_id: string;
  agent_name: string;
  next_retraining: string;
  days_until_due: number;
  is_due: boolean;
}

export function RetrainingScheduleCard({ onUpdate }: RetrainingScheduleCardProps) {
  const [loading, setLoading] = useState(true);
  const [scheduling, setScheduling] = useState<string | null>(null);
  const [schedule, setSchedule] = useState<ScheduleItem[]>([]);
  const [dueCount, setDueCount] = useState(0);
  const [effectiveness, setEffectiveness] = useState<{
    avg_accuracy: number;
    improvement_trend: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [scheduleData, dueData, effectivenessData] = await Promise.all([
        getRetrainingSchedule(30),
        getAgentsDueForRetraining(),
        getTrainingEffectiveness(undefined, 5),
      ]);

      setSchedule(scheduleData.schedule || []);
      setDueCount(dueData.due_count);
      setEffectiveness(effectivenessData);
    } catch (err) {
      console.error('Failed to load retraining data:', err);
      setError('Failed to load retraining schedule.');
    } finally {
      setLoading(false);
    }
  };

  const handleScheduleAgent = async (agentId: string) => {
    try {
      setScheduling(agentId);
      setError(null);
      
      await scheduleRetraining(agentId, { priority: 'normal' });
      
      await loadData();
      onUpdate?.();
    } catch (err) {
      console.error('Failed to schedule retraining:', err);
      setError('Failed to schedule retraining.');
    } finally {
      setScheduling(null);
    }
  };

  const handleScheduleAll = async () => {
    try {
      setScheduling('all');
      setError(null);
      
      await scheduleAllRetraining();
      
      await loadData();
      onUpdate?.();
    } catch (err) {
      console.error('Failed to schedule all retraining:', err);
      setError('Failed to schedule all retraining.');
    } finally {
      setScheduling(null);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const getDaysBadge = (days: number, isDue: boolean) => {
    if (isDue) {
      return (
        <Badge className="bg-red-500/15 text-red-400 border-red-500/25">
          Overdue
        </Badge>
      );
    }
    if (days <= 3) {
      return (
        <Badge className="bg-yellow-500/15 text-yellow-400 border-yellow-500/25">
          {days}d left
        </Badge>
      );
    }
    if (days <= 7) {
      return (
        <Badge className="bg-blue-500/15 text-blue-400 border-blue-500/25">
          {days}d left
        </Badge>
      );
    }
    return (
      <Badge className="bg-green-500/15 text-green-400 border-green-500/25">
        {days}d left
      </Badge>
    );
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'improving':
        return <span className="text-green-400">↑ Improving</span>;
      case 'declining':
        return <span className="text-red-400">↓ Declining</span>;
      default:
        return <span className="text-yellow-400">→ Stable</span>;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="w-6 h-6 animate-spin text-orange-400" />
      </div>
    );
  }

  const dueAgents = schedule.filter((s) => s.is_due);
  const upcomingAgents = schedule.filter((s) => !s.is_due);

  return (
    <div className="space-y-4">
      {error && (
        <div className="bg-red-500/10 border border-red-500/25 rounded-lg p-3 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Effectiveness Summary */}
      {effectiveness && (
        <Card className="bg-[#1A1A1A] border-white/[0.08]">
          <CardContent className="p-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-green-500/15 flex items-center justify-center">
                  <CheckCircle className="w-5 h-5 text-green-400" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Avg Accuracy</p>
                  <p className="text-xl font-bold text-white">
                    {(effectiveness.avg_accuracy * 100).toFixed(1)}%
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-500/15 flex items-center justify-center">
                  <Zap className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Trend</p>
                  <p className="text-lg font-medium mt-1">
                    {getTrendIcon(effectiveness.improvement_trend)}
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Due for Retraining */}
      {dueAgents.length > 0 && (
        <Card className="bg-[#1A1A1A] border-orange-500/30">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base text-white flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-orange-400" />
                Due for Retraining ({dueAgents.length})
              </CardTitle>
              <Button
                onClick={handleScheduleAll}
                disabled={scheduling === 'all'}
                size="sm"
                className="bg-gradient-to-r from-orange-500 to-orange-600"
              >
                {scheduling === 'all' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Schedule All
                  </>
                )}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {dueAgents.map((agent) => (
              <div
                key={agent.agent_id}
                className="flex items-center justify-between p-3 bg-white/[0.03] rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-red-500/15 flex items-center justify-center">
                    <AlertTriangle className="w-4 h-4 text-red-400" />
                  </div>
                  <div>
                    <p className="text-white font-medium">{agent.agent_name}</p>
                    <p className="text-xs text-gray-500">
                      Last trained: {formatDate(agent.next_retraining)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {getDaysBadge(agent.days_until_due, agent.is_due)}
                  <Button
                    onClick={() => handleScheduleAgent(agent.agent_id)}
                    disabled={scheduling === agent.agent_id}
                    size="sm"
                    variant="outline"
                    className="bg-white/5 border-white/10"
                  >
                    {scheduling === agent.agent_id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      'Schedule'
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Upcoming Schedule */}
      {upcomingAgents.length > 0 && (
        <Card className="bg-[#1A1A1A] border-white/[0.08]">
          <CardHeader className="pb-2">
            <CardTitle className="text-base text-white flex items-center gap-2">
              <Calendar className="w-4 h-4 text-blue-400" />
              Upcoming Schedule
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {upcomingAgents.map((agent) => (
              <div
                key={agent.agent_id}
                className="flex items-center justify-between p-3 bg-white/[0.03] rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-500/15 flex items-center justify-center">
                    <Clock className="w-4 h-4 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-white font-medium">{agent.agent_name}</p>
                    <p className="text-xs text-gray-500">
                      Next: {formatDate(agent.next_retraining)}
                    </p>
                  </div>
                </div>
                {getDaysBadge(agent.days_until_due, agent.is_due)}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {schedule.length === 0 && (
        <Card className="bg-[#1A1A1A] border-white/[0.08]">
          <CardContent className="p-8 text-center">
            <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-4">
              <Calendar className="w-8 h-8 text-gray-500" />
            </div>
            <h3 className="text-lg font-medium text-white mb-2">No Agents Scheduled</h3>
            <p className="text-gray-400">
              Agents will appear here when they need retraining.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Info */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3">
        <p className="text-xs text-blue-300">
          <strong>Bi-Weekly Retraining:</strong> Agents are automatically scheduled for retraining
          every 14 days to maintain optimal performance and adapt to new patterns.
        </p>
      </div>
    </div>
  );
}
