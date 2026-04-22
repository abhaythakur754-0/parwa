'use client';

import Link from 'next/link';
import { ArrowLeft, Bot, Shield, Zap, Globe } from 'lucide-react';

export default function AboutPage() {
  return (
    <div
      className="min-h-screen py-12 px-4 sm:px-6 lg:px-8"
      style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}
    >
      <div className="max-w-4xl mx-auto">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-orange-200/50 hover:text-orange-300 transition-colors mb-8">
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </Link>

        <div className="text-center mb-12">
          <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4">
            About <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-orange-600">PARWA</span>
          </h1>
          <p className="text-lg text-white/50 max-w-2xl mx-auto">
            AI-powered customer support that handles tickets across email, chat, SMS, voice &amp; social media — saving businesses 85-92% on support costs.
          </p>
        </div>

        <div className="grid sm:grid-cols-3 gap-6 mb-12">
          {[
            { icon: Bot, title: 'AI-First', desc: '700+ features built around AI agents that learn and improve with every interaction.' },
            { icon: Shield, title: 'Enterprise Security', desc: 'SOC 2 Type II, GDPR, AES-256 encryption, and per-tenant isolation.' },
            { icon: Globe, title: 'Global Scale', desc: 'Trusted by 2,400+ businesses across 4 continents with 99.9% uptime.' },
          ].map((item) => (
            <div
              key={item.title}
              className="rounded-2xl p-6 text-center"
              style={{
                background: 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            >
              <item.icon className="w-8 h-8 text-orange-400 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-white mb-2">{item.title}</h3>
              <p className="text-sm text-white/50 leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>

        <div
          className="rounded-2xl p-8 sm:p-10"
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)',
            border: '1px solid rgba(255,127,17,0.2)',
          }}
        >
          <div className="flex items-center gap-3 mb-4">
            <Zap className="w-5 h-5 text-orange-400" />
            <h2 className="text-xl font-bold text-white">Our Mission</h2>
          </div>
          <p className="text-white/60 leading-relaxed">
            PARWA was founded to make world-class customer support accessible to every business.
            Our platform handles the repetitive 80% of tickets automatically, freeing your team to
            focus on complex, high-value interactions.
          </p>
        </div>
      </div>
    </div>
  );
}
