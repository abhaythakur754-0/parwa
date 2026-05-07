'use client';

export default function VariantsPage() {
  const variants = [
    {
      name: 'PARWA Starter',
      tier: 'Entry',
      status: 'Active',
      model: 'GPT-4o-mini',
      tickets: 1247,
      resolution: '60%',
      avgTime: '3.2 min',
      cost: '$0.02/ticket',
    },
    {
      name: 'PARWA Growth',
      tier: 'Growth',
      status: 'Active',
      model: 'GPT-4o',
      tickets: 3891,
      resolution: '78%',
      avgTime: '1.8 min',
      cost: '$0.05/ticket',
    },
    {
      name: 'PARWA High',
      tier: 'Enterprise',
      status: 'Paused',
      model: 'GPT-4o + Custom',
      tickets: 0,
      resolution: '88%',
      avgTime: '0.9 min',
      cost: '$0.12/ticket',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="pb-6 border-b border-white/[0.06]">
        <h1 className="text-xl font-bold text-white">Variant Engine</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Configure and monitor your AI variant instances
        </p>
      </div>

      {/* Variant Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {variants.map((variant) => (
          <div
            key={variant.name}
            className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5 hover:border-white/[0.1] transition-all duration-300"
          >
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-white">{variant.name}</h3>
                <span className="text-xs text-zinc-500">{variant.tier}</span>
              </div>
              <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                variant.status === 'Active'
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-zinc-500/10 text-zinc-400 border border-zinc-500/20'
              }`}>
                {variant.status}
              </span>
            </div>

            <div className="space-y-3 mb-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-500">Model</span>
                <span className="text-zinc-300 font-medium">{variant.model}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-500">Tickets Processed</span>
                <span className="text-zinc-300 font-medium">{variant.tickets.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-500">AI Resolution</span>
                <span className="text-orange-400 font-semibold">{variant.resolution}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-500">Avg Response Time</span>
                <span className="text-zinc-300 font-medium">{variant.avgTime}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-500">Cost per Ticket</span>
                <span className="text-zinc-300 font-medium">{variant.cost}</span>
              </div>
            </div>

            <div className="flex gap-2 pt-4 border-t border-white/[0.06]">
              <button className="flex-1 text-xs font-medium py-2 rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/20 hover:bg-orange-500/20 transition-colors">
                Configure
              </button>
              <button className="flex-1 text-xs font-medium py-2 rounded-lg bg-white/5 text-zinc-400 border border-white/10 hover:border-white/20 hover:text-zinc-300 transition-colors">
                View Logs
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Performance Comparison */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
        <h3 className="text-sm font-semibold text-white mb-4">Performance Comparison</h3>
        <div className="space-y-4">
          {[
            { metric: 'Resolution Rate', values: [60, 78, 88], max: 100 },
            { metric: 'Speed Score', values: [45, 72, 95], max: 100 },
            { metric: 'Cost Efficiency', values: [92, 85, 70], max: 100 },
          ].map((row) => (
            <div key={row.metric}>
              <p className="text-xs text-zinc-500 mb-2">{row.metric}</p>
              <div className="flex items-center gap-3">
                {variants.map((v, i) => (
                  <div key={v.name} className="flex-1">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-zinc-400">{v.name.split(' ')[1]}</span>
                      <span className="text-zinc-300 font-medium">{row.values[i]}%</span>
                    </div>
                    <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-orange-500 to-orange-400 transition-all duration-700"
                        style={{ width: `${(row.values[i] / row.max) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
