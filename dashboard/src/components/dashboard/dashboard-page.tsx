'use client';

import { KPICards } from './kpi-cards';
import { AutomationChart } from './automation-chart';
import { VariantDistributionChart } from './variant-distribution';
import { ChannelDistributionChart } from './channel-distribution';
import { RecentTickets } from './recent-tickets';
import { ActiveAlerts } from './active-alerts';

export function DashboardPage() {
  return (
    <div className="space-y-6">
      <KPICards />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AutomationChart />
        <VariantDistributionChart />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChannelDistributionChart />
        <ActiveAlerts />
      </div>
      <RecentTickets />
    </div>
  );
}
