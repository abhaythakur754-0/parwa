'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';
import { useState } from 'react';

import { getCurrentTenantId } from '@/lib/auth-context';

export default function FlagPanel() {
  const queryClient = useQueryClient();
  const [showSetForm, setShowSetForm] = useState(false);
  const [newFlagName, setNewFlagName] = useState('');
  const [newFlagValue, setNewFlagValue] = useState('true');

  const { data, isLoading } = useQuery<any>({
    queryKey: ['flags', getCurrentTenantId()],
    queryFn: () => jarvisApi.getFlags(getCurrentTenantId()),
    refetchInterval: 20000,
  });

  const setFlagMutation = useMutation({
    mutationFn: () =>
      jarvisApi.setFlag({
        tenant_id: getCurrentTenantId(),
        flag_name: newFlagName,
        flag_value: newFlagValue,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flags'] });
      setShowSetForm(false);
      setNewFlagName('');
      setNewFlagValue('true');
    },
  });

  const flags: Array<{ name: string; value: any; description?: string; set_at?: string }> =
    Array.isArray(data)
      ? data
      : data?.flags || data?.items || Object.entries(data || {}).map(([k, v]: [string, any]) => ({
          name: k,
          value: v,
        }));

  return (
    <div className="jarvis-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase">System Flags</h3>
        <button
          onClick={() => setShowSetForm(!showSetForm)}
          className="jarvis-btn-ghost text-[10px] px-2 py-1"
        >
          {showSetForm ? 'CANCEL' : '+ SET FLAG'}
        </button>
      </div>

      {/* Set Flag Form */}
      {showSetForm && (
        <div className="mb-3 p-2.5 bg-jarvis-bg/50 rounded-lg border border-jarvis-border/30 space-y-2 fade-in">
          <input
            type="text"
            value={newFlagName}
            onChange={(e) => setNewFlagName(e.target.value)}
            placeholder="Flag name"
            className="jarvis-input text-xs w-full"
          />
          <div className="flex gap-2">
            <select
              value={newFlagValue}
              onChange={(e) => setNewFlagValue(e.target.value)}
              className="jarvis-input text-xs flex-1"
            >
              <option value="true">true</option>
              <option value="false">false</option>
            </select>
            <button
              onClick={() => setFlagMutation.mutate()}
              disabled={!newFlagName.trim() || setFlagMutation.isPending}
              className="jarvis-btn-primary text-[10px] disabled:opacity-30"
            >
              {setFlagMutation.isPending ? '...' : 'SET'}
            </button>
          </div>
          {setFlagMutation.isError && (
            <p className="text-[10px] text-jarvis-red">{(setFlagMutation.error as Error)?.message}</p>
          )}
        </div>
      )}

      {/* Flags List */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-8 rounded" />
          ))}
        </div>
      ) : flags.length > 0 ? (
        <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
          {flags.map((flag, idx) => {
            const isActive = flag.value === true || flag.value === 'true';
            return (
              <div
                key={idx}
                className="flex items-center justify-between py-1.5 px-2 rounded bg-jarvis-bg/30 hover:bg-jarvis-bg/50 transition-colors"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className={`inline-flex w-2 h-2 rounded-full flex-shrink-0 ${
                      isActive ? 'bg-jarvis-green' : 'bg-jarvis-red/50'
                    }`}
                  />
                  <span className="text-[11px] text-jarvis-text truncate font-medium">
                    {flag.name}
                  </span>
                  {flag.description && (
                    <span className="text-[9px] text-jarvis-muted hidden sm:inline">
                      — {flag.description}
                    </span>
                  )}
                </div>
                <span
                  className={`text-[10px] font-bold tabular-nums ${
                    isActive ? 'text-jarvis-green' : 'text-jarvis-red/60'
                  }`}
                >
                  {String(flag.value).toUpperCase()}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-4 text-jarvis-muted text-sm">
          No system flags set
        </div>
      )}
    </div>
  );
}