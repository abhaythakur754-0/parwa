export default function DashboardLoading() {
  return (
    <main className="min-h-screen bg-zinc-950">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Header skeleton */}
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="h-6 w-48 bg-white/[0.06] rounded-lg animate-pulse" />
            <div className="h-3 w-64 bg-white/[0.06] rounded animate-pulse" />
          </div>
          <div className="h-8 w-32 bg-white/[0.06] rounded-lg animate-pulse" />
        </div>

        {/* Stats skeleton */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4 animate-pulse">
              <div className="h-3 w-24 bg-white/[0.06] rounded mb-3" />
              <div className="h-7 w-12 bg-white/[0.06] rounded" />
            </div>
          ))}
        </div>

        {/* Filter skeleton */}
        <div className="h-12 bg-[#1A1A1A] border border-white/[0.06] rounded-xl animate-pulse" />

        {/* Card skeletons */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4 animate-pulse space-y-3">
              <div className="flex items-center justify-between">
                <div className="h-4 w-32 bg-white/[0.06] rounded" />
                <div className="h-5 w-20 bg-white/[0.06] rounded-full" />
              </div>
              <div className="h-3 w-full bg-white/[0.06] rounded" />
              <div className="h-3 w-3/4 bg-white/[0.06] rounded" />
              <div className="flex gap-2">
                <div className="h-5 w-14 bg-white/[0.06] rounded-full" />
                <div className="h-5 w-16 bg-white/[0.06] rounded-full" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
