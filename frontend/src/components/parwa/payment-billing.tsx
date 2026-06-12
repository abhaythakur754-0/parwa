'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  CreditCard, Wallet, Building2, Check, Loader2, DollarSign,
  TrendingUp, AlertTriangle, Shield, Plus, Trash2, Calculator,
} from 'lucide-react';
import {
  getUsage, getGateways, registerGateway, getCost, estimateOverage,
  VARIANT_DETAILS, type VariantType, type PaymentProvider, type PaymentGateway, type UsageSummary, type CostCalculation,
} from '@/lib/api';
import { toast } from 'sonner';

interface PaymentBillingProps {
  activeVariants: VariantType[];
}

const providerIcons: Record<PaymentProvider, React.ElementType> = {
  stripe: CreditCard,
  paypal: Wallet,
  razorpay: CreditCard,
  paddle: Shield,
  custom: Building2,
};

const providerColors: Record<PaymentProvider, string> = {
  stripe: 'bg-[#635BFF]/10 text-[#635BFF]',
  paypal: 'bg-[#003087]/10 text-[#003087]',
  razorpay: 'bg-[#0066FF]/10 text-[#0066FF]',
  paddle: 'bg-[#0A3D2E]/10 text-[#0A3D2E]',
  custom: 'bg-[#1A1A1A]/10 text-[#1A1A1A]',
};

const providerFields: Record<PaymentProvider, { label: string; key: string }[]> = {
  stripe: [
    { label: 'Publishable Key', key: 'publishable_key' },
    { label: 'Secret Key', key: 'secret_key' },
  ],
  paypal: [
    { label: 'Client ID', key: 'client_id' },
    { label: 'Client Secret', key: 'client_secret' },
  ],
  razorpay: [
    { label: 'Key ID', key: 'key_id' },
    { label: 'Key Secret', key: 'key_secret' },
  ],
  paddle: [
    { label: 'Vendor ID', key: 'vendor_id' },
    { label: 'API Key', key: 'api_key' },
  ],
  custom: [
    { label: 'API Endpoint', key: 'endpoint' },
    { label: 'API Key', key: 'api_key' },
  ],
};

export default function PaymentBilling({ activeVariants }: PaymentBillingProps) {
  const [gateways, setGateways] = useState<PaymentGateway[]>([]);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [costCalc, setCostCalc] = useState<CostCalculation | null>(null);
  const [loading, setLoading] = useState(true);

  // Register gateway dialog
  const [registerOpen, setRegisterOpen] = useState(false);
  const [regProvider, setRegProvider] = useState<PaymentProvider>('stripe');
  const [regCredentials, setRegCredentials] = useState<Record<string, string>>({});
  const [regLoading, setRegLoading] = useState(false);

  // Overage calculator
  const [overageVariant, setOverageVariant] = useState<VariantType>('parwa');
  const [overageTickets, setOverageTickets] = useState('3000');
  const [overageResult, setOverageResult] = useState<{ overage_tickets: number; overage_cost: number } | null>(null);
  const [overageLoading, setOverageLoading] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [g, u, c] = await Promise.all([
        getGateways().catch(() => []),
        getUsage().catch(() => null),
        activeVariants.length > 0 ? getCost(activeVariants).catch(() => null) : Promise.resolve(null),
      ]);
      setGateways(g);
      setUsage(u);
      setCostCalc(c);
      setLoading(false);
    }
    load();
  }, [activeVariants]);

  const handleRegister = async () => {
    setRegLoading(true);
    try {
      const gw = await registerGateway(regProvider, regCredentials);
      setGateways([...gateways, gw]);
      toast.success(`${regProvider.charAt(0).toUpperCase() + regProvider.slice(1)} gateway registered!`);
    } catch {
      toast.error('Failed to register gateway');
    }
    setRegLoading(false);
    setRegisterOpen(false);
    setRegCredentials({});
  };

  const handleEstimateOverage = async () => {
    setOverageLoading(true);
    try {
      const result = await estimateOverage(overageVariant, parseInt(overageTickets) || 0);
      setOverageResult(result);
    } catch {
      setOverageResult({
        overage_tickets: Math.max(0, parseInt(overageTickets) - 2000),
        overage_cost: Math.max(0, (parseInt(overageTickets) - 2000) * 0.05),
      });
    }
    setOverageLoading(false);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Payment & Billing</h2>
        <p className="text-muted-foreground">Manage your payment gateways, view usage, and calculate costs.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Payment Gateways - Prominent Section */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="border-[#0A3D2E]/20 bg-gradient-to-br from-[#0A3D2E]/5 to-[#1B5E40]/5">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <CreditCard className="h-5 w-5 text-[#0A3D2E]" />
                    Payment Gateways
                  </CardTitle>
                  <CardDescription>Configure how your customers pay for PARWA</CardDescription>
                </div>
                <Button
                  onClick={() => setRegisterOpen(true)}
                  className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]"
                >
                  <Plus className="h-4 w-4 mr-1" />
                  Add Gateway
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="space-y-3">
                  {[1, 2].map(i => <Skeleton key={i} className="h-16 w-full" />)}
                </div>
              ) : gateways.length === 0 ? (
                <div className="text-center py-8 border-2 border-dashed border-[#0A3D2E]/20 rounded-lg">
                  <CreditCard className="h-10 w-10 text-[#1B5E40] mx-auto mb-3" />
                  <p className="text-sm font-medium text-[#0A3D2E]">No payment gateways configured</p>
                  <p className="text-xs text-muted-foreground mt-1">Add a gateway to start accepting payments</p>
                  <Button
                    onClick={() => setRegisterOpen(true)}
                    variant="outline"
                    className="mt-3 border-[#0A3D2E]/30 hover:bg-[#0A3D2E]/5"
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    Register Gateway
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {gateways.map((gw) => {
                    const Icon = providerIcons[gw.provider] || CreditCard;
                    return (
                      <div key={gw.id} className="flex items-center justify-between p-4 rounded-lg border bg-white">
                        <div className="flex items-center gap-3">
                          <div className={`p-2 rounded-lg ${providerColors[gw.provider]}`}>
                            <Icon className="h-5 w-5" />
                          </div>
                          <div>
                            <p className="font-medium">{gw.provider.charAt(0).toUpperCase() + gw.provider.slice(1)}</p>
                            <p className="text-xs text-muted-foreground">Added {new Date(gw.created_at).toLocaleDateString()}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge className={gw.status === 'active' ? 'bg-[#0A3D2E]/10 text-[#0A3D2E]' : 'bg-red-100 text-red-800'}>
                            {gw.status === 'active' ? '● Active' : '● Error'}
                          </Badge>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Cost Calculator */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calculator className="h-5 w-5 text-[#0A3D2E]" />
                Cost Calculator
              </CardTitle>
              <CardDescription>Estimate your monthly costs based on selected variants</CardDescription>
            </CardHeader>
            <CardContent>
              {costCalc ? (
                <div className="space-y-3">
                  {costCalc.breakdown.map((b) => (
                    <div key={b.variant} className="flex items-center justify-between py-2 px-3 rounded-lg bg-muted/50">
                      <span className="text-sm capitalize">{b.variant}</span>
                      <span className="font-medium">${b.cost}/mo</span>
                    </div>
                  ))}
                  {costCalc.add_ons.length > 0 && (
                    <>
                      <Separator />
                      {costCalc.add_ons.map((a) => (
                        <div key={a.name} className="flex items-center justify-between py-2 px-3">
                          <span className="text-sm text-muted-foreground">{a.name}</span>
                          <span className="text-sm">${a.cost}/mo</span>
                        </div>
                      ))}
                    </>
                  )}
                  <Separator />
                  <div className="flex items-center justify-between py-2 px-3 bg-[#0A3D2E]/5 rounded-lg">
                    <span className="font-semibold text-[#0A3D2E]">Total Monthly Cost</span>
                    <span className="text-xl font-bold text-[#D4AF37]">${costCalc.monthly_cost}/mo</span>
                  </div>
                </div>
              ) : (
                <div className="text-center py-6">
                  <p className="text-sm text-muted-foreground">Select a variant to see pricing</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column */}
        <div className="space-y-4">
          {/* Usage Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-[#0A3D2E]" />
                Usage This Month
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="space-y-3">
                  {[1, 2].map(i => <Skeleton key={i} className="h-12 w-full" />)}
                </div>
              ) : usage ? (
                <div className="space-y-4">
                  {usage.variants.map((v) => {
                    const pct = v.tickets_limit > 0 ? Math.round((v.tickets_used / v.tickets_limit) * 100) : 0;
                    return (
                      <div key={v.variant}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm capitalize font-medium">{v.variant}</span>
                          <span className="text-sm text-muted-foreground">
                            {v.tickets_used.toLocaleString()} / {v.tickets_limit.toLocaleString()}
                          </span>
                        </div>
                        <div className="h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              pct > 90 ? 'bg-red-500' : pct > 70 ? 'bg-amber-500' : 'bg-[#0A3D2E]/50'
                            }`}
                            style={{ width: `${Math.min(pct, 100)}%` }}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">{pct}% used</p>
                      </div>
                    );
                  })}
                  <Separator />
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Total tickets</span>
                    <span className="text-sm font-bold">{usage.total_tickets_used.toLocaleString()}</span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">No usage data available</p>
              )}
            </CardContent>
          </Card>

          {/* Overage Estimator */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                Overage Estimator
              </CardTitle>
              <CardDescription>Calculate potential overage costs</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <Label className="text-xs">Variant</Label>
                <Select value={overageVariant} onValueChange={(v) => setOverageVariant(v as VariantType)}>
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="mini">Mini (500 tickets)</SelectItem>
                    <SelectItem value="parwa">Standard (2,000 tickets)</SelectItem>
                    <SelectItem value="high">High (Unlimited)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Projected Tickets</Label>
                <Input
                  type="number"
                  value={overageTickets}
                  onChange={(e) => setOverageTickets(e.target.value)}
                  className="mt-1"
                  placeholder="e.g. 3000"
                />
              </div>
              <Button
                onClick={handleEstimateOverage}
                disabled={overageLoading}
                variant="outline"
                className="w-full border-amber-300 hover:bg-amber-50"
              >
                {overageLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <DollarSign className="h-4 w-4 mr-2" />}
                Estimate Overage
              </Button>
              {overageResult && (
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span>Overage tickets:</span>
                    <span className="font-medium">{overageResult.overage_tickets.toLocaleString()}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span>Overage cost:</span>
                    <span className="font-bold text-amber-700">${overageResult.overage_cost.toFixed(2)}</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Register Gateway Dialog */}
      <Dialog open={registerOpen} onOpenChange={setRegisterOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Register Payment Gateway</DialogTitle>
            <DialogDescription>Connect a payment provider to accept subscriptions</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <Label>Provider</Label>
              <Select value={regProvider} onValueChange={(v) => {
                setRegProvider(v as PaymentProvider);
                setRegCredentials({});
              }}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="stripe">Stripe</SelectItem>
                  <SelectItem value="paypal">PayPal</SelectItem>
                  <SelectItem value="razorpay">Razorpay</SelectItem>
                  <SelectItem value="paddle">Paddle</SelectItem>
                  <SelectItem value="custom">Custom Gateway</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {providerFields[regProvider].map((field) => (
              <div key={field.key}>
                <Label>{field.label}</Label>
                <Input
                  type={field.key.includes('secret') || field.key.includes('key') ? 'password' : 'text'}
                  value={regCredentials[field.key] || ''}
                  onChange={(e) => setRegCredentials({ ...regCredentials, [field.key]: e.target.value })}
                  className="mt-1"
                  placeholder={`Enter ${field.label.toLowerCase()}`}
                />
              </div>
            ))}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setRegisterOpen(false)}>Cancel</Button>
            <Button
              onClick={handleRegister}
              disabled={regLoading}
              className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]"
            >
              {regLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Check className="h-4 w-4 mr-2" />}
              Register Gateway
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
