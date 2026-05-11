'use client';

export default function TicketsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Tickets</h1>
        <p className="text-zinc-400 mt-1">Manage and track customer support tickets</p>
      </div>
      <div className="bg-[#1A1A1A] border border-zinc-800 rounded-xl p-8 text-center">
        <p className="text-zinc-500">Connect your backend to view tickets</p>
      </div>
    </div>
  );
}
