'use client';

export default function KnowledgePage() {
  const documents = [
    { name: 'Product FAQ Guide', type: 'PDF', size: '2.4 MB', status: 'Active', chunks: 142, updated: '2 days ago' },
    { name: 'Return Policy Document', type: 'PDF', size: '890 KB', status: 'Active', chunks: 67, updated: '1 week ago' },
    { name: 'Shipping Information', type: 'DOCX', size: '1.2 MB', status: 'Active', chunks: 89, updated: '2 weeks ago' },
    { name: 'Technical Specifications', type: 'CSV', size: '345 KB', status: 'Processing', chunks: 0, updated: 'Just now' },
    { name: 'Customer Service Guidelines', type: 'PDF', size: '1.8 MB', status: 'Active', chunks: 124, updated: '1 month ago' },
  ];

  return (
    <div className="space-y-6">
      <div className="pb-6 border-b border-white/[0.06]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Knowledge Base</h1>
            <p className="text-sm text-zinc-500 mt-0.5">
              Manage your knowledge sources and AI training data
            </p>
          </div>
          <button className="text-xs font-medium px-4 py-2.5 rounded-lg bg-gradient-to-r from-orange-500 to-orange-400 text-white hover:from-orange-400 hover:to-orange-300 transition-all shadow-lg shadow-orange-500/25">
            Upload Document
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
          <p className="text-2xl font-bold text-white">5</p>
          <p className="text-xs text-zinc-500 mt-1">Total Documents</p>
        </div>
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
          <p className="text-2xl font-bold text-white">422</p>
          <p className="text-xs text-zinc-500 mt-1">Knowledge Chunks</p>
        </div>
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
          <p className="text-2xl font-bold text-orange-400">96%</p>
          <p className="text-xs text-zinc-500 mt-1">AI Accuracy with KB</p>
        </div>
      </div>

      {/* Documents List */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
        <div className="px-5 py-4 border-b border-white/[0.06]">
          <h3 className="text-sm font-semibold text-white">Documents</h3>
        </div>
        <div className="divide-y divide-white/[0.04]">
          {documents.map((doc) => (
            <div key={doc.name} className="flex items-center justify-between px-5 py-4 hover:bg-white/[0.02] transition-colors">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center text-xs font-bold text-orange-400">
                  {doc.type}
                </div>
                <div>
                  <p className="text-sm font-medium text-zinc-200">{doc.name}</p>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    {doc.size} · {doc.chunks > 0 ? `${doc.chunks} chunks` : 'Processing...'} · {doc.updated}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                  doc.status === 'Active'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
                }`}>
                  {doc.status}
                </span>
                <button className="text-zinc-500 hover:text-zinc-300 transition-colors">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 12.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 18.75a.75.75 0 110-1.5.75.75 0 010 1.5z" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
