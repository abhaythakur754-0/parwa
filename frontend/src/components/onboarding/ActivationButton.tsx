'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  ShieldCheck,
  Plug,
  Building2,
  ArrowRight,
  XCircle,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────

type ActivationState =
  | 'idle'
  | 'checking_prereqs'
  | 'ready'
  | 'unmet_prereqs'
  | 'activating'
  | 'polling_warmup'
  | 'done'
  | 'error';

interface PrerequisiteChecklist {
  legal_consent: boolean;
  integrations_connected: boolean;
  company_details_completed: boolean;
}

interface ActivationButtonProps {
  config: {
    ai_name: string;
    ai_tone: 'professional' | 'friendly' | 'casual';
    ai_response_style: 'concise' | 'detailed';
    ai_greeting?: string;
  };
  onActivationComplete: (result: {
    success: boolean;
    warmup_required: boolean;
    message: string;
  }) => void;
  onActivationError: (error: string) => void;
  disabled?: boolean;
}

interface PrerequisitesResponse {
  can_activate: boolean;
  missing: string[];
}

interface WarmupStatus {
  overall_status: string;
  models_ready: number;
  models_total: number;
  message: string;
}

// ── Constants ──────────────────────────────────────────────────────────────

const PREREQ_ITEMS: Array<{
  key: keyof PrerequisiteChecklist;
  label: string;
  icon: React.ElementType;
}> = [
  { key: 'legal_consent', label: 'Legal consent accepted', icon: ShieldCheck },
  { key: 'integrations_connected', label: 'At least 1 integration connected', icon: Plug },
  { key: 'company_details_completed', label: 'Company details completed', icon: Building2 },
];

const WARMUP_BACKOFF_INTERVALS = [2000, 3000, 5000]; // exponential: 2s → 3s → 5s
const MAX_WARMUP_POLL_ATTEMPTS = 10;

// ── Component ──────────────────────────────────────────────────────────────

export function ActivationButton({
  config,
  onActivationComplete,
  onActivationError,
  disabled = false,
}: ActivationButtonProps) {
  const [state, setState] = useState<ActivationState>('idle');
  const [prerequisites, setPrerequisites] = useState<PrerequisiteChecklist | null>(null);
  const [missingItems, setMissingItems] = useState<string[]>([]);
  const [prereqError, setPrereqError] = useState<string | null>(null);
  const [warmupStatus, setWarmupStatus] = useState<WarmupStatus | null>(null);
  const [pollAttempt, setPollAttempt] = useState(0);
  const [activationError, setActivationError] = useState<string | null>(null);

  const mountedRef = useRef(true);
  const warmupTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevPollAttemptRef = useRef(0);
  const hasActivatedRef = useRef(false); // D14-P1: prevent double-fire of activation POST

  // ── Cleanup on unmount ─────────────────────────────────────────────────

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (warmupTimerRef.current) {
        clearTimeout(warmupTimerRef.current);
        warmupTimerRef.current = null;
      }
    };
  }, []);

  // ── Parse missing prerequisites into checklist ─────────────────────────

  const parseMissingPrereqs = useCallback((missing: string[]): PrerequisiteChecklist => {
    const checklist: PrerequisiteChecklist = {
      legal_consent: true,
      integrations_connected: true,
      company_details_completed: true,
    };

    for (const item of missing) {
      const lower = item.toLowerCase();
      if (lower.includes('consent') || lower.includes('legal') || lower.includes('terms')) {
        checklist.legal_consent = false;
      }
      if (lower.includes('integration') || lower.includes('channel') || lower.includes('connect')) {
        checklist.integrations_connected = false;
      }
      if (lower.includes('company') || lower.includes('detail') || lower.includes('profile')) {
        checklist.company_details_completed = false;
      }
    }

    return checklist;
  }, []);

  // ── Check prerequisites on mount ──────────────────────────────────────

  useEffect(() => {
    setState('checking_prereqs');

    const checkActivationState = async () => {
      // D14-P1: On mount, check if AI is already activated to prevent double-activation
      // when user clicks browser Back to the AIConfig step.
      try {
        const stateRes = await fetch('/api/onboarding/state');
        if (stateRes.ok) {
          const stateData = await stateRes.json();
          if (
            stateData.status === 'completed' ||
            (Array.isArray(stateData.completed_steps) && stateData.completed_steps.includes(5))
          ) {
            if (mountedRef.current) {
              hasActivatedRef.current = true;
              setState('done');
              return true; // Signal to skip prereq check
            }
          }
        }
      } catch {
        // Best effort — continue with prereq check
      }
      return false;
    };

    const checkPrereqs = async () => {
      try {
        const res = await fetch('/api/onboarding/prerequisites');
        const data: PrerequisitesResponse = await res.json();

        if (!mountedRef.current) return;

        if (data && typeof data.can_activate === 'boolean') {
          if (data.can_activate) {
            setPrerequisites({
              legal_consent: true,
              integrations_connected: true,
              company_details_completed: true,
            });
            setState('ready');
          } else {
            const checklist = parseMissingPrereqs(data.missing || []);
            setPrerequisites(checklist);
            setMissingItems(data.missing || []);
            setState('unmet_prereqs');
          }
        } else {
          setPrereqError('Unable to verify prerequisites. Please refresh.');
          setMissingItems(['Unable to verify prerequisites. Please refresh.']);
          setState('unmet_prereqs');
        }
      } catch {
        if (!mountedRef.current) return;
        setPrereqError('Could not reach server. Check your connection and refresh.');
        setMissingItems(['Server unreachable — cannot verify prerequisites.']);
        setPrerequisites({
          legal_consent: false,
          integrations_connected: false,
          company_details_completed: false,
        });
        setState('unmet_prereqs');
      }
    };

    checkActivationState().then((alreadyActivated) => {
      if (!alreadyActivated) checkPrereqs();
    });
  }, [parseMissingPrereqs]);

  // ── Warmup polling with exponential backoff ────────────────────────────

  const pollWarmup = useCallback(
    (attempt: number) => {
      if (!mountedRef.current) return;
      // D14-P3: When max poll attempts exhausted, transition to error with a helpful message
      // instead of silently staying in polling_warmup forever.
      if (attempt >= MAX_WARMUP_POLL_ATTEMPTS) {
        setState('error');
        setActivationError(
            'AI models are still warming up in the background. Your AI is activating — you can proceed to the dashboard.',
          );
        onActivationError('Warmup polling exhausted. AI activation is proceeding in the background.');
        return;
      }

      const backoffIndex = Math.min(attempt, WARMUP_BACKOFF_INTERVALS.length - 1);
      const interval = WARMUP_BACKOFF_INTERVALS[backoffIndex];

      warmupTimerRef.current = setTimeout(async () => {
        if (!mountedRef.current) return;

        try {
          const res = await fetch('/api/onboarding/warmup-status');
          if (res.ok) {
            const data: WarmupStatus = await res.json();
            if (mountedRef.current) {
              setWarmupStatus(data);
              const nextAttempt = attempt + 1;
              setPollAttempt(nextAttempt);
              prevPollAttemptRef.current = nextAttempt;

              if (data.overall_status === 'warm') {
                setState('done');
                onActivationComplete({
                  success: true,
                  warmup_required: false,
                  message: 'AI models are fully warmed up and ready!',
                });
                return;
              }

              pollWarmup(nextAttempt);
            }
          } else {
            // Non-ok response — retry with backoff
            const nextAttempt = attempt + 1;
            setPollAttempt(nextAttempt);
            pollWarmup(nextAttempt);
          }
        } catch {
          // Network error — retry
          if (mountedRef.current) {
            const nextAttempt = attempt + 1;
            setPollAttempt(nextAttempt);
            pollWarmup(nextAttempt);
          }
        }
      }, interval);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [onActivationComplete],
  );

  // ── Handle activation ─────────────────────────────────────────────────

  const handleActivate = useCallback(async () => {
    // D14-P1: Guard against double-fire (e.g., browser Back remount)
    if (hasActivatedRef.current) return;

    // Client-side validation
    const validationErrors: string[] = [];
    const trimmedName = config.ai_name.trim();

    if (!trimmedName) {
      validationErrors.push('Assistant name is required.');
    } else if (trimmedName.length < 2) {
      validationErrors.push('Assistant name must be at least 2 characters.');
    }

    const validTones = ['professional', 'friendly', 'casual'];
    if (!validTones.includes(config.ai_tone)) {
      validationErrors.push(`Invalid tone: ${config.ai_tone}.`);
    }

    const validStyles = ['concise', 'detailed'];
    if (!validStyles.includes(config.ai_response_style)) {
      validationErrors.push(`Invalid response style: ${config.ai_response_style}.`);
    }

    if (config.ai_greeting && config.ai_greeting.length > 500) {
      validationErrors.push('Greeting must be 500 characters or fewer.');
    }

    if (validationErrors.length > 0) {
      setActivationError(validationErrors.join(' '));
      setState('error');
      onActivationError(validationErrors.join(' '));
      return;
    }

    setState('activating');
    setActivationError(null);

    try {
      const res = await fetch('/api/onboarding/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ai_name: trimmedName,
          ai_tone: config.ai_tone,
          ai_response_style: config.ai_response_style,
          ai_greeting: config.ai_greeting?.trim() || undefined,
        }),
      });

      const responseData = await res.json().catch(() => ({}));

      if (!res.ok) {
        const errMsg =
          responseData?.detail || responseData?.error?.message || 'Activation failed';
        throw new Error(errMsg);
      }

      // Activation succeeded — begin warmup polling
      // D14-P1: Mark as activated to prevent double-fire
      hasActivatedRef.current = true;

      setState('polling_warmup');
      onActivationComplete({
        success: true,
        warmup_required: true,
        message: 'AI assistant activated! Models are warming up...',
      });

      // Start polling from attempt 0
      setPollAttempt(0);
      prevPollAttemptRef.current = 0;
      pollWarmup(0);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Activation failed';
      // D14-P11: Sanitize error messages — never expose internal tracebacks to users
      const sanitized =
        errorMsg.includes('Traceback') ||
        errorMsg.includes('File "/') ||
        errorMsg.length > 200
          ? 'Something went wrong on our end. Please try again.'
          : errorMsg;
      setActivationError(sanitized);
      setState('error');
      onActivationError(sanitized);
    }
  }, [config, onActivationComplete, onActivationError, pollWarmup]);

  // ── Retry from error state ────────────────────────────────────────────

  const handleRetry = useCallback(() => {
    setActivationError(null);
    setState('ready');
  }, []);

  // ── Re-check prerequisites ────────────────────────────────────────────

  const handleRecheckPrereqs = useCallback(async () => {
    setState('checking_prereqs');
    setPrereqError(null);

    try {
      const res = await fetch('/api/onboarding/prerequisites');
      const data: PrerequisitesResponse = await res.json();

      if (!mountedRef.current) return;

      if (data && typeof data.can_activate === 'boolean') {
        if (data.can_activate) {
          setPrerequisites({
            legal_consent: true,
            integrations_connected: true,
            company_details_completed: true,
          });
          setMissingItems([]);
          setState('ready');
        } else {
          const checklist = parseMissingPrereqs(data.missing || []);
          setPrerequisites(checklist);
          setMissingItems(data.missing || []);
          setState('unmet_prereqs');
        }
      }
    } catch {
      if (mountedRef.current) {
        setPrereqError('Could not reach server. Please try again.');
        setState('unmet_prereqs');
      }
    }
  }, [parseMissingPrereqs]);

  // ── Button text & icon based on state ─────────────────────────────────

  const getButtonContent = () => {
    switch (state) {
      case 'idle':
        return (
          <>
            <Sparkles className="mr-2 h-5 w-5" />
            Check Requirements
          </>
        );
      case 'checking_prereqs':
        return (
          <>
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Checking...
          </>
        );
      case 'ready':
        return (
          <>
            <Sparkles className="mr-2 h-5 w-5" />
            Activate AI Assistant
          </>
        );
      case 'unmet_prereqs':
        return (
          <>
            <AlertTriangle className="mr-2 h-5 w-5" />
            Requirements Not Met
          </>
        );
      case 'activating':
        return (
          <>
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Activating...
          </>
        );
      case 'polling_warmup':
        return (
          <>
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Warming Up Models...
            {warmupStatus && (
              <span className="ml-1 text-xs opacity-80">
                ({warmupStatus.models_ready}/{warmupStatus.models_total})
              </span>
            )}
          </>
        );
      case 'done':
        return (
          <>
            <CheckCircle2 className="mr-2 h-5 w-5" />
            Activated!
          </>
        );
      case 'error':
        return (
          <>
            <AlertTriangle className="mr-2 h-5 w-5" />
            Retry Activation
          </>
        );
    }
  };

  const getButtonVariant = () => {
    if (state === 'error') return 'destructive' as const;
    if (state === 'unmet_prereqs') return 'secondary' as const;
    if (state === 'done') return 'outline' as const;
    return 'default' as const;
  };

  const getButtonDisabled = () => {
    if (disabled) return true;
    if (state === 'idle' || state === 'checking_prereqs') return false;
    if (state === 'unmet_prereqs') return true;
    if (state === 'ready' || state === 'error') return false;
    // activating, polling_warmup, done
    return true;
  };

  const getButtonClass = () => {
    if (state === 'ready') {
      return 'bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white shadow-lg shadow-green-600/20 hover:shadow-green-600/30';
    }
    if (state === 'done') {
      return 'border-green-600 text-green-600 bg-green-50 dark:bg-green-950/20';
    }
    return '';
  };

  const handleClick = () => {
    if (state === 'ready') handleActivate();
    if (state === 'error') handleRetry();
    if (state === 'idle' || state === 'checking_prereqs') {
      // Allow clicking "Check Requirements" early
      setState('checking_prereqs');
    }
  };

  // ── Warmup progress bar calculation ───────────────────────────────────

  const warmupProgress =
    warmupStatus && warmupStatus.models_total > 0
      ? Math.round((warmupStatus.models_ready / warmupStatus.models_total) * 100)
      : 0;

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Prerequisite Fetch Error */}
      {prereqError && state === 'unmet_prereqs' && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{prereqError}</AlertDescription>
        </Alert>
      )}

      {/* Prerequisites Checklist */}
      {prerequisites && (state === 'unmet_prereqs' || state === 'checking_prereqs') && (
        <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
          <p className="text-sm font-medium">Activation Requirements</p>
          <ul className="space-y-2" role="list" aria-label="Activation prerequisites">
            {PREREQ_ITEMS.map(({ key, label, icon: Icon }) => {
              const met = prerequisites[key];
              return (
                <li
                  key={key}
                  className="flex items-center gap-2 text-sm"
                  role="listitem"
                  aria-label={`${label}: ${met ? 'completed' : 'not completed'}`}
                >
                  {state === 'checking_prereqs' ? (
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground shrink-0" />
                  ) : met ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" aria-hidden="true" />
                  ) : (
                    <XCircle className="h-4 w-4 text-destructive shrink-0" aria-hidden="true" />
                  )}
                  <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" aria-hidden="true" />
                  <span className={met ? 'text-foreground' : 'text-muted-foreground'}>
                    {label}
                  </span>
                  {met && (
                    <Badge variant="secondary" className="ml-auto text-xs bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400">
                      Done
                    </Badge>
                  )}
                </li>
              );
            })}
          </ul>
          {state === 'unmet_prereqs' && (
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={handleRecheckPrereqs}
              aria-label="Re-check prerequisites"
            >
              <Loader2 className="mr-1.5 h-3.5 w-3.5" />
              Re-check Requirements
            </Button>
          )}
        </div>
      )}

      {/* Warmup Progress Panel */}
      {state === 'polling_warmup' && warmupStatus && (
        <div className="rounded-lg border bg-muted/30 p-4 space-y-3 animate-in fade-in duration-300">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">Model Warmup Progress</p>
            <Badge
              variant="outline"
              className="text-xs text-amber-600 border-amber-300 dark:border-amber-700"
            >
              {warmupStatus.models_ready} / {warmupStatus.models_total} models
            </Badge>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-gradient-to-r from-amber-400 to-green-500 transition-all duration-500 ease-out"
              style={{ width: `${warmupProgress}%` }}
              role="progressbar"
              aria-valuenow={warmupProgress}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Warmup progress"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            {warmupStatus.message || 'Your AI models are getting ready...'}
          </p>
        </div>
      )}

      {/* Activation Error */}
      {activationError && state === 'error' && (
        <Alert variant="destructive" className="animate-in fade-in duration-200">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{activationError}</AlertDescription>
        </Alert>
      )}

      {/* D14-P3: Skip to Dashboard when warmup polling is exhausted */}
      {activationError &&
        state === 'error' &&
        activationError.includes('proceed to the dashboard') && (
          <div className="flex justify-end">
            <Button
              variant="outline"
              onClick={() =>
                onActivationComplete({
                  success: true,
                  warmup_required: true,
                  message: 'AI activation proceeding — skipped warmup wait.',
                })
              }
              className="gap-2"
            >
              Skip to Dashboard
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        )}

      {/* Success State */}
      {state === 'done' && (
        <Alert className="bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800 animate-in fade-in duration-300">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800 dark:text-green-300">
            AI assistant activated successfully!
            {warmupStatus?.overall_status === 'warm'
              ? ' (All models ready — fully operational!)'
              : ' Your AI is ready to go!'}
          </AlertDescription>
        </Alert>
      )}

      {/* Activation Button */}
      <div className="flex justify-end">
        <Button
          onClick={handleClick}
          disabled={getButtonDisabled()}
          size="lg"
          variant={getButtonVariant()}
          className={`min-w-[220px] ${getButtonClass()}`}
          aria-label={
            state === 'ready'
              ? 'Activate AI Assistant'
              : state === 'error'
                ? 'Retry activation'
                : state === 'done'
                  ? 'AI Assistant activated'
                  : state === 'activating'
                    ? 'Activating AI Assistant'
                    : state === 'polling_warmup'
                      ? 'Warming up AI models'
                      : 'Check activation requirements'
          }
        >
          {getButtonContent()}
        </Button>
      </div>
    </div>
  );
}
