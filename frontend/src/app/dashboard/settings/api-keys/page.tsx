"use client";

/**
 * PARWA API Keys Settings Page
 *
 * Manage API keys for programmatic access to PARWA.
 */

import { useState, useEffect } from "react";
import { apiClient, APIError } from "@/services/api/client";
import { useToasts } from "@/stores/uiStore";
import SettingsNav from "@/components/settings/SettingsNav";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/utils/utils";

/**
 * API key permission level.
 */
type APIKeyPermission = "read" | "write" | "admin";

/**
 * API key data.
 */
interface APIKey {
  id: string;
  name: string;
  prefix: string; // First 8 characters of the key
  permission: APIKeyPermission;
  createdAt: string;
  lastUsed?: string;
  expiresAt?: string;
}

/**
 * API keys response from API.
 */
interface APIKeysResponse {
  keys: APIKey[];
}

/**
 * Permission badge colors.
 */
const permissionColors: Record<APIKeyPermission, "default" | "secondary" | "destructive" | "outline"> = {
  read: "outline",
  write: "secondary",
  admin: "default",
};

/**
 * Format date.
 */
function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * Format relative time.
 */
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return formatDate(dateString);
}

/**
 * API keys settings page component.
 */
export default function APIKeysSettingsPage() {
  const { addToast } = useToasts();

  // State
  const [keys, setKeys] = useState<APIKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showRevokeModal, setShowRevokeModal] = useState<APIKey | null>(null);
  const [showKeyModal, setShowKeyModal] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // New key form
  const [newKeyForm, setNewKeyForm] = useState({
    name: "",
    permission: "read" as APIKeyPermission,
  });

  /**
   * Fetch API keys on mount.
   */
  useEffect(() => {
    const fetchKeys = async () => {
      setIsLoading(true);

      try {
        const response = await apiClient.get<APIKeysResponse>("/api-keys");
        setKeys(response.data.keys);
      } catch (error) {
        // Set demo data for development
        setKeys([
          {
            id: "key-1",
            name: "Production Integration",
            prefix: "pk_live_x7",
            permission: "admin",
            createdAt: "2026-01-15",
            lastUsed: new Date(Date.now() - 3600000).toISOString(),
          },
          {
            id: "key-2",
            name: "Development Testing",
            prefix: "pk_test_a3",
            permission: "write",
            createdAt: "2026-02-01",
            lastUsed: new Date(Date.now() - 86400000).toISOString(),
          },
          {
            id: "key-3",
            name: "Analytics Dashboard",
            prefix: "pk_read_b2",
            permission: "read",
            createdAt: "2026-02-15",
            lastUsed: new Date(Date.now() - 7 * 86400000).toISOString(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchKeys();
  }, []);

  /**
   * Create new API key.
   */
  const handleCreateKey = async () => {
    if (!newKeyForm.name.trim()) {
      addToast({
        title: "Error",
        description: "Please enter a name for the API key",
        variant: "error",
      });
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await apiClient.post<{ key: APIKey; fullKey: string }>("/api-keys", newKeyForm);

      addToast({
        title: "Success",
        description: "API key created successfully",
        variant: "success",
      });

      // Add to list
      setKeys((prev) => [...prev, response.data.key]);

      // Show the full key
      setShowKeyModal(response.data.fullKey);
      setShowCreateModal(false);
      setNewKeyForm({ name: "", permission: "read" });
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to create API key";
      addToast({
        title: "Error",
        description: message,
        variant: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Revoke API key.
   */
  const handleRevokeKey = async (key: APIKey) => {
    setIsSubmitting(true);

    try {
      await apiClient.delete(`/api-keys/${key.id}`);

      addToast({
        title: "Success",
        description: `API key "${key.name}" revoked successfully`,
        variant: "success",
      });

      // Remove from list
      setKeys((prev) => prev.filter((k) => k.id !== key.id));
      setShowRevokeModal(null);
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to revoke API key";
      addToast({
        title: "Error",
        description: message,
        variant: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Copy to clipboard.
   */
  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      addToast({
        title: "Copied",
        description: "API key copied to clipboard",
        variant: "success",
      });
    } catch (error) {
      addToast({
        title: "Error",
        description: "Failed to copy to clipboard",
        variant: "error",
      });
    }
  };

  /**
   * Loading skeleton.
   */
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-muted animate-pulse rounded" />
        <div className="h-64 bg-muted animate-pulse rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">API Keys</h1>
          <p className="text-muted-foreground">
            Manage API keys for programmatic access
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Create API Key
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar Navigation */}
        <div className="lg:col-span-1">
          <Card className="sticky top-6">
            <CardContent className="pt-6">
              <SettingsNav />
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <div className="lg:col-span-3 space-y-6">
          {/* Warning Card */}
          <Card className="border-yellow-200 dark:border-yellow-900">
            <CardContent className="pt-6">
              <div className="flex gap-3">
                <div className="h-10 w-10 rounded-lg bg-yellow-100 dark:bg-yellow-900/30 flex items-center justify-center text-yellow-600">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-semibold">Security Notice</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    API keys provide full access to your account. Keep them secure and never
                    share them publicly. Keys are only shown once when created.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* API Keys Table */}
          <Card>
            <CardHeader>
              <CardTitle>API Keys</CardTitle>
              <CardDescription>
                {keys.length} active API key{keys.length !== 1 ? "s" : ""}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {keys.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Key</TableHead>
                      <TableHead>Permission</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Last Used</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {keys.map((key) => (
                      <TableRow key={key.id}>
                        <TableCell className="font-medium">{key.name}</TableCell>
                        <TableCell>
                          <code className="px-2 py-1 bg-muted rounded text-xs font-mono">
                            {key.prefix}...
                          </code>
                        </TableCell>
                        <TableCell>
                          <Badge variant={permissionColors[key.permission]}>
                            {key.permission}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatDate(key.createdAt)}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {key.lastUsed ? formatRelativeTime(key.lastUsed) : "Never"}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => setShowRevokeModal(key)}
                          >
                            Revoke
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-12">
                  <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
                    <svg className="h-6 w-6 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                    </svg>
                  </div>
                  <p className="text-muted-foreground">No API keys yet</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    Create your first API key to get started
                  </p>
                  <Button className="mt-4" onClick={() => setShowCreateModal(true)}>
                    Create API Key
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Permission Descriptions */}
          <Card>
            <CardHeader>
              <CardTitle>Permission Levels</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex gap-4">
                  <Badge variant="outline">Read</Badge>
                  <p className="text-sm text-muted-foreground">
                    View tickets, analytics, and settings. Cannot make any changes.
                  </p>
                </div>
                <div className="flex gap-4">
                  <Badge variant="secondary">Write</Badge>
                  <p className="text-sm text-muted-foreground">
                    Create and update tickets, send messages, manage integrations.
                  </p>
                </div>
                <div className="flex gap-4">
                  <Badge variant="default">Admin</Badge>
                  <p className="text-sm text-muted-foreground">
                    Full access including user management, billing, and settings.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Usage Example */}
          <Card>
            <CardHeader>
              <CardTitle>Usage Example</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-muted rounded-lg p-4 font-mono text-sm overflow-x-auto">
                <pre>
{`curl -X GET "https://api.parwa.io/v1/tickets" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json"`}
                </pre>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Create API Key Modal */}
      <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create API Key</DialogTitle>
            <DialogDescription>
              Generate a new API key for programmatic access
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <label htmlFor="key-name" className="text-sm font-medium mb-1.5 block">
                Key Name
              </label>
              <input
                id="key-name"
                type="text"
                value={newKeyForm.name}
                onChange={(e) => setNewKeyForm({ ...newKeyForm, name: e.target.value })}
                placeholder="e.g., Production Integration"
                className="w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <p className="text-xs text-muted-foreground mt-1">
                A descriptive name to help you identify this key
              </p>
            </div>
            <div>
              <label htmlFor="key-permission" className="text-sm font-medium mb-1.5 block">
                Permission Level
              </label>
              <select
                id="key-permission"
                value={newKeyForm.permission}
                onChange={(e) => setNewKeyForm({ ...newKeyForm, permission: e.target.value as APIKeyPermission })}
                className="w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="read">Read - View data only</option>
                <option value="write">Write - Create and update data</option>
                <option value="admin">Admin - Full access</option>
              </select>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateKey} disabled={isSubmitting}>
              {isSubmitting ? "Creating..." : "Create Key"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Show Key Modal */}
      <Dialog open={!!showKeyModal} onOpenChange={() => setShowKeyModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>API Key Created</DialogTitle>
            <DialogDescription>
              Make sure to copy your API key now. You won&apos;t be able to see it again!
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            <div className="bg-muted rounded-lg p-4 flex items-center justify-between">
              <code className="font-mono text-sm">{showKeyModal}</code>
              <Button variant="ghost" size="sm" onClick={() => copyToClipboard(showKeyModal || "")}>
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </Button>
            </div>
          </div>

          <DialogFooter>
            <Button onClick={() => setShowKeyModal(null)}>
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Revoke Key Modal */}
      <Dialog open={!!showRevokeModal} onOpenChange={() => setShowRevokeModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Revoke API Key</DialogTitle>
            <DialogDescription>
              Are you sure you want to revoke &quot;{showRevokeModal?.name}&quot;? This action
              cannot be undone and any applications using this key will stop working.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRevokeModal(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => showRevokeModal && handleRevokeKey(showRevokeModal)}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Revoking..." : "Revoke Key"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
