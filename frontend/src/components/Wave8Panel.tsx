'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';

import { getCurrentTenantId } from '@/lib/auth-context';

// ── Agent Provisioning Panel ─────────────────────────────────

function AgentProvisioner() {
  const [command, setCommand] = useState('');
  const provisionMutation = useMutation({
    mutationFn: (cmd: string) => jarvisApi.provisionAgent({ tenant_id: getCurrentTenantId(), command: cmd }),
  });

  const handleProvision = (e: React.FormEvent) => {
    e.preventDefault();
    if (!command.trim()) return;
    provisionMutation.mutate(command);
  };

  return (
    <div className="bg-jarvis-bg/50 rounded-lg p-3 border border-jarvis-border/30">
      <h4 className="text-[10px] text-jarvis-cyan tracking-wider uppercase mb-2">Agent Provisioning</h4>
      <form onSubmit={handleProvision} className="space-y-2">
        <input
          type="text"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          placeholder='e.g. "Add 3 mini agents for the weekend"'
          className="jarvis-input w-full text-xs"
          disabled={provisionMutation.isPending}
        />
        <button
          type="submit"
          disabled={provisionMutation.isPending || !command.trim()}
          className="jarvis-btn-primary w-full text-xs disabled:opacity-30"
        >
          {provisionMutation.isPending ? 'PROVISIONING...' : 'PROVISION AGENTS'}
        </button>
      </form>
      {provisionMutation.data && (
        <div className="mt-2 bg-jarvis-green/5 rounded p-2 border border-jarvis-green/10">
          <pre className="text-[10px] text-jarvis-green font-mono whitespace-pre-wrap">
            {provisionMutation.data.summary || JSON.stringify(provisionMutation.data, null, 2)}
          </pre>
        </div>
      )}
      {provisionMutation.isError && (
        <div className="mt-2 text-[10px] text-jarvis-red">
          Error: {(provisionMutation.error as Error).message}
        </div>
      )}
    </div>
  );
}

// ── Skill Instructor Panel ────────────────────────────────────

function SkillInstructor() {
  const [description, setDescription] = useState('');
  const teachMutation = useMutation({
    mutationFn: (desc: string) => jarvisApi.teachSkill({ tenant_id: getCurrentTenantId(), description: desc }),
  });

  const handleTeach = (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim() || description.length < 20) return;
    teachMutation.mutate(description);
  };

  return (
    <div className="bg-jarvis-bg/50 rounded-lg p-3 border border-jarvis-border/30">
      <h4 className="text-[10px] text-jarvis-yellow tracking-wider uppercase mb-2">Teach Skill</h4>
      <form onSubmit={handleTeach} className="space-y-2">
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder='e.g. "Here is how to handle International Returns. First verify the customer..."'
          className="jarvis-input w-full text-xs h-16 resize-none"
          disabled={teachMutation.isPending}
        />
        <div className="flex items-center justify-between">
          <span className="text-[9px] text-jarvis-muted">{description.length}/20 min chars</span>
          <button
            type="submit"
            disabled={teachMutation.isPending || description.length < 20}
            className="jarvis-btn-primary px-3 text-xs disabled:opacity-30"
          >
            TEACH
          </button>
        </div>
      </form>
      {teachMutation.data && (
        <div className="mt-2 bg-jarvis-yellow/5 rounded p-2 border border-jarvis-yellow/10">
          <pre className="text-[10px] text-jarvis-yellow font-mono whitespace-pre-wrap">
            {teachMutation.data.summary || JSON.stringify(teachMutation.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

// ── Co-Pilot Draft Panel ───────────────────────────────────────

function CoPilotPanel() {
  const [query, setQuery] = useState('');
  const [draftResult, setDraftResult] = useState<any>(null);
  const draftMutation = useMutation({
    mutationFn: (q: string) => jarvisApi.copilotDraft({ tenant_id: getCurrentTenantId(), customer_query: q }),
    onSuccess: (data) => setDraftResult(data),
  });

  const handleDraft = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    draftMutation.mutate(query);
  };

  const [editText, setEditText] = useState('');
  const editMutation = useMutation({
    mutationFn: ({ draftId, text }: { draftId: string; text: string }) =>
      jarvisApi.copilotEdit({ tenant_id: getCurrentTenantId(), draft_id: draftId, edited_text: text }),
    onSuccess: () => {
      setDraftResult(null);
      setEditText('');
    },
  });

  return (
    <div className="bg-jarvis-bg/50 rounded-lg p-3 border border-jarvis-border/30">
      <h4 className="text-[10px] text-purple-400 tracking-wider uppercase mb-2">Co-Pilot Draft</h4>
      <form onSubmit={handleDraft} className="space-y-2">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='Customer query to draft a response for...'
          className="jarvis-input w-full text-xs h-16 resize-none"
          disabled={draftMutation.isPending}
        />
        <button
          type="submit"
          disabled={draftMutation.isPending || !query.trim()}
          className="jarvis-btn-primary w-full text-xs disabled:opacity-30"
        >
          {draftMutation.isPending ? 'GENERATING DRAFT...' : 'GENERATE DRAFT'}
        </button>
      </form>
      {draftResult && (
        <div className="mt-2 space-y-2">
          <div className="bg-purple-400/5 rounded p-2 border border-purple-400/10">
            <p className="text-[9px] text-jarvis-muted mb-1">Generated Draft (ID: {draftResult.draft_id}):</p>
            <pre className="text-[10px] text-purple-400 font-mono whitespace-pre-wrap">
              {draftResult.draft_text || 'No draft generated'}
            </pre>
          </div>
          <div>
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              placeholder="Edit the draft above, then save to teach the AI..."
              className="jarvis-input w-full text-xs h-12 resize-none"
            />
            <button
              onClick={() => draftResult && editMutation.mutate({ draftId: draftResult.draft_id, text: editText })}
              disabled={editMutation.isPending || !editText.trim()}
              className="jarvis-btn-primary w-full mt-1 text-xs disabled:opacity-30"
            >
              SAVE EDIT (AI LEARNS)
            </button>
          </div>
          {editMutation.isSuccess && (
            <div className="text-[10px] text-jarvis-green">AI has learned from your edit.</div>
          )}
        </div>
      )}
    </div>
  );
}

// ── DSPy Correction Panel ─────────────────────────────────────

function CorrectionPanel() {
  const [target, setTarget] = useState('');
  const [code, setCode] = useState('');
  const correctionMutation = useMutation({
    mutationFn: ({ t, c }: { t: string; c: string }) =>
      jarvisApi.applyCorrection({ tenant_id: getCurrentTenantId(), target: t, code: c, description: `Fix: ${t}` }),
  });

  return (
    <div className="bg-jarvis-bg/50 rounded-lg p-3 border border-jarvis-border/30">
      <h4 className="text-[10px] text-orange-400 tracking-wider uppercase mb-2">DSPy Correction</h4>
      <div className="space-y-2">
        <input
          type="text"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="Behavior to fix (e.g. 'refund tone')"
          className="jarvis-input w-full text-xs"
        />
        <input
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="Correction code (e.g. 'V2.0')"
          className="jarvis-input w-full text-xs"
        />
        <button
          onClick={() => target && correctionMutation.mutate({ t: target, c: code || 'manual' })}
          disabled={correctionMutation.isPending || !target.trim()}
          className="jarvis-btn-primary w-full text-xs disabled:opacity-30"
        >
          APPLY CORRECTION
        </button>
      </div>
      {correctionMutation.data && (
        <div className="mt-2 bg-orange-400/5 rounded p-2 border border-orange-400/10">
          <pre className="text-[10px] text-orange-400 font-mono whitespace-pre-wrap">
            {correctionMutation.data.summary || JSON.stringify(correctionMutation.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

// ── Main Wave 8 Panel ──────────────────────────────────────────

export default function Wave8Panel() {
  const queryClient = useQueryClient();

  const { data: agents } = useQuery({
    queryKey: ['wave8-agents', getCurrentTenantId()],
    queryFn: () => jarvisApi.listAgents(getCurrentTenantId()),
    refetchInterval: 30000,
  });

  const { data: skills } = useQuery({
    queryKey: ['wave8-skills', getCurrentTenantId()],
    queryFn: () => jarvisApi.listSkills(getCurrentTenantId()),
    refetchInterval: 30000,
  });

  const agentCount = agents?.count || 0;
  const skillCount = skills?.count || 0;

  return (
    <div className="jarvis-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase">Wave 8 — Advanced</h3>
        <div className="flex gap-2">
          <span className="jarvis-badge jarvis-badge-cyan">{agentCount} Agents</span>
          <span className="jarvis-badge jarvis-badge-yellow">{skillCount} Skills</span>
        </div>
      </div>

      <div className="space-y-3">
        <AgentProvisioner />
        <SkillInstructor />
        <CoPilotPanel />
        <CorrectionPanel />
      </div>

      {/* Agent List */}
      {agents?.agents?.length > 0 && (
        <div className="mt-3">
          <h4 className="text-[10px] text-jarvis-muted tracking-wider uppercase mb-2">Active Agents</h4>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {agents.agents.map((agent: any, i: number) => (
              <div key={i} className="bg-jarvis-bg/30 rounded px-2 py-1.5 text-[10px] flex items-center justify-between">
                <span className="text-jarvis-text">{agent.agent_name || agent.name || `Agent ${i + 1}`}</span>
                <span className="text-jarvis-muted">
                  {agent.agent_type || '?'} | {agent.status || 'active'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Skills List */}
      {skills?.skills?.length > 0 && (
        <div className="mt-3">
          <h4 className="text-[10px] text-jarvis-muted tracking-wider uppercase mb-2">Learned Skills</h4>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {skills.skills.map((skill: any, i: number) => (
              <div key={i} className="bg-jarvis-bg/30 rounded px-2 py-1.5 text-[10px]">
                <div className="flex items-center justify-between">
                  <span className="text-jarvis-text">{skill.display_name || skill.skill_name || `Skill ${i + 1}`}</span>
                  <span className="text-jarvis-muted">{skill.step_count || '?'} steps</span>
                </div>
                {skill.trigger_keywords && (
                  <div className="text-[9px] text-jarvis-muted mt-0.5">
                    Triggers: {skill.trigger_keywords.slice(0, 5).join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
