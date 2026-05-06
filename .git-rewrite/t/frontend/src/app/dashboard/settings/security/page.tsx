"use client";

/**
 * PARWA Security Settings Page
 *
 * Manage password, two-factor authentication, and active sessions.
 */

import { useState, useEffect } from "react";
import { apiClient, APIError } from "@/services/api/client";
import { useAuthStore } from "@/stores/authStore";
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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/utils/utils";

/**
 * Session data.
 */
interface Session {
  id: string;
  device: string;
  browser: string;
  os: string;
  ip: string;
  location: string;
  lastActive: string;
  createdAt: string;
  isCurrent: boolean;
}

/**
 * Security settings data.
 */
interface SecurityData {
  sessions: Session[];
  twoFactorEnabled: boolean;
  lastPasswordChange: string;
  loginHistory: Array<{
    id: string;
    timestamp: string;
    ip: string;
    location: string;
    device: string;
    success: boolean;
  }>;
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

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

/**
 * Security settings page component.
 */
export default function SecuritySettingsPage() {
  const { user } = useAuthStore();
  const { addToast } = useToasts();

  // State
  const [securityData, setSecurityData] = useState<SecurityData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Password change form
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [passwordErrors, setPasswordErrors] = useState<Record<string, string>>({});

  // 2FA setup
  const [show2FAModal, setShow2FAModal] = useState(false);
  const [twoFACode, setTwoFACode] = useState("");
  const [twoFASecret, setTwoFASecret] = useState("");

  // Session revoke
  const [showRevokeModal, setShowRevokeModal] = useState<Session | null>(null);

  /**
   * Fetch security data on mount.
   */
  useEffect(() => {
    const fetchSecurityData = async () => {
      setIsLoading(true);

      try {
        const response = await apiClient.get<SecurityData>("/settings/security");
        setSecurityData(response.data);
      } catch (error) {
        // Set demo data for development
        setSecurityData({
          sessions: [
            {
              id: "sess-1",
              device: "MacBook Pro",
              browser: "Chrome",
              os: "macOS",
              ip: "192.168.1.100",
              location: "San Francisco, CA",
              lastActive: new Date().toISOString(),
              createdAt: new Date(Date.now() - 7 * 86400000).toISOString(),
              isCurrent: true,
            },
            {
              id: "sess-2",
              device: "iPhone 14",
              browser: "Safari",
              os: "iOS",
              ip: "192.168.1.105",
              location: "San Francisco, CA",
              lastActive: new Date(Date.now() - 3600000).toISOString(),
              createdAt: new Date(Date.now() - 3 * 86400000).toISOString(),
              isCurrent: false,
            },
          ],
          twoFactorEnabled: false,
          lastPasswordChange: new Date(Date.now() - 30 * 86400000).toISOString(),
          loginHistory: [
            {
              id: "log-1",
              timestamp: new Date().toISOString(),
              ip: "192.168.1.100",
              location: "San Francisco, CA",
              device: "Chrome on macOS",
              success: true,
            },
            {
              id: "log-2",
              timestamp: new Date(Date.now() - 86400000).toISOString(),
              ip: "192.168.1.105",
              location: "San Francisco, CA",
              device: "Safari on iOS",
              success: true,
            },
            {
              id: "log-3",
              timestamp: new Date(Date.now() - 3 * 86400000).toISOString(),
              ip: "10.0.0.1",
              location: "Unknown",
              device: "Firefox on Windows",
              success: false,
            },
          ],
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchSecurityData();
  }, []);

  /**
   * Validate password form.
   */
  const validatePasswordForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!passwordForm.currentPassword) {
      errors.currentPassword = "Current password is required";
    }
    if (!passwordForm.newPassword) {
      errors.newPassword = "New password is required";
    } else if (passwordForm.newPassword.length < 8) {
      errors.newPassword = "Password must be at least 8 characters";
    } else if (!/[A-Z]/.test(passwordForm.newPassword)) {
      errors.newPassword = "Password must contain at least one uppercase letter";
    } else if (!/[0-9]/.test(passwordForm.newPassword)) {
      errors.newPassword = "Password must contain at least one number";
    }
    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      errors.confirmPassword = "Passwords do not match";
    }

    setPasswordErrors(errors);
    return Object.keys(errors).length === 0;
  };

  /**
   * Handle password change.
   */
  const handlePasswordChange = async () => {
    if (!validatePasswordForm()) return;

    setIsSubmitting(true);

    try {
      await apiClient.post("/auth/change-password", {
        currentPassword: passwordForm.currentPassword,
        newPassword: passwordForm.newPassword,
      });

      addToast({
        title: "Success",
        description: "Password changed successfully",
        variant: "success",
      });

      setPasswordForm({ currentPassword: "", newPassword: "", confirmPassword: "" });
      setShowPasswordModal(false);

      // Update last password change
      if (securityData) {
        setSecurityData({
          ...securityData,
          lastPasswordChange: new Date().toISOString(),
        });
      }
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to change password";
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
   * Handle 2FA setup.
   */
  const handle2FASetup = async () => {
    setIsSubmitting(true);

    try {
      // Generate 2FA secret
      const response = await apiClient.post<{ secret: string; qrCode: string }>("/auth/2fa/setup");
      setTwoFASecret(response.data.secret);
      // Would show QR code in real implementation
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to setup 2FA";
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
   * Handle 2FA verification.
   */
  const handle2FAVerify = async () => {
    if (!twoFACode || twoFACode.length !== 6) {
      addToast({
        title: "Error",
        description: "Please enter a valid 6-digit code",
        variant: "error",
      });
      return;
    }

    setIsSubmitting(true);

    try {
      await apiClient.post("/auth/2fa/verify", { code: twoFACode });

      addToast({
        title: "Success",
        description: "Two-factor authentication enabled",
        variant: "success",
      });

      if (securityData) {
        setSecurityData({ ...securityData, twoFactorEnabled: true });
      }

      setShow2FAModal(false);
      setTwoFACode("");
      setTwoFASecret("");
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Invalid verification code";
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
   * Handle session revoke.
   */
  const handleRevokeSession = async (session: Session) => {
    setIsSubmitting(true);

    try {
      await apiClient.delete(`/auth/sessions/${session.id}`);

      addToast({
        title: "Success",
        description: "Session revoked successfully",
        variant: "success",
      });

      if (securityData) {
        setSecurityData({
          ...securityData,
          sessions: securityData.sessions.filter((s) => s.id !== session.id),
        });
      }

      setShowRevokeModal(null);
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to revoke session";
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
      <div>
        <h1 className="text-2xl font-bold">Security</h1>
        <p className="text-muted-foreground">
          Manage your account security settings
        </p>
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
          {/* Password */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                    </svg>
                  </div>
                  <div>
                    <CardTitle>Password</CardTitle>
                    <CardDescription>
                      Last changed {formatRelativeTime(securityData?.lastPasswordChange || "")}
                    </CardDescription>
                  </div>
                </div>
                <Button variant="outline" onClick={() => setShowPasswordModal(true)}>
                  Change
                </Button>
              </div>
            </CardHeader>
          </Card>

          {/* Two-Factor Authentication */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "h-10 w-10 rounded-lg flex items-center justify-center",
                    securityData?.twoFactorEnabled
                      ? "bg-green-100 dark:bg-green-900/30 text-green-600"
                      : "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600"
                  )}>
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                  </div>
                  <div>
                    <CardTitle>Two-Factor Authentication</CardTitle>
                    <CardDescription>
                      {securityData?.twoFactorEnabled
                        ? "Your account is protected with 2FA"
                        : "Add an extra layer of security to your account"}
                    </CardDescription>
                  </div>
                </div>
                <Button
                  variant={securityData?.twoFactorEnabled ? "outline" : "default"}
                  onClick={() => setShow2FAModal(true)}
                >
                  {securityData?.twoFactorEnabled ? "Manage" : "Enable"}
                </Button>
              </div>
            </CardHeader>
            {securityData?.twoFactorEnabled && (
              <CardContent>
                <div className="flex items-center gap-2">
                  <Badge variant="default" className="bg-green-600">Enabled</Badge>
                  <span className="text-sm text-muted-foreground">
                    Using authenticator app
                  </span>
                </div>
              </CardContent>
            )}
          </Card>

          {/* Active Sessions */}
          <Card>
            <CardHeader>
              <CardTitle>Active Sessions</CardTitle>
              <CardDescription>
                Devices currently logged into your account
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {securityData?.sessions.map((session) => (
                  <div
                    key={session.id}
                    className="flex items-center justify-between p-4 border rounded-lg"
                  >
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-lg bg-muted flex items-center justify-center">
                        <svg className="h-5 w-5 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-medium">{session.device}</p>
                          {session.isCurrent && (
                            <Badge variant="outline">Current</Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {session.browser} on {session.os} • {session.location}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          IP: {session.ip} • Active {formatRelativeTime(session.lastActive)}
                        </p>
                      </div>
                    </div>
                    {!session.isCurrent && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => setShowRevokeModal(session)}
                      >
                        Revoke
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Login History */}
          <Card>
            <CardHeader>
              <CardTitle>Login History</CardTitle>
              <CardDescription>
                Recent login attempts to your account
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {securityData?.loginHistory.map((log) => (
                  <div
                    key={log.id}
                    className="flex items-center justify-between p-3 border rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "h-8 w-8 rounded-full flex items-center justify-center",
                        log.success
                          ? "bg-green-100 dark:bg-green-900/30 text-green-600"
                          : "bg-red-100 dark:bg-red-900/30 text-red-600"
                      )}>
                        {log.success ? (
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        ) : (
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        )}
                      </div>
                      <div>
                        <p className="font-medium text-sm">{log.device}</p>
                        <p className="text-xs text-muted-foreground">
                          {log.location} • {log.ip}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm">{formatRelativeTime(log.timestamp)}</p>
                      <Badge variant={log.success ? "default" : "destructive"} className="text-xs">
                        {log.success ? "Success" : "Failed"}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Password Change Modal */}
      <Dialog open={showPasswordModal} onOpenChange={setShowPasswordModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change Password</DialogTitle>
            <DialogDescription>
              Enter your current password and choose a new one
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <label htmlFor="current-password" className="text-sm font-medium mb-1.5 block">
                Current Password
              </label>
              <input
                id="current-password"
                type="password"
                value={passwordForm.currentPassword}
                onChange={(e) => setPasswordForm({ ...passwordForm, currentPassword: e.target.value })}
                className={cn(
                  "w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary",
                  passwordErrors.currentPassword && "border-destructive"
                )}
              />
              {passwordErrors.currentPassword && (
                <p className="text-destructive text-xs mt-1">{passwordErrors.currentPassword}</p>
              )}
            </div>
            <div>
              <label htmlFor="new-password" className="text-sm font-medium mb-1.5 block">
                New Password
              </label>
              <input
                id="new-password"
                type="password"
                value={passwordForm.newPassword}
                onChange={(e) => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
                className={cn(
                  "w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary",
                  passwordErrors.newPassword && "border-destructive"
                )}
              />
              {passwordErrors.newPassword && (
                <p className="text-destructive text-xs mt-1">{passwordErrors.newPassword}</p>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                Must be at least 8 characters with 1 uppercase and 1 number
              </p>
            </div>
            <div>
              <label htmlFor="confirm-password" className="text-sm font-medium mb-1.5 block">
                Confirm New Password
              </label>
              <input
                id="confirm-password"
                type="password"
                value={passwordForm.confirmPassword}
                onChange={(e) => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                className={cn(
                  "w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary",
                  passwordErrors.confirmPassword && "border-destructive"
                )}
              />
              {passwordErrors.confirmPassword && (
                <p className="text-destructive text-xs mt-1">{passwordErrors.confirmPassword}</p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowPasswordModal(false)}>
              Cancel
            </Button>
            <Button onClick={handlePasswordChange} disabled={isSubmitting}>
              {isSubmitting ? "Changing..." : "Change Password"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 2FA Modal */}
      <Dialog open={show2FAModal} onOpenChange={setShow2FAModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {securityData?.twoFactorEnabled ? "Manage 2FA" : "Enable Two-Factor Authentication"}
            </DialogTitle>
            <DialogDescription>
              {securityData?.twoFactorEnabled
                ? "Manage your two-factor authentication settings"
                : "Use an authenticator app to secure your account"}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {!securityData?.twoFactorEnabled && (
              <>
                <div className="p-4 bg-muted rounded-lg text-center">
                  <p className="text-sm text-muted-foreground mb-2">
                    Scan this QR code with your authenticator app
                  </p>
                  <div className="h-32 w-32 mx-auto bg-white rounded-lg flex items-center justify-center">
                    <span className="text-xs text-muted-foreground">QR Code</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2 font-mono">
                    {twoFASecret || "Secret will appear here"}
                  </p>
                </div>
                <div>
                  <label htmlFor="2fa-code" className="text-sm font-medium mb-1.5 block">
                    Enter 6-digit code
                  </label>
                  <input
                    id="2fa-code"
                    type="text"
                    maxLength={6}
                    value={twoFACode}
                    onChange={(e) => setTwoFACode(e.target.value.replace(/\D/g, ""))}
                    placeholder="000000"
                    className="w-full px-3 py-2 border rounded-md bg-background text-sm text-center tracking-widest focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShow2FAModal(false)}>
              Cancel
            </Button>
            {!securityData?.twoFactorEnabled && (
              <Button onClick={handle2FAVerify} disabled={isSubmitting || twoFACode.length !== 6}>
                {isSubmitting ? "Verifying..." : "Verify & Enable"}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Revoke Session Modal */}
      <Dialog open={!!showRevokeModal} onOpenChange={() => setShowRevokeModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Revoke Session</DialogTitle>
            <DialogDescription>
              Are you sure you want to revoke this session? The device will be logged out
              immediately.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRevokeModal(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => showRevokeModal && handleRevokeSession(showRevokeModal)}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Revoking..." : "Revoke"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
