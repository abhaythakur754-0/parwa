'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import { useAppStore } from '@/lib/store';
import {
  fetchUserProfile, fetchAPIKeys, createAPIKey, revokeAPIKey,
  fetchIntegrations, fetchNotificationPreferences, updateNotificationPreferences,
  fetchCompanySettings, updateCompanySettings,
} from '@/lib/api';
import type { User, APIKey, Integration, NotificationPreference, CompanySettings } from '@/lib/types';
import {
  User as UserIcon, Shield, Key, Plug, Bell, Building2,
  Copy, Eye, EyeOff, Plus, Trash2, Check, X, RefreshCw,
} from 'lucide-react';

// --- Profile ---
function ProfilePanel() {
  const { user } = useAppStore();
  const [name, setName] = useState(user?.name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [phone, setPhone] = useState(user?.phone || '');

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Profile</CardTitle>
        <CardDescription>Update your personal information</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-4">
          <Avatar className="h-16 w-16">
            <AvatarFallback className="bg-emerald-600 text-white text-lg">
              {name.split(' ').map(n => n[0]).join('')}
            </AvatarFallback>
          </Avatar>
          <div>
            <Button variant="outline" size="sm">Change Avatar</Button>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div><Label>Full Name</Label><Input value={name} onChange={e => setName(e.target.value)} className="mt-1" /></div>
          <div><Label>Email</Label><Input value={email} onChange={e => setEmail(e.target.value)} className="mt-1" /></div>
          <div><Label>Phone</Label><Input value={phone} onChange={e => setPhone(e.target.value)} className="mt-1" /></div>
          <div><Label>Role</Label><Input value={user?.role || ''} readOnly className="mt-1 capitalize" /></div>
        </div>
        <Button className="bg-emerald-600 hover:bg-emerald-700 text-white">Save Changes</Button>
      </CardContent>
    </Card>
  );
}

// --- Security ---
function SecurityPanel() {
  const [showMFA, setShowMFA] = useState(false);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Security</CardTitle>
          <CardDescription>Manage your account security</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-3 rounded-lg border border-border">
            <div className="flex items-center gap-3">
              <Shield className="h-8 w-8 text-emerald-600 dark:text-emerald-400" />
              <div>
                <p className="text-sm font-medium">Multi-Factor Authentication</p>
                <p className="text-xs text-muted-foreground">Add an extra layer of security to your account</p>
              </div>
            </div>
            <Switch checked={showMFA} onCheckedChange={setShowMFA} />
          </div>

          <Separator />

          <div>
            <Label>Current Password</Label>
            <Input type="password" placeholder="••••••••" className="mt-1" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><Label>New Password</Label><Input type="password" placeholder="••••••••" className="mt-1" /></div>
            <div><Label>Confirm Password</Label><Input type="password" placeholder="••••••••" className="mt-1" /></div>
          </div>
          <Button variant="outline">Change Password</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Active Sessions</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between p-3 rounded-lg border border-border">
            <div>
              <p className="text-sm font-medium">Current Session</p>
              <p className="text-xs text-muted-foreground">Chrome on macOS • Last active: just now</p>
            </div>
            <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 border-0">Active</Badge>
          </div>
          <div className="flex items-center justify-between p-3 rounded-lg border border-border">
            <div>
              <p className="text-sm font-medium">Mobile App</p>
              <p className="text-xs text-muted-foreground">iPhone • Last active: 2 hours ago</p>
            </div>
            <Button variant="ghost" size="sm" className="text-destructive">Revoke</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// --- API Keys ---
function APIKeysPanel() {
  const [keys, setKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');

  useEffect(() => {
    fetchAPIKeys().then(d => { setKeys(d); setLoading(false); });
  }, []);

  const handleCreate = async () => {
    if (!newKeyName) return;
    const key = await createAPIKey(newKeyName, ['tickets:read', 'tickets:write']);
    setKeys(prev => [...prev, key]);
    setNewKeyName('');
    setShowCreate(false);
  };

  const handleRevoke = async (id: string) => {
    await revokeAPIKey(id);
    setKeys(prev => prev.map(k => k.id === id ? { ...k, status: 'revoked' as const } : k));
  };

  if (loading) return <Skeleton className="h-64 w-full" />;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">API Keys</CardTitle>
          <Button variant="outline" size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="h-3 w-3 mr-1" /> Create Key
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {showCreate && (
          <div className="flex gap-2 p-3 rounded-lg border border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/20">
            <Input value={newKeyName} onChange={e => setNewKeyName(e.target.value)} placeholder="Key name..." />
            <Button size="sm" onClick={handleCreate} className="bg-emerald-600 hover:bg-emerald-700 text-white">Create</Button>
            <Button size="sm" variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
          </div>
        )}
        {keys.map(key => (
          <div key={key.id} className="flex items-center justify-between p-3 rounded-lg border border-border">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Key className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">{key.name}</span>
                <Badge className={`text-[10px] border-0 ${
                  key.status === 'active' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-gray-100 text-gray-500 dark:bg-gray-800'
                }`}>{key.status}</Badge>
              </div>
              <p className="text-xs font-mono text-muted-foreground">{key.key}</p>
              <div className="flex gap-1">
                {key.scope.map(s => (
                  <Badge key={s} variant="secondary" className="text-[9px]">{s}</Badge>
                ))}
              </div>
              <p className="text-[10px] text-muted-foreground">Created {new Date(key.createdAt).toLocaleDateString()}</p>
            </div>
            {key.status === 'active' && (
              <Button variant="ghost" size="sm" className="text-destructive" onClick={() => handleRevoke(key.id)}>
                <Trash2 className="h-3 w-3" />
              </Button>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// --- Integrations ---
function IntegrationsPanel() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchIntegrations().then(d => { setIntegrations(d); setLoading(false); });
  }, []);

  if (loading) return <Skeleton className="h-64 w-full" />;

  const providerIcons: Record<string, string> = {
    paddle: '💳', brevo: '📧', twilio: '📱', shopify: '🛒',
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Integrations</CardTitle>
        <CardDescription>Manage connected services</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {integrations.map(int => (
          <div key={int.id} className="flex items-center justify-between p-4 rounded-lg border border-border">
            <div className="flex items-center gap-3">
              <span className="text-2xl">{providerIcons[int.provider]}</span>
              <div>
                <p className="text-sm font-medium">{int.name}</p>
                <p className="text-xs text-muted-foreground">
                  {int.status === 'connected' && int.lastSync && `Last synced: ${new Date(int.lastSync).toLocaleString()}`}
                  {int.status === 'disconnected' && 'Not connected'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge className={`text-[10px] border-0 ${
                int.status === 'connected' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' :
                int.status === 'error' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                'bg-gray-100 text-gray-600 dark:bg-gray-800'
              }`}>{int.status}</Badge>
              <Button variant="outline" size="sm">
                {int.status === 'connected' ? 'Configure' : 'Connect'}
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// --- Notifications ---
function NotificationsPanel() {
  const [prefs, setPrefs] = useState<NotificationPreference[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchNotificationPreferences().then(d => { setPrefs(d); setLoading(false); });
  }, []);

  const toggle = (index: number, channel: 'email' | 'sms' | 'push' | 'inApp') => {
    setPrefs(prev => {
      const next = [...prev];
      next[index] = { ...next[index], [channel]: !next[index][channel] };
      return next;
    });
  };

  if (loading) return <Skeleton className="h-64 w-full" />;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Notification Preferences</CardTitle>
        <CardDescription>Choose how you want to be notified</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left font-medium text-muted-foreground pb-3">Event</th>
                <th className="text-center font-medium text-muted-foreground pb-3"><Bell className="h-3 w-3 mx-auto" /> Email</th>
                <th className="text-center font-medium text-muted-foreground pb-3">SMS</th>
                <th className="text-center font-medium text-muted-foreground pb-3">Push</th>
                <th className="text-center font-medium text-muted-foreground pb-3">In-App</th>
              </tr>
            </thead>
            <tbody>
              {prefs.map((pref, i) => (
                <tr key={pref.event} className="border-b border-border/30">
                  <td className="py-3 text-sm">{pref.event}</td>
                  <td className="py-3 text-center"><Switch checked={pref.email} onCheckedChange={() => toggle(i, 'email')} className="mx-auto" /></td>
                  <td className="py-3 text-center"><Switch checked={pref.sms} onCheckedChange={() => toggle(i, 'sms')} className="mx-auto" /></td>
                  <td className="py-3 text-center"><Switch checked={pref.push} onCheckedChange={() => toggle(i, 'push')} className="mx-auto" /></td>
                  <td className="py-3 text-center"><Switch checked={pref.inApp} onCheckedChange={() => toggle(i, 'inApp')} className="mx-auto" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Button className="mt-4 bg-emerald-600 hover:bg-emerald-700 text-white">Save Preferences</Button>
      </CardContent>
    </Card>
  );
}

// --- Company Settings ---
function CompanySettingsPanel() {
  const [settings, setSettings] = useState<CompanySettings | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCompanySettings().then(d => { setSettings(d); setLoading(false); });
  }, []);

  if (loading || !settings) return <Skeleton className="h-64 w-full" />;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Brand Voice & Tone</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Brand Voice</Label>
            <textarea
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[80px]"
              value={settings.brandVoice}
              onChange={e => setSettings({ ...settings, brandVoice: e.target.value })}
            />
          </div>
          <div>
            <Label>Tone Guidelines</Label>
            <textarea
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[80px]"
              value={settings.toneGuidelines}
              onChange={e => setSettings({ ...settings, toneGuidelines: e.target.value })}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">PII Detection Patterns</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {settings.piiPatterns.map(pattern => (
              <Badge key={pattern} variant="secondary" className="text-xs">
                {pattern}
                <button className="ml-1 hover:text-destructive"><X className="h-3 w-3" /></button>
              </Badge>
            ))}
            <Button variant="outline" size="sm"><Plus className="h-3 w-3 mr-1" /> Add</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">RAG Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <Label className="text-xs">Chunk Size</Label>
              <Input type="number" value={settings.ragConfig.chunkSize} className="mt-1" onChange={e => setSettings({ ...settings, ragConfig: { ...settings.ragConfig, chunkSize: Number(e.target.value) } })} />
            </div>
            <div>
              <Label className="text-xs">Overlap</Label>
              <Input type="number" value={settings.ragConfig.overlap} className="mt-1" onChange={e => setSettings({ ...settings, ragConfig: { ...settings.ragConfig, overlap: Number(e.target.value) } })} />
            </div>
            <div>
              <Label className="text-xs">Top K</Label>
              <Input type="number" value={settings.ragConfig.topK} className="mt-1" onChange={e => setSettings({ ...settings, ragConfig: { ...settings.ragConfig, topK: Number(e.target.value) } })} />
            </div>
            <div>
              <Label className="text-xs">Similarity Threshold</Label>
              <Input type="number" step="0.05" value={settings.ragConfig.similarityThreshold} className="mt-1" onChange={e => setSettings({ ...settings, ragConfig: { ...settings.ragConfig, similarityThreshold: Number(e.target.value) } })} />
            </div>
          </div>
        </CardContent>
      </Card>

      <Button className="bg-emerald-600 hover:bg-emerald-700 text-white">Save Company Settings</Button>
    </div>
  );
}

export function SettingsPage() {
  const { settingsTab, setSettingsTab } = useAppStore();

  return (
    <Tabs value={settingsTab} onValueChange={setSettingsTab}>
      <TabsList className="flex-wrap">
        <TabsTrigger value="profile"><UserIcon className="h-3 w-3 mr-1" /> Profile</TabsTrigger>
        <TabsTrigger value="security"><Shield className="h-3 w-3 mr-1" /> Security</TabsTrigger>
        <TabsTrigger value="api-keys"><Key className="h-3 w-3 mr-1" /> API Keys</TabsTrigger>
        <TabsTrigger value="integrations"><Plug className="h-3 w-3 mr-1" /> Integrations</TabsTrigger>
        <TabsTrigger value="notifications"><Bell className="h-3 w-3 mr-1" /> Notifications</TabsTrigger>
        <TabsTrigger value="company"><Building2 className="h-3 w-3 mr-1" /> Company</TabsTrigger>
      </TabsList>
      <TabsContent value="profile" className="mt-6"><ProfilePanel /></TabsContent>
      <TabsContent value="security" className="mt-6"><SecurityPanel /></TabsContent>
      <TabsContent value="api-keys" className="mt-6"><APIKeysPanel /></TabsContent>
      <TabsContent value="integrations" className="mt-6"><IntegrationsPanel /></TabsContent>
      <TabsContent value="notifications" className="mt-6"><NotificationsPanel /></TabsContent>
      <TabsContent value="company" className="mt-6"><CompanySettingsPanel /></TabsContent>
    </Tabs>
  );
}
