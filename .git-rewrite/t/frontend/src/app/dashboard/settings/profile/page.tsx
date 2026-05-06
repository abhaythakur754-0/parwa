"use client";

/**
 * PARWA Profile Settings Page
 *
 * Allows users to update their profile information including
 * name, email, phone, timezone, and language preferences.
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
import { cn } from "@/utils/utils";

/**
 * Profile form data.
 */
interface ProfileFormData {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  timezone: string;
  language: string;
  bio: string;
}

/**
 * Timezone options.
 */
const timezoneOptions = [
  { value: "UTC", label: "UTC (Coordinated Universal Time)" },
  { value: "America/New_York", label: "Eastern Time (ET)" },
  { value: "America/Chicago", label: "Central Time (CT)" },
  { value: "America/Denver", label: "Mountain Time (MT)" },
  { value: "America/Los_Angeles", label: "Pacific Time (PT)" },
  { value: "Europe/London", label: "London (GMT)" },
  { value: "Europe/Paris", label: "Paris (CET)" },
  { value: "Asia/Tokyo", label: "Tokyo (JST)" },
  { value: "Asia/Shanghai", label: "Shanghai (CST)" },
  { value: "Asia/Kolkata", label: "Mumbai (IST)" },
];

/**
 * Language options.
 */
const languageOptions = [
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "ja", label: "Japanese" },
  { value: "zh", label: "Chinese" },
  { value: "hi", label: "Hindi" },
];

/**
 * Profile settings page component.
 */
export default function ProfileSettingsPage() {
  const { user, updateProfile } = useAuthStore();
  const { addToast } = useToasts();

  // State
  const [formData, setFormData] = useState<ProfileFormData>({
    firstName: "",
    lastName: "",
    email: "",
    phone: "",
    timezone: "UTC",
    language: "en",
    bio: "",
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<keyof ProfileFormData, string>>>({});

  /**
   * Load profile data on mount.
   */
  useEffect(() => {
    if (user) {
      const nameParts = (user.name || "").split(" ");
      setFormData({
        firstName: nameParts[0] || "",
        lastName: nameParts.slice(1).join(" ") || "",
        email: user.email || "",
        phone: "",
        timezone: "UTC",
        language: "en",
        bio: "",
      });
    }
  }, [user]);

  /**
   * Handle input change.
   */
  const handleChange = (field: keyof ProfileFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setHasChanges(true);
    // Clear error when field is modified
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }));
    }
  };

  /**
   * Validate form data.
   */
  const validateForm = (): boolean => {
    const newErrors: Partial<Record<keyof ProfileFormData, string>> = {};

    if (!formData.firstName.trim()) {
      newErrors.firstName = "First name is required";
    }
    if (!formData.lastName.trim()) {
      newErrors.lastName = "Last name is required";
    }
    if (formData.phone && !/^\+?[\d\s-()]+$/.test(formData.phone)) {
      newErrors.phone = "Invalid phone number format";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /**
   * Handle form submission.
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSaving(true);

    try {
      await updateProfile({
        name: `${formData.firstName} ${formData.lastName}`.trim(),
      });

      // Update other fields via API
      await apiClient.patch("/user/profile", {
        phone: formData.phone,
        timezone: formData.timezone,
        language: formData.language,
        bio: formData.bio,
      });

      addToast({
        title: "Success",
        description: "Profile updated successfully",
        variant: "success",
      });
      setHasChanges(false);
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to update profile";
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
   * Handle avatar upload.
   */
  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith("image/")) {
      addToast({
        title: "Error",
        description: "Please upload an image file",
        variant: "error",
      });
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      addToast({
        title: "Error",
        description: "Image must be less than 5MB",
        variant: "error",
      });
      return;
    }

    // TODO: Implement avatar upload
    addToast({
      title: "Coming Soon",
      description: "Avatar upload will be available soon",
      variant: "warning",
    });
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold">Profile Settings</h1>
        <p className="text-muted-foreground">
          Manage your personal information and preferences
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
          <form onSubmit={handleSubmit}>
            {/* Avatar Section */}
            <Card className="mb-6">
              <CardHeader>
                <CardTitle>Profile Picture</CardTitle>
                <CardDescription>
                  Upload a profile picture to personalize your account
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-6">
                  <div className="relative">
                    <div className="h-24 w-24 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-3xl font-bold">
                      {formData.firstName.charAt(0).toUpperCase() || user?.name?.charAt(0).toUpperCase() || "U"}
                    </div>
                    <label
                      htmlFor="avatar-upload"
                      className="absolute bottom-0 right-0 h-8 w-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center cursor-pointer hover:bg-primary/90 transition-colors"
                    >
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                    </label>
                    <input
                      id="avatar-upload"
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={handleAvatarUpload}
                    />
                  </div>
                  <div>
                    <p className="font-medium">Upload new picture</p>
                    <p className="text-sm text-muted-foreground">
                      JPG, PNG or GIF. Max 5MB.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Personal Information */}
            <Card className="mb-6">
              <CardHeader>
                <CardTitle>Personal Information</CardTitle>
                <CardDescription>
                  Your basic information and contact details
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* First Name */}
                  <div>
                    <label htmlFor="firstName" className="text-sm font-medium mb-1.5 block">
                      First Name <span className="text-destructive">*</span>
                    </label>
                    <input
                      id="firstName"
                      type="text"
                      value={formData.firstName}
                      onChange={(e) => handleChange("firstName", e.target.value)}
                      className={cn(
                        "w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary",
                        errors.firstName && "border-destructive"
                      )}
                    />
                    {errors.firstName && (
                      <p className="text-destructive text-xs mt-1">{errors.firstName}</p>
                    )}
                  </div>

                  {/* Last Name */}
                  <div>
                    <label htmlFor="lastName" className="text-sm font-medium mb-1.5 block">
                      Last Name <span className="text-destructive">*</span>
                    </label>
                    <input
                      id="lastName"
                      type="text"
                      value={formData.lastName}
                      onChange={(e) => handleChange("lastName", e.target.value)}
                      className={cn(
                        "w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary",
                        errors.lastName && "border-destructive"
                      )}
                    />
                    {errors.lastName && (
                      <p className="text-destructive text-xs mt-1">{errors.lastName}</p>
                    )}
                  </div>

                  {/* Email (read-only) */}
                  <div>
                    <label htmlFor="email" className="text-sm font-medium mb-1.5 block">
                      Email Address
                    </label>
                    <div className="flex gap-2">
                      <input
                        id="email"
                        type="email"
                        value={formData.email}
                        readOnly
                        className="w-full px-3 py-2 border rounded-md bg-muted text-sm text-muted-foreground"
                      />
                      <Button variant="outline" type="button">
                        Change
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Email changes require verification
                    </p>
                  </div>

                  {/* Phone */}
                  <div>
                    <label htmlFor="phone" className="text-sm font-medium mb-1.5 block">
                      Phone Number
                    </label>
                    <input
                      id="phone"
                      type="tel"
                      value={formData.phone}
                      onChange={(e) => handleChange("phone", e.target.value)}
                      placeholder="+1 (555) 000-0000"
                      className={cn(
                        "w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary",
                        errors.phone && "border-destructive"
                      )}
                    />
                    {errors.phone && (
                      <p className="text-destructive text-xs mt-1">{errors.phone}</p>
                    )}
                  </div>
                </div>

                {/* Bio */}
                <div>
                  <label htmlFor="bio" className="text-sm font-medium mb-1.5 block">
                    Bio
                  </label>
                  <textarea
                    id="bio"
                    value={formData.bio}
                    onChange={(e) => handleChange("bio", e.target.value)}
                    rows={3}
                    placeholder="Tell us a bit about yourself..."
                    className="w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    {formData.bio.length}/500 characters
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Preferences */}
            <Card className="mb-6">
              <CardHeader>
                <CardTitle>Preferences</CardTitle>
                <CardDescription>
                  Your timezone and language settings
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Timezone */}
                  <div>
                    <label htmlFor="timezone" className="text-sm font-medium mb-1.5 block">
                      Timezone
                    </label>
                    <select
                      id="timezone"
                      value={formData.timezone}
                      onChange={(e) => handleChange("timezone", e.target.value)}
                      className="w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      {timezoneOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Language */}
                  <div>
                    <label htmlFor="language" className="text-sm font-medium mb-1.5 block">
                      Language
                    </label>
                    <select
                      id="language"
                      value={formData.language}
                      onChange={(e) => handleChange("language", e.target.value)}
                      className="w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      {languageOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-3">
              {hasChanges && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    if (user) {
                      const nameParts = (user.name || "").split(" ");
                      setFormData({
                        firstName: nameParts[0] || "",
                        lastName: nameParts.slice(1).join(" ") || "",
                        email: user.email || "",
                        phone: "",
                        timezone: "UTC",
                        language: "en",
                        bio: "",
                      });
                    }
                    setHasChanges(false);
                  }}
                >
                  Cancel
                </Button>
              )}
              <Button type="submit" disabled={isSaving || !hasChanges}>
                {isSaving ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
