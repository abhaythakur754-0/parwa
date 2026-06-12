'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Check, Zap, Crown, Rocket, Loader2, Shield, Sparkles, Infinity, Star, X } from 'lucide-react';
import { VARIANT_DETAILS, addVariant, removeVariant, type VariantType, type PaymentProvider } from '@/lib/api';
import { toast } from 'sonner';

interface VariantSelectionProps {
  activeVariants: VariantType[];
  onVariantChange: (variants: VariantType[]) => void;
}

const variantIcons: Record<VariantType, React.ElementType> = {
  mini: Zap,
  parwa: Rocket,
  high: Crown,
};

const variantGradients: Record<VariantType, string> = {
  mini: 'from-[#D4AF37] to-[#B8962E]',
  parwa: 'from-[#0A3D2E] to-[#1B5E40]',
  high: 'from-[#1A1A1A] to-[#0A3D2E]',
};

const variantBg: Record<VariantType, string> = {
  mini: 'bg-gradient-to-br from-[#D4AF37]/10 to-[#B8962E]/10',
  parwa: 'bg-gradient-to-br from-[#0A3D2E]/5 to-[#1B5E40]/5',
  high: 'bg-gradient-to-br from-[#1A1A1A]/5 to-[#0A3D2E]/5',
};

export default function VariantSelection({ activeVariants, onVariantChange }: VariantSelectionProps) {
  const [confirmVariant, setConfirmVariant] = useState<VariantType | null>(null);
  const [paymentProvider, setPaymentProvider] = useState<PaymentProvider>('stripe');
  const [loading, setLoading] = useState(false);
  const [removeConfirm, setRemoveConfirm] = useState<VariantType | null>(null);

  const handleAddVariant = async () => {
    if (!confirmVariant) return;
    setLoading(true);
    try {
      await addVariant(confirmVariant, paymentProvider);
      if (!activeVariants.includes(confirmVariant)) {
        onVariantChange([...activeVariants, confirmVariant]);
      }
      toast.success(`${VARIANT_DETAILS.find(v => v.id === confirmVariant)?.name} has been activated!`);
    } catch {
      if (!activeVariants.includes(confirmVariant)) {
        onVariantChange([...activeVariants, confirmVariant]);
      }
      toast.success(`${VARIANT_DETAILS.find(v => v.id === confirmVariant)?.name} activated (demo mode)`);
    }
    setLoading(false);
    setConfirmVariant(null);
  };

  const handleRemoveVariant = async (variant: VariantType) => {
    setLoading(true);
    try {
      await removeVariant(variant);
      onVariantChange(activeVariants.filter(v => v !== variant));
      toast.success(`${VARIANT_DETAILS.find(v => v.id === variant)?.name} has been removed.`);
    } catch {
      onVariantChange(activeVariants.filter(v => v !== variant));
      toast.success(`${VARIANT_DETAILS.find(v => v.id === variant)?.name} removed (demo mode)`);
    }
    setLoading(false);
    setRemoveConfirm(null);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Choose Your Plan</h2>
        <p className="text-muted-foreground">Select the PARWA variant that best fits your customer support needs.</p>
      </div>

      {/* Active Variant Badge */}
      {activeVariants.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-muted-foreground">Active:</span>
          {activeVariants.map(v => (
            <Badge key={v} variant="secondary" className="bg-[#0A3D2E]/10 text-[#0A3D2E]">
              {VARIANT_DETAILS.find(vd => vd.id === v)?.name}
              <button
                onClick={() => setRemoveConfirm(v)}
                className="ml-1.5 hover:text-red-600 transition-colors"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}

      {/* Variant Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {VARIANT_DETAILS.map((v) => {
          const Icon = variantIcons[v.id];
          const isActive = activeVariants.includes(v.id);
          return (
            <Card
              key={v.id}
              className={`relative overflow-hidden transition-all hover:shadow-lg ${
                isActive
                  ? 'border-[#0A3D2E] ring-2 ring-[#0A3D2E]/20'
                  : v.popular
                  ? 'border-[#0A3D2E]/30 hover:border-[#0A3D2E]/50'
                  : 'hover:border-[#0A3D2E]/20'
              }`}
            >
              {/* Popular badge */}
              {v.popular && (
                <div className="absolute top-0 right-0">
                  <div className="bg-[#D4AF37] text-[#1A1A1A] text-xs font-bold px-3 py-1 rounded-bl-lg flex items-center gap-1">
                    <Star className="h-3 w-3" /> POPULAR
                  </div>
                </div>
              )}

              {/* Header gradient */}
              <div className={`${variantBg[v.id]} p-6 pb-4`}>
                <div className="flex items-center gap-3 mb-3">
                  <div className={`p-2.5 rounded-xl bg-gradient-to-br ${variantGradients[v.id]} text-white shadow-lg`}>
                    <Icon className="h-6 w-6" />
                  </div>
                  <div>
                    <CardTitle className="text-xl">{v.name}</CardTitle>
                    {isActive && <Badge className="bg-[#D4AF37] text-[#1A1A1A] text-xs mt-1">Active</Badge>}
                  </div>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-4xl font-bold">${v.price}</span>
                  <span className="text-muted-foreground">/month</span>
                </div>
              </div>

              <CardContent className="p-6 pt-4 space-y-3">
                {[
                  { icon: Ticket, text: v.tickets },
                  { icon: MessageSquare, text: v.channels },
                  { icon: Sparkles, text: v.ai },
                  { icon: Shield, text: v.integrations },
                  ...v.extras.map(extra => ({ icon: Check, text: extra })),
                ].map((feature, idx) => (
                  <div key={idx} className="flex items-center gap-3">
                    <feature.icon className="h-4 w-4 text-[#0A3D2E] shrink-0" />
                    <span className="text-sm">{feature.text}</span>
                  </div>
                ))}
              </CardContent>

              <CardFooter className="p-6 pt-0">
                {isActive ? (
                  <div className="w-full space-y-2">
                    <Button variant="outline" className="w-full" disabled>
                      <Check className="h-4 w-4 mr-2" /> Currently Active
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full text-red-600 hover:text-red-700 hover:bg-red-50"
                      onClick={() => setRemoveConfirm(v.id)}
                    >
                      Remove this variant
                    </Button>
                  </div>
                ) : (
                  <Button
                    className={`w-full bg-gradient-to-r ${variantGradients[v.id]} hover:opacity-90 ${v.id === 'high' ? 'text-[#D4AF37]' : 'text-white'}`}
                    onClick={() => setConfirmVariant(v.id)}
                  >
                    Select {v.name}
                  </Button>
                )}
              </CardFooter>
            </Card>
          );
        })}
      </div>

      {/* Comparison Table */}
      <Card>
        <CardHeader>
          <CardTitle>Feature Comparison</CardTitle>
          <CardDescription>Compare all variants side by side</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-3 px-4 text-left font-medium text-muted-foreground">Feature</th>
                  <th className="py-3 px-4 text-center font-medium text-muted-foreground">Mini</th>
                  <th className="py-3 px-4 text-center font-medium text-[#0A3D2E]">Standard</th>
                  <th className="py-3 px-4 text-center font-medium text-muted-foreground">High</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { feature: 'Monthly Tickets', mini: '500', parwa: '2,000', high: 'Unlimited' },
                  { feature: 'Channels', mini: 'Email + Chat', parwa: 'All', high: 'All' },
                  { feature: 'AI Capabilities', mini: 'Basic', parwa: 'Advanced', high: 'Full Suite' },
                  { feature: 'Integrations', mini: '2', parwa: '10', high: 'Unlimited' },
                  { feature: 'Knowledge Base', mini: '✗', parwa: '✓', high: '✓' },
                  { feature: 'Priority Support', mini: '✗', parwa: 'Email', high: 'Dedicated' },
                  { feature: 'Custom Connectors', mini: '✗', parwa: '✗', high: '✓' },
                  { feature: 'SLA Guarantees', mini: '✗', parwa: '✗', high: '✓' },
                  { feature: 'Price', mini: '$29/mo', parwa: '$79/mo', high: '$199/mo' },
                ].map((row, idx) => (
                  <tr key={idx} className="border-b last:border-0">
                    <td className="py-3 px-4 font-medium">{row.feature}</td>
                    <td className="py-3 px-4 text-center">{row.mini}</td>
                    <td className="py-3 px-4 text-center bg-[#D4AF37]/10 font-medium">{row.parwa}</td>
                    <td className="py-3 px-4 text-center">{row.high}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Confirm Add Dialog */}
      <Dialog open={confirmVariant !== null} onOpenChange={() => setConfirmVariant(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Activate {VARIANT_DETAILS.find(v => v.id === confirmVariant)?.name}</DialogTitle>
            <DialogDescription>
              You&apos;re about to activate the {VARIANT_DETAILS.find(v => v.id === confirmVariant)?.name} plan at ${VARIANT_DETAILS.find(v => v.id === confirmVariant)?.price}/month.
              Please select your payment provider.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <label className="text-sm font-medium mb-2 block">Payment Provider</label>
              <Select value={paymentProvider} onValueChange={(v) => setPaymentProvider(v as PaymentProvider)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select provider" />
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

            {confirmVariant && (
              <Card className="bg-muted/50">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Monthly cost</span>
                    <span className="text-lg font-bold text-[#0A3D2E]">
                      ${VARIANT_DETAILS.find(v => v.id === confirmVariant)?.price}/mo
                    </span>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmVariant(null)}>Cancel</Button>
            <Button
              onClick={handleAddVariant}
              disabled={loading}
              className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Activate Plan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirm Remove Dialog */}
      <Dialog open={removeConfirm !== null} onOpenChange={() => setRemoveConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove {VARIANT_DETAILS.find(v => v.id === removeConfirm)?.name}</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove the {VARIANT_DETAILS.find(v => v.id === removeConfirm)?.name} variant? This will affect your available features and ticket capacity.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRemoveConfirm(null)}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={() => removeConfirm && handleRemoveVariant(removeConfirm)}
              disabled={loading}
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Remove Variant
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Additional icons used
function MessageSquare(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  );
}

function Ticket(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/>
      <path d="M13 5v2"/>
      <path d="M13 17v2"/>
      <path d="M13 11v2"/>
    </svg>
  );
}
