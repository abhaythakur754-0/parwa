'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Snowflake,
  Play,
  CheckCircle,
  Loader2,
  RefreshCw,
  Rocket,
  Database,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ColdStartStatus, IndustryTemplate } from '@/lib/training-api';
import { initializeColdStart, listIndustryTemplates } from '@/lib/training-api';

interface ColdStartCardProps {
  agents: ColdStartStatus[];
  onUpdate?: () => void;
}

export function ColdStartCard({ agents, onUpdate }: ColdStartCardProps) {
  const [loading, setLoading] = useState<string | null>(null);
  const [templates, setTemplates] = useState<IndustryTemplate[]>([]);
  const [selectedIndustry, setSelectedIndustry] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const data = await listIndustryTemplates();
      setTemplates(data.templates);
    } catch (err) {
      console.error('Failed to load templates:', err);
    }
  };

  const handleInitialize = async (agentId: string) => {
    try {
      setLoading(agentId);
      setError(null);
      
      const industry = selectedIndustry[agentId] || 'generic';
      await initializeColdStart(agentId, { industry, auto_train: true });
      
      onUpdate?.();
    } catch (err) {
      console.error('Failed to initialize cold start:', err);
      setError('Failed to initialize agent. Please try again.');
    } finally {
      setLoading(null);
    }
  };

  const handleInitializeAll = async () => {
    try {
      setLoading('all');
      setError(null);
      
      await Promise.all(
        agents.map((agent) =>
          initializeColdStart(agent.agent_id, {
            industry: selectedIndustry[agent.agent_id] || 'generic',
            auto_train: true,
          })
        )
      );
      
      onUpdate?.();
    } catch (err) {
      console.error('Failed to initialize all agents:', err);
      setError('Failed to initialize some agents. Please try again.');
    } finally {
      setLoading(null);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'cold_start_needed':
        return <Badge className="bg-purple-500/15 text-purple-400">Needs Init</Badge>;
      case 'initializing':
        return <Badge className="bg-blue-500/15 text-blue-400">Initializing</Badge>;
      case 'training':
        return <Badge className="bg-orange-500/15 text-orange-400">Training</Badge>;
      case 'ready':
        return <Badge className="bg-green-500/15 text-green-400">Ready</Badge>;
      default:
        return <Badge className="bg-gray-500/15 text-gray-400">{status}</Badge>;
    }
  };

  if (agents.length === 0) {
    return (
      <Card className="bg-[#1A1A1A] border-white/[0.08]">
        <CardContent className="p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-8 h-8 text-green-400" />
          </div>
          <h3 className="text-lg font-medium text-white mb-2">All Agents Initialized</h3>
          <p className="text-gray-400">
            All your AI agents have completed cold start initialization.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="bg-red-500/10 border border-red-500/25 rounded-lg p-3 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Bulk Action */}
      <Card className="bg-[#1A1A1A] border-white/[0.08]">
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/15 flex items-center justify-center">
                <Snowflake className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <p className="text-white font-medium">{agents.length} Agents Need Cold Start</p>
                <p className="text-gray-400 text-sm">
                  Initialize with industry templates for faster onboarding
                </p>
              </div>
            </div>
            <Button
              onClick={handleInitializeAll}
              disabled={loading === 'all'}
              className="bg-gradient-to-r from-purple-500 to-purple-600 hover:from-purple-600 hover:to-purple-700"
            >
              {loading === 'all' ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Rocket className="w-4 h-4 mr-2" />
              )}
              Initialize All
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Agent List */}
      {agents.map((agent) => (
        <Card key={agent.agent_id} className="bg-[#1A1A1A] border-white/[0.08]">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center">
                  <Database className="w-5 h-5 text-gray-400" />
                </div>
                <div>
                  <p className="text-white font-medium">Agent {agent.agent_id.slice(0, 8)}</p>
                  <div className="flex items-center gap-2 mt-1">
                    {getStatusBadge(agent.status)}
                    <span className="text-gray-500 text-xs">
                      {agent.training_run_count} training runs
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {/* Industry Selector */}
                <Select
                  value={selectedIndustry[agent.agent_id] || agent.suggested_industry}
                  onValueChange={(value) =>
                    setSelectedIndustry((prev) => ({ ...prev, [agent.agent_id]: value }))
                  }
                >
                  <SelectTrigger className="w-40 bg-white/5 border-white/10">
                    <SelectValue placeholder="Select industry" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#1A1A1A] border-white/10">
                    {templates.map((template) => (
                      <SelectItem key={template.industry} value={template.industry}>
                        {template.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Button
                  onClick={() => handleInitialize(agent.agent_id)}
                  disabled={loading === agent.agent_id}
                  variant="outline"
                  className="bg-white/5 border-white/10 text-gray-300 hover:text-white hover:bg-white/10"
                >
                  {loading === agent.agent_id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <Play className="w-4 h-4 mr-2" />
                      Initialize
                    </>
                  )}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}

      {/* Industry Templates Info */}
      <Card className="bg-[#1A1A1A] border-white/[0.08]">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-white">Available Templates</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
            {templates.slice(0, 10).map((template) => (
              <div
                key={template.industry}
                className="bg-white/[0.03] rounded-lg p-2 text-center"
              >
                <p className="text-xs text-white font-medium truncate">{template.name}</p>
                <p className="text-[10px] text-gray-500">
                  {template.sample_prompts} prompts
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
