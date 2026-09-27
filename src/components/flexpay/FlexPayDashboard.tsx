/**
 * FlexPay Dashboard Component — Production-Ready Payment Progress UI
 *
 * Shows customers their FlexPay installment plan progress with:
 * - "Day X of 30" progress indicator
 * - Visual progress bar with percentage
 * - Recent payment history (last 5 installments)
 * - Plan status badges (active/paused/completed)
 * - Action buttons (pause/resume/cancel)
 * - Financial summary (collected, remaining, next charge)
 *
 * Business Rules (from CLAUDE.md P-002):
 * - PARWA ($2,999): ~25 days
 * - PARWA High ($3,999): 30 days ($100 base + extra $100 every 3rd day)
 *
 * CLAUDE.md Compliance:
 * - P-003: Simple language in UI text
 * - P-004: Business-first design (builds trust, shows transparency)
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

// Icons (using simple SVG components to avoid heavy icon library dependencies)
const CheckCircleIcon = ({ className = "h-5 w-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const XCircleIcon = ({ className = "h-5 w-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const ClockIcon = ({ className = "h-5 w-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const PauseIcon = ({ className = "h-5 w-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const PlayIcon = ({ className = "h-5 w-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const AlertTriangleIcon = ({ className = "h-5 w-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
  </svg>
);


// ─── Types ────────────────────────────────────────────────────────

interface Installment {
  number: number;
  amount: number;
  status: 'pending' | 'processing' | 'paid' | 'failed' | 'skipped';
  processed_at?: string;
  is_extra?: boolean;
}

interface FlexPlanStatus {
  plan_id: string;
  variant_tier: string;
  status: 'pending' | 'active' | 'paused' | 'completed' | 'cancelled' | 'failed';
  total_amount: number;
  collected_amount: number;
  remaining_amount: number;
  progress_percent: number;
  installments: {
    total: number;
    completed: number;
    pending: number;
    failed: number;
  };
  period: {
    start: string | null;
    end: string | null;
  };
  failure_info: {
    consecutive_failures: number;
    last_reason: string | null;
    last_failure_at: string | null;
  } | null;
  recent_installments: Installment[];
}


// ─── Helper Functions ─────────────────────────────────────────────

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(amount);
}

function formatDate(dateStr: string): string {
  if (!dateStr) return 'N/A';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'active':
      return 'bg-green-100 text-green-800 border-green-200';
    case 'paused':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    case 'completed':
      return 'bg-blue-100 text-blue-800 border-blue-200';
    case 'cancelled':
      return 'bg-gray-100 text-gray-800 border-gray-200';
    case 'failed':
      return 'bg-red-100 text-red-800 border-red-200';
    case 'pending':
      return 'bg-purple-100 text-purple-800 border-purple-200';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200';
  }
}

function getInstallmentStatusIcon(status: string) {
  switch (status) {
    case 'paid':
      return <CheckCircleIcon className="h-4 w-4 text-green-600" />;
    case 'failed':
      return <XCircleIcon className="h-4 w-4 text-red-600" />;
    case 'processing':
      return <ClockIcon className="h-4 w-4 text-blue-600 animate-spin" />;
    default:
      return <ClockIcon className="h-4 w-4 text-gray-400" />;
  }
}

function getVariantDisplayName(variant: string): string {
  const names: Record<string, string> = {
    parwa: 'PARWA',
    high: 'PARWA High',
  };
  return names[variant] || variant.toUpperCase();
}


// ─── Main Component ───────────────────────────────────────────────

interface FlexPayDashboardProps {
  /** The FlexPay plan ID to display */
  planId?: string;
  /** Optional callback when action is taken */
  onAction?: (action: string, data?: any) => void;
  /** Whether to show admin controls (pause/resume/cancel) */
  showControls?: boolean;
  /** Auto-refresh interval in milliseconds (0 = no auto-refresh) */
  refreshInterval?: number;
}

export function FlexPayDashboard({
  planId,
  onAction,
  showControls = true,
  refreshInterval = 30000, // Refresh every 30 seconds by default
}: FlexPayDashboardProps) {
  // State
  const [planStatus, setPlanStatus] = useState<FlexPlanStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  
  // Dialog states
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [pauseDialogOpen, setPauseDialogOpen] = useState(false);
  const [resumeDialogOpen, setResumeDialogOpen] = useState(false);
  
  // Fetch plan status
  const fetchStatus = useCallback(async () => {
    if (!planId) {
      setLoading(false);
      return;
    }

    try {
      setError(null);
      const response = await fetch(`/api/flexpay/${planId}/status`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch status: ${response.statusText}`);
      }

      const data: FlexPlanStatus = await response.json();
      setPlanStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load plan status');
    } finally {
      setLoading(false);
    }
  }, [planId]);

  // Initial fetch and auto-refresh
  useEffect(() => {
    fetchStatus();

    if (refreshInterval > 0) {
      const interval = setInterval(fetchStatus, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchStatus, refreshInterval]);

  // Action handlers
  const handleAction = async (action: string, payload?: any) => {
    if (!planId) return;

    setActionLoading(action);
    try {
      const response = await fetch(`/api/flexpay/${planId}/${action}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
        body: JSON.stringify(payload || {}),
      });

      if (!response.ok) {
        throw new Error(`Action failed: ${response.statusText}`);
      }

      // Refresh status after action
      await fetchStatus();
      
      // Close dialogs
      setCancelDialogOpen(false);
      setPauseDialogOpen(false);
      setResumeDialogOpen(false);

      // Notify parent
      onAction?.(action, payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Loading state
  if (loading) {
    return (
      <Card className="w-full max-w-4xl mx-auto">
        <CardContent className="p-8">
          <div className="flex items-center justify-center space-x-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            <span className="text-muted-foreground">Loading your FlexPay progress...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (error && !planStatus) {
    return (
      <Card className="w-full max-w-4xl mx-auto border-destructive">
        <CardContent className="p-6">
          <div className="flex items-center space-x-3 text-destructive">
            <AlertTriangleIcon className="h-6 w-6" />
            <div>
              <h3 className="font-semibold">Unable to Load FlexPay Data</h3>
              <p className="text-sm mt-1">{error}</p>
              <Button variant="outline" size="sm" className="mt-3" onClick={fetchStatus}>
                Try Again
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // No plan selected
  if (!planStatus) {
    return (
      <Card className="w-full max-w-4xl mx-auto">
        <CardContent className="p-8 text-center">
          <ClockIcon className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No Active FlexPay Plan</h3>
          <p className="text-muted-foreground">
            Select a plan or create a new FlexPay installment plan to get started.
          </p>
        </CardContent>
      </Card>
    );
  }

  // Calculate day info
  const currentDay = planStatus.installments.completed + 1;
  const totalDays = Math.ceil(planStatus.installments.total / 1.33); // Approximate (accounts for extra charges)

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      {/* Header Card */}
      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <CardTitle className="text-2xl font-bold flex items-center gap-3">
                FlexPay Dashboard
                <Badge variant="outline" className={getStatusColor(planStatus.status)}>
                  {planStatus.status.charAt(0).toUpperCase() + planStatus.status.slice(1)}
                </Badge>
              </CardTitle>
              <CardDescription className="text-base">
                {getVariantDisplayName(planStatus.variant_tier)} • {formatCurrency(planStatus.total_amount)} total
              </CardDescription>
            </div>
            
            {showControls && (
              <div className="flex gap-2">
                {(planStatus.status === 'active' || planStatus.status === 'pending') && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPauseDialogOpen(true)}
                    disabled={!!actionLoading}
                  >
                    <PauseIcon className="h-4 w-4 mr-2" />
                    Pause
                  </Button>
                )}
                
                {planStatus.status === 'paused' && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setResumeDialogOpen(true)}
                    disabled={!!actionLoading}
                  >
                    <PlayIcon className="h-4 w-4 mr-2" />
                    Resume
                  </Button>
                )}
                
                {!['completed', 'cancelled'].includes(planStatus.status) && (
                  <Dialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
                    <DialogTrigger asChild>
                      <Button variant="destructive" size="sm" disabled={!!actionLoading}>
                        Cancel Plan
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Cancel FlexPay Plan?</DialogTitle>
                        <DialogDescription>
                          This will stop all future payments. You'll keep access for the portion you've already paid ({formatCurrency(planStatus.collected_amount)}).
                          <br /><br />
                          <strong>This action cannot be undone.</strong>
                        </DialogDescription>
                      </DialogHeader>
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setCancelDialogOpen(false)}>
                          Keep Plan
                        </Button>
                        <Button
                          variant="destructive"
                          onClick={() => handleAction('cancel', { reason: 'Customer requested cancellation' })}
                          disabled={actionLoading === 'cancel'}
                        >
                          {actionLoading === 'cancel' ? 'Cancelling...' : 'Yes, Cancel Plan'}
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                )}
              </div>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Day X of Y Progress */}
          <div className="space-y-3">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium text-muted-foreground">Payment Progress</span>
              <span className="text-3xl font-bold text-primary">
                Day {Math.min(currentDay, totalDays)} of {totalDays}
              </span>
            </div>
            
            <Progress value={planStatus.progress_percent} className="h-3" />
            
            <div className="flex justify-between text-sm text-muted-foreground">
              <span>{formatCurrency(planStatus.collected_amount)} collected</span>
              <span>{planStatus.progress_percent.toFixed(1)}% complete</span>
              <span>{formatCurrency(planStatus.remaining_amount)} remaining</span>
            </div>
          </div>

          <Separator />

          {/* Quick Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-3 bg-green-50 dark:bg-green-950 rounded-lg">
              <div className="text-2xl font-bold text-green-700 dark:text-green-300">
                {planStatus.installments.completed}
              </div>
              <div className="text-xs text-green-600 dark:text-green-400 mt-1">Paid</div>
            </div>
            
            <div className="text-center p-3 bg-blue-50 dark:bg-blue-950 rounded-lg">
              <div className="text-2xl font-bold text-blue-700 dark:text-blue-300">
                {planStatus.installments.pending}
              </div>
              <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">Pending</div>
            </div>
            
            <div className="text-center p-3 bg-yellow-50 dark:bg-yellow-950 rounded-lg">
              <div className="text-2xl font-bold text-yellow-700 dark:text-yellow-300">
                {formatCurrency(planStatus.total_amount / totalDays)}
              </div>
              <div className="text-xs text-yellow-600 dark:text-yellow-400 mt-1">Daily Avg</div>
            </div>
            
            <div className="text-center p-3 bg-purple-50 dark:bg-purple-950 rounded-lg">
              <div className="text-2xl font-bold text-purple-700 dark:text-purple-300">
                {planStatus.installments.failed}
              </div>
              <div className="text-xs text-purple-600 dark:text-purple-400 mt-1">Failed</div>
            </div>
          </div>

          {/* Failure Warning */}
          {planStatus.failure_info && planStatus.failure_info.consecutive_failures > 0 && (
            <Alert variant="destructive">
              <AlertTriangleIcon className="h-4 w-4" />
              <AlertDescription>
                <strong>Payment Issues Detected</strong><br />
                Last failure: {planStatus.failure_info.last_reason || 'Unknown reason'}<br />
                Consecutive failures: {planStatus.failure_info.consecutive_failures}/3 before auto-pause
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Recent Installments */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Recent Payments</CardTitle>
          <CardDescription>Last 5 installment transactions</CardDescription>
        </CardHeader>
        <CardContent>
          {planStatus.recent_installments.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No payments processed yet. Your first charge will happen soon!
            </div>
          ) : (
            <div className="space-y-3">
              {planStatus.recent_installments.map((inst) => (
                <div
                  key={inst.number}
                  className="flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
                >
                  <div className="flex items-center gap-3">
                    {getInstallmentStatusIcon(inst.status)}
                    <div>
                      <div className="font-medium">
                        Installment #{inst.number}
                        {inst.is_extra && (
                          <Badge variant="secondary" className="ml-2 text-xs">
                            Extra Charge
                          </Badge>
                        )}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {inst.processed_at ? formatDate(inst.processed_at) : 'Scheduled'}
                      </div>
                    </div>
                  </div>
                  
                  <div className="text-right">
                    <div className={`font-semibold ${
                      inst.status === 'paid' ? 'text-green-600' :
                      inst.status === 'failed' ? 'text-red-600' :
                      'text-foreground'
                    }`}>
                      {formatCurrency(inst.amount)}
                    </div>
                    <Badge variant="outline" className="text-xs mt-1 capitalize">
                      {inst.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* How It Works Info Card */}
      {planStatus.status === 'pending' || planStatus.status === 'active' ? (
        <Card className="border-dashed">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <ClockIcon className="h-5 w-5 text-primary" />
              How FlexPay Works
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>
              Instead of paying <strong className="text-foreground">{formatCurrency(planStatus.total_amount)}</strong> upfront,
              we split it into smaller daily installments that fit within payment limits.
            </p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li><strong>Daily base charge:</strong> $100 every morning (9 AM UTC)</li>
              <li><strong>Extra charge:</strong> Additional $100 every 3rd day (11 AM UTC)</li>
              <li><strong>Total duration:</strong> {totalDays} days to collect full amount</li>
              <li><strong>Auto-retry:</strong> Failed payments retry automatically after 24 hours</li>
              <li><strong>Auto-pause:</strong> Plan pauses after 3 consecutive failures</li>
            </ul>
            <p className="pt-2">
              You can pause or cancel anytime from this dashboard.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {/* Pause Dialog */}
      <Dialog open={pauseDialogOpen} onOpenChange={setPauseDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Pause FlexPay Plan?</DialogTitle>
            <DialogDescription>
              This will temporarily stop all future payments until you resume.
              Your service access will continue for already-paid portions.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPauseDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="default"
              onClick={() => handleAction('pause', { reason: 'Customer paused manually' })}
              disabled={actionLoading === 'pause'}
            >
              {actionLoading === 'pause' ? 'Pausing...' : 'Yes, Pause Plan'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Resume Dialog */}
      <Dialog open={resumeDialogOpen} onOpenChange={setResumeDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Resume FlexPay Plan?</DialogTitle>
            <DialogDescription>
              This will restart automatic payments from where they left off.
              Make sure your payment method is up to date before resuming.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setResumeDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="default"
              onClick={() => handleAction('resume', { notes: 'Customer resumed manually' })}
              disabled={actionLoading === 'resume'}
            >
              {actionLoading === 'resume' ? 'Resuming...' : 'Yes, Resume Plan'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Error Toast */}
      {error && (
        <Alert variant="destructive" className="animate-in slide-in-from-top-2">
          <AlertTriangleIcon className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>{error}</span>
            <Button variant="ghost" size="sm" className="h-auto p-1" onClick={() => setError(null)}>
              ✕
            </Button>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}


// ─── Export Default ───────────────────────────────────────────────

export default FlexPayDashboard;


// ─── Company Plans List Component ──────────────────────────────────

interface CompanyPlansListProps {
  /** Callback when a plan is selected */
  onSelectPlan: (planId: string) => void;
  /** Show completed/cancelled plans too */
  includeCompleted?: boolean;
}

export function FlexPayCompanyPlansList({ 
  onSelectPlan, 
  includeCompleted = false 
}: CompanyPlansListProps) {
  const [plans, setPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchPlans() {
      try {
        const response = await fetch(
          `/api/flexpay/company-plans?include_completed=${includeCompleted}`,
          {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error('Failed to fetch plans');
        }

        const data = await response.json();
        setPlans(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load plans');
      } finally {
        setLoading(false);
      }
    }

    fetchPlans();
  }, [includeCompleted]);

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 bg-muted rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangleIcon className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (plans.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          No FlexPay plans found for your company.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {plans.map((plan) => (
        <Card
          key={plan.plan_id}
          className="cursor-pointer hover:shadow-md transition-shadow"
          onClick={() => onSelectPlan(plan.plan_id)}
        >
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{getVariantDisplayName(plan.variant_tier)}</span>
                  <Badge variant="outline" className={getStatusColor(plan.status)}>
                    {plan.status}
                  </Badge>
                </div>
                <div className="text-sm text-muted-foreground">
                  {plan.current_day && plan.total_days
                    ? `Day ${plan.current_day} of ${plan.total_days}`
                    : `Created ${formatDate(plan.created_at)}`}
                </div>
              </div>
              
              <div className="text-right space-y-1">
                <div className="font-semibold">
                  {formatCurrency(plan.collected_amount)} / {formatCurrency(plan.total_amount)}
                </div>
                <Progress value={plan.progress_percent} className="w-24 h-2" />
                <div className="text-xs text-muted-foreground">
                  {plan.progress_percent.toFixed(1)}%
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
