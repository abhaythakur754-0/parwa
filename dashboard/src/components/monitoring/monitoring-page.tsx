'use client';

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAppStore } from '@/lib/store';
import { RouterStatus } from './router-status';
import { FailoverHistory } from './failover-history';
import { ColdStartStatusPanel } from './cold-start';
import { QualityMetricsPanel } from './quality-metrics';
import { PerformanceMetricsPanel } from './performance-metrics';
import { ActiveAlerts } from '@/components/dashboard/active-alerts';
import { Server, GitBranch, Flame, Shield, Gauge, AlertTriangle } from 'lucide-react';

export function MonitoringPage() {
  const { monitoringTab, setMonitoringTab } = useAppStore();

  return (
    <Tabs value={monitoringTab} onValueChange={setMonitoringTab}>
      <TabsList>
        <TabsTrigger value="router"><Server className="h-3 w-3 mr-1" /> Router</TabsTrigger>
        <TabsTrigger value="failover"><GitBranch className="h-3 w-3 mr-1" /> Failover</TabsTrigger>
        <TabsTrigger value="coldstart"><Flame className="h-3 w-3 mr-1" /> Cold Start</TabsTrigger>
        <TabsTrigger value="quality"><Shield className="h-3 w-3 mr-1" /> Quality</TabsTrigger>
        <TabsTrigger value="performance"><Gauge className="h-3 w-3 mr-1" /> Performance</TabsTrigger>
        <TabsTrigger value="alerts"><AlertTriangle className="h-3 w-3 mr-1" /> Alerts</TabsTrigger>
      </TabsList>
      <TabsContent value="router" className="mt-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <RouterStatus />
          <FailoverHistory />
        </div>
      </TabsContent>
      <TabsContent value="failover" className="mt-6"><FailoverHistory /></TabsContent>
      <TabsContent value="coldstart" className="mt-6"><ColdStartStatusPanel /></TabsContent>
      <TabsContent value="quality" className="mt-6"><QualityMetricsPanel /></TabsContent>
      <TabsContent value="performance" className="mt-6"><PerformanceMetricsPanel /></TabsContent>
      <TabsContent value="alerts" className="mt-6"><ActiveAlerts /></TabsContent>
    </Tabs>
  );
}
