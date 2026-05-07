'use client';

import React, { useState } from 'react';
import { X, Calendar, Building2, Briefcase, Clock, MessageSquare, Send, Loader2, CheckCircle } from 'lucide-react';
import toast from 'react-hot-toast';

interface BookDemoModalProps {
  isOpen: boolean;
  onClose: () => void;
  preSelectedIndustry?: string;
}

const INDUSTRIES = ['E-commerce', 'SaaS', 'Logistics', 'Healthcare', 'Other'];

const TIME_SLOTS = [
  '9:00 AM - 10:00 AM',
  '10:00 AM - 11:00 AM',
  '11:00 AM - 12:00 PM',
  '1:00 PM - 2:00 PM',
  '2:00 PM - 3:00 PM',
  '3:00 PM - 4:00 PM',
  '4:00 PM - 5:00 PM',
];

export function BookDemoModal({ isOpen, onClose, preSelectedIndustry }: BookDemoModalProps) {
  const [form, setForm] = useState({
    name: '',
    email: '',
    company: '',
    industry: preSelectedIndustry || '',
    preferredDate: '',
    preferredTime: '',
    message: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleChange = (field: string, value: string) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name || !form.email || !form.company) return;

    setIsSubmitting(true);
    try {
      const res = await fetch('/api/book-demo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();

      if (data.status === 'success') {
        setIsSubmitted(true);
        toast.success('Demo request submitted!', {
          style: {
            background: '#2A1A0A',
            color: '#FFF4E6',
            border: '1px solid rgba(255,127,17,0.25)',
            borderRadius: '12px',
          },
        });
        setTimeout(() => {
          setIsSubmitted(false);
          setForm({ name: '', email: '', company: '', industry: '', preferredDate: '', preferredTime: '', message: '' });
          onClose();
        }, 3000);
      } else {
        toast.error(data.message || 'Something went wrong');
      }
    } catch {
      toast.error('Network error. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4" onClick={onClose}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className="relative w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-2xl"
        style={{
          background: 'linear-gradient(180deg, #1A1A1A 0%, #2A1A0A 100%)',
          border: '1px solid rgba(255,127,17,0.25)',
          boxShadow: '0 25px 60px rgba(0,0,0,0.5), 0 0 80px rgba(255,127,17,0.08)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b" style={{ borderColor: 'rgba(255,127,17,0.15)' }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #FF7F11 0%, #E06A00 100%)' }}>
              <Calendar className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Book an Instant Demo</h2>
              <p className="text-xs text-orange-300/50">See how this agent talks to your clients — just $1, no commitment</p>
            </div>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-lg flex items-center justify-center text-white/40 hover:text-white hover:bg-white/10 transition-all">
            <X className="w-5 h-5" />
          </button>
        </div>

        {isSubmitted ? (
          <div className="px-6 py-16 text-center">
            <div className="w-16 h-16 rounded-full bg-orange-500/20 flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-8 h-8 text-orange-400" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">Request Submitted!</h3>
            <p className="text-sm text-orange-200/50">Our team will reach out within 24 hours to set up your instant demo for just $1.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
            {/* Name */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-orange-200/70 mb-2">
                <Building2 className="w-3.5 h-3.5 text-orange-400/60" />
                Full Name *
              </label>
              <input
                type="text"
                required
                value={form.name}
                onChange={(e) => handleChange('name', e.target.value)}
                placeholder="John Doe"
                className="w-full px-4 py-3 rounded-xl text-sm text-white placeholder-white/25 focus:outline-none focus:ring-2 focus:ring-orange-500/30"
                style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)' }}
              />
            </div>

            {/* Email */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-orange-200/70 mb-2">
                <Briefcase className="w-3.5 h-3.5 text-orange-400/60" />
                Work Email *
              </label>
              <input
                type="email"
                required
                value={form.email}
                onChange={(e) => handleChange('email', e.target.value)}
                placeholder="john@company.com"
                className="w-full px-4 py-3 rounded-xl text-sm text-white placeholder-white/25 focus:outline-none focus:ring-2 focus:ring-orange-500/30"
                style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)' }}
              />
            </div>

            {/* Company */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-orange-200/70 mb-2">
                <Building2 className="w-3.5 h-3.5 text-orange-400/60" />
                Company Name *
              </label>
              <input
                type="text"
                required
                value={form.company}
                onChange={(e) => handleChange('company', e.target.value)}
                placeholder="Acme Inc."
                className="w-full px-4 py-3 rounded-xl text-sm text-white placeholder-white/25 focus:outline-none focus:ring-2 focus:ring-orange-500/30"
                style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)' }}
              />
            </div>

            {/* Industry */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-orange-200/70 mb-2">
                <Briefcase className="w-3.5 h-3.5 text-orange-400/60" />
                Industry
              </label>
              <select
                value={form.industry}
                onChange={(e) => handleChange('industry', e.target.value)}
                className="w-full px-4 py-3 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-orange-500/30 appearance-none cursor-pointer"
                style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)' }}
              >
                <option value="" style={{ background: '#1A1A1A' }}>Select industry...</option>
                {INDUSTRIES.map(ind => (
                  <option key={ind} value={ind} style={{ background: '#1A1A1A' }}>{ind}</option>
                ))}
              </select>
            </div>

            {/* Date & Time Row */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-orange-200/70 mb-2">
                  <Calendar className="w-3.5 h-3.5 text-orange-400/60" />
                  Preferred Date
                </label>
                <input
                  type="date"
                  value={form.preferredDate}
                  onChange={(e) => handleChange('preferredDate', e.target.value)}
                  min={new Date().toISOString().split('T')[0]}
                  className="w-full px-4 py-3 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-orange-500/30"
                  style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', colorScheme: 'dark' }}
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-orange-200/70 mb-2">
                  <Clock className="w-3.5 h-3.5 text-orange-400/60" />
                  Preferred Time
                </label>
                <select
                  value={form.preferredTime}
                  onChange={(e) => handleChange('preferredTime', e.target.value)}
                  className="w-full px-4 py-3 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-orange-500/30 appearance-none cursor-pointer"
                  style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)' }}
                >
                  <option value="" style={{ background: '#1A1A1A' }}>Select time...</option>
                  {TIME_SLOTS.map(slot => (
                    <option key={slot} value={slot} style={{ background: '#1A1A1A' }}>{slot}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Message */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-orange-200/70 mb-2">
                <MessageSquare className="w-3.5 h-3.5 text-orange-400/60" />
                What would you like to see in the demo?
              </label>
              <textarea
                value={form.message}
                onChange={(e) => handleChange('message', e.target.value)}
                rows={3}
                placeholder="Tell us about your support challenges..."
                className="w-full px-4 py-3 rounded-xl text-sm text-white placeholder-white/25 focus:outline-none focus:ring-2 focus:ring-orange-500/30 resize-none"
                style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)' }}
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting || !form.name || !form.email || !form.company}
              className="w-full py-3.5 rounded-xl text-sm font-bold transition-all duration-500 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              style={{
                background: 'linear-gradient(135deg, #FF7F11 0%, #E06A00 100%)',
                color: '#1A1A1A',
                boxShadow: '0 8px 30px rgba(255,127,17,0.3)',
              }}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  Book Instant Demo — $1
                </>
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
