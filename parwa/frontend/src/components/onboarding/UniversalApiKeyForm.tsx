"use client";

import { useState } from "react";
import type { Integration, AuthType } from "@/lib/integration-catalog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Key, Loader2, CheckCircle2, XCircle, RotateCcw, Trash2, Shield, ArrowLeft } from "lucide-react";

interface ExistingCredential {
  masked_key: string;
  last_4_chars: string | null;
  status: string;
  auth_type: string;
}

interface UniversalApiKeyFormProps {
  integration: Integration;
  existingCredential?: ExistingCredential;
  onSave: () => void;
  onTest: () => void;
  onCancel?: () => void;
}

export function UniversalApiKeyForm({
  integration,
  existingCredential,
  onSave,
  onTest,
  onCancel,
}: UniversalApiKeyFormProps) {
  const [formData, setFormData] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    integration.auth_schema.fields.forEach((f) => {
      initial[f.name] = "";
    });
    return initial;
  });
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rotating, setRotating] = useState(false);

  const authType = integration.auth_type;
  const hasExisting = !!existingCredential;
  const isFormValid = integration.auth_schema.fields.every(
    (f) => !f.required || formData[f.name]?.trim()
  );

  const handleFieldChange = (name: string, value: string) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
    setError(null);
    setTestResult(null);
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      // First save the key if it doesn't exist
      if (!hasExisting) {
        await fetch("/api/api-keys/store", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            integration_id: integration.id,
            auth_type: authType,
            credentials: formData,
          }),
        });
      }

      // Then test it
      const res = await fetch("/api/api-keys/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ integration_id: integration.id }),
      });

      const data = await res.json();
      setTestResult({
        success: data.success ?? false,
        message: data.message || (data.success ? "Connection successful!" : "Connection failed"),
      });
    } catch {
      setTestResult({
        success: false,
        message: "Network error. Could not test connection.",
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!isFormValid) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/api-keys/store", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          integration_id: integration.id,
          auth_type: authType,
          credentials: formData,
        }),
      });

      if (res.ok) {
        onSave();
      } else {
        const data = await res.json();
        setError(data.detail || "Failed to save credentials.");
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handleRotate = async () => {
    setRotating(true);
    try {
      const res = await fetch("/api/api-keys/rotate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          integration_id: integration.id,
          new_credentials: formData,
        }),
      });

      if (res.ok) {
        onSave();
      }
    } catch {
      setError("Failed to rotate key.");
    } finally {
      setRotating(false);
    }
  };

  const handleRevoke = async () => {
    try {
      await fetch("/api/api-keys/revoke", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ integration_id: integration.id }),
      });
      onSave();
    } catch {
      setError("Failed to revoke key.");
    }
  };

  const getAuthTypeLabel = (type: AuthType) => {
    const labels: Record<AuthType, string> = {
      bearer: "Bearer Token",
      header: "API Key Header",
      query: "API Key Query Param",
      basic: "Basic Authentication",
      oauth2: "OAuth 2.0",
    };
    return labels[type] || type;
  };

  const getAuthTypeDescription = (type: AuthType) => {
    const descriptions: Record<AuthType, string> = {
      bearer: "Authentication using a Bearer token in the Authorization header",
      header: "Authentication using a custom API key header",
      query: "Authentication using an API key as a query parameter",
      basic: "Authentication using username and password (HTTP Basic)",
      oauth2: "Authentication using OAuth 2.0 client credentials flow",
    };
    return descriptions[type] || "";
  };

  return (
    <div className="space-y-6">
      {/* Back Button */}
      {onCancel && (
        <Button variant="ghost" size="sm" onClick={onCancel} className="text-sm">
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to integrations
        </Button>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">{integration.name}</CardTitle>
              <p className="text-sm text-muted-foreground mt-1">{integration.description}</p>
            </div>
            <Badge variant="outline" className="text-xs">
              <Shield className="h-3 w-3 mr-1" />
              {getAuthTypeLabel(authType)}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            {getAuthTypeDescription(authType)}
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Existing Credential Status */}
          {hasExisting && (
            <div className="p-3 bg-muted/50 rounded-lg">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Key className="h-4 w-4 text-emerald-500" />
                  <span className="text-sm font-medium">Current key: {existingCredential?.masked_key}</span>
                </div>
                <Badge
                  variant={existingCredential?.status === "active" ? "default" : "destructive"}
                  className="text-xs"
                >
                  {existingCredential?.status}
                </Badge>
              </div>
              {existingCredential?.status === "error" && (
                <p className="text-xs text-amber-600 mt-1">
                  Key may need rotation. Connection test failed or returned 401/403.
                </p>
              )}
            </div>
          )}

          {/* Dynamic Form Fields */}
          {!hasExisting && (
            <div className="space-y-3">
              {integration.auth_schema.fields.map((field) => (
                <div key={field.name} className="space-y-1.5">
                  <Label htmlFor={field.name} className="text-sm">
                    {field.label}
                    {field.required && <span className="text-destructive ml-1">*</span>}
                  </Label>
                  <Input
                    id={field.name}
                    type={field.type === "password" ? "password" : field.type === "email" ? "email" : "text"}
                    placeholder={`Enter ${field.label.toLowerCase()}`}
                    value={formData[field.name] || ""}
                    onChange={(e) => handleFieldChange(field.name, e.target.value)}
                    disabled={saving}
                    className="text-sm"
                  />
                </div>
              ))}
            </div>
          )}

          {/* Rotate form fields (shown when rotating) */}
          {hasExisting && (
            <div className="space-y-3">
              <p className="text-sm font-medium">Enter new credentials to rotate:</p>
              {integration.auth_schema.fields.map((field) => (
                <div key={field.name} className="space-y-1.5">
                  <Label htmlFor={`rotate-${field.name}`} className="text-sm">
                    {field.label}
                    {field.required && <span className="text-destructive ml-1">*</span>}
                  </Label>
                  <Input
                    id={`rotate-${field.name}`}
                    type={field.type === "password" ? "password" : field.type === "email" ? "email" : "text"}
                    placeholder={`Enter new ${field.label.toLowerCase()}`}
                    value={formData[field.name] || ""}
                    onChange={(e) => handleFieldChange(field.name, e.target.value)}
                    disabled={saving}
                    className="text-sm"
                  />
                </div>
              ))}
            </div>
          )}

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {testResult && (
            <Alert variant={testResult.success ? "default" : "destructive"}>
              {testResult.success ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <XCircle className="h-4 w-4" />
              )}
              <AlertDescription>{testResult.message}</AlertDescription>
            </Alert>
          )}

          {/* Actions */}
          <div className="flex flex-wrap gap-2">
            {!hasExisting ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleTest}
                  disabled={!isFormValid || testing}
                  className="text-xs"
                >
                  {testing ? (
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                  )}
                  Test Connection
                </Button>
                <Button
                  size="sm"
                  onClick={handleSave}
                  disabled={!isFormValid || saving}
                  className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  {saving ? (
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  ) : (
                    <Key className="h-3 w-3 mr-1" />
                  )}
                  Save
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleTest}
                  disabled={testing}
                  className="text-xs"
                >
                  {testing ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <CheckCircle2 className="h-3 w-3 mr-1" />}
                  Test
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRotate}
                  disabled={!isFormValid || rotating}
                  className="text-xs text-amber-600 border-amber-300 hover:bg-amber-50 dark:border-amber-700"
                >
                  {rotating ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <RotateCcw className="h-3 w-3 mr-1" />}
                  Rotate Key
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRevoke}
                  className="text-xs text-destructive border-destructive/30 hover:bg-destructive/10"
                >
                  <Trash2 className="h-3 w-3 mr-1" />
                  Revoke (Instant Stop)
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
