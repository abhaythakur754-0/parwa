"use client";

/**
 * PARWA Notifications Settings Page
 *
 * Manage notification preferences for email, Slack, and push notifications.
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
import { cn } from "@/utils/utils";

/**
 * Notification type settings.
 */
interface NotificationSettings {
  // Email notifications
  emailTickets: boolean;
  emailApprovals: boolean;
  emailEscalations: boolean;
  emailReports: boolean;
  emailDigest: boolean;

  // Slack notifications
  slackEnabled: boolean;
  slackWebhookUrl: string;
  slackTickets: boolean;
  slackApprovals: boolean;
  slackEscalations: boolean;

  // Push notifications
  pushEnabled: boolean;
  pushTickets: boolean;
  pushApprovals: boolean;
  pushEscalations: boolean;

  // Quiet hours
  quietHoursEnabled: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
  quietHoursTimezone: string;
}

/**
 * Toggle switch component.
 */
function ToggleSwitch({
  checked,
  onChange,
  disabled = false,
  label,
  description,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label: string;
  description?: string;
}) {
  return (
    <div className="flex items-center justify-between py-3">
      <div className="flex-1 min-w-0 mr-4">
        <p className={cn("font-medium", disabled && "text-muted-foreground")}>{label}</p>
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
          checked ? "bg-primary" : "bg-muted",
          disabled && "opacity-50 cursor-not-allowed"
        )}
      >
        <span
          className={cn(
            "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out",
            checked ? "translate-x-5" : "translate-x-0"
          )}
        />
      </button>
    </div>
  );
}

/**
 * Notifications settings page component.
 */
export default function NotificationsSettingsPage() {
  const { addToast } = useToasts();

  // State
  const [settings, setSettings] = useState<NotificationSettings>({
    emailTickets: true,
    emailApprovals: true,
    emailEscalations: true,
    emailReports: true,
    emailDigest: false,
    slackEnabled: false,
    slackWebhookUrl: "",
    slackTickets: true,
    slackApprovals: true,
    slackEscalations: true,
    pushEnabled: true,
    pushTickets: true,
    pushApprovals: true,
    pushEscalations: true,
    quietHoursEnabled: false,
    quietHoursStart: "22:00",
    quietHoursEnd: "08:00",
    quietHoursTimezone: "UTC",
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  /**
   * Fetch settings on mount.
   */
  useEffect(() => {
    const fetchSettings = async () => {
      setIsLoading(true);

      try {
        const response = await apiClient.get<NotificationSettings>("/settings/notifications");
        setSettings(response.data);
      } catch (error) {
        // Use default settings for development
      } finally {
        setIsLoading(false);
      }
    };

    fetchSettings();
  }, []);

  /**
   * Update setting.
   */
  const updateSetting = <K extends keyof NotificationSettings>(
    key: K,
    value: NotificationSettings[K]
  ) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  /**
   * Save settings.
   */
  const handleSave = async () => {
    setIsSaving(true);

    try {
      await apiClient.patch("/settings/notifications", settings);

      addToast({
        title: "Success",
        description: "Notification settings saved",
        variant: "success",
      });
      setHasChanges(false);
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to save settings";
      addToast({
        title: "Error",
        description: message,
        variant: "error",
      });
    } finally {
      setIsSaving(false);
    }
  };

  /**
   * Test Slack webhook.
   */
  const testSlackWebhook = async () => {
    if (!settings.slackWebhookUrl) {
      addToast({
        title: "Error",
        description: "Please enter a Slack webhook URL",
        variant: "error",
      });
      return;
    }

    try {
      await apiClient.post("/settings/notifications/test-slack", {
        webhookUrl: settings.slackWebhookUrl,
      });

      addToast({
        title: "Success",
        description: "Test notification sent to Slack",
        variant: "success",
      });
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to send test notification";
      addToast({
        title: "Error",
        description: message,
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
          <h1 className="text-2xl font-bold">Notifications</h1>
          <p className="text-muted-foreground">
            Manage how you receive notifications
          </p>
        </div>
        <Button onClick={handleSave} disabled={isSaving || !hasChanges}>
          {isSaving ? "Saving..." : "Save Changes"}
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
          {/* Email Notifications */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                </div>
                <div>
                  <CardTitle>Email Notifications</CardTitle>
                  <CardDescription>
                    Receive updates via email
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="divide-y">
              <ToggleSwitch
                checked={settings.emailTickets}
                onChange={(checked) => updateSetting("emailTickets", checked)}
                label="New Tickets"
                description="Get notified when new tickets are created"
              />
              <ToggleSwitch
                checked={settings.emailApprovals}
                onChange={(checked) => updateSetting("emailApprovals", checked)}
                label="Approval Requests"
                description="Get notified about pending approvals"
              />
              <ToggleSwitch
                checked={settings.emailEscalations}
                onChange={(checked) => updateSetting("emailEscalations", checked)}
                label="Escalations"
                description="Get notified when tickets are escalated"
              />
              <ToggleSwitch
                checked={settings.emailReports}
                onChange={(checked) => updateSetting("emailReports", checked)}
                label="Weekly Reports"
                description="Receive weekly performance reports"
              />
              <ToggleSwitch
                checked={settings.emailDigest}
                onChange={(checked) => updateSetting("emailDigest", checked)}
                label="Daily Digest"
                description="Receive a daily summary of activity"
              />
            </CardContent>
          </Card>

          {/* Slack Notifications */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center text-purple-600">
                    <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" />
                    </svg>
                  </div>
                  <div>
                    <CardTitle>Slack Notifications</CardTitle>
                    <CardDescription>
                      Send notifications to Slack channels
                    </CardDescription>
                  </div>
                </div>
                <ToggleSwitch
                  checked={settings.slackEnabled}
                  onChange={(checked) => updateSetting("slackEnabled", checked)}
                  label=""
                />
              </div>
            </CardHeader>
            <CardContent>
              {/* Webhook URL */}
              <div className="mb-4">
                <label htmlFor="slack-webhook" className="text-sm font-medium mb-1.5 block">
                  Slack Webhook URL
                </label>
                <div className="flex gap-2">
                  <input
                    id="slack-webhook"
                    type="url"
                    value={settings.slackWebhookUrl}
                    onChange={(e) => updateSetting("slackWebhookUrl", e.target.value)}
                    placeholder="https://hooks.slack.com/services/..."
                    disabled={!settings.slackEnabled}
                    className="flex-1 px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                  />
                  <Button
                    variant="outline"
                    disabled={!settings.slackEnabled || !settings.slackWebhookUrl}
                    onClick={testSlackWebhook}
                  >
                    Test
                  </Button>
                </div>
              </div>

              {/* Notification types */}
              <div className="divide-y border rounded-lg">
                <ToggleSwitch
                  checked={settings.slackTickets}
                  onChange={(checked) => updateSetting("slackTickets", checked)}
                  disabled={!settings.slackEnabled}
                  label="New Tickets"
                  description="Notify about new tickets"
                />
                <ToggleSwitch
                  checked={settings.slackApprovals}
                  onChange={(checked) => updateSetting("slackApprovals", checked)}
                  disabled={!settings.slackEnabled}
                  label="Approval Requests"
                  description="Notify about pending approvals"
                />
                <ToggleSwitch
                  checked={settings.slackEscalations}
                  onChange={(checked) => updateSetting("slackEscalations", checked)}
                  disabled={!settings.slackEnabled}
                  label="Escalations"
                  description="Notify about ticket escalations"
                />
              </div>
            </CardContent>
          </Card>

          {/* Push Notifications */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center text-green-600">
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                    </svg>
                  </div>
                  <div>
                    <CardTitle>Push Notifications</CardTitle>
                    <CardDescription>
                      Receive notifications on your devices
                    </CardDescription>
                  </div>
                </div>
                <ToggleSwitch
                  checked={settings.pushEnabled}
                  onChange={(checked) => updateSetting("pushEnabled", checked)}
                  label=""
                />
              </div>
            </CardHeader>
            <CardContent className="divide-y border rounded-lg">
              <ToggleSwitch
                checked={settings.pushTickets}
                onChange={(checked) => updateSetting("pushTickets", checked)}
                disabled={!settings.pushEnabled}
                label="New Tickets"
                description="Get push notifications for new tickets"
              />
              <ToggleSwitch
                checked={settings.pushApprovals}
                onChange={(checked) => updateSetting("pushApprovals", checked)}
                disabled={!settings.pushEnabled}
                label="Approval Requests"
                description="Get push notifications for approvals"
              />
              <ToggleSwitch
                checked={settings.pushEscalations}
                onChange={(checked) => updateSetting("pushEscalations", checked)}
                disabled={!settings.pushEnabled}
                label="Escalations"
                description="Get push notifications for escalations"
              />
            </CardContent>
          </Card>

          {/* Quiet Hours */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-yellow-100 dark:bg-yellow-900/30 flex items-center justify-center text-yellow-600">
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                    </svg>
                  </div>
                  <div>
                    <CardTitle>Quiet Hours</CardTitle>
                    <CardDescription>
                      Pause notifications during specific hours
                    </CardDescription>
                  </div>
                </div>
                <ToggleSwitch
                  checked={settings.quietHoursEnabled}
                  onChange={(checked) => updateSetting("quietHoursEnabled", checked)}
                  label=""
                />
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="quiet-start" className="text-sm font-medium mb-1.5 block">
                    Start Time
                  </label>
                  <input
                    id="quiet-start"
                    type="time"
                    value={settings.quietHoursStart}
                    onChange={(e) => updateSetting("quietHoursStart", e.target.value)}
                    disabled={!settings.quietHoursEnabled}
                    className="w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                  />
                </div>
                <div>
                  <label htmlFor="quiet-end" className="text-sm font-medium mb-1.5 block">
                    End Time
                  </label>
                  <input
                    id="quiet-end"
                    type="time"
                    value={settings.quietHoursEnd}
                    onChange={(e) => updateSetting("quietHoursEnd", e.target.value)}
                    disabled={!settings.quietHoursEnabled}
                    className="w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                  />
                </div>
              </div>
              <p className="text-sm text-muted-foreground mt-4">
                During quiet hours, notifications will be queued and delivered when quiet hours end.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
