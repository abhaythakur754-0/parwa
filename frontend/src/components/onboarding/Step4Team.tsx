"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import { Button } from "@/components/ui/button";

interface TeamMember {
  email: string;
  role: string;
}

interface Step4TeamProps {
  teamMembers: TeamMember[];
  updateData: (updates: { teamMembers: TeamMember[] }) => void;
  onValidate?: (isValid: boolean) => void;
}

const roles = [
  { value: "admin", label: "Admin", description: "Full access to all features" },
  { value: "agent", label: "Agent", description: "Handle customer conversations" },
  { value: "viewer", label: "Viewer", description: "Read-only access to reports" },
];

const MAX_TEAM_MEMBERS = 5;

export function Step4Team({ teamMembers, updateData, onValidate }: Step4TeamProps) {
  const [errors, setErrors] = React.useState<Record<number, string>>({});

  React.useEffect(() => {
    // Validate that all added members have valid emails
    const newErrors: Record<number, string> = {};
    teamMembers.forEach((member, index) => {
      if (member.email && !isValidEmail(member.email)) {
        newErrors[index] = "Please enter a valid email address";
      }
    });
    setErrors(newErrors);

    // Step is valid if no errors (team members are optional)
    onValidate?.(Object.keys(newErrors).length === 0);
  }, [teamMembers, onValidate]);

  const isValidEmail = (email: string): boolean => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  const addTeamMember = () => {
    if (teamMembers.length < MAX_TEAM_MEMBERS) {
      updateData({
        teamMembers: [...teamMembers, { email: "", role: "agent" }],
      });
    }
  };

  const removeTeamMember = (index: number) => {
    updateData({
      teamMembers: teamMembers.filter((_, i) => i !== index),
    });
    // Clear error for removed member
    const newErrors = { ...errors };
    delete newErrors[index];
    setErrors(newErrors);
  };

  const updateTeamMember = (index: number, field: keyof TeamMember, value: string) => {
    const newMembers = [...teamMembers];
    newMembers[index] = { ...newMembers[index], [field]: value };
    updateData({ teamMembers: newMembers });
  };

  const canAddMore = teamMembers.length < MAX_TEAM_MEMBERS;
  const remainingSlots = MAX_TEAM_MEMBERS - teamMembers.length;

  return (
    <div className="space-y-6">
      <div className="text-center mb-6">
        <h2 className="text-lg font-semibold">Invite your team</h2>
        <p className="text-sm text-muted-foreground">
          Add team members to collaborate on customer support
        </p>
      </div>

      {/* Team Members List */}
      {teamMembers.length > 0 && (
        <div className="space-y-3">
          {teamMembers.map((member, index) => (
            <div key={index} className="flex flex-col gap-2 p-3 rounded-lg border border-border bg-muted/30">
              <div className="flex gap-2">
                {/* Email Input */}
                <div className="flex-1">
                  <input
                    type="email"
                    placeholder="colleague@example.com"
                    value={member.email}
                    onChange={(e) => updateTeamMember(index, "email", e.target.value)}
                    className={cn(
                      "flex h-10 w-full rounded-md border bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                      errors[index] ? "border-destructive" : "border-input"
                    )}
                  />
                  {errors[index] && (
                    <p className="text-xs text-destructive mt-1">{errors[index]}</p>
                  )}
                </div>

                {/* Role Select */}
                <select
                  value={member.role}
                  onChange={(e) => updateTeamMember(index, "role", e.target.value)}
                  className="h-10 w-32 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  {roles.map((role) => (
                    <option key={role.value} value={role.value}>
                      {role.label}
                    </option>
                  ))}
                </select>

                {/* Remove Button */}
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => removeTeamMember(index)}
                  className="h-10 w-10 shrink-0"
                  aria-label="Remove team member"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </Button>
              </div>

              {/* Role Description */}
              <p className="text-xs text-muted-foreground">
                Role: {roles.find((r) => r.value === member.role)?.description}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Add Member Button */}
      {canAddMore && (
        <Button
          variant="outline"
          onClick={addTeamMember}
          className="w-full border-dashed"
        >
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Team Member ({remainingSlots} slots remaining)
        </Button>
      )}

      {/* Maximum Reached */}
      {!canAddMore && (
        <div className="text-center p-3 rounded-lg bg-muted">
          <p className="text-sm text-muted-foreground">
            You&apos;ve reached the maximum of {MAX_TEAM_MEMBERS} team members for onboarding.
            You can add more from your dashboard after setup.
          </p>
        </div>
      )}

      {/* Role Legend */}
      <div className="bg-muted/50 rounded-lg p-4">
        <h4 className="text-sm font-medium mb-2">Role Permissions</h4>
        <div className="space-y-2">
          {roles.map((role) => (
            <div key={role.value} className="flex items-start gap-2 text-sm">
              <div
                className={cn(
                  "w-2 h-2 rounded-full mt-1.5",
                  role.value === "admin"
                    ? "bg-primary"
                    : role.value === "agent"
                    ? "bg-blue-500"
                    : "bg-gray-400"
                )}
              />
              <div>
                <span className="font-medium">{role.label}:</span>{" "}
                <span className="text-muted-foreground">{role.description}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <p className="text-xs text-center text-muted-foreground">
        Team members will receive an email invitation to join your workspace. You can skip this step and invite members later.
      </p>
    </div>
  );
}

export default Step4Team;
