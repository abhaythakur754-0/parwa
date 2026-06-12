"use client";

import { useState, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { IntegrationHealthDashboard } from "@/components/integrations/IntegrationHealthDashboard";
import { VariantMixer } from "@/components/variants/VariantMixer";
import { AiToolSelector } from "@/components/ai/AiToolSelector";
import {
  Plug,
  Key,
  Bell,
  Shield,
  Clock,
  FileText,
  Loader2,
  Trash2,
  RotateCcw,
  Upload,
  Plus,
  Building2,
  AlertTriangle,
} from "lucide-react";
import { PRICES, VARIANT_LIMITS } from "@/lib/config";
import { INTEGRATION_CATALOG, CATEGORY_LABELS, type Integration } from "@/lib/integration-catalog";

// ==========================================
// API Keys Tab
// ==========================================
function ApiKeysTab() {
  const [keys, setKeys] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadKeys();
  }, []);

  const loadKeys = async () => {
    try {
      const res = await fetch("/api/api-keys/list");
      if (res.ok) {
        const data = await res.json();
        setKeys(data.api_keys || []);
      }
    } catch {
      // Error handled silently
    } finally {
      setLoading(false);
    }
  };

  const handleRevoke = async (integrationId: string) => {
    try {
      await fetch("/api/api-keys/revoke", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ integration_id: integrationId }),
      });
      loadKeys();
    } catch {
      // Error handled silently
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-emerald-500" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Manage encrypted API keys for your integrations. Keys are never shown in full.
        </p>
      </div>
      {keys.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Key className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No API keys stored yet</p>
            <p className="text-xs text-muted-foreground">Connect an integration to store keys.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {(keys as Array<{ integration_id: string; integration_name: string; masked_key: string; auth_type: string; status: string; last_tested_at: string | null; rotated_at: string | null }>).map((key) => (
            <Card key={key.integration_id}>
              <CardContent className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
                    <Key className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{key.integration_name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <code className="text-xs text-muted-foreground">{key.masked_key}</code>
                      <Badge variant="outline" className="text-[10px]">{key.auth_type}</Badge>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={key.status === "active" ? "default" : "destructive"} className="text-xs">
                    {key.status}
                  </Badge>
                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0" title="Rotate">
                    <RotateCcw className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-destructive"
                    title="Revoke"
                    onClick={() => handleRevoke(key.integration_id)}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ==========================================
// Knowledge Tab
// ==========================================
function KnowledgeTab() {
  const [faqs, setFaqs] = useState<Array<{ id: string; question: string; answer: string; category?: string }>>([]);
  const [newFaq, setNewFaq] = useState({ question: "", answer: "", category: "" });
  const [showFaqForm, setShowFaqForm] = useState(false);

  const addFaq = () => {
    if (!newFaq.question || !newFaq.answer) return;
    setFaqs((prev) => [...prev, { id: Math.random().toString(36).substr(2, 9), ...newFaq }]);
    setNewFaq({ question: "", answer: "", category: "" });
    setShowFaqForm(false);
  };

  return (
    <div className="space-y-6">
      {/* Documents */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Documents</CardTitle>
        </CardHeader>
        <CardContent>
          <label className="flex flex-col items-center justify-center border-2 border-dashed border-border rounded-lg p-6 cursor-pointer hover:border-emerald-300 transition-colors">
            <Upload className="h-6 w-6 text-muted-foreground mb-2" />
            <p className="text-sm font-medium">Upload documents</p>
            <p className="text-xs text-muted-foreground mt-1">PDF, DOCX, TXT, CSV, HTML, JSON, MD</p>
            <input type="file" className="hidden" multiple accept=".pdf,.docx,.txt,.csv,.html,.json,.md" />
          </label>
        </CardContent>
      </Card>

      {/* FAQs */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">FAQ Entries</CardTitle>
          <Button variant="outline" size="sm" className="text-xs" onClick={() => setShowFaqForm(true)}>
            <Plus className="h-3 w-3 mr-1" /> Add FAQ
          </Button>
        </CardHeader>
        <CardContent>
          {showFaqForm && (
            <div className="space-y-3 p-4 bg-muted/50 rounded-lg mb-4">
              <Input placeholder="Question" value={newFaq.question} onChange={(e) => setNewFaq((p) => ({ ...p, question: e.target.value }))} />
              <Textarea placeholder="Answer" value={newFaq.answer} onChange={(e) => setNewFaq((p) => ({ ...p, answer: e.target.value }))} rows={2} />
              <Input placeholder="Category (optional)" value={newFaq.category} onChange={(e) => setNewFaq((p) => ({ ...p, category: e.target.value }))} />
              <div className="flex gap-2">
                <Button size="sm" onClick={addFaq} className="text-xs bg-emerald-600 text-white">Save</Button>
                <Button size="sm" variant="outline" onClick={() => setShowFaqForm(false)} className="text-xs">Cancel</Button>
              </div>
            </div>
          )}
          {faqs.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">No FAQs added yet</p>
          ) : (
            <div className="space-y-2">
              {faqs.map((faq) => (
                <div key={faq.id} className="p-3 bg-muted/50 rounded-lg">
                  <p className="text-sm font-medium">{faq.question}</p>
                  <p className="text-xs text-muted-foreground mt-1">{faq.answer}</p>
                  {faq.category && <Badge variant="secondary" className="text-[10px] mt-1">{faq.category}</Badge>}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ==========================================
// Notifications Tab
// ==========================================
function NotificationsTab() {
  const [notifications, setNotifications] = useState({
    integration_health: true,
    billing: true,
    webhook: false,
    ai_action: true,
    compliance: true,
    system: true,
  });

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">Configure which notifications you want to receive.</p>
      {Object.entries(notifications).map(([key, value]) => (
        <div key={key} className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
          <div>
            <Label className="text-sm font-medium capitalize">{key.replace(/_/g, " ")}</Label>
            <p className="text-xs text-muted-foreground">Get notified about {key.replace(/_/g, " ")} events</p>
          </div>
          <Switch
            checked={value}
            onCheckedChange={(checked) => setNotifications((prev) => ({ ...prev, [key]: checked }))}
          />
        </div>
      ))}
    </div>
  );
}

// ==========================================
// Compliance Tab
// ==========================================
function ComplianceTab() {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Shield className="h-4 w-4" />
            PII Scan Results
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <Shield className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No PII issues detected</p>
            <p className="text-xs text-muted-foreground">Your knowledge base is clean.</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Data Processing Agreement
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Badge variant="default" className="text-xs">Accepted</Badge>
          <p className="text-xs text-muted-foreground mt-2">DPA accepted during onboarding.</p>
        </CardContent>
      </Card>
    </div>
  );
}

// ==========================================
// SLA Tab
// ==========================================
function SLATab() {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Clock className="h-4 w-4" />
            SLA Tracker
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
              <span className="text-sm">First Response Time</span>
              <Badge variant="default" className="text-xs">Under 2 min</Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
              <span className="text-sm">Resolution Time</span>
              <Badge variant="default" className="text-xs">Under 1 hour</Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
              <span className="text-sm">Uptime SLA</span>
              <Badge variant="default" className="text-xs">99.9%</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ==========================================
// Audit Log Tab
// ==========================================
function AuditLogTab() {
  const [entries, setEntries] = useState<Array<{ id: string; action: string; actor: string | null; severity: string; details: unknown; created_at: string | null }>>([]);
  const [stats, setStats] = useState<{ total: number; last_24h: number; severity_breakdown: Record<string, number> } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [entriesRes, statsRes] = await Promise.all([
        fetch("/api/audit/entries?limit=20"),
        fetch("/api/audit/stats"),
      ]);
      if (entriesRes.ok) {
        const data = await entriesRes.json();
        setEntries(data.entries || []);
      }
      if (statsRes.ok) {
        const data = await statsRes.json();
        setStats(data);
      }
    } catch {
      // Error handled silently
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format: string) => {
    try {
      const res = await fetch(`/api/audit/export?format=${format}`);
      if (res.ok) {
        const data = await res.json();
        const blob = new Blob([format === "csv" ? data.data : JSON.stringify(data.data, null, 2)], {
          type: format === "csv" ? "text/csv" : "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit-log.${format}`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch {
      // Error handled silently
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-emerald-500" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Card>
            <CardContent className="p-3 text-center">
              <p className="text-2xl font-bold">{stats.total}</p>
              <p className="text-xs text-muted-foreground">Total Entries</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-3 text-center">
              <p className="text-2xl font-bold">{stats.last_24h}</p>
              <p className="text-xs text-muted-foreground">Last 24h</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-3 text-center">
              <p className="text-2xl font-bold text-amber-600">{stats.severity_breakdown?.warning || 0}</p>
              <p className="text-xs text-muted-foreground">Warnings</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-3 text-center">
              <p className="text-2xl font-bold text-destructive">{stats.severity_breakdown?.critical || 0}</p>
              <p className="text-xs text-muted-foreground">Critical</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Export */}
      <div className="flex gap-2">
        <Button variant="outline" size="sm" className="text-xs" onClick={() => handleExport("json")}>
          Export JSON
        </Button>
        <Button variant="outline" size="sm" className="text-xs" onClick={() => handleExport("csv")}>
          Export CSV
        </Button>
      </div>

      {/* Entries */}
      {entries.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <FileText className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No audit entries yet</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {entries.map((entry) => (
            <div key={entry.id} className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
              <div>
                <p className="text-sm font-medium">{entry.action}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-muted-foreground">{entry.actor || "System"}</span>
                  <span className="text-xs text-muted-foreground">
                    {entry.created_at ? new Date(entry.created_at).toLocaleString() : ""}
                  </span>
                </div>
              </div>
              <Badge
                variant={
                  entry.severity === "critical"
                    ? "destructive"
                    : entry.severity === "warning"
                    ? "secondary"
                    : "outline"
                }
                className="text-xs"
              >
                {entry.severity}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ==========================================
// Integrations Tab
// ==========================================
function IntegrationsTab() {
  const [catalog, setCatalog] = useState<Integration[]>([]);
  const [connected, setConnected] = useState<Array<{ integration_id: string; integration_name: string; status: string; last_4_chars: string | null }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [catalogRes, listRes] = await Promise.all([
        fetch("/api/integrations/catalog"),
        fetch("/api/integrations/list"),
      ]);
      if (catalogRes.ok) {
        const data = await catalogRes.json();
        setCatalog(data.integrations || []);
      }
      if (listRes.ok) {
        const data = await listRes.json();
        setConnected(data.integrations || []);
      }
    } catch {
      // Error handled silently
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async (integration: Integration) => {
    // In a real app, this would open the UniversalApiKeyForm
    const apiKey = prompt(`Enter your ${integration.auth_schema.fields[0]?.label || "API Key"}:`);
    if (!apiKey) return;

    const credentials: Record<string, string> = {};
    integration.auth_schema.fields.forEach((f, i) => {
      credentials[f.name] = i === 0 ? apiKey : "";
    });

    try {
      const res = await fetch("/api/integrations/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          integration_id: integration.id,
          auth_type: integration.auth_type,
          credentials,
        }),
      });
      if (res.ok) {
        loadData();
      }
    } catch {
      // Error handled silently
    }
  };

  const handleDisconnect = async (integrationId: string) => {
    if (!confirm("Are you sure you want to disconnect this integration?")) return;
    try {
      await fetch("/api/integrations/disconnect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ integration_id: integrationId }),
      });
      loadData();
    } catch {
      // Error handled silently
    }
  };

  const isConnected = (id: string) => connected.some((c) => c.integration_id === id && c.status === "active");

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-emerald-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Health Dashboard */}
      <IntegrationHealthDashboard />

      {/* Integration Grid */}
      <div>
        <h3 className="font-medium text-sm mb-3">Available Integrations</h3>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 max-h-96 overflow-y-auto">
          {catalog.map((integration) => {
            const conn = isConnected(integration.id);
            return (
              <Card key={integration.id} className={conn ? "border-emerald-200 dark:border-emerald-800" : ""}>
                <CardContent className="p-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Plug className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium">{integration.name}</span>
                    </div>
                    <Badge variant="outline" className="text-[10px]">{CATEGORY_LABELS[integration.category]}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mb-2">{integration.description}</p>
                  {conn ? (
                    <Button variant="ghost" size="sm" className="w-full text-xs text-destructive" onClick={() => handleDisconnect(integration.id)}>
                      Disconnect
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" className="w-full text-xs" onClick={() => handleConnect(integration)}>
                      Connect
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ==========================================
// Plan & Industry Tab
// ==========================================
function PlanIndustryTab() {
  const [industry, setIndustry] = useState<string>("");
  const [showWarning, setShowWarning] = useState(false);

  return (
    <div className="space-y-6">
      {/* Industry */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            Industry
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {showWarning && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                Changing your industry will affect which integrations are recommended. This cannot be undone.
              </AlertDescription>
            </Alert>
          )}
          <div className="flex gap-2">
            {["saas", "ecommerce", "logistics", "other"].map((ind) => (
              <Badge
                key={ind}
                variant={industry === ind ? "default" : "secondary"}
                className="cursor-pointer capitalize"
                onClick={() => {
                  setIndustry(ind);
                  setShowWarning(true);
                }}
              >
                {ind}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Variant Mixer */}
      <VariantMixer />
    </div>
  );
}

// ==========================================
// Main Settings Page
// ==========================================
export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Manage your PARWA workspace settings.</p>
      </div>

      <Tabs defaultValue="plan" className="space-y-4">
        <TabsList className="flex flex-wrap h-auto gap-1">
          <TabsTrigger value="plan" className="text-xs">Plan & Industry</TabsTrigger>
          <TabsTrigger value="integrations" className="text-xs">Integrations</TabsTrigger>
          <TabsTrigger value="knowledge" className="text-xs">Knowledge</TabsTrigger>
          <TabsTrigger value="apikeys" className="text-xs">API Keys</TabsTrigger>
          <TabsTrigger value="notifications" className="text-xs">Notifications</TabsTrigger>
          <TabsTrigger value="compliance" className="text-xs">Compliance</TabsTrigger>
          <TabsTrigger value="sla" className="text-xs">SLA</TabsTrigger>
          <TabsTrigger value="audit" className="text-xs">Audit Log</TabsTrigger>
        </TabsList>

        <TabsContent value="plan"><PlanIndustryTab /></TabsContent>
        <TabsContent value="integrations"><IntegrationsTab /></TabsContent>
        <TabsContent value="knowledge"><KnowledgeTab /></TabsContent>
        <TabsContent value="apikeys"><ApiKeysTab /></TabsContent>
        <TabsContent value="notifications"><NotificationsTab /></TabsContent>
        <TabsContent value="compliance"><ComplianceTab /></TabsContent>
        <TabsContent value="sla"><SLATab /></TabsContent>
        <TabsContent value="audit"><AuditLogTab /></TabsContent>
      </Tabs>
    </div>
  );
}
