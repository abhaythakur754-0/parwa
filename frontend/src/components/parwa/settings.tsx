'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
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
  Settings, Building2, AlertTriangle, Check, Loader2,
  RefreshCw, Shield, Globe, Zap,
} from 'lucide-react';
import {
  getIndustryPreview, applyIndustryChange, getConnectors,
  type IndustryPreview, type CustomConnector,
} from '@/lib/api';
import { toast } from 'sonner';

const INDUSTRIES = [
  { value: 'technology', label: 'Technology' },
  { value: 'saas', label: 'SaaS' },
  { value: 'ecommerce', label: 'E-Commerce' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'finance', label: 'Finance & Banking' },
  { value: 'education', label: 'Education' },
  { value: 'realestate', label: 'Real Estate' },
  { value: 'hospitality', label: 'Hospitality' },
  { value: 'retail', label: 'Retail' },
  { value: 'manufacturing', label: 'Manufacturing' },
];

export default function SettingsPage() {
  const [currentIndustry, setCurrentIndustry] = useState('technology');
  const [selectedIndustry, setSelectedIndustry] = useState('');
  const [preview, setPreview] = useState<IndustryPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [applyLoading, setApplyLoading] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [connectors, setConnectors] = useState<CustomConnector[]>([]);
  const [connectorsLoading, setConnectorsLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setConnectorsLoading(true);
      const c = await getConnectors().catch(() => []);
      setConnectors(c);
      setConnectorsLoading(false);
    }
    load();
  }, []);

  const handlePreview = async () => {
    if (!selectedIndustry || selectedIndustry === currentIndustry) return;
    setPreviewLoading(true);
    try {
      const result = await getIndustryPreview(selectedIndustry);
      setPreview(result);
    } catch {
      setPreview({
        current_industry: currentIndustry,
        new_industry: selectedIndustry,
        integrations_to_disconnect: [],
        new_default_faqs: [
          { question: 'How do I get started?', answer: 'Follow our quick setup guide to get started in minutes.' },
          { question: 'What are your business hours?', answer: 'We are available 24/7 through our AI assistant.' },
        ],
        impact_summary: `Switching to ${selectedIndustry} will update your default templates and suggest industry-specific integrations.`,
      });
    }
    setPreviewLoading(false);
    setPreviewOpen(true);
  };

  const handleApply = async () => {
    if (!preview) return;
    setApplyLoading(true);
    try {
      const disconnectIds = preview.integrations_to_disconnect.map(i => i.id);
      await applyIndustryChange(preview.new_industry, disconnectIds.length > 0 ? disconnectIds : undefined);
      setCurrentIndustry(preview.new_industry);
      setSelectedIndustry('');
      toast.success(`Industry changed to ${INDUSTRIES.find(i => i.value === preview.new_industry)?.label || preview.new_industry}!`);
    } catch {
      setCurrentIndustry(preview.new_industry);
      setSelectedIndustry('');
      toast.success('Industry updated (demo mode)');
    }
    setApplyLoading(false);
    setPreviewOpen(false);
    setPreview(null);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
        <p className="text-muted-foreground">Configure your PARWA instance and manage industry settings.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Industry Settings */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-[#0A3D2E]" />
              Industry Configuration
            </CardTitle>
            <CardDescription>
              Changing your industry will update default templates, integrations, and knowledge base content.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label>Current Industry</Label>
                <div className="mt-1 p-3 rounded-lg border bg-muted/50 flex items-center gap-2">
                  <Globe className="h-4 w-4 text-[#0A3D2E]" />
                  <span className="font-medium">
                    {INDUSTRIES.find(i => i.value === currentIndustry)?.label || currentIndustry}
                  </span>
                </div>
              </div>
              <div>
                <Label>New Industry</Label>
                <Select value={selectedIndustry} onValueChange={setSelectedIndustry}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select new industry" />
                  </SelectTrigger>
                  <SelectContent>
                    {INDUSTRIES.filter(i => i.value !== currentIndustry).map((industry) => (
                      <SelectItem key={industry.value} value={industry.value}>
                        {industry.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <Button
              onClick={handlePreview}
              disabled={!selectedIndustry || selectedIndustry === currentIndustry || previewLoading}
              className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]"
            >
              {previewLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
              Preview Changes
            </Button>
          </CardContent>
        </Card>

        {/* Custom Connectors */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Zap className="h-4 w-4 text-[#0A3D2E]" />
              Custom Connectors
            </CardTitle>
            <CardDescription>API connectors available on PARWA High</CardDescription>
          </CardHeader>
          <CardContent>
            {connectorsLoading ? (
              <div className="space-y-3">
                {[1, 2].map(i => <Skeleton key={i} className="h-12 w-full" />)}
              </div>
            ) : connectors.length === 0 ? (
              <div className="text-center py-6">
                <Zap className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">No custom connectors</p>
                <p className="text-xs text-muted-foreground mt-1">Available with PARWA High variant</p>
              </div>
            ) : (
              <div className="space-y-2">
                {connectors.map((conn) => (
                  <div key={conn.id} className="flex items-center justify-between p-3 rounded-lg border">
                    <div>
                      <p className="text-sm font-medium">{conn.name}</p>
                      <p className="text-xs text-muted-foreground">{conn.type}</p>
                    </div>
                    <Badge className={conn.status === 'active' ? 'bg-[#0A3D2E]/10 text-[#0A3D2E]' : 'bg-slate-100 text-slate-800'}>
                      {conn.status}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Account Info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Shield className="h-4 w-4 text-[#0A3D2E]" />
              Account Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded-lg border">
              <span className="text-sm text-muted-foreground">Company ID</span>
              <code className="text-sm bg-muted px-2 py-0.5 rounded">demo-company-001</code>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg border">
              <span className="text-sm text-muted-foreground">Instance Status</span>
              <Badge className="bg-[#0A3D2E]/10 text-[#0A3D2E]">Active</Badge>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg border">
              <span className="text-sm text-muted-foreground">Region</span>
              <span className="text-sm font-medium">US East</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg border">
              <span className="text-sm text-muted-foreground">Created</span>
              <span className="text-sm font-medium">June 5, 2026</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Industry Preview Dialog */}
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-[#0A3D2E]" />
              Industry Change Preview
            </DialogTitle>
            <DialogDescription>
              Review the impact of changing your industry before applying.
            </DialogDescription>
          </DialogHeader>

          {preview && (
            <div className="space-y-4 py-2">
              {/* Industry Change */}
              <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
                <span className="font-medium">{INDUSTRIES.find(i => i.value === preview.current_industry)?.label}</span>
                <span className="text-muted-foreground">→</span>
                <span className="font-medium text-[#0A3D2E]">{INDUSTRIES.find(i => i.value === preview.new_industry)?.label}</span>
              </div>

              {/* Impact Summary */}
              <div className="p-3 rounded-lg border bg-[#0A3D2E]/5/50">
                <h4 className="text-sm font-medium flex items-center gap-1.5 mb-1">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  Impact Summary
                </h4>
                <p className="text-sm text-muted-foreground">{preview.impact_summary}</p>
              </div>

              {/* Integrations to Disconnect */}
              {preview.integrations_to_disconnect.length > 0 && (
                <div className="p-3 rounded-lg border border-red-200 bg-red-50/50">
                  <h4 className="text-sm font-medium text-red-700 mb-2">
                    Integrations to Disconnect ({preview.integrations_to_disconnect.length})
                  </h4>
                  <div className="space-y-1">
                    {preview.integrations_to_disconnect.map((intg) => (
                      <div key={intg.id} className="flex items-center gap-2 text-sm">
                        <Badge variant="destructive" className="text-xs">{intg.name}</Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* New Default FAQs */}
              {preview.new_default_faqs.length > 0 && (
                <div className="p-3 rounded-lg border">
                  <h4 className="text-sm font-medium mb-2">New Default FAQs</h4>
                  <div className="space-y-2">
                    {preview.new_default_faqs.map((faq, idx) => (
                      <div key={idx} className="text-sm">
                        <p className="font-medium">{faq.question}</p>
                        <p className="text-muted-foreground">{faq.answer}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="ghost" onClick={() => { setPreviewOpen(false); setPreview(null); }}>
              Cancel
            </Button>
            <Button
              onClick={handleApply}
              disabled={applyLoading}
              className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]"
            >
              {applyLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Check className="h-4 w-4 mr-2" />}
              Apply Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
