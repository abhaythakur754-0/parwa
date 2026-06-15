"use client";

import { useState } from "react";
import { useOnboardingStore } from "@/store/onboarding-store";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Bot, MessageSquare, Settings2, Sparkles, CheckCircle2, Loader2 } from "lucide-react";

const personalities = [
  { id: "professional", name: "Professional", description: "Formal and concise responses", icon: MessageSquare },
  { id: "friendly", name: "Friendly", description: "Warm and approachable tone", icon: Bot },
  { id: "technical", name: "Technical", description: "Detailed and precise explanations", icon: Settings2 },
  { id: "casual", name: "Casual", description: "Relaxed and conversational", icon: Sparkles },
];

const responseStyles = [
  { id: "concise", name: "Concise", description: "Short, direct answers" },
  { id: "detailed", name: "Detailed", description: "Comprehensive explanations" },
  { id: "balanced", name: "Balanced", description: "Mix of brevity and detail" },
];

export function AIConfigStep() {
  const { setAiConfigured } = useOnboardingStore();
  const [personality, setPersonality] = useState("professional");
  const [responseStyle, setResponseStyle] = useState("balanced");
  const [customInstructions, setCustomInstructions] = useState("");
  const [saving, setSaving] = useState(false);
  const [complete, setComplete] = useState(false);

  const handleComplete = async () => {
    setSaving(true);
    try {
      await fetch("/api/onboarding/complete-step", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ step: 5 }),
      });
      setAiConfigured(true);
      setComplete(true);
    } catch {
      // Error handled silently
    } finally {
      setSaving(false);
    }
  };

  if (complete) {
    return (
      <Card className="border-emerald-200 dark:border-emerald-800">
        <CardContent className="p-8 text-center">
          <CheckCircle2 className="h-12 w-12 text-emerald-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">AI Configuration Complete</h3>
          <p className="text-sm text-muted-foreground">
            Your AI agent is configured and ready to handle support tickets.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">AI Configuration</h2>
        <p className="text-sm text-muted-foreground">
          Customize how your AI agent responds to customers.
        </p>
      </div>

      {/* Personality */}
      <div>
        <h3 className="font-medium text-sm mb-3">AI Personality</h3>
        <div className="grid grid-cols-2 gap-3">
          {personalities.map((p) => (
            <Card
              key={p.id}
              className={`cursor-pointer transition-all ${
                personality === p.id
                  ? "ring-2 ring-emerald-500 border-emerald-300 dark:border-emerald-700"
                  : "hover:shadow-sm"
              }`}
              onClick={() => setPersonality(p.id)}
            >
              <CardContent className="p-4 flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
                  <p.icon className="h-5 w-5 text-muted-foreground" />
                </div>
                <div>
                  <p className="font-medium text-sm">{p.name}</p>
                  <p className="text-xs text-muted-foreground">{p.description}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Response Style */}
      <div>
        <h3 className="font-medium text-sm mb-3">Response Style</h3>
        <div className="flex gap-3">
          {responseStyles.map((style) => (
            <Badge
              key={style.id}
              variant={responseStyle === style.id ? "default" : "secondary"}
              className="cursor-pointer px-4 py-2 text-sm"
              onClick={() => setResponseStyle(style.id)}
            >
              {style.name}
            </Badge>
          ))}
        </div>
      </div>

      {/* Custom Instructions */}
      <div>
        <h3 className="font-medium text-sm mb-3">Custom Instructions</h3>
        <Textarea
          placeholder="Add any specific instructions for your AI agent. For example: 'Always mention our return policy when customers ask about refunds' or 'Use the customer's first name when available'."
          value={customInstructions}
          onChange={(e) => setCustomInstructions(e.target.value)}
          rows={4}
        />
      </div>

      {/* Complete */}
      <div className="flex justify-end">
        <Button
          onClick={handleComplete}
          disabled={saving}
          className="bg-gradient-to-r from-emerald-500 to-teal-600 text-white"
        >
          {saving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            "Continue"
          )}
        </Button>
      </div>
    </div>
  );
}
