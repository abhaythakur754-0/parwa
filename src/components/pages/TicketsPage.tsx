'use client';

export default function TicketsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Tickets</h1>
        <p className="text-zinc-400 mt-1">Manage and track customer support tickets</p>
      </div>

      {/* Empty State */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A]">
        <div className="flex flex-col items-center justify-center py-20 px-6">
          {/* Ticket Icon */}
          <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-white/5 mb-6">
            <svg
              className="w-8 h-8 text-zinc-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125V6.375c0-.621-.504-1.125-1.125-1.125H3.375Z"
              />
            </svg>
          </div>

          <h3 className="text-lg font-semibold text-zinc-300 mb-2">
            No tickets to display
          </h3>
          <p className="text-sm text-zinc-500 text-center max-w-md leading-relaxed">
            Tickets will appear here once your AI agents start processing customer requests. Connect your backend to get started.
          </p>
        </div>
      </div>
    </div>
  );
}
