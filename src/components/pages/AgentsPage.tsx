'use client';

export default function AgentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">AI Agents</h1>
        <p className="text-zinc-400 mt-1">Monitor and configure your AI agent workforce</p>
      </div>

      {/* Agent Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {[
          { name: 'PARWA Starter', status: 'Active', tier: 'Entry', tickets: '1,247', resolution: '60%' },
          { name: 'PARWA Growth', status: 'Active', tier: 'Growth', tickets: '3,891', resolution: '78%' },
          { name: 'PARWA High', status: 'Paused', tier: 'Enterprise', tickets: '8,432', resolution: '88%' },
        ].map((agent) => (
          <div
            key={agent.name}
            className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5 hover:border-white/[0.1] transition-all duration-300"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-white">{agent.name}</h3>
              <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                agent.status === 'Active'
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-zinc-500/10 text-zinc-400 border border-zinc-500/20'
              }`}>
                {agent.status}
              </span>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-500">Tier</span>
                <span className="text-zinc-300 font-medium">{agent.tier}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-500">Tickets Resolved</span>
                <span className="text-zinc-300 font-medium">{agent.tickets}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-500">AI Resolution</span>
                <span className="text-orange-400 font-semibold">{agent.resolution}</span>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-white/[0.06]">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-xs text-emerald-400">Online</span>
                </div>
                <button className="text-xs font-medium text-orange-400 hover:text-orange-300 transition-colors">
                  Configure
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
