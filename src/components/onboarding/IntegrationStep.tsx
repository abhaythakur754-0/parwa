"use client";

import { useState, useEffect } from "react";
import { useOnboardingStore } from "@/store/onboarding-store";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { UniversalApiKeyForm } from "./UniversalApiKeyForm";
import {
  getIntegrationsByIndustry,
  getCategories,
  CATEGORY_LABELS,
  type Integration,
} from "@/lib/integration-catalog";
import {
  Plug,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";

interface ConnectedIntegration {
  integration_id: string;
  integration_name: string;
  status: string;
  last_4_chars: string | null;
  auth_type: string;
}

export function IntegrationStep() {
  const { industry } = useOnboardingStore();
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null);
  const [connectedIntegrations, setConnectedIntegrations] = useState<ConnectedIntegration[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState<string>("all");

  const availableIntegrations = getIntegrationsByIndustry(industry || "other");
  const categories = getCategories();

  useEffect(() => {
    loadConnected();
  }, []);

  const loadConnected = async () => {
    try {
      const res = await fetch("/api/integrations/list");
      if (res.ok) {
        const data = await res.json();
        setConnectedIntegrations(data.integrations || []);
      }
    } catch {
      // Error handled silently
    } finally {
      setLoading(false);
    }
  };

  const isConnected = (integrationId: string) =>
    connectedIntegrations.some((c) => c.integration_id === integrationId && c.status === "active");

  const getConnected = (integrationId: string) =>
    connectedIntegrations.find((c) => c.integration_id === integrationId);

  const filteredIntegrations = activeCategory === "all"
    ? availableIntegrations
    : availableIntegrations.filter((i) => i.category === activeCategory);

  const handleSave = () => {
    setSelectedIntegration(null);
    loadConnected();
  };

  const handleTest = async (integrationId: string) => {
    try {
      await fetch("/api/integrations/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ integration_id: integrationId }),
      });
    } catch {
      // Error handled silently
    }
  };

  const handleDisconnect = async (integrationId: string) => {
    try {
      await fetch("/api/integrations/disconnect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ integration_id: integrationId }),
      });
      loadConnected();
    } catch {
      // Error handled silently
    }
  };

  if (selectedIntegration) {
    const existing = getConnected(selectedIntegration.id);
    return (
      <UniversalApiKeyForm
        integration={selectedIntegration}
        existingCredential={existing ? {
          masked_key: `••••••••${existing.last_4_chars || ""}`,
          last_4_chars: existing.last_4_chars,
          status: existing.status,
          auth_type: existing.auth_type,
        } : undefined}
        onSave={handleSave}
        onTest={() => handleTest(selectedIntegration.id)}
        onCancel={() => setSelectedIntegration(null)}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">Connect Integrations</h2>
        <p className="text-sm text-muted-foreground">
          Connect the tools your team uses. {connectedIntegrations.filter((c) => c.status === "active").length} connected.
        </p>
      </div>

      {/* Category Filter */}
      <div className="flex flex-wrap gap-2">
        <Badge
          variant={activeCategory === "all" ? "default" : "secondary"}
          className="cursor-pointer"
          onClick={() => setActiveCategory("all")}
        >
          All
        </Badge>
        {categories.map((cat) => (
          <Badge
            key={cat}
            variant={activeCategory === cat ? "default" : "secondary"}
            className="cursor-pointer"
            onClick={() => setActiveCategory(cat)}
          >
            {CATEGORY_LABELS[cat] || cat}
          </Badge>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-emerald-500" />
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 max-h-96 overflow-y-auto pr-1">
          {filteredIntegrations.map((integration) => {
            const connected = isConnected(integration.id);
            const conn = getConnected(integration.id);

            return (
              <Card
                key={integration.id}
                className={`transition-all ${
                  connected
                    ? "border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/20"
                    : "hover:shadow-md cursor-pointer"
                }`}
                onClick={() => !connected && setSelectedIntegration(integration)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
                        <Plug className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div>
                        <p className="font-medium text-sm">{integration.name}</p>
                        <p className="text-xs text-muted-foreground">{CATEGORY_LABELS[integration.category]}</p>
                      </div>
                    </div>
                    {connected ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                    ) : (
                      <XCircle className="h-5 w-5 text-muted-foreground/30" />
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mb-3">{integration.description}</p>
                  {connected && conn ? (
                    <div className="flex items-center justify-between">
                      <Badge variant="outline" className="text-xs text-emerald-600 border-emerald-200 dark:border-emerald-800">
                        Connected ••••{conn.last_4_chars || "****"}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-xs text-destructive hover:text-destructive"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDisconnect(integration.id);
                        }}
                      >
                        Disconnect
                      </Button>
                    </div>
                  ) : (
                    <Button size="sm" variant="outline" className="w-full text-xs">
                      Connect
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
