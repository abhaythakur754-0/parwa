'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, CheckCircle2, Shield } from 'lucide-react';

interface LegalComplianceProps {
  onComplete: () => void;
  isSubmitting?: boolean;
}

export function LegalCompliance({ onComplete, isSubmitting = false }: LegalComplianceProps) {
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);
  const [acceptAiData, setAcceptAiData] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const allAccepted = acceptTerms && acceptPrivacy && acceptAiData;

  const handleSubmit = async () => {
    if (!allAccepted) {
      setError('All consents must be accepted to continue.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch('/api/onboarding/legal-consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          accept_terms: acceptTerms,
          accept_privacy: acceptPrivacy,
          accept_ai_data: acceptAiData,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || data?.error?.message || 'Failed to accept consents');
      }

      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <Shield className="h-12 w-12 mx-auto text-blue-600" />
        <h2 className="text-2xl font-bold">Legal Compliance</h2>
        <p className="text-muted-foreground">
          Review and accept our policies to continue setting up your account.
        </p>
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Checkbox
                id="terms"
                checked={acceptTerms}
                onCheckedChange={(v) => setAcceptTerms(v === true)}
              />
              Terms of Service
            </CardTitle>
            <CardDescription>
              Our terms govern your use of PARWA&apos;s AI-powered customer support platform,
              including service level commitments, data handling responsibilities, and
              acceptable use policies.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-muted-foreground bg-muted p-4 rounded-lg max-h-40 overflow-y-auto">
              <p>
                These Terms of Service (&quot;Terms&quot;) govern your access to and use of PARWA,
                including our AI-powered customer support platform, analytics dashboard, and
                all associated services. By creating an account, you agree to be bound by
                these Terms and our Privacy Policy.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Checkbox
                id="privacy"
                checked={acceptPrivacy}
                onCheckedChange={(v) => setAcceptPrivacy(v === true)}
              />
              Privacy Policy
            </CardTitle>
            <CardDescription>
              How we collect, process, and protect your data in compliance with
              GDPR, CCPA, and other applicable regulations.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-muted-foreground bg-muted p-4 rounded-lg max-h-40 overflow-y-auto">
              <p>
                PARWA is committed to protecting your privacy. We collect only the data
                necessary to provide our services, process it transparently, and never
                sell your data to third parties. Our AI systems are designed with
                privacy-by-design principles, ensuring customer data is handled
                responsibly and in compliance with applicable data protection laws.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Checkbox
                id="ai-data"
                checked={acceptAiData}
                onCheckedChange={(v) => setAcceptAiData(v === true)}
              />
              AI Data Processing Agreement
            </CardTitle>
            <CardDescription>
              Consent for using your data to improve AI models and provide
              intelligent customer support responses.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-muted-foreground bg-muted p-4 rounded-lg max-h-40 overflow-y-auto">
              <p>
                To provide AI-powered customer support, PARWA processes your uploaded
                knowledge base documents, conversation logs, and customer interactions.
                This data is used to train and improve our AI models. You retain full
                ownership of your data and can request deletion at any time. Data is
                encrypted at rest and in transit, and processed within your isolated
                tenant environment.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex justify-end">
        <Button
          onClick={handleSubmit}
          disabled={!allAccepted || submitting || isSubmitting}
          size="lg"
        >
          {submitting || isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Accepting...
            </>
          ) : (
            <>
              <CheckCircle2 className="mr-2 h-4 w-4" />
              Accept All & Continue
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
