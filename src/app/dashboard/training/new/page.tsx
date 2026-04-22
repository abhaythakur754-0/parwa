'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';
import {
  Play,
  Loader2,
  ArrowLeft,
  Brain,
  Zap,
  Clock,
  DollarSign,
  AlertCircle,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { startTraining, listTrainingRuns, type TrainingRun } from '@/lib/training-api';

export default function NewTrainingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [agents, setAgents] = useState<Array<{ id: string; name: string }>>([]);
  const [datasets, setDatasets] = useState<Array<{ id: string; name: string }>>([]);
  
  // Form state
  const [agentId, setAgentId] = useState('');
  const [datasetId, setDatasetId] = useState('');
  const [runName, setRunName] = useState('');
  const [baseModel, setBaseModel] = useState('gpt-3.5-turbo');
  const [epochs, setEpochs] = useState(3);
  const [learningRate, setLearningRate] = useState(0.0001);
  const [batchSize, setBatchSize] = useState(16);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Load agents and datasets (mock data for now)
    setAgents([
      { id: 'agent-1', name: 'Support Agent Alpha' },
      { id: 'agent-2', name: 'Sales Agent Beta' },
      { id: 'agent-3', name: 'Technical Support Gamma' },
    ]);
    setDatasets([
      { id: 'dataset-1', name: 'Customer FAQ Dataset' },
      { id: 'dataset-2', name: 'Product Knowledge Base' },
      { id: 'dataset-3', name: 'Support Ticket History' },
    ]);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!agentId || !datasetId) {
      setError('Please select an agent and dataset.');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const result = await startTraining(agentId, {
        dataset_id: datasetId,
        name: runName || undefined,
        trigger: 'manual',
        base_model: baseModel || undefined,
        epochs,
        learning_rate: learningRate,
        batch_size: batchSize,
      });

      // Navigate to training dashboard
      router.push('/dashboard/training');
    } catch (err) {
      console.error('Failed to start training:', err);
      setError('Failed to start training. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const estimatedTime = epochs * 15; // Rough estimate: 15 min per epoch
  const estimatedCost = epochs * 0.5; // Rough estimate: $0.50 per epoch

  return (
    <div className="min-h-screen bg-[#0D0D0D] text-white p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Link href="/dashboard/training">
            <Button variant="ghost" size="icon" className="text-gray-400 hover:text-white">
              <ArrowLeft className="w-5 h-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white">Start Training</h1>
            <p className="text-gray-400 text-sm">
              Configure and launch a new training run for your AI agent
            </p>
          </div>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/25 rounded-lg p-4 text-red-400 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Agent & Dataset Selection */}
          <Card className="bg-[#1A1A1A] border-white/[0.08]">
            <CardHeader>
              <CardTitle className="text-lg text-white flex items-center gap-2">
                <Brain className="w-5 h-5 text-orange-400" />
                Training Configuration
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Agent Select */}
              <div className="space-y-2">
                <Label className="text-gray-300">Select Agent</Label>
                <Select value={agentId} onValueChange={setAgentId}>
                  <SelectTrigger className="bg-white/5 border-white/10 text-white">
                    <SelectValue placeholder="Choose an agent to train" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#1A1A1A] border-white/10">
                    {agents.map((agent) => (
                      <SelectItem key={agent.id} value={agent.id} className="text-white">
                        {agent.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Dataset Select */}
              <div className="space-y-2">
                <Label className="text-gray-300">Select Dataset</Label>
                <Select value={datasetId} onValueChange={setDatasetId}>
                  <SelectTrigger className="bg-white/5 border-white/10 text-white">
                    <SelectValue placeholder="Choose a training dataset" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#1A1A1A] border-white/10">
                    {datasets.map((dataset) => (
                      <SelectItem key={dataset.id} value={dataset.id} className="text-white">
                        {dataset.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Run Name */}
              <div className="space-y-2">
                <Label className="text-gray-300">Run Name (Optional)</Label>
                <Input
                  value={runName}
                  onChange={(e) => setRunName(e.target.value)}
                  placeholder="e.g., Weekly Retraining - Support FAQ"
                  className="bg-white/5 border-white/10 text-white placeholder:text-gray-500"
                />
              </div>

              {/* Base Model */}
              <div className="space-y-2">
                <Label className="text-gray-300">Base Model</Label>
                <Select value={baseModel} onValueChange={setBaseModel}>
                  <SelectTrigger className="bg-white/5 border-white/10 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#1A1A1A] border-white/10">
                    <SelectItem value="gpt-3.5-turbo" className="text-white">GPT-3.5 Turbo</SelectItem>
                    <SelectItem value="gpt-4" className="text-white">GPT-4</SelectItem>
                    <SelectItem value="llama-2-7b" className="text-white">Llama 2 7B</SelectItem>
                    <SelectItem value="llama-2-13b" className="text-white">Llama 2 13B</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Hyperparameters */}
          <Card className="bg-[#1A1A1A] border-white/[0.08]">
            <CardHeader>
              <CardTitle className="text-lg text-white flex items-center gap-2">
                <Zap className="w-5 h-5 text-yellow-400" />
                Hyperparameters
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Epochs */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="text-gray-300">Training Epochs</Label>
                  <Badge className="bg-orange-500/15 text-orange-400">{epochs}</Badge>
                </div>
                <Slider
                  value={[epochs]}
                  onValueChange={([v]) => setEpochs(v)}
                  min={1}
                  max={10}
                  step={1}
                  className="py-2"
                />
                <p className="text-xs text-gray-500">
                  More epochs = better learning but longer training time
                </p>
              </div>

              {/* Learning Rate */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="text-gray-300">Learning Rate</Label>
                  <Badge className="bg-blue-500/15 text-blue-400">
                    {learningRate.toExponential(2)}
                  </Badge>
                </div>
                <Slider
                  value={[Math.log10(learningRate)]}
                  onValueChange={([v]) => setLearningRate(Math.pow(10, v))}
                  min={-6}
                  max={-2}
                  step={0.5}
                  className="py-2"
                />
                <p className="text-xs text-gray-500">
                  Recommended: 1e-4 to 1e-5 for fine-tuning
                </p>
              </div>

              {/* Batch Size */}
              <div className="space-y-2">
                <Label className="text-gray-300">Batch Size</Label>
                <Select value={String(batchSize)} onValueChange={(v) => setBatchSize(Number(v))}>
                  <SelectTrigger className="bg-white/5 border-white/10 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#1A1A1A] border-white/10">
                    <SelectItem value="8" className="text-white">8</SelectItem>
                    <SelectItem value="16" className="text-white">16</SelectItem>
                    <SelectItem value="32" className="text-white">32</SelectItem>
                    <SelectItem value="64" className="text-white">64</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Estimates */}
          <Card className="bg-[#1A1A1A] border-white/[0.08]">
            <CardContent className="p-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-500/15 flex items-center justify-center">
                    <Clock className="w-5 h-5 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase">Est. Time</p>
                    <p className="text-lg font-medium text-white">~{estimatedTime} min</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-green-500/15 flex items-center justify-center">
                    <DollarSign className="w-5 h-5 text-green-400" />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase">Est. Cost</p>
                    <p className="text-lg font-medium text-white">${estimatedCost.toFixed(2)}</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Submit Button */}
          <div className="flex justify-end gap-3">
            <Link href="/dashboard/training">
              <Button variant="outline" className="bg-[#1A1A1A] border-white/[0.1] text-gray-300">
                Cancel
              </Button>
            </Link>
            <Button
              type="submit"
              disabled={loading || !agentId || !datasetId}
              className="bg-gradient-to-r from-[#FF7F11] to-orange-500 hover:from-orange-500 hover:to-orange-400"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Start Training
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
