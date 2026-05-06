'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { fetchEmailChannel, fetchSMSChannel, fetchChatWidgetConfig, fetchVoiceChannel } from '@/lib/api';
import type { EmailChannelConfig, SMSChannelConfig, ChatWidgetConfig, VoiceChannelConfig } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import { useAppStore } from '@/lib/store';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Mail, MessageSquare, Phone, MessageCircle,
  ArrowDownToLine, ArrowUpFromLine, Clock, CheckCircle, XCircle,
  Copy,
} from 'lucide-react';

function StatCard({ label, value, icon: Icon, color }: { label: string; value: string | number; icon: React.ElementType; color: string }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border border-border">
      <div className={`h-8 w-8 rounded-lg flex items-center justify-center ${color}`}>
        <Icon className="h-4 w-4 text-white" />
      </div>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-bold">{value}</p>
      </div>
    </div>
  );
}

function EmailChannelPanel() {
  const [config, setConfig] = useState<EmailChannelConfig | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEmailChannel().then(d => { setConfig(d); setLoading(false); });
  }, []);

  if (loading || !config) return <div className="space-y-4"><Skeleton className="h-32 w-full" /><Skeleton className="h-48 w-full" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold flex items-center gap-2"><Mail className="h-4 w-4" /> Email Channel</h3>
          <p className="text-sm text-muted-foreground">Powered by Brevo</p>
        </div>
        <div className="flex items-center gap-2">
          <Switch checked={config.enabled} />
          <Label className="text-sm">{config.enabled ? 'Enabled' : 'Disabled'}</Label>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <StatCard label="Inbound Today" value={config.stats.inboundToday} icon={ArrowDownToLine} color="bg-emerald-600" />
        <StatCard label="Outbound Today" value={config.stats.outboundToday} icon={ArrowUpFromLine} color="bg-amber-500" />
        <StatCard label="Avg Response" value={`${config.stats.avgResponseTime}s`} icon={Clock} color="bg-blue-500" />
        <StatCard label="Success Rate" value={`${config.stats.successRate}%`} icon={CheckCircle} color="bg-emerald-600" />
        <StatCard label="Error Rate" value={`${config.stats.errorRate}%`} icon={XCircle} color="bg-red-500" />
      </div>

      <Card>
        <CardHeader><CardTitle className="text-sm">Configuration</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div><Label className="text-xs">Inbound Address</Label><Input value={config.inboundAddress} readOnly className="mt-1" /></div>
            <div><Label className="text-xs">Brevo API Key</Label><Input value={config.brevoApiKey || ''} readOnly type="password" className="mt-1" /></div>
          </div>
          <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
            <div>
              <p className="text-sm font-medium">OOO Detection</p>
              <p className="text-xs text-muted-foreground">{config.oooDetectedCount} OOO emails detected</p>
            </div>
            <Switch checked={config.oooDetectionEnabled} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function SMSChannelPanel() {
  const [config, setConfig] = useState<SMSChannelConfig | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSMSChannel().then(d => { setConfig(d); setLoading(false); });
  }, []);

  if (loading || !config) return <div className="space-y-4"><Skeleton className="h-32 w-full" /><Skeleton className="h-48 w-full" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold flex items-center gap-2"><MessageSquare className="h-4 w-4" /> SMS Channel</h3>
          <p className="text-sm text-muted-foreground">Powered by Twilio</p>
        </div>
        <div className="flex items-center gap-2">
          <Switch checked={config.enabled} />
          <Label className="text-sm">{config.enabled ? 'Enabled' : 'Disabled'}</Label>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <StatCard label="Inbound Today" value={config.stats.inboundToday} icon={ArrowDownToLine} color="bg-emerald-600" />
        <StatCard label="Outbound Today" value={config.stats.outboundToday} icon={ArrowUpFromLine} color="bg-amber-500" />
        <StatCard label="Avg Response" value={`${config.stats.avgResponseTime}s`} icon={Clock} color="bg-blue-500" />
        <StatCard label="Success Rate" value={`${config.stats.successRate}%`} icon={CheckCircle} color="bg-emerald-600" />
        <StatCard label="Error Rate" value={`${config.stats.errorRate}%`} icon={XCircle} color="bg-red-500" />
      </div>

      <Card>
        <CardHeader><CardTitle className="text-sm">Configuration</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div><Label className="text-xs">Twilio Phone</Label><Input value={config.twilioPhone} readOnly className="mt-1" /></div>
            <div><Label className="text-xs">Account SID</Label><Input value={config.twilioAccountSid || ''} readOnly type="password" className="mt-1" /></div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ChatChannelPanel() {
  const [config, setConfig] = useState<ChatWidgetConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchChatWidgetConfig().then(d => { setConfig(d); setLoading(false); });
  }, []);

  if (loading || !config) return <div className="space-y-4"><Skeleton className="h-32 w-full" /><Skeleton className="h-48 w-full" /></div>;

  const handleCopy = () => {
    navigator.clipboard.writeText(config.embedCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold flex items-center gap-2"><MessageCircle className="h-4 w-4" /> Chat Widget</h3>
          <p className="text-sm text-muted-foreground">Embeddable chat widget for your website</p>
        </div>
        <div className="flex items-center gap-2">
          <Switch checked={config.enabled} />
          <Label className="text-sm">{config.enabled ? 'Enabled' : 'Disabled'}</Label>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <StatCard label="Sessions Today" value={config.stats.inboundToday} icon={ArrowDownToLine} color="bg-emerald-600" />
        <StatCard label="Responses Today" value={config.stats.outboundToday} icon={ArrowUpFromLine} color="bg-amber-500" />
        <StatCard label="Avg Response" value={`${config.stats.avgResponseTime}s`} icon={Clock} color="bg-blue-500" />
        <StatCard label="Success Rate" value={`${config.stats.successRate}%`} icon={CheckCircle} color="bg-emerald-600" />
        <StatCard label="Error Rate" value={`${config.stats.errorRate}%`} icon={XCircle} color="bg-red-500" />
      </div>

      <Card>
        <CardHeader><CardTitle className="text-sm">Widget Configuration</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div><Label className="text-xs">Widget Color</Label><Input value={config.widgetColor} readOnly className="mt-1" /></div>
            <div><Label className="text-xs">Position</Label><Input value={config.position} readOnly className="mt-1" /></div>
          </div>
          <div><Label className="text-xs">Greeting Message</Label><Input value={config.greeting} readOnly className="mt-1" /></div>
          <div>
            <Label className="text-xs">Embed Code</Label>
            <div className="flex gap-2 mt-1">
              <Input value={config.embedCode} readOnly className="font-mono text-xs" />
              <Button variant="outline" size="icon" onClick={handleCopy}>
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            {copied && <p className="text-xs text-emerald-600 mt-1">Copied to clipboard!</p>}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function VoiceChannelPanel() {
  const [config, setConfig] = useState<VoiceChannelConfig | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchVoiceChannel().then(d => { setConfig(d); setLoading(false); });
  }, []);

  if (loading || !config) return <div className="space-y-4"><Skeleton className="h-32 w-full" /><Skeleton className="h-48 w-full" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold flex items-center gap-2"><Phone className="h-4 w-4" /> Voice Channel</h3>
          <p className="text-sm text-muted-foreground">Powered by Twilio Voice</p>
        </div>
        <div className="flex items-center gap-2">
          <Switch checked={config.enabled} />
          <Label className="text-sm">{config.enabled ? 'Enabled' : 'Disabled'}</Label>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <StatCard label="Calls Today" value={config.stats.inboundToday} icon={ArrowDownToLine} color="bg-emerald-600" />
        <StatCard label="Outbound Today" value={config.stats.outboundToday} icon={ArrowUpFromLine} color="bg-amber-500" />
        <StatCard label="Avg Response" value={`${config.stats.avgResponseTime}s`} icon={Clock} color="bg-blue-500" />
        <StatCard label="Success Rate" value={`${config.stats.successRate}%`} icon={CheckCircle} color="bg-emerald-600" />
        <StatCard label="Error Rate" value={`${config.stats.errorRate}%`} icon={XCircle} color="bg-red-500" />
      </div>

      <Card>
        <CardHeader><CardTitle className="text-sm">Configuration</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div><Label className="text-xs">Twilio Phone</Label><Input value={config.twilioPhone} readOnly className="mt-1" /></div>
          <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
            <div>
              <p className="text-sm font-medium">IVR Menu</p>
              <p className="text-xs text-muted-foreground">{config.ivrMenu}</p>
            </div>
            <Switch checked={config.ivrEnabled} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function ChannelsPage() {
  const { channelTab, setChannelTab } = useAppStore();

  return (
    <Tabs value={channelTab} onValueChange={setChannelTab}>
      <TabsList>
        <TabsTrigger value="chat"><MessageCircle className="h-3 w-3 mr-1" /> Chat</TabsTrigger>
        <TabsTrigger value="email"><Mail className="h-3 w-3 mr-1" /> Email</TabsTrigger>
        <TabsTrigger value="sms"><MessageSquare className="h-3 w-3 mr-1" /> SMS</TabsTrigger>
        <TabsTrigger value="voice"><Phone className="h-3 w-3 mr-1" /> Voice</TabsTrigger>
      </TabsList>
      <TabsContent value="chat" className="mt-6"><ChatChannelPanel /></TabsContent>
      <TabsContent value="email" className="mt-6"><EmailChannelPanel /></TabsContent>
      <TabsContent value="sms" className="mt-6"><SMSChannelPanel /></TabsContent>
      <TabsContent value="voice" className="mt-6"><VoiceChannelPanel /></TabsContent>
    </Tabs>
  );
}
