"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/hooks/use-toast";

interface Webhook {
  id: string;
  url: string;
  secret: string;
  events: string[];
  status: "active" | "inactive";
  lastTrigger: string | null;
  created: string;
}

const AVAILABLE_EVENTS = [
  { id: "ticket.created", label: "Ticket Created" },
  { id: "ticket.updated", label: "Ticket Updated" },
  { id: "ticket.closed", label: "Ticket Closed" },
  { id: "approval.pending", label: "Approval Pending" },
  { id: "approval.approved", label: "Approval Approved" },
  { id: "approval.denied", label: "Approval Denied" },
  { id: "escalation.created", label: "Escalation Created" },
  { id: "agent.status_changed", label: "Agent Status Changed" },
];

const mockWebhooks: Webhook[] = [
  {
    id: "wh_1",
    url: "https://api.example.com/webhooks/parwa",
    secret: "whsec_xxxxx",
    events: ["ticket.created", "approval.pending", "approval.approved"],
    status: "active",
    lastTrigger: "2026-03-22T10:30:00Z",
    created: "2026-03-01T09:00:00Z",
  },
  {
    id: "wh_2",
    url: "https://hooks.slack.com/services/T00/B00/XXX",
    secret: "whsec_yyyyy",
    events: ["escalation.created"],
    status: "active",
    lastTrigger: "2026-03-21T15:45:00Z",
    created: "2026-02-15T14:00:00Z",
  },
];

export default function WebhooksPage() {
  const { toast } = useToast();
  const [webhooks, setWebhooks] = useState<Webhook[]>(mockWebhooks);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newWebhook, setNewWebhook] = useState({
    url: "",
    events: [] as string[],
  });
  const [testingId, setTestingId] = useState<string | null>(null);

  const handleCreateWebhook = () => {
    if (!newWebhook.url || newWebhook.events.length === 0) {
      toast({ title: "Error", description: "URL and at least one event required", variant: "destructive" });
      return;
    }

    const webhook: Webhook = {
      id: `wh_${Date.now()}`,
      url: newWebhook.url,
      secret: `whsec_${Math.random().toString(36).substring(7)}`,
      events: newWebhook.events,
      status: "active",
      lastTrigger: null,
      created: new Date().toISOString(),
    };

    setWebhooks([...webhooks, webhook]);
    setIsDialogOpen(false);
    setNewWebhook({ url: "", events: [] });
    toast({ title: "Success", description: "Webhook created successfully" });
  };

  const handleDeleteWebhook = (id: string) => {
    setWebhooks(webhooks.filter(wh => wh.id !== id));
    toast({ title: "Success", description: "Webhook deleted" });
  };

  const handleTestWebhook = async (id: string) => {
    setTestingId(id);
    // Simulate webhook test
    await new Promise(resolve => setTimeout(resolve, 1500));
    setTestingId(null);
    toast({ title: "Success", description: "Test webhook sent successfully" });
  };

  const handleToggleStatus = (id: string) => {
    setWebhooks(webhooks.map(wh =>
      wh.id === id ? { ...wh, status: wh.status === "active" ? "inactive" : "active" } : wh
    ));
    toast({ title: "Success", description: "Webhook status updated" });
  };

  const toggleEvent = (eventId: string) => {
    setNewWebhook(prev => ({
      ...prev,
      events: prev.events.includes(eventId)
        ? prev.events.filter(e => e !== eventId)
        : [...prev.events, eventId],
    }));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Webhooks</h1>
          <p className="text-muted-foreground">Configure webhooks for real-time event notifications</p>
        </div>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button>Add Webhook</Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Create Webhook</DialogTitle>
              <DialogDescription>Configure a new webhook endpoint</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="url">Endpoint URL</Label>
                <Input
                  id="url"
                  placeholder="https://api.example.com/webhook"
                  value={newWebhook.url}
                  onChange={e => setNewWebhook({ ...newWebhook, url: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Events to Subscribe</Label>
                <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto border rounded p-2">
                  {AVAILABLE_EVENTS.map(event => (
                    <div key={event.id} className="flex items-center space-x-2">
                      <Checkbox
                        id={event.id}
                        checked={newWebhook.events.includes(event.id)}
                        onCheckedChange={() => toggleEvent(event.id)}
                      />
                      <label htmlFor={event.id} className="text-sm">{event.label}</label>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleCreateWebhook}>Create</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Active Webhooks</CardTitle>
          <CardDescription>Manage your webhook endpoints</CardDescription>
        </CardHeader>
        <CardContent>
          {webhooks.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No webhooks configured. Add one to receive real-time notifications.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>URL</TableHead>
                  <TableHead>Events</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Trigger</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {webhooks.map(webhook => (
                  <TableRow key={webhook.id}>
                    <TableCell className="font-mono text-sm max-w-xs truncate">{webhook.url}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {webhook.events.slice(0, 2).map(event => (
                          <Badge key={event} variant="secondary" className="text-xs">{event}</Badge>
                        ))}
                        {webhook.events.length > 2 && (
                          <Badge variant="outline" className="text-xs">+{webhook.events.length - 2}</Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={webhook.status === "active" ? "default" : "secondary"}>
                        {webhook.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {webhook.lastTrigger ? new Date(webhook.lastTrigger).toLocaleString() : "Never"}
                    </TableCell>
                    <TableCell className="text-right space-x-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleTestWebhook(webhook.id)}
                        disabled={testingId === webhook.id}
                      >
                        {testingId === webhook.id ? "Testing..." : "Test"}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleToggleStatus(webhook.id)}
                      >
                        {webhook.status === "active" ? "Disable" : "Enable"}
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDeleteWebhook(webhook.id)}
                      >
                        Delete
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Webhook Secret</CardTitle>
          <CardDescription>Use this secret to verify webhook signatures</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <code className="flex-1 p-2 bg-muted rounded text-sm font-mono">
              {webhooks[0]?.secret || "Create a webhook to see your secret"}
            </code>
            <Button variant="outline" size="sm" onClick={() => {
              navigator.clipboard.writeText(webhooks[0]?.secret || "");
              toast({ title: "Copied", description: "Secret copied to clipboard" });
            }}>
              Copy
            </Button>
          </div>
          <p className="text-sm text-muted-foreground mt-2">
            Include this in the X-Webhook-Secret header when verifying requests.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
