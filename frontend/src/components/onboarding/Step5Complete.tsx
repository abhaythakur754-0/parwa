"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface Step5CompleteProps {
  data: {
    companyName: string;
    industry: string;
    selectedVariant: "mini" | "parwa" | "parwa_high" | null;
    integrations: {
      shopify: boolean;
      zendesk: boolean;
      twilio: boolean;
      email: boolean;
    };
    teamMembers: Array<{
      email: string;
      role: string;
    }>;
  };
  onComplete: () => void;
  isSubmitting: boolean;
}

const variantNames = {
  mini: "Mini PARWA",
  parwa: "PARWA Junior",
  parwa_high: "PARWA High",
};

const integrationNames = {
  shopify: "Shopify",
  zendesk: "Zendesk",
  twilio: "Twilio",
  email: "Email Provider",
};

const roleLabels: Record<string, string> = {
  admin: "Admin",
  agent: "Agent",
  viewer: "Viewer",
};

export function Step5Complete({ data, onComplete, isSubmitting }: Step5CompleteProps) {
  const connectedIntegrations = Object.entries(data.integrations)
    .filter(([, connected]) => connected)
    .map(([id]) => integrationNames[id as keyof typeof integrationNames]);

  const validTeamMembers = data.teamMembers.filter((m) => m.email);

  return (
    <div className="space-y-6">
      {/* Success Animation */}
      <div className="flex justify-center">
        <div className="relative">
          <div className="w-24 h-24 rounded-full bg-green-100 flex items-center justify-center animate-in zoom-in duration-300">
            <svg
              className="w-12 h-12 text-green-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          {/* Confetti dots */}
          <div className="absolute -top-2 -right-2 w-3 h-3 rounded-full bg-primary animate-ping" />
          <div className="absolute -bottom-1 -left-3 w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
          <div className="absolute top-0 -left-4 w-2 h-2 rounded-full bg-yellow-500 animate-bounce" />
        </div>
      </div>

      {/* Success Message */}
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-bold">You&apos;re all set!</h2>
        <p className="text-muted-foreground">
          Your PARWA workspace has been configured and is ready to use.
        </p>
      </div>

      {/* Summary Card */}
      <Card className="overflow-hidden">
        <CardContent className="p-0">
          {/* Header */}
          <div className="bg-gradient-to-r from-primary/10 to-primary/5 px-6 py-4 border-b">
            <h3 className="font-semibold">Setup Summary</h3>
          </div>

          {/* Details */}
          <div className="divide-y">
            {/* Company */}
            <div className="px-6 py-4 flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                  <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Company</p>
                  <p className="font-medium">{data.companyName || "Not specified"}</p>
                </div>
              </div>
              {data.industry && (
                <span className="text-xs bg-muted px-2 py-1 rounded">{data.industry}</span>
              )}
            </div>

            {/* Plan */}
            <div className="px-6 py-4 flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Selected Plan</p>
                  <p className="font-medium">
                    {data.selectedVariant ? variantNames[data.selectedVariant] : "Not selected"}
                  </p>
                </div>
              </div>
              <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">14-day trial</span>
            </div>

            {/* Integrations */}
            <div className="px-6 py-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
                  <svg className="w-4 h-4 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Integrations</p>
                  <p className="font-medium">
                    {connectedIntegrations.length > 0
                      ? `${connectedIntegrations.length} connected`
                      : "None connected"}
                  </p>
                </div>
              </div>
              {connectedIntegrations.length > 0 && (
                <div className="flex flex-wrap gap-2 ml-11">
                  {connectedIntegrations.map((name) => (
                    <span
                      key={name}
                      className="text-xs bg-muted px-2 py-1 rounded"
                    >
                      {name}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Team */}
            <div className="px-6 py-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 rounded-lg bg-orange-500/10 flex items-center justify-center">
                  <svg className="w-4 h-4 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Team Members</p>
                  <p className="font-medium">
                    {validTeamMembers.length > 0
                      ? `${validTeamMembers.length} invited`
                      : "No invites sent"}
                  </p>
                </div>
              </div>
              {validTeamMembers.length > 0 && (
                <div className="ml-11 space-y-1">
                  {validTeamMembers.map((member, index) => (
                    <div key={index} className="flex items-center gap-2 text-sm">
                      <span className="text-muted-foreground">{member.email}</span>
                      <span className="text-xs bg-muted px-2 py-0.5 rounded">
                        {roleLabels[member.role] || member.role}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <div className="space-y-3">
        <Button
          onClick={onComplete}
          disabled={isSubmitting}
          className="w-full"
          size="lg"
        >
          {isSubmitting ? (
            <>
              <svg
                className="animate-spin -ml-1 mr-2 h-4 w-4"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Setting up your workspace...
            </>
          ) : (
            <>
              Go to Dashboard
              <svg className="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </>
          )}
        </Button>

        <p className="text-center text-sm text-muted-foreground">
          Want a guided tour?{" "}
          <a href="/docs/getting-started" className="text-primary hover:underline">
            Start the tutorial
          </a>
        </p>
      </div>
    </div>
  );
}

export default Step5Complete;
