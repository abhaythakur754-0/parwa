'use client';

export default function MonitoringPage() {
  const metrics = [
    { label: 'System Uptime', value: '99.97%', status: 'healthy', icon: '⚡' },
    { label: 'API Response Time', value: '142ms', status: 'healthy', icon: '📊' },
    { label: 'AI Pipeline', value: 'Active', status: 'healthy', icon: '🤖' },
    { label: 'Error Rate', value: '0.03%', status: 'healthy', icon: '✅' },
    { label: 'Active Connections', value: '1,247', status: 'healthy', icon: '🔗' },
    { label: 'Queue Depth', value: '23', status: 'warning', icon: '📋' },
  ];

  return (
    <div className="space-y-6">
      <div className="pb-6 border-b border-white/[0.06]">
        <h1 className="text-xl font-bold text-white">Monitoring</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Real-time system health and performance monitoring
        </p>
      </div>

      {/* Status Overview */}
      <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
        <div className="relative w-2.5 h-2.5">
          <div className="absolute inset-0 rounded-full bg-emerald-400 animate-pulse" />
          <div className="absolute inset-0 rounded-full bg-emerald-400" />
        </div>
        <span className="text-sm font-medium text-emerald-400">All systems operational</span>
        <span className="text-xs text-zinc-500 ml-2">Last checked: just now</span>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5 hover:border-white/[0.1] transition-all duration-300"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xl">{metric.icon}</span>
              <span className={`w-2 h-2 rounded-full ${
                metric.status === 'healthy' ? 'bg-emerald-400' : 'bg-yellow-400'
              }`} />
            </div>
            <p className="text-2xl font-bold text-white">{metric.value}</p>
            <p className="text-xs text-zinc-500 mt-1">{metric.label}</p>
          </div>
        ))}
      </div>

      {/* Activity Log */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
        <h3 className="text-sm font-semibold text-white mb-4">Recent Activity</h3>
        <div className="space-y-3">
          {[
            { time: '2 min ago', event: 'AI Pipeline scaled to handle increased volume', type: 'info' },
            { time: '15 min ago', event: 'Email channel reconnected after brief timeout', type: 'warning' },
            { time: '1h ago', event: 'Daily backup completed successfully', type: 'success' },
            { time: '3h ago', event: 'New agent variant deployed to production', type: 'info' },
          ].map((log, i) => (
            <div key={i} className="flex items-start gap-3 text-sm">
              <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                log.type === 'success' ? 'bg-emerald-400' : log.type === 'warning' ? 'bg-yellow-400' : 'bg-blue-400'
              }`} />
              <div className="flex-1 min-w-0">
                <p className="text-zinc-300">{log.event}</p>
                <p className="text-xs text-zinc-500 mt-0.5">{log.time}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
