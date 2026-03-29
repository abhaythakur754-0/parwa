'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Copy, Check, AlertCircle, Download } from 'lucide-react';

/**
 * Enterprise SSO Configuration Page
 * 
 * Allows administrators to configure Single Sign-On
 * with identity providers like Okta, Azure AD, and Google.
 */

const identityProviders = [
  { id: 'okta', name: 'Okta', logo: '/idps/okta.svg' },
  { id: 'azure', name: 'Azure AD', logo: '/idps/azure.svg' },
  { id: 'google', name: 'Google Workspace', logo: '/idps/google.svg' },
  { id: 'onelogin', name: 'OneLogin', logo: '/idps/onelogin.svg' },
  { id: 'saml', name: 'Custom SAML', logo: null },
];

export default function SSOConfigurationPage() {
  const [selectedProvider, setSelectedProvider] = useState('okta');
  const [copied, setCopied] = useState<string | null>(null);
  const [configSaved, setConfigSaved] = useState(false);

  const spConfig = {
    entityId: 'https://parwa.ai/sp/tenant-123',
    acsUrl: 'https://api.parwa.ai/sso/acs/tenant-123',
    sloUrl: 'https://api.parwa.ai/sso/slo/tenant-123',
    metadataUrl: 'https://api.parwa.ai/sso/metadata/tenant-123',
  };

  const copyToClipboard = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopied(field);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">SSO Configuration</h1>
        <p className="text-muted-foreground">
          Configure Single Sign-On with your identity provider
        </p>
      </div>

      {/* Status Banner */}
      <div className="rounded-lg border bg-amber-50 p-4 flex items-center space-x-3">
        <AlertCircle className="h-5 w-5 text-amber-600" />
        <div>
          <p className="font-medium text-amber-900">SSO Setup Required</p>
          <p className="text-sm text-amber-700">
            Complete the configuration below to enable SSO for your organization
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Provider Selection */}
        <Card>
          <CardHeader>
            <CardTitle>Identity Provider</CardTitle>
            <CardDescription>
              Select your identity provider to get started
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Select value={selectedProvider} onValueChange={setSelectedProvider}>
              <SelectTrigger>
                <SelectValue placeholder="Select provider" />
              </SelectTrigger>
              <SelectContent>
                {identityProviders.map((provider) => (
                  <SelectItem key={provider.id} value={provider.id}>
                    {provider.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {/* Service Provider Metadata */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Service Provider Metadata</CardTitle>
                <CardDescription>
                  Provide these values to your IdP administrator
                </CardDescription>
              </div>
              <Button variant="outline" size="sm">
                <Download className="h-4 w-4 mr-2" />
                Download XML
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Entity ID (SP Identifier)</Label>
              <div className="flex items-center space-x-2">
                <Input value={spConfig.entityId} readOnly className="font-mono text-sm" />
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => copyToClipboard(spConfig.entityId, 'entityId')}
                >
                  {copied === 'entityId' ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Assertion Consumer Service (ACS) URL</Label>
              <div className="flex items-center space-x-2">
                <Input value={spConfig.acsUrl} readOnly className="font-mono text-sm" />
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => copyToClipboard(spConfig.acsUrl, 'acsUrl')}
                >
                  {copied === 'acsUrl' ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Single Logout (SLO) URL</Label>
              <div className="flex items-center space-x-2">
                <Input value={spConfig.sloUrl} readOnly className="font-mono text-sm" />
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => copyToClipboard(spConfig.sloUrl, 'sloUrl')}
                >
                  {copied === 'sloUrl' ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Configuration Tabs */}
      <Card>
        <CardHeader>
          <CardTitle>Identity Provider Configuration</CardTitle>
          <CardDescription>
            Enter your identity provider settings
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="metadata">
            <TabsList>
              <TabsTrigger value="metadata">Metadata URL</TabsTrigger>
              <TabsTrigger value="manual">Manual Config</TabsTrigger>
            </TabsList>

            <TabsContent value="metadata" className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label htmlFor="metadataUrl">IdP Metadata URL</Label>
                <Input
                  id="metadataUrl"
                  placeholder="https://your-idp.com/metadata"
                  className="font-mono"
                />
                <p className="text-sm text-muted-foreground">
                  Enter the metadata URL from your identity provider
                </p>
              </div>
              <Button>Fetch Metadata</Button>
            </TabsContent>

            <TabsContent value="manual" className="space-y-4 mt-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="idpEntityId">IdP Entity ID</Label>
                  <Input
                    id="idpEntityId"
                    placeholder="https://idp.example.com/saml"
                    className="font-mono"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="ssoUrl">SSO URL</Label>
                  <Input
                    id="ssoUrl"
                    placeholder="https://idp.example.com/sso"
                    className="font-mono"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="certificate">X.509 Certificate</Label>
                <Textarea
                  id="certificate"
                  placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
                  className="font-mono text-sm h-32"
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="nameIdFormat">Name ID Format</Label>
                  <Select defaultValue="email">
                    <SelectTrigger id="nameIdFormat">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="email">Email Address</SelectItem>
                      <SelectItem value="unspecified">Unspecified</SelectItem>
                      <SelectItem value="persistent">Persistent</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="signatureAlgorithm">Signature Algorithm</Label>
                  <Select defaultValue="sha256">
                    <SelectTrigger id="signatureAlgorithm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="sha256">SHA-256</SelectItem>
                      <SelectItem value="sha512">SHA-512</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <Button onClick={() => setConfigSaved(true)}>
                {configSaved ? 'Configuration Saved!' : 'Save Configuration'}
              </Button>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Attribute Mapping */}
      <Card>
        <CardHeader>
          <CardTitle>Attribute Mapping</CardTitle>
          <CardDescription>
            Map identity provider attributes to PARWA user fields
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="emailAttr">Email Attribute</Label>
                <Input id="emailAttr" placeholder="email" defaultValue="email" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="firstNameAttr">First Name Attribute</Label>
                <Input id="firstNameAttr" placeholder="firstName" defaultValue="firstName" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="lastNameAttr">Last Name Attribute</Label>
                <Input id="lastNameAttr" placeholder="lastName" defaultValue="lastName" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="roleAttr">Role Attribute (Optional)</Label>
                <Input id="roleAttr" placeholder="role" />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Test Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Test Configuration</CardTitle>
          <CardDescription>
            Verify your SSO configuration before enabling
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center space-x-4">
            <Button variant="outline">Test SSO Connection</Button>
            <p className="text-sm text-muted-foreground">
              This will attempt to authenticate with your IdP
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
