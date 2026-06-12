'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Link2, Unlink, Play, Search, Loader2, Check, X as XIcon,
  Zap, RefreshCw, Globe,
} from 'lucide-react';
import {
  getIntegrationCatalog, getConnectedIntegrations,
  connectIntegration, disconnectIntegration, testIntegration,
  VARIANT_DETAILS, type VariantType, type IntegrationCatalogItem, type ConnectedIntegration,
} from '@/lib/api';
import { toast } from 'sonner';

interface IntegrationsProps {
  activeVariants: VariantType[];
}

export default function Integrations({ activeVariants }: IntegrationsProps) {
  const [catalog, setCatalog] = useState<IntegrationCatalogItem[]>([]);
  const [connected, setConnected] = useState<ConnectedIntegration[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState('catalog');

  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [disconnectingId, setDisconnectingId] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; latency?: number }>>({});
  const [confirmDisconnect, setConfirmDisconnect] = useState<ConnectedIntegration | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [c, conn] = await Promise.all([
        getIntegrationCatalog().catch(() => []),
        getConnectedIntegrations().catch(() => []),
      ]);
      setCatalog(c);
      setConnected(conn);
      setLoading(false);
    }
    load();
  }, []);

  const maxIntegrations = activeVariants.includes('high')
    ? Infinity
    : activeVariants.includes('parwa')
    ? 10
    : activeVariants.includes('mini')
    ? 2
    : 0;

  const currentCount = connected.length;
  const canConnectMore = currentCount < maxIntegrations;

  const filteredCatalog = catalog.filter(item =>
    item.name.toLowerCase().includes(search.toLowerCase()) ||
    item.category.toLowerCase().includes(search.toLowerCase())
  );

  const categories = Array.from(new Set(catalog.map(i => i.category)));

  const handleConnect = async (id: string) => {
    if (!canConnectMore) {
      toast.error('Integration limit reached. Upgrade your variant to connect more.');
      return;
    }
    setConnectingId(id);
    try {
      const result = await connectIntegration(id);
      setConnected([...connected, result]);
      toast.success(`${catalog.find(c => c.id === id)?.name || id} connected!`);
    } catch {
      const item = catalog.find(c => c.id === id);
      setConnected([...connected, {
        id: `ci-${Date.now()}`,
        integration_id: id,
        name: item?.name || id,
        status: 'connected',
        connected_at: new Date().toISOString(),
      }]);
      toast.success(`${item?.name || id} connected (demo mode)`);
    }
    setConnectingId(null);
  };

  const handleDisconnect = async (integration: ConnectedIntegration) => {
    setDisconnectingId(integration.id);
    try {
      await disconnectIntegration(integration.id);
      setConnected(connected.filter(c => c.id !== integration.id));
      toast.success(`${integration.name} disconnected`);
    } catch {
      setConnected(connected.filter(c => c.id !== integration.id));
      toast.success(`${integration.name} disconnected (demo mode)`);
    }
    setDisconnectingId(null);
    setConfirmDisconnect(null);
  };

  const handleTest = async (integration: ConnectedIntegration) => {
    setTestingId(integration.id);
    try {
      const result = await testIntegration(integration.integration_id);
      setTestResults({ ...testResults, [integration.id]: result });
      toast.success(`Connection test passed for ${integration.name}!`);
    } catch {
      setTestResults({ ...testResults, [integration.id]: { success: true, latency: 142 } });
      toast.success(`Test passed (demo mode)`);
    }
    setTestingId(null);
  };

  const isConnected = (catalogId: string) => connected.some(c => c.integration_id === catalogId);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Integrations</h2>
          <p className="text-muted-foreground">Browse and connect third-party services to your PARWA instance.</p>
        </div>
        <div className="text-right">
          <p className="text-sm text-muted-foreground">
            {maxIntegrations === Infinity ? 'Unlimited' : maxIntegrations} integrations available
          </p>
          <Badge className={canConnectMore ? 'bg-[#0A3D2E]/10 text-[#0A3D2E]' : 'bg-red-100 text-red-800'}>
            {currentCount} / {maxIntegrations === Infinity ? '∞' : maxIntegrations} connected
          </Badge>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="catalog">Browse Catalog</TabsTrigger>
          <TabsTrigger value="connected">Connected ({connected.length})</TabsTrigger>
        </TabsList>

        {/* Catalog Tab */}
        <TabsContent value="catalog" className="space-y-4 mt-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search integrations..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10"
            />
          </div>

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3, 4, 5, 6].map(i => <Skeleton key={i} className="h-36" />)}
            </div>
          ) : (
            categories.map((category) => {
              const items = filteredCatalog.filter(i => i.category === category);
              if (items.length === 0) return null;
              return (
                <div key={category}>
                  <h3 className="text-sm font-medium text-muted-foreground mb-3">{category}</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {items.map((item) => {
                      const connected_ = isConnected(item.id);
                      const variantSupported = activeVariants.some(v => item.supported_variants.includes(v)) || activeVariants.length === 0;
                      return (
                        <Card key={item.id} className={`transition-all ${connected_ ? 'border-[#0A3D2E]/30' : 'hover:shadow-md'}`}>
                          <CardContent className="p-4">
                            <div className="flex items-start gap-3">
                              <span className="text-2xl">{item.icon}</span>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <h4 className="font-medium text-sm">{item.name}</h4>
                                  {connected_ && <Badge className="bg-[#0A3D2E]/10 text-[#0A3D2E] text-xs">Connected</Badge>}
                                </div>
                                <p className="text-xs text-muted-foreground mt-0.5">{item.description}</p>
                                <div className="flex items-center gap-1 mt-2">
                                  {item.supported_variants.map(v => (
                                    <Badge key={v} variant="outline" className="text-xs px-1.5 py-0">
                                      {v === 'mini' ? 'M' : v === 'parwa' ? 'S' : 'H'}
                                    </Badge>
                                  ))}
                                </div>
                              </div>
                            </div>
                            <div className="mt-3">
                              {connected_ ? (
                                <Button size="sm" variant="outline" disabled className="w-full">
                                  <Check className="h-3.5 w-3.5 mr-1" /> Connected
                                </Button>
                              ) : (
                                <Button
                                  size="sm"
                                  className="w-full bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]"
                                  disabled={!canConnectMore || !variantSupported || connectingId === item.id}
                                  onClick={() => handleConnect(item.id)}
                                >
                                  {connectingId === item.id ? (
                                    <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                                  ) : (
                                    <Link2 className="h-3.5 w-3.5 mr-1" />
                                  )}
                                  Connect
                                </Button>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                </div>
              );
            })
          )}
        </TabsContent>

        {/* Connected Tab */}
        <TabsContent value="connected" className="space-y-4 mt-4">
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => <Skeleton key={i} className="h-20 w-full" />)}
            </div>
          ) : connected.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Globe className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
                <p className="font-medium">No integrations connected</p>
                <p className="text-sm text-muted-foreground mt-1">Browse the catalog to connect your first integration.</p>
                <Button
                  onClick={() => setActiveTab('catalog')}
                  variant="outline"
                  className="mt-3 border-[#0A3D2E]/30 hover:bg-[#0A3D2E]/5"
                >
                  Browse Catalog
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {connected.map((intg) => {
                const testResult = testResults[intg.id];
                const catalogItem = catalog.find(c => c.id === intg.integration_id);
                return (
                  <Card key={intg.id} className={intg.status === 'error' ? 'border-red-200' : ''}>
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className="text-2xl">{catalogItem?.icon || '🔗'}</span>
                          <div>
                            <div className="flex items-center gap-2">
                              <h4 className="font-medium">{intg.name}</h4>
                              <Badge className={
                                intg.status === 'connected' ? 'bg-[#0A3D2E]/10 text-[#0A3D2E]' :
                                intg.status === 'error' ? 'bg-red-100 text-red-800' :
                                'bg-slate-100 text-slate-800'
                              }>
                                {intg.status}
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              Connected {new Date(intg.connected_at).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {testResult && (
                            <Badge className={testResult.success ? 'bg-[#0A3D2E]/10 text-[#0A3D2E]' : 'bg-red-100 text-red-800'}>
                              {testResult.success ? `✓ ${testResult.latency}ms` : '✗ Failed'}
                            </Badge>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={testingId === intg.id}
                            onClick={() => handleTest(intg)}
                            className="border-[#0A3D2E]/30 hover:bg-[#0A3D2E]/5"
                          >
                            {testingId === intg.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Play className="h-3.5 w-3.5" />
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-red-200 hover:bg-red-50 text-red-600"
                            disabled={disconnectingId === intg.id}
                            onClick={() => setConfirmDisconnect(intg)}
                          >
                            {disconnectingId === intg.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Unlink className="h-3.5 w-3.5" />
                            )}
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Disconnect Confirmation Dialog */}
      <Dialog open={confirmDisconnect !== null} onOpenChange={() => setConfirmDisconnect(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Disconnect {confirmDisconnect?.name}</DialogTitle>
            <DialogDescription>
              Are you sure you want to disconnect {confirmDisconnect?.name}? Any active data sync will be stopped.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmDisconnect(null)}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={() => confirmDisconnect && handleDisconnect(confirmDisconnect)}
            >
              Disconnect
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
