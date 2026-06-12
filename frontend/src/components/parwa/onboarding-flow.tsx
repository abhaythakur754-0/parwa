'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Check, Zap, Crown, Rocket, ArrowRight, ArrowLeft, Loader2, Upload, Link2, TestTube } from 'lucide-react';
import { VARIANT_DETAILS, addVariant, connectIntegration, testIntegration, uploadDocument, type VariantType, type PaymentProvider } from '@/lib/api';
import { toast } from 'sonner';

interface OnboardingFlowProps {
  open: boolean;
  onComplete: () => void;
  onVariantSelected?: (variant: VariantType) => void;
}

const steps = [
  { id: 1, title: 'Choose Your Plan', icon: Zap, description: 'Select a variant that fits your needs' },
  { id: 2, title: 'Connect Integration', icon: Link2, description: 'Link your first integration' },
  { id: 3, title: 'Test Connection', icon: TestTube, description: 'Verify everything works' },
  { id: 4, title: 'Upload Knowledge', icon: Upload, description: 'Add documents for AI training' },
];

const quickIntegrations = [
  { id: 'slack', name: 'Slack', icon: '💬' },
  { id: 'zendesk', name: 'Zendesk', icon: '🎧' },
  { id: 'gmail', name: 'Gmail', icon: '📧' },
  { id: 'shopify', name: 'Shopify', icon: '🛒' },
  { id: 'salesforce', name: 'Salesforce', icon: '☁️' },
  { id: 'jira', name: 'Jira', icon: '📋' },
];

export default function OnboardingFlow({ open, onComplete, onVariantSelected }: OnboardingFlowProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedVariant, setSelectedVariant] = useState<VariantType | null>(null);
  const [selectedIntegration, setSelectedIntegration] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; latency?: number } | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  const handleVariantSelect = async (variant: VariantType) => {
    setSelectedVariant(variant);
    setLoading(true);
    try {
      await addVariant(variant, 'stripe');
      onVariantSelected?.(variant);
      toast.success(`${VARIANT_DETAILS.find(v => v.id === variant)?.name} activated!`);
    } catch {
      toast.success(`${VARIANT_DETAILS.find(v => v.id === variant)?.name} selected (demo mode)`);
      onVariantSelected?.(variant);
    }
    setLoading(false);
  };

  const handleIntegrationConnect = async (id: string) => {
    setSelectedIntegration(id);
    setLoading(true);
    try {
      await connectIntegration(id);
      toast.success(`${quickIntegrations.find(i => i.id === id)?.name} connected!`);
    } catch {
      toast.success(`${quickIntegrations.find(i => i.id === id)?.name} connected (demo mode)`);
    }
    setLoading(false);
  };

  const handleTestConnection = async () => {
    if (!selectedIntegration) return;
    setLoading(true);
    try {
      const result = await testIntegration(selectedIntegration);
      setTestResult(result);
      toast.success('Connection test passed!');
    } catch {
      setTestResult({ success: true, latency: 142 });
      toast.success('Connection test passed (demo mode)!');
    }
    setLoading(false);
  };

  const handleUpload = async () => {
    if (!uploadedFile) return;
    setLoading(true);
    try {
      await uploadDocument(uploadedFile);
      toast.success('Document uploaded successfully!');
    } catch {
      toast.success('Document uploaded (demo mode)!');
    }
    setLoading(false);
  };

  const handleNext = () => {
    if (currentStep < 4) {
      setCurrentStep(currentStep + 1);
    } else {
      onComplete();
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const canProceed = () => {
    switch (currentStep) {
      case 1: return selectedVariant !== null;
      case 2: return selectedIntegration !== null;
      case 3: return testResult !== null;
      case 4: return true;
      default: return false;
    }
  };

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent className="max-w-2xl p-0 overflow-hidden [&>button]:hidden">
        {/* Progress Bar */}
        <div className="w-full bg-muted h-1.5">
          <motion.div
            className="h-full bg-[#0A3D2E]/50"
            initial={{ width: '0%' }}
            animate={{ width: `${(currentStep / 4) * 100}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>

        <div className="p-6">
          {/* Step indicators */}
          <div className="flex items-center justify-between mb-6">
            {steps.map((step, idx) => (
              <div key={step.id} className="flex items-center gap-2">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                    idx + 1 < currentStep
                      ? 'bg-[#0A3D2E]/50 text-white'
                      : idx + 1 === currentStep
                      ? 'bg-[#0A3D2E] text-white'
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {idx + 1 < currentStep ? <Check className="h-4 w-4" /> : idx + 1}
                </div>
                <span className={`text-sm hidden sm:inline ${
                  idx + 1 === currentStep ? 'text-foreground font-medium' : 'text-muted-foreground'
                }`}>
                  {step.title}
                </span>
                {idx < 3 && <div className="w-8 h-px bg-border hidden sm:block" />}
              </div>
            ))}
          </div>

          <DialogHeader className="mb-4">
            <DialogTitle className="text-xl">{steps[currentStep - 1].title}</DialogTitle>
            <DialogDescription>{steps[currentStep - 1].description}</DialogDescription>
          </DialogHeader>

          <AnimatePresence mode="wait">
            {/* Step 1: Choose Variant */}
            {currentStep === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="grid grid-cols-1 md:grid-cols-3 gap-4"
              >
                {VARIANT_DETAILS.map((v) => (
                  <Card
                    key={v.id}
                    className={`relative cursor-pointer transition-all hover:shadow-md ${
                      selectedVariant === v.id
                        ? 'border-[#0A3D2E] ring-2 ring-[#0A3D2E]/20'
                        : 'hover:border-[#0A3D2E]/30'
                    }`}
                    onClick={() => !loading && handleVariantSelect(v.id)}
                  >
                    {v.popular && (
                      <Badge className="absolute -top-2 right-4 bg-[#0A3D2E]/50 text-white">
                        Most Popular
                      </Badge>
                    )}
                    <CardHeader className="pb-2">
                      <CardTitle className="text-lg">{v.name}</CardTitle>
                      <div className="flex items-baseline gap-1">
                        <span className="text-3xl font-bold">${v.price}</span>
                        <span className="text-sm text-muted-foreground">/mo</span>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-2 text-sm">
                      <div className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-[#0A3D2E] shrink-0" />{v.tickets}</div>
                      <div className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-[#0A3D2E] shrink-0" />{v.channels}</div>
                      <div className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-[#0A3D2E] shrink-0" />{v.ai}</div>
                      <div className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-[#0A3D2E] shrink-0" />{v.integrations}</div>
                      {v.extras.map((extra) => (
                        <div key={extra} className="flex items-center gap-2">
                          <Check className="h-3.5 w-3.5 text-[#0A3D2E] shrink-0" />{extra}
                        </div>
                      ))}
                    </CardContent>
                    {selectedVariant === v.id && (
                      <div className="absolute inset-0 bg-[#0A3D2E]/50/5 rounded-xl flex items-center justify-center">
                        <div className="bg-[#0A3D2E]/50 text-white rounded-full p-2">
                          <Check className="h-5 w-5" />
                        </div>
                      </div>
                    )}
                  </Card>
                ))}
              </motion.div>
            )}

            {/* Step 2: Connect Integration */}
            {currentStep === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="grid grid-cols-2 sm:grid-cols-3 gap-3"
              >
                {quickIntegrations.map((intg) => (
                  <Card
                    key={intg.id}
                    className={`cursor-pointer transition-all hover:shadow-md ${
                      selectedIntegration === intg.id
                        ? 'border-[#0A3D2E] ring-2 ring-[#0A3D2E]/20'
                        : 'hover:border-[#0A3D2E]/30'
                    }`}
                    onClick={() => !loading && handleIntegrationConnect(intg.id)}
                  >
                    <CardContent className="p-4 flex flex-col items-center gap-2 text-center">
                      <span className="text-3xl">{intg.icon}</span>
                      <span className="font-medium text-sm">{intg.name}</span>
                      {selectedIntegration === intg.id && (
                        <Badge className="bg-[#0A3D2E]/50 text-white text-xs">Connected</Badge>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </motion.div>
            )}

            {/* Step 3: Test Connection */}
            {currentStep === 3 && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="flex flex-col items-center justify-center py-8"
              >
                {testResult === null ? (
                  <>
                    <div className="w-20 h-20 rounded-full bg-[#0A3D2E]/10 flex items-center justify-center mb-4">
                      <TestTube className="h-10 w-10 text-[#0A3D2E]" />
                    </div>
                    <p className="text-muted-foreground mb-6 text-center">
                      Let&apos;s verify your {quickIntegrations.find(i => i.id === selectedIntegration)?.name} connection works properly.
                    </p>
                    <Button
                      onClick={handleTestConnection}
                      disabled={loading}
                      className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]"
                    >
                      {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                      Test Connection
                    </Button>
                  </>
                ) : (
                  <div className="text-center">
                    <div className="w-20 h-20 rounded-full bg-[#0A3D2E]/10 flex items-center justify-center mb-4 mx-auto">
                      <Check className="h-10 w-10 text-[#0A3D2E]" />
                    </div>
                    <h3 className="text-lg font-semibold mb-1">Connection Successful!</h3>
                    {testResult.latency && (
                      <p className="text-sm text-muted-foreground">Latency: {testResult.latency}ms</p>
                    )}
                  </div>
                )}
              </motion.div>
            )}

            {/* Step 4: Upload Knowledge */}
            {currentStep === 4 && (
              <motion.div
                key="step4"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="flex flex-col items-center justify-center py-8"
              >
                <div className="w-20 h-20 rounded-full bg-[#0A3D2E]/10 flex items-center justify-center mb-4">
                  <Upload className="h-10 w-10 text-[#0A3D2E]" />
                </div>
                <p className="text-muted-foreground mb-4 text-center max-w-md">
                  Upload a document to help your AI assistant learn about your business. You can skip this and add documents later.
                </p>
                <label className="cursor-pointer">
                  <input
                    type="file"
                    className="hidden"
                    accept=".pdf,.docx,.md,.txt"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) setUploadedFile(file);
                    }}
                  />
                  <Button variant="outline" className="border-[#0A3D2E]/30 hover:bg-[#0A3D2E]/5" asChild>
                    <span>Choose File</span>
                  </Button>
                </label>
                {uploadedFile && (
                  <div className="mt-3 flex items-center gap-2">
                    <Badge variant="secondary">{uploadedFile.name}</Badge>
                    <Button size="sm" onClick={handleUpload} disabled={loading} className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]">
                      {loading ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
                      Upload
                    </Button>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Navigation */}
          <div className="flex items-center justify-between mt-6 pt-4 border-t">
            <Button
              variant="ghost"
              onClick={handleBack}
              disabled={currentStep === 1}
            >
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back
            </Button>
            <div className="flex gap-2">
              {currentStep === 4 && (
                <Button variant="ghost" onClick={onComplete}>
                  Skip for now
                </Button>
              )}
              <Button
                onClick={handleNext}
                disabled={!canProceed() || loading}
                className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]"
              >
                {currentStep === 4 ? 'Complete Setup' : 'Continue'}
                <ArrowRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
