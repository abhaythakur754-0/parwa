'use client';

import { useState } from 'react';
import Link from 'next/link';

/**
 * Footer - Dark footer for contrast anchoring on light page
 */

interface FooterSection {
  title: string;
  links: { name: string; href: string }[];
}

const footerSections: FooterSection[] = [
  { title: 'Product', links: [{ name: 'Features', href: '#features' }, { name: 'Models', href: '/models' }, { name: 'Pricing', href: '/pricing' }] },
  { title: 'Resources', links: [{ name: 'Blog', href: '/blog' }, { name: 'Documentation', href: '/docs' }, { name: 'API Reference', href: '/api-docs' }] },
  { title: 'Company', links: [{ name: 'About Us', href: '/about' }, { name: 'Careers', href: '/careers' }, { name: 'Contact', href: '/contact' }] },
  { title: 'Legal', links: [{ name: 'Privacy Policy', href: '/privacy' }, { name: 'Terms of Service', href: '/terms' }, { name: 'Cookie Policy', href: '/cookies' }] },
];

const socialLinks = [
  { name: 'LinkedIn', href: 'https://linkedin.com', icon: <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z" /></svg> },
  { name: 'Twitter', href: 'https://twitter.com', icon: <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" /></svg> },
  { name: 'GitHub', href: 'https://github.com', icon: <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" /></svg> },
];

function FooterSectionMobile({ section, isOpen, onToggle }: { section: FooterSection; isOpen: boolean; onToggle: () => void }) {
  return (
    <div className="border-b border-white/10 last:border-0">
      <button onClick={onToggle} className="w-full flex items-center justify-between py-4 text-left focus-visible-ring rounded-lg" aria-expanded={isOpen}>
        <h4 className="font-semibold text-white text-sm">{section.title}</h4>
        <svg className={`w-4 h-4 text-gray-400 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <div className={`overflow-hidden transition-all duration-300 ${isOpen ? 'max-h-48 opacity-100' : 'max-h-0 opacity-0'}`}>
        <ul className="pb-4 space-y-2.5">
          {section.links.map((link) => (
            <li key={link.name}>
              <Link href={link.href} className="text-gray-400 hover:text-white text-sm transition-colors focus-visible-ring rounded">{link.name}</Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function Footer() {
  const [openSections, setOpenSections] = useState<string[]>([]);
  const toggleSection = (title: string) => setOpenSections(prev => prev.includes(title) ? prev.filter(t => t !== title) : [...prev, title]);

  return (
    <footer className="relative bg-gray-900 border-t border-gray-800" role="contentinfo">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-400/40 to-transparent" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14 sm:py-18 md:py-20">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-10 sm:gap-14">
          <div className="md:col-span-1">
            <Link href="/" className="flex items-center gap-2.5 mb-5 group focus-visible-ring rounded-xl px-1 py-0.5">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-600 to-emerald-700 flex items-center justify-center shadow-lg shadow-emerald-600/20">
                <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
                </svg>
              </div>
              <span className="text-lg font-bold text-white group-hover:text-emerald-300 transition-colors duration-300">PARWA</span>
            </Link>
            <p className="text-gray-400 text-sm leading-relaxed mb-1">AI-powered support that feels like magic.</p>
            <p className="text-gray-500 text-xs leading-relaxed">Trusted by 2,400+ businesses worldwide.</p>
          </div>
          <div className="md:hidden col-span-1">
            {footerSections.map((section) => (
              <FooterSectionMobile key={section.title} section={section} isOpen={openSections.includes(section.title)} onToggle={() => toggleSection(section.title)} />
            ))}
          </div>
          {footerSections.map((section) => (
            <div key={section.title} className="hidden md:block">
              <h4 className="font-semibold text-white mb-4 text-sm tracking-wide">{section.title}</h4>
              <ul className="space-y-2.5">
                {section.links.map((link) => (
                  <li key={link.name}>
                    <Link href={link.href} className="text-gray-400 hover:text-white text-sm transition-colors duration-300 focus-visible-ring rounded">{link.name}</Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 sm:mt-16 pt-6 sm:pt-8 border-t border-gray-800 flex flex-col md:flex-row justify-between items-center gap-5 sm:gap-6">
          <p className="text-gray-500 text-xs sm:text-sm">&copy; 2026 PARWA. All rights reserved.</p>
          <div className="flex items-center gap-2">
            {socialLinks.map((social) => (
              <a key={social.name} href={social.href} target="_blank" rel="noopener noreferrer"
                className="w-10 h-10 rounded-xl bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white border border-white/10 hover:border-white/20 hover:shadow-lg hover:shadow-emerald-600/10 flex items-center justify-center transition-all duration-500 focus-visible-ring"
                aria-label={social.name}>
                {social.icon}
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
