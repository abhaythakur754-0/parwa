'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { dashboardApi, type Customer } from '@/lib/dashboard-api';

const PAGE_SIZE = 25;

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [verifiedFilter, setVerifiedFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showMergeModal, setShowMergeModal] = useState(false);

  const fetchCustomers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await dashboardApi.getCustomers({
        page, pageSize: PAGE_SIZE,
        search: search || undefined,
        verified: verifiedFilter !== 'all' ? verifiedFilter : undefined,
      });
      setCustomers(data.items || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err.message || 'Failed to load customers');
    } finally {
      setLoading(false);
    }
  }, [page, search, verifiedFilter]);

  useEffect(() => { fetchCustomers(); }, [fetchCustomers]);

  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchInput), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const toggleSelect = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedIds(next);
  };
  const toggleAll = () => {
    if (selectedIds.size === customers.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(customers.map(c => c.id)));
  };

  const statusColor = (verified: boolean) =>
    verified ? 'bg-emerald-500/10 text-emerald-400' : 'bg-zinc-800 text-zinc-400';

  return (
    <div className="min-h-screen bg-[#0a0a0a] p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">Customers</h1>
          <p className="text-sm text-zinc-500 mt-1">{total} total customers</p>
        </div>
        <div className="flex items-center gap-3">
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-zinc-400">{selectedIds.size} selected</span>
              {/* TODO: Implement CSV export for selected customers */}
              <button disabled className="px-3 py-1.5 text-xs font-medium bg-zinc-800 text-zinc-200 rounded-lg hover:bg-zinc-700 transition-colors opacity-50 cursor-not-allowed">Export CSV</button>
              {selectedIds.size >= 2 && (
                <button onClick={() => setShowMergeModal(true)} className="px-3 py-1.5 text-xs font-medium bg-orange-500/10 text-orange-400 rounded-lg hover:bg-orange-500/20 transition-colors">Merge Selected</button>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-md">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" /></svg>
          <input type="text" placeholder="Search by name, email, phone..." value={searchInput} onChange={(e) => { setSearchInput(e.target.value); setPage(1); }} className="w-full pl-10 pr-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/50" />
        </div>
        <select value={verifiedFilter} onChange={(e) => { setVerifiedFilter(e.target.value); setPage(1); }} className="px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-zinc-300 focus:outline-none focus:border-orange-500/50">
          <option value="all">All Status</option>
          <option value="true">Verified</option>
          <option value="false">Unverified</option>
        </select>
      </div>

      <div className="bg-zinc-900/50 rounded-xl border border-white/[0.06] overflow-hidden overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="px-4 py-3 text-left w-10"><input type="checkbox" checked={customers.length > 0 && selectedIds.size === customers.length} onChange={toggleAll} className="rounded border-zinc-700 bg-zinc-800 text-orange-500" /></th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">Name</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">Email</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">Phone</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {loading ? <tr><td colSpan={6} className="px-4 py-12 text-center text-zinc-500">Loading...</td></tr> : error ? <tr><td colSpan={6} className="px-4 py-12 text-center text-red-400">{error}</td></tr> : customers.length === 0 ? <tr><td colSpan={6} className="px-4 py-12 text-center text-zinc-500">No customers found</td></tr> : customers.map(c => (
              <tr key={c.id} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-4 py-3"><input type="checkbox" checked={selectedIds.has(c.id)} onChange={() => toggleSelect(c.id)} className="rounded border-zinc-700 bg-zinc-800 text-orange-500" /></td>
                <td className="px-4 py-3"><Link href={`/dashboard/customers/${c.id}`} className="text-sm font-medium text-zinc-200 hover:text-orange-400 transition-colors">{c.name || <span className="text-zinc-600 italic">Unnamed</span>}</Link></td>
                <td className="px-4 py-3 text-sm text-zinc-400">{c.email || '\u2014'}</td>
                <td className="px-4 py-3 text-sm text-zinc-400">{c.phone || '\u2014'}</td>
                <td className="px-4 py-3"><span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(c.is_verified)}`}>{c.is_verified ? 'Verified' : 'Unverified'}</span></td>
                <td className="px-4 py-3 text-sm text-zinc-500">{new Date(c.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-sm text-zinc-500">Showing {(page - 1) * PAGE_SIZE + 1}\u2013{Math.min(page * PAGE_SIZE, total)} of {total}</span>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1.5 text-sm bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 disabled:opacity-40">Prev</button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => Math.max(1, Math.min(page - 2, totalPages - 4)) + i).filter(p => p <= totalPages).map(p => (
              <button key={p} onClick={() => setPage(p)} className={`px-3 py-1.5 text-sm rounded-lg ${p === page ? 'bg-orange-500 text-white' : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'}`}>{p}</button>
            ))}
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="px-3 py-1.5 text-sm bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 disabled:opacity-40">Next</button>
          </div>
        </div>
      )}

      {showMergeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-zinc-900 border border-white/[0.06] rounded-2xl p-6 w-full max-w-lg shadow-2xl">
            <h2 className="text-lg font-semibold text-zinc-100 mb-4">Merge Customers</h2>
            <p className="text-sm text-zinc-400 mb-4">Select the primary customer. Data from others will be merged into it.</p>
            <MergeModalBody customerIds={Array.from(selectedIds)} customers={customers} onSuccess={() => { setShowMergeModal(false); fetchCustomers(); setSelectedIds(new Set()); }} onCancel={() => setShowMergeModal(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

function MergeModalBody({ customerIds, customers, onSuccess, onCancel }: { customerIds: string[]; customers: Customer[]; onSuccess: () => void; onCancel: () => void }) {
  const [primaryId, setPrimaryId] = useState(customerIds[0] || '');
  const [merging, setMerging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selected = customers.filter(c => customerIds.includes(c.id));

  const handleMerge = async () => {
    setMerging(true); setError(null);
    try {
      await dashboardApi.mergeCustomers({ primary_customer_id: primaryId, merged_customer_ids: customerIds.filter(id => id !== primaryId) });
      onSuccess();
    } catch (err: any) { setError(err.message || 'Merge failed'); }
    finally { setMerging(false); }
  };

  return (<>
    <div className="space-y-2 mb-4">
      {selected.map(c => (
        <label key={c.id} className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer ${primaryId === c.id ? 'border-orange-500/50 bg-orange-500/5' : 'border-zinc-800 hover:border-zinc-700'}`}>
          <input type="radio" name="primary" checked={primaryId === c.id} onChange={() => setPrimaryId(c.id)} className="text-orange-500" />
          <div><p className="text-sm font-medium text-zinc-200">{c.name || 'Unnamed'}</p><p className="text-xs text-zinc-500">{c.email || c.phone || c.id}</p></div>
        </label>
      ))}
    </div>
    {error && <p className="text-sm text-red-400 mb-4">{error}</p>}
    <div className="flex justify-end gap-3">
      <button onClick={onCancel} className="px-4 py-2 text-sm bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700">Cancel</button>
      <button onClick={handleMerge} disabled={merging || !primaryId} className="px-4 py-2 text-sm bg-orange-500 text-white rounded-lg hover:bg-orange-600 disabled:opacity-50">{merging ? 'Merging...' : 'Confirm Merge'}</button>
    </div>
  </>);
}
