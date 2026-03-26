"use client";

/**
 * PARWA Team Settings Page
 *
 * Manage team members, invites, and roles.
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
 * Team member role.
 */
type TeamRole = "admin" | "agent" | "viewer";

/**
 * Team member status.
 */
type MemberStatus = "active" | "pending" | "inactive";

/**
 * Team member data.
 */
interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: TeamRole;
  status: MemberStatus;
  lastActive: string;
  createdAt: string;
}

/**
 * Pending invite data.
 */
interface PendingInvite {
  id: string;
  email: string;
  role: TeamRole;
  createdAt: string;
  expiresAt: string;
}

/**
 * Team data from API.
 */
interface TeamData {
  members: TeamMember[];
  pendingInvites: PendingInvite[];
  maxMembers: number;
}

/**
 * Role badge colors.
 */
const roleColors: Record<TeamRole, "default" | "secondary" | "outline"> = {
  admin: "default",
  agent: "secondary",
  viewer: "outline",
};

/**
 * Status badge colors.
 */
const statusColors: Record<MemberStatus, "default" | "secondary" | "destructive" | "outline"> = {
  active: "default",
  pending: "secondary",
  inactive: "outline",
};

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
 * Team settings page component.
 */
export default function TeamSettingsPage() {
  const { addToast } = useToasts();

  // State
  const [teamData, setTeamData] = useState<TeamData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [showRemoveModal, setShowRemoveModal] = useState<TeamMember | null>(null);
  const [inviteForm, setInviteForm] = useState({
    email: "",
    role: "agent" as TeamRole,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  /**
   * Fetch team data on mount.
   */
  useEffect(() => {
    const fetchTeamData = async () => {
      setIsLoading(true);

      try {
        const response = await apiClient.get<TeamData>("/team");
        setTeamData(response.data);
      } catch (error) {
        // Set demo data for development
        setTeamData({
          members: [
            {
              id: "1",
              name: "John Admin",
              email: "john@company.com",
              role: "admin",
              status: "active",
              lastActive: new Date().toISOString(),
              createdAt: "2026-01-15",
            },
            {
              id: "2",
              name: "Sarah Agent",
              email: "sarah@company.com",
              role: "agent",
              status: "active",
              lastActive: new Date(Date.now() - 3600000).toISOString(),
              createdAt: "2026-02-01",
            },
            {
              id: "3",
              name: "Mike Viewer",
              email: "mike@company.com",
              role: "viewer",
              status: "active",
              lastActive: new Date(Date.now() - 86400000).toISOString(),
              createdAt: "2026-02-15",
            },
          ],
          pendingInvites: [
            {
              id: "inv-1",
              email: "newmember@company.com",
              role: "agent",
              createdAt: new Date(Date.now() - 86400000).toISOString(),
              expiresAt: new Date(Date.now() + 6 * 86400000).toISOString(),
            },
          ],
          maxMembers: 10,
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchTeamData();
  }, []);

  /**
   * Handle invite member.
   */
  const handleInvite = async () => {
    if (!inviteForm.email.trim()) {
      addToast({
        title: "Error",
        description: "Email is required",
        variant: "error",
      });
      return;
    }

    setIsSubmitting(true);

    try {
      await apiClient.post("/team/invite", inviteForm);

      addToast({
        title: "Success",
        description: `Invitation sent to ${inviteForm.email}`,
        variant: "success",
      });

      // Add to pending invites
      if (teamData) {
        setTeamData({
          ...teamData,
          pendingInvites: [
            ...teamData.pendingInvites,
            {
              id: `inv-${Date.now()}`,
              email: inviteForm.email,
              role: inviteForm.role,
              createdAt: new Date().toISOString(),
              expiresAt: new Date(Date.now() + 7 * 86400000).toISOString(),
            },
          ],
        });
      }

      setInviteForm({ email: "", role: "agent" });
      setShowInviteModal(false);
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to send invitation";
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
   * Handle remove member.
   */
  const handleRemoveMember = async (member: TeamMember) => {
    setIsSubmitting(true);

    try {
      await apiClient.delete(`/team/members/${member.id}`);

      addToast({
        title: "Success",
        description: `${member.name} has been removed from the team`,
        variant: "success",
      });

      // Remove from list
      if (teamData) {
        setTeamData({
          ...teamData,
          members: teamData.members.filter((m) => m.id !== member.id),
        });
      }

      setShowRemoveModal(null);
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to remove member";
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
   * Handle cancel invite.
   */
  const handleCancelInvite = async (inviteId: string) => {
    try {
      await apiClient.delete(`/team/invites/${inviteId}`);

      addToast({
        title: "Success",
        description: "Invitation cancelled",
        variant: "success",
      });

      // Remove from list
      if (teamData) {
        setTeamData({
          ...teamData,
          pendingInvites: teamData.pendingInvites.filter((i) => i.id !== inviteId),
        });
      }
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to cancel invitation";
      addToast({
        title: "Error",
        description: message,
        variant: "error",
      });
    }
  };

  /**
   * Handle role change.
   */
  const handleRoleChange = async (member: TeamMember, newRole: TeamRole) => {
    try {
      await apiClient.patch(`/team/members/${member.id}`, { role: newRole });

      addToast({
        title: "Success",
        description: `${member.name}'s role updated to ${newRole}`,
        variant: "success",
      });

      // Update in list
      if (teamData) {
        setTeamData({
          ...teamData,
          members: teamData.members.map((m) =>
            m.id === member.id ? { ...m, role: newRole } : m
          ),
        });
      }
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to update role";
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
          <h1 className="text-2xl font-bold">Team</h1>
          <p className="text-muted-foreground">
            Manage your team members and their roles
          </p>
        </div>
        <Button onClick={() => setShowInviteModal(true)}>
          <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Invite Member
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
          {/* Team Overview */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">
                  {teamData?.members.length || 0}
                </div>
                <p className="text-sm text-muted-foreground">Active Members</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">
                  {teamData?.pendingInvites.length || 0}
                </div>
                <p className="text-sm text-muted-foreground">Pending Invites</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">
                  {teamData?.maxMembers || 0}
                </div>
                <p className="text-sm text-muted-foreground">Max Team Size</p>
              </CardContent>
            </Card>
          </div>

          {/* Pending Invites */}
          {teamData?.pendingInvites && teamData.pendingInvites.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Pending Invites</CardTitle>
                <CardDescription>
                  Invitations waiting for acceptance
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {teamData.pendingInvites.map((invite) => (
                    <div
                      key={invite.id}
                      className="flex items-center justify-between p-3 border rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-full bg-yellow-100 dark:bg-yellow-900/30 flex items-center justify-center text-yellow-600">
                          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        </div>
                        <div>
                          <p className="font-medium">{invite.email}</p>
                          <p className="text-sm text-muted-foreground">
                            Role: {invite.role} • Sent {formatRelativeTime(invite.createdAt)}
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => handleCancelInvite(invite.id)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Team Members */}
          <Card>
            <CardHeader>
              <CardTitle>Team Members</CardTitle>
              <CardDescription>
                Manage your team&apos;s access and permissions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Member</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Last Active</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {teamData?.members.map((member) => (
                    <TableRow key={member.id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-10 rounded-full bg-primary flex items-center justify-center text-primary-foreground font-medium">
                            {member.name.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p className="font-medium">{member.name}</p>
                            <p className="text-sm text-muted-foreground">{member.email}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <select
                          value={member.role}
                          onChange={(e) => handleRoleChange(member, e.target.value as TeamRole)}
                          className="px-2 py-1 border rounded bg-background text-sm"
                        >
                          <option value="admin">Admin</option>
                          <option value="agent">Agent</option>
                          <option value="viewer">Viewer</option>
                        </select>
                      </TableCell>
                      <TableCell>
                        <Badge variant={statusColors[member.status]}>
                          {member.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatRelativeTime(member.lastActive)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => setShowRemoveModal(member)}
                        >
                          Remove
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Role Descriptions */}
          <Card>
            <CardHeader>
              <CardTitle>Role Permissions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex gap-4">
                  <Badge variant="default">Admin</Badge>
                  <p className="text-sm text-muted-foreground">
                    Full access to all features including billing, team management, and settings
                  </p>
                </div>
                <div className="flex gap-4">
                  <Badge variant="secondary">Agent</Badge>
                  <p className="text-sm text-muted-foreground">
                    Can handle tickets, approve requests, and access integrations
                  </p>
                </div>
                <div className="flex gap-4">
                  <Badge variant="outline">Viewer</Badge>
                  <p className="text-sm text-muted-foreground">
                    Read-only access to dashboard, tickets, and analytics
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Invite Modal */}
      <Dialog open={showInviteModal} onOpenChange={setShowInviteModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite Team Member</DialogTitle>
            <DialogDescription>
              Send an invitation to add a new member to your team
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <label htmlFor="invite-email" className="text-sm font-medium mb-1.5 block">
                Email Address
              </label>
              <input
                id="invite-email"
                type="email"
                value={inviteForm.email}
                onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
                placeholder="colleague@company.com"
                className="w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label htmlFor="invite-role" className="text-sm font-medium mb-1.5 block">
                Role
              </label>
              <select
                id="invite-role"
                value={inviteForm.role}
                onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value as TeamRole })}
                className="w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="admin">Admin</option>
                <option value="agent">Agent</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowInviteModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleInvite} disabled={isSubmitting}>
              {isSubmitting ? "Sending..." : "Send Invitation"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Remove Member Modal */}
      <Dialog open={!!showRemoveModal} onOpenChange={() => setShowRemoveModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove Team Member</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove {showRemoveModal?.name} from the team?
              They will lose access immediately.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRemoveModal(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => showRemoveModal && handleRemoveMember(showRemoveModal)}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Removing..." : "Remove"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
