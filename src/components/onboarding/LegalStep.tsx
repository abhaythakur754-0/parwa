"use client";

import { useState } from "react";
import { useOnboardingStore } from "@/store/onboarding-store";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Shield, FileText, Lock, CheckCircle2 } from "lucide-react";

const legalItems = [
  {
    id: "tos",
    label: "Terms of Service",
    description: "I agree to the PARWA Terms of Service, including usage policies and SLA terms.",
    icon: FileText,
  },
  {
    id: "privacy",
    label: "Privacy Policy",
    description: "I acknowledge and agree to the PARWA Privacy Policy regarding data handling.",
    icon: Shield,
  },
  {
    id: "dpa",
    label: "Data Processing Agreement",
    description: "I accept the Data Processing Agreement for GDPR/CCPA compliance.",
    icon: Lock,
  },
];

export function LegalStep() {
  const { legalAccepted, setLegalAccepted } = useOnboardingStore();
  const [checked, setChecked] = useState<Record<string, boolean>>({
    tos: false,
    privacy: false,
    dpa: false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const allChecked = Object.values(checked).every(Boolean);

  const handleToggle = (id: string) => {
    setChecked((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleAcceptAll = () => {
    const allTrue = { tos: true, privacy: true, dpa: true };
    setChecked(allTrue);
  };

  const handleSubmit = async () => {
    if (!allChecked) {
      setError("Please accept all agreements to continue.");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const res = await fetch("/api/onboarding/legal-consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accepted: true }),
      });

      if (res.ok) {
        setLegalAccepted(true);
        setSuccess(true);
      } else {
        const data = await res.json();
        setError(data.detail || "Failed to save legal consent.");
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  if (success || legalAccepted) {
    return (
      <Card className="border-emerald-200 dark:border-emerald-800">
        <CardContent className="p-8 text-center">
          <CheckCircle2 className="h-12 w-12 text-emerald-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">Legal Agreements Accepted</h3>
          <p className="text-sm text-muted-foreground">
            You&apos;ve accepted all required agreements. You can continue to the next step.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">Legal Consent</h2>
        <p className="text-sm text-muted-foreground">
          Please review and accept the following agreements to continue.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="space-y-4">
        {legalItems.map((item) => (
          <Card key={item.id} className="hover:shadow-sm transition-shadow">
            <CardContent className="p-4 flex items-start gap-4">
              <div className="h-10 w-10 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
                <item.icon className="h-5 w-5 text-muted-foreground" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <p className="font-medium text-sm">{item.label}</p>
                </div>
                <p className="text-xs text-muted-foreground">{item.description}</p>
              </div>
              <Checkbox
                checked={checked[item.id]}
                onCheckedChange={() => handleToggle(item.id)}
              />
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex gap-3">
        <Button
          variant="outline"
          onClick={handleAcceptAll}
          className="text-sm"
        >
          Accept All
        </Button>
        <Button
          onClick={handleSubmit}
          disabled={!allChecked || saving}
          className="bg-gradient-to-r from-emerald-500 to-teal-600 text-white text-sm"
        >
          {saving ? "Saving..." : "Confirm & Continue"}
        </Button>
      </div>
    </div>
  );
}
