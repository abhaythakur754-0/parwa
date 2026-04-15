'use client';

import React, { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Eye, EyeOff, KeyRound, Lock, Info } from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────

export type AuthType = 'bearer' | 'basic' | 'api_key' | 'oauth2' | 'none';

interface AuthConfigProps {
  /** Current authentication type to render */
  authType: AuthType;
  /** Current credential values keyed by field name */
  value: Record<string, string>;
  /** Callback when any credential field changes */
  onChange: (value: Record<string, string>) => void;
  /** Disable all fields when true (e.g., during a test) */
  disabled?: boolean;
}

/** Metadata for each auth type describing its form fields */
const AUTH_TYPE_FIELDS: Record<
  AuthType,
  Array<{
    key: string;
    label: string;
    placeholder: string;
    type?: 'password' | 'text';
    defaultValue?: string;
  }>
> = {
  bearer: [
    {
      key: 'token',
      label: 'Bearer Token',
      placeholder: 'eyJhbGciOiJIUzI1NiIsInR5cCI6...',
      type: 'password',
    },
  ],
  basic: [
    {
      key: 'username',
      label: 'Username',
      placeholder: 'api_user',
      type: 'text',
    },
    {
      key: 'password',
      label: 'Password',
      placeholder: 'Enter password',
      type: 'password',
    },
  ],
  api_key: [
    {
      key: 'api_key',
      label: 'API Key',
      placeholder: 'your-api-key-here',
      type: 'password',
    },
    {
      key: 'api_key_header',
      label: 'Header Name',
      placeholder: 'X-API-Key',
      type: 'text',
      defaultValue: 'X-API-Key',
    },
  ],
  oauth2: [
    {
      key: 'client_id',
      label: 'Client ID',
      placeholder: 'my-app-client-id',
      type: 'text',
    },
    {
      key: 'client_secret',
      label: 'Client Secret',
      placeholder: 'my-app-client-secret',
      type: 'password',
    },
    {
      key: 'token_url',
      label: 'Token URL',
      placeholder: 'https://auth.example.com/oauth/token',
      type: 'text',
    },
    {
      key: 'scope',
      label: 'Scope',
      placeholder: 'read write',
      type: 'text',
    },
  ],
  none: [],
};

/** Human-readable descriptions for each auth type */
const AUTH_TYPE_DESCRIPTIONS: Record<AuthType, string> = {
  bearer: 'Authenticate using a Bearer token in the Authorization header.',
  basic: 'Authenticate using HTTP Basic authentication (username + password).',
  api_key: 'Authenticate by sending an API key in a custom header.',
  oauth2: 'Authenticate using OAuth 2.0 client credentials flow.',
  none: 'No authentication is required for this endpoint.',
};

// ── Component ─────────────────────────────────────────────────────────

export function AuthConfig({ authType, value, onChange, disabled }: AuthConfigProps) {
  const fields = AUTH_TYPE_FIELDS[authType];
  const [visibleFields, setVisibleFields] = useState<Record<string, boolean>>({});

  // Toggle password visibility for a specific field
  const toggleVisibility = (fieldKey: string) => {
    setVisibleFields((prev) => ({
      ...prev,
      [fieldKey]: !prev[fieldKey],
    }));
  };

  // Update a single field in the value record
  const updateField = (fieldKey: string, fieldValue: string) => {
    onChange({ ...value, [fieldKey]: fieldValue });
  };

  // For "none" auth type, render a simple info message
  if (authType === 'none') {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <KeyRound className="h-4 w-4 text-muted-foreground" />
          <span>Authentication</span>
        </div>
        <div className="rounded-lg border border-dashed bg-muted/30 p-4">
          <div className="flex items-start gap-3">
            <Info className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
            <div>
              <p className="text-sm font-medium">No Authentication Required</p>
              <p className="text-xs text-muted-foreground mt-1">
                This endpoint does not require authentication. Anyone who can reach
                the URL can interact with the integration.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Auth type header with description */}
      <div className="flex items-center gap-2 text-sm font-medium">
        <Lock className="h-4 w-4 text-muted-foreground" />
        <span>
          Authentication{' '}
          <span className="text-muted-foreground font-normal">
            ({authType.replace('_', ' ')})
          </span>
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        {AUTH_TYPE_DESCRIPTIONS[authType]}
      </p>

      {/* Render form fields — 2-column grid for oauth2, single column otherwise */}
      <div
        className={
          authType === 'oauth2'
            ? 'grid grid-cols-1 sm:grid-cols-2 gap-3'
            : authType === 'basic'
              ? 'grid grid-cols-1 sm:grid-cols-2 gap-3'
              : 'space-y-3'
        }
      >
        {fields.map((field) => {
          const isPassword = field.type === 'password';
          const isVisible = visibleFields[field.key] ?? false;
          const inputType = isPassword ? (isVisible ? 'text' : 'password') : 'text';

          return (
            <div key={field.key} className="relative">
              <Label htmlFor={`auth-${field.key}`} className="text-xs">
                {field.label}
              </Label>
              <div className="relative mt-1">
                <Input
                  id={`auth-${field.key}`}
                  type={inputType}
                  value={value[field.key] || field.defaultValue || ''}
                  onChange={(e) => updateField(field.key, e.target.value)}
                  placeholder={field.placeholder}
                  disabled={disabled}
                  className={isPassword ? 'pr-10' : ''}
                />
                {/* Show/hide toggle for password fields */}
                {isPassword && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-0 top-0 h-full px-2 hover:bg-transparent"
                    onClick={() => toggleVisibility(field.key)}
                    tabIndex={-1}
                    aria-label={isVisible ? `Hide ${field.label}` : `Show ${field.label}`}
                  >
                    {isVisible ? (
                      <EyeOff className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <Eye className="h-4 w-4 text-muted-foreground" />
                    )}
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
