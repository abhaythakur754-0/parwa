'use client';

export default function BillingPage() {
  const plan = {
    name: 'PARWA Growth',
    tier: 'Most Popular',
    price: '$2,499',
    period: '/month',
    nextBilling: 'Jun 15, 2025',
    agents: '8 AI Agents',
    tickets: '5,000 tickets/month',
    channels: 'Email, Chat, SMS, Voice',
  };

  const invoices = [
    { id: 'INV-2025-05', date: 'May 1, 2025', amount: '$2,499.00', status: 'Paid' },
    { id: 'INV-2025-04', date: 'Apr 1, 2025', amount: '$2,499.00', status: 'Paid' },
    { id: 'INV-2025-03', date: 'Mar 1, 2025', amount: '$2,499.00', status: 'Paid' },
  ];

  const usage = [
    { label: 'Tickets Used', current: 3421, limit: 5000, unit: '' },
    { label: 'AI Agents Active', current: 6, limit: 8, unit: '' },
    { label: 'API Calls', current: 124500, limit: 500000, unit: '' },
  ];

  return (
    <div className="space-y-6">
      <div className="pb-6 border-b border-white/[0.06]">
        <h1 className="text-xl font-bold text-white">Billing</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Manage your subscription, invoices, and payment methods
        </p>
      </div>

      {/* Current Plan */}
      <div className="rounded-2xl border-2 border-orange-500/30 bg-gradient-to-br from-orange-500/5 to-transparent p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-lg font-bold text-white">{plan.name}</h2>
              <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-orange-500/20 text-orange-400 border border-orange-500/30">
                {plan.tier}
              </span>
            </div>
            <p className="text-sm text-zinc-400">Next billing date: {plan.nextBilling}</p>
          </div>
          <div className="text-right">
            <span className="text-3xl font-black text-orange-400">{plan.price}</span>
            <span className="text-sm text-zinc-400">{plan.period}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          <span className="text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-zinc-300">{plan.agents}</span>
          <span className="text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-zinc-300">{plan.tickets}</span>
          <span className="text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-zinc-300">{plan.channels}</span>
        </div>
        <div className="flex gap-3 mt-5">
          <button className="text-xs font-medium px-4 py-2 rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/20 hover:bg-orange-500/20 transition-colors">
            Upgrade Plan
          </button>
          <button className="text-xs font-medium px-4 py-2 rounded-lg bg-white/5 text-zinc-400 border border-white/10 hover:border-white/20 hover:text-zinc-300 transition-colors">
            View All Plans
          </button>
        </div>
      </div>

      {/* Usage */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
        <h3 className="text-sm font-semibold text-white mb-4">Current Usage</h3>
        <div className="space-y-4">
          {usage.map((item) => {
            const percent = Math.round((item.current / item.limit) * 100);
            return (
              <div key={item.label}>
                <div className="flex items-center justify-between text-sm mb-1.5">
                  <span className="text-zinc-400">{item.label}</span>
                  <span className="text-zinc-300 font-medium">
                    {item.current.toLocaleString()} / {item.limit.toLocaleString()}{item.unit}
                  </span>
                </div>
                <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      percent > 80 ? 'bg-rose-500' : percent > 60 ? 'bg-yellow-500' : 'bg-emerald-500'
                    }`}
                    style={{ width: `${Math.min(percent, 100)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Invoices */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
        <div className="px-5 py-4 border-b border-white/[0.06]">
          <h3 className="text-sm font-semibold text-white">Recent Invoices</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.04]">
                <th className="text-left px-5 py-3 text-zinc-500 font-medium text-xs uppercase">Invoice</th>
                <th className="text-left px-5 py-3 text-zinc-500 font-medium text-xs uppercase">Date</th>
                <th className="text-left px-5 py-3 text-zinc-500 font-medium text-xs uppercase">Amount</th>
                <th className="text-left px-5 py-3 text-zinc-500 font-medium text-xs uppercase">Status</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-b border-white/[0.04]">
                  <td className="px-5 py-3 text-zinc-300 font-medium">{inv.id}</td>
                  <td className="px-5 py-3 text-zinc-400">{inv.date}</td>
                  <td className="px-5 py-3 text-zinc-300">{inv.amount}</td>
                  <td className="px-5 py-3">
                    <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      {inv.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
