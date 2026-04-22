/**
 * Training API Client
 * 
 * Frontend API client for agent training pipeline (F-100 to F-108).
 * Connects to backend training endpoints.
 */

import { apiFetch } from './api';

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

export interface MistakeReport {
  agent_id: string;
  ticket_id?: string;
  mistake_type: string;
  original_response?: string;
  expected_response?: string;
  correction?: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
}

export interface MistakeReportResponse {
  status: string;
  mistake_id: string;
  agent_id: string;
  current_count: number;
  threshold: number;
  training_triggered: boolean;
  training_run_id?: string;
}

export interface ThresholdStatus {
  agent_id: string;
  current_count: number;
  threshold: number;
  percentage: number;
  triggered: boolean;
  remaining: number;
}

export interface MistakeHistoryItem {
  id: string;
  ticket_id?: string;
  mistake_type: string;
  severity: string;
  original_response?: string;
  used_in_training: boolean;
  created_at?: string;
}

export interface MistakeHistory {
  mistakes: MistakeHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface MistakeStats {
  total_mistakes: number;
  threshold: number;
  percentage_to_threshold: number;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
  used_in_training: number;
  available_for_training: number;
}

export interface TrainingRunCreate {
  agent_id: string;
  dataset_id: string;
  name?: string;
  trigger?: 'manual' | 'auto_threshold' | 'scheduled' | 'cold_start';
  base_model?: string;
  epochs?: number;
  learning_rate?: number;
  batch_size?: number;
}

export interface TrainingRun {
  id: string;
  company_id: string;
  agent_id: string;
  dataset_id?: string;
  name?: string;
  trigger: string;
  base_model?: string;
  status: 'queued' | 'preparing' | 'running' | 'validating' | 'completed' | 'failed' | 'cancelled';
  progress_pct: number;
  current_epoch: number;
  total_epochs: number;
  epochs: number;
  learning_rate?: number;
  batch_size: number;
  metrics: Record<string, unknown>;
  model_path?: string;
  checkpoint_path?: string;
  provider?: string;
  instance_id?: string;
  gpu_type?: string;
  cost_usd: number;
  started_at?: string;
  completed_at?: string;
  created_at?: string;
  error_message?: string;
}

export interface TrainingRunList {
  runs: TrainingRun[];
  total: number;
  limit: number;
  offset: number;
}

export interface TrainingStats {
  total_runs: number;
  completed: number;
  failed: number;
  running: number;
  queued: number;
  total_cost_usd: number;
  by_trigger: Record<string, number>;
}

export interface RetrainingSchedule {
  company_id: string;
  schedule: Array<{
    agent_id: string;
    agent_name: string;
    next_retraining: string;
    days_until_due: number;
    is_due: boolean;
  }>;
  total_agents: number;
  due_count: number;
}

export interface ColdStartStatus {
  agent_id: string;
  needs_cold_start: boolean;
  has_training_data: boolean;
  training_run_count: number;
  suggested_industry: string;
  status: 'cold_start_needed' | 'initializing' | 'initialized' | 'training' | 'ready';
}

export interface IndustryTemplate {
  industry: string;
  name: string;
  description: string;
  sample_prompts: number;
  faq_count: number;
  response_templates: number;
}

// ═══════════════════════════════════════════════════════════════════════════════
// API Functions - F-101 Mistake Threshold
// ═══════════════════════════════════════════════════════════════════════════════

export async function reportMistake(
  agentId: string,
  data: Omit<MistakeReport, 'agent_id'>
): Promise<MistakeReportResponse> {
  return apiFetch(`/api/v1/agents/${agentId}/mistakes`, {
    method: 'POST',
    body: JSON.stringify({ agent_id: agentId, ...data }),
  });
}

export async function getThresholdStatus(agentId: string): Promise<ThresholdStatus> {
  return apiFetch(`/api/v1/agents/${agentId}/mistakes/threshold`);
}

export async function getMistakeHistory(
  agentId: string,
  params?: { limit?: number; offset?: number; severity?: string; mistake_type?: string }
): Promise<MistakeHistory> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.offset) searchParams.set('offset', String(params.offset));
  if (params?.severity) searchParams.set('severity', params.severity);
  if (params?.mistake_type) searchParams.set('mistake_type', params.mistake_type);
  
  const query = searchParams.toString();
  return apiFetch(`/api/v1/agents/${agentId}/mistakes/history${query ? `?${query}` : ''}`);
}

export async function getMistakeStats(agentId: string): Promise<MistakeStats> {
  return apiFetch(`/api/v1/agents/${agentId}/mistakes/stats`);
}

// ═══════════════════════════════════════════════════════════════════════════════
// API Functions - F-100 Training Runs
// ═══════════════════════════════════════════════════════════════════════════════

export async function startTraining(
  agentId: string,
  data: Omit<TrainingRunCreate, 'agent_id'>
): Promise<TrainingRun> {
  return apiFetch(`/api/v1/agents/${agentId}/train`, {
    method: 'POST',
    body: JSON.stringify({ agent_id: agentId, ...data }),
  });
}

export async function listTrainingRuns(params?: {
  agent_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<TrainingRunList> {
  const searchParams = new URLSearchParams();
  if (params?.agent_id) searchParams.set('agent_id', params.agent_id);
  if (params?.status) searchParams.set('status', params.status);
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.offset) searchParams.set('offset', String(params.offset));
  
  const query = searchParams.toString();
  return apiFetch(`/api/v1/training/runs${query ? `?${query}` : ''}`);
}

export async function getTrainingRun(runId: string): Promise<TrainingRun> {
  return apiFetch(`/api/v1/training/runs/${runId}`);
}

export async function cancelTrainingRun(runId: string): Promise<{ status: string; run_id: string }> {
  return apiFetch(`/api/v1/training/runs/${runId}/cancel`, {
    method: 'POST',
  });
}

export async function getTrainingStats(agentId?: string): Promise<TrainingStats> {
  const query = agentId ? `?agent_id=${agentId}` : '';
  return apiFetch(`/api/v1/training/stats${query}`);
}

export async function getBestCheckpoint(runId: string): Promise<{
  checkpoint_id: string;
  checkpoint_name: string;
  model_path?: string;
  epoch: number;
  metrics?: Record<string, unknown>;
  created_at?: string;
}> {
  return apiFetch(`/api/v1/training/runs/${runId}/checkpoints/best`);
}

// ═══════════════════════════════════════════════════════════════════════════════
// API Functions - F-106 Fallback Training
// ═══════════════════════════════════════════════════════════════════════════════

export async function getRetrainingSchedule(daysAhead = 30): Promise<RetrainingSchedule> {
  return apiFetch(`/api/v1/training/retraining/schedule?days_ahead=${daysAhead}`);
}

export async function getAgentsDueForRetraining(includeForce = false): Promise<{
  company_id: string;
  agents: Array<{
    agent_id: string;
    agent_name: string;
    last_training: string;
    days_since_training: number;
    is_due_for_retraining: boolean;
  }>;
  total: number;
  due_count: number;
}> {
  return apiFetch(`/api/v1/training/retraining/due?include_force=${includeForce}`);
}

export async function scheduleRetraining(
  agentId: string,
  options?: { force?: boolean; priority?: 'low' | 'normal' | 'high' }
): Promise<{ status: string; run_id?: string; error?: string }> {
  const searchParams = new URLSearchParams();
  if (options?.force) searchParams.set('force', 'true');
  if (options?.priority) searchParams.set('priority', options.priority);
  
  return apiFetch(`/api/v1/training/retraining/schedule/${agentId}?${searchParams.toString()}`, {
    method: 'POST',
  });
}

export async function scheduleAllRetraining(): Promise<{
  scheduled: number;
  runs: string[];
}> {
  return apiFetch('/api/v1/training/retraining/schedule-all', {
    method: 'POST',
  });
}

export async function getTrainingEffectiveness(agentId?: string, runs = 5): Promise<{
  runs: TrainingRun[];
  avg_accuracy: number;
  avg_loss: number;
  improvement_trend: 'improving' | 'stable' | 'declining';
}> {
  const searchParams = new URLSearchParams();
  searchParams.set('runs', String(runs));
  if (agentId) searchParams.set('agent_id', agentId);
  
  return apiFetch(`/api/v1/training/retraining/effectiveness?${searchParams.toString()}`);
}

// ═══════════════════════════════════════════════════════════════════════════════
// API Functions - F-107 Cold Start
// ═══════════════════════════════════════════════════════════════════════════════

export async function getColdStartStatus(agentId: string): Promise<ColdStartStatus> {
  return apiFetch(`/api/v1/training/cold-start/status/${agentId}`);
}

export async function getAgentsNeedingColdStart(): Promise<{
  company_id: string;
  agents: ColdStartStatus[];
  total: number;
}> {
  return apiFetch('/api/v1/training/cold-start/agents');
}

export async function initializeColdStart(
  agentId: string,
  options?: { industry?: string; specialty?: string; auto_train?: boolean }
): Promise<{ status: string; run_id?: string; error?: string }> {
  const searchParams = new URLSearchParams();
  if (options?.industry) searchParams.set('industry', options.industry);
  if (options?.specialty) searchParams.set('specialty', options.specialty);
  if (options?.auto_train !== undefined) searchParams.set('auto_train', String(options.auto_train));
  
  return apiFetch(`/api/v1/training/cold-start/initialize/${agentId}?${searchParams.toString()}`, {
    method: 'POST',
  });
}

export async function initializeAllColdStart(
  options?: { default_industry?: string }
): Promise<{
  status: string;
  initialized_count: number;
  errors: string[];
}> {
  const searchParams = new URLSearchParams();
  if (options?.default_industry) searchParams.set('default_industry', options.default_industry);

  return apiFetch(`/api/v1/training/cold-start/initialize-all?${searchParams.toString()}`, {
    method: 'POST',
  });
}

export async function listIndustryTemplates(): Promise<{
  templates: IndustryTemplate[];
  total: number;
}> {
  return apiFetch('/api/v1/training/cold-start/templates');
}

export async function getIndustryTemplate(industry: string): Promise<{
  template: IndustryTemplate | null;
}> {
  return apiFetch(`/api/v1/training/cold-start/templates/${industry}`);
}

// ═══════════════════════════════════════════════════════════════════════════════
// API Functions - F-108 Peer Review
// ═══════════════════════════════════════════════════════════════════════════════

export async function getPeerReviewQueue(): Promise<{
  reviews: Array<{
    id: string;
    agent_id: string;
    agent_name: string;
    ticket_id: string;
    response: string;
    confidence: number;
    status: 'pending' | 'approved' | 'rejected' | 'escalated';
    created_at: string;
  }>;
  total: number;
}> {
  return apiFetch('/api/v1/training/peer-review/queue');
}

export async function submitPeerReview(
  reviewId: string,
  data: {
    action: 'approve' | 'reject' | 'escalate';
    feedback?: string;
    correction?: string;
  }
): Promise<{ status: string; review_id: string }> {
  return apiFetch(`/api/v1/training/peer-review/${reviewId}/submit`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
