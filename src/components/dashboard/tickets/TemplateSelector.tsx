'use client';

import React, { useState, useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';

/**
 * TemplateSelector - Dropdown for selecting response templates
 *
 * Features:
 * - Search templates
 * - Variable preview
 * - Quick insert
 * - Category filtering
 */

export interface Template {
  id: string;
  name: string;
  category: string;
  subject_template?: string;
  body_template: string;
  variables: string[];
  language: string;
  usage_count?: number;
}

interface TemplateSelectorProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (template: Template) => void;
  onInsert: (template: Template, variables: Record<string, string>) => void;
  className?: string;
  position?: 'top' | 'bottom';
  variables?: Record<string, string>;
}

const CATEGORY_COLORS: Record<string, string> = {
  greeting: 'bg-emerald-500/20 text-emerald-400',
  apology: 'bg-amber-500/20 text-amber-400',
  escalation: 'bg-red-500/20 text-red-400',
  refund: 'bg-blue-500/20 text-blue-400',
  technical: 'bg-violet-500/20 text-violet-400',
  billing: 'bg-cyan-500/20 text-cyan-400',
  general: 'bg-zinc-500/20 text-zinc-400',
  custom: 'bg-pink-500/20 text-pink-400',
  farewell: 'bg-indigo-500/20 text-indigo-400',
};

const CATEGORY_LABELS: Record<string, string> = {
  greeting: '👋 Greeting',
  apology: '🙏 Apology',
  escalation: '⬆️ Escalation',
  refund: '💰 Refund',
  technical: '🔧 Technical',
  billing: '💳 Billing',
  general: '📋 General',
  custom: '✨ Custom',
  farewell: '👋 Farewell',
};

// Default templates (would come from API in production)
const DEFAULT_TEMPLATES: Template[] = [
  {
    id: 'tpl-1',
    name: 'Greeting - New Customer',
    category: 'greeting',
    subject_template: 'Welcome, {{customer_name}}!',
    body_template: 'Hello {{customer_name}},\n\nThank you for reaching out to {{company_name}} support. We\'re happy to help you with your inquiry.\n\nOur team will review your request and get back to you within {{response_time}}.\n\nBest regards,\n{{agent_name}}\n{{company_name}} Support Team',
    variables: ['customer_name', 'company_name', 'response_time', 'agent_name'],
    language: 'en',
  },
  {
    id: 'tpl-2',
    name: 'Apology - Service Issue',
    category: 'apology',
    subject_template: 'We\'re Sorry, {{customer_name}}',
    body_template: 'Dear {{customer_name}},\n\nWe sincerely apologise for the inconvenience you\'ve experienced with {{issue_description}}. This is not the level of service we strive to deliver.\n\nWe understand how frustrating this must be, and we want to make things right. Our team is already looking into this matter and we expect to have a resolution within {{resolution_time}}.\n\nWarm regards,\n{{agent_name}}\n{{company_name}} Support Team',
    variables: ['customer_name', 'issue_description', 'resolution_time', 'agent_name', 'company_name'],
    language: 'en',
  },
  {
    id: 'tpl-3',
    name: 'Escalation Notice',
    category: 'escalation',
    subject_template: 'Your Case Has Been Escalated — {{ticket_id}}',
    body_template: 'Dear {{customer_name}},\n\nThank you for your patience. We want to let you know that your case ({{ticket_id}}) has been escalated to our specialist team for further review.\n\nA dedicated team member will contact you within {{escalation_response_time}} with an update and next steps.\n\nKind regards,\n{{agent_name}}\n{{company_name}} Support Team',
    variables: ['customer_name', 'ticket_id', 'escalation_response_time', 'agent_name', 'company_name'],
    language: 'en',
  },
  {
    id: 'tpl-4',
    name: 'Refund Confirmation',
    category: 'refund',
    subject_template: 'Refund Confirmation — {{order_id}}',
    body_template: 'Dear {{customer_name}},\n\nWe\'re writing to confirm that a refund has been processed for your order {{order_id}}.\n\nRefund details:\n- Amount: {{refund_amount}}\n- Payment method: {{payment_method}}\n- Expected processing time: {{processing_time}}\n\nIf you have any questions, please reply to this message.\n\nBest regards,\n{{agent_name}}\n{{company_name}} Finance Team',
    variables: ['customer_name', 'order_id', 'refund_amount', 'payment_method', 'processing_time', 'agent_name', 'company_name'],
    language: 'en',
  },
  {
    id: 'tpl-5',
    name: 'Technical Support',
    category: 'technical',
    subject_template: 'Technical Support — {{issue_summary}}',
    body_template: 'Hi {{customer_name}},\n\nThank you for providing the details about the technical issue you\'re experiencing with {{product_or_service}}.\n\nBased on the information provided, here are the steps we recommend:\n\n{{troubleshooting_steps}}\n\nIf these steps don\'t resolve the issue, please let us know and include:\n- Any error messages you\'re seeing\n- Screenshots (if applicable)\n- Steps you\'ve already tried\n\nBest regards,\n{{agent_name}}\n{{company_name}} Technical Support',
    variables: ['customer_name', 'issue_summary', 'product_or_service', 'troubleshooting_steps', 'agent_name', 'company_name'],
    language: 'en',
  },
];

export default function TemplateSelector({
  isOpen,
  onClose,
  onSelect,
  onInsert,
  className,
  position = 'top',
  variables: providedVariables = {},
}: TemplateSelectorProps) {
  const [templates, setTemplates] = useState<Template[]>(DEFAULT_TEMPLATES);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [variableValues, setVariableValues] = useState<Record<string, string>>({});
  const containerRef = useRef<HTMLDivElement>(null);

  // Fetch templates from API
  useEffect(() => {
    if (isOpen) {
      // In production, fetch from /api/templates
      // For now, use defaults
      setTemplates(DEFAULT_TEMPLATES);
    }
  }, [isOpen]);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  // Filter templates
  const filteredTemplates = templates.filter((t) => {
    const matchesSearch = search
      ? t.name.toLowerCase().includes(search.toLowerCase()) ||
        t.body_template.toLowerCase().includes(search.toLowerCase())
      : true;

    const matchesCategory = selectedCategory
      ? t.category === selectedCategory
      : true;

    return matchesSearch && matchesCategory;
  });

  // Get unique categories
  const categories = [...new Set(templates.map((t) => t.category))];

  // Initialize variable values when template selected
  useEffect(() => {
    if (selectedTemplate) {
      const initial: Record<string, string> = {};
      selectedTemplate.variables.forEach((v) => {
        initial[v] = providedVariables[v] || '';
      });
      setVariableValues(initial);
    }
  }, [selectedTemplate, providedVariables]);

  // Handle insert
  const handleInsert = () => {
    if (selectedTemplate) {
      onInsert(selectedTemplate, variableValues);
      onClose();
    }
  };

  // Render template preview with variables
  const renderPreview = (template: Template) => {
    let preview = template.body_template;
    Object.entries(variableValues).forEach(([key, value]) => {
      preview = preview.replace(new RegExp(`{{${key}}}`, 'g'), value || `{{${key}}}`);
    });
    return preview.slice(0, 200) + (preview.length > 200 ? '...' : '');
  };

  if (!isOpen) return null;

  return (
    <div
      ref={containerRef}
      className={cn(
        'absolute z-50 w-96 bg-[#1A1A1A] rounded-xl border border-white/[0.1] shadow-2xl',
        position === 'top' ? 'bottom-full mb-2' : 'top-full mt-2',
        className
      )}
    >
      {/* Search */}
      <div className="p-2 border-b border-white/[0.06]">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search templates..."
          className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-violet-500"
          autoFocus
        />
      </div>

      {/* Categories */}
      <div className="flex items-center gap-1 p-2 overflow-x-auto border-b border-white/[0.06]">
        <button
          onClick={() => setSelectedCategory(null)}
          className={cn(
            'px-2 py-1 text-xs rounded whitespace-nowrap transition-colors',
            !selectedCategory
              ? 'bg-violet-500/20 text-violet-400'
              : 'text-zinc-500 hover:text-white'
          )}
        >
          All
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={cn(
              'px-2 py-1 text-xs rounded whitespace-nowrap transition-colors',
              selectedCategory === cat
                ? 'bg-violet-500/20 text-violet-400'
                : 'text-zinc-500 hover:text-white'
            )}
          >
            {CATEGORY_LABELS[cat] || cat}
          </button>
        ))}
      </div>

      {/* Templates List or Variable Editor */}
      {!selectedTemplate ? (
        <div className="max-h-80 overflow-y-auto">
          {filteredTemplates.length === 0 ? (
            <div className="p-4 text-center text-sm text-zinc-500">
              No templates found
            </div>
          ) : (
            filteredTemplates.map((template) => (
              <button
                key={template.id}
                onClick={() => setSelectedTemplate(template)}
                className="w-full p-3 text-left hover:bg-white/[0.04] transition-colors border-b border-white/[0.04] last:border-b-0"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className={cn(
                    'px-1.5 py-0.5 rounded text-[10px] font-medium',
                    CATEGORY_COLORS[template.category] || CATEGORY_COLORS.general
                  )}>
                    {CATEGORY_LABELS[template.category] || template.category}
                  </span>
                  <span className="text-sm font-medium text-white truncate">
                    {template.name}
                  </span>
                </div>
                <p className="text-xs text-zinc-500 line-clamp-2">
                  {template.body_template.slice(0, 100)}...
                </p>
                {template.variables.length > 0 && (
                  <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                    {template.variables.slice(0, 4).map((v) => (
                      <span
                        key={v}
                        className="px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 text-[10px]"
                      >
                        {`{{${v}}}`}
                      </span>
                    ))}
                    {template.variables.length > 4 && (
                      <span className="text-[10px] text-zinc-600">
                        +{template.variables.length - 4} more
                      </span>
                    )}
                  </div>
                )}
              </button>
            ))
          )}
        </div>
      ) : (
        <div className="p-3">
          {/* Back button */}
          <button
            onClick={() => setSelectedTemplate(null)}
            className="flex items-center gap-1 text-xs text-zinc-500 hover:text-white mb-3"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
            Back to templates
          </button>

          {/* Template name */}
          <div className="mb-3">
            <span className={cn(
              'px-1.5 py-0.5 rounded text-[10px] font-medium',
              CATEGORY_COLORS[selectedTemplate.category] || CATEGORY_COLORS.general
            )}>
              {CATEGORY_LABELS[selectedTemplate.category] || selectedTemplate.category}
            </span>
            <h4 className="text-sm font-medium text-white mt-1">{selectedTemplate.name}</h4>
          </div>

          {/* Variables */}
          {selectedTemplate.variables.length > 0 && (
            <div className="space-y-2 mb-3">
              <p className="text-xs text-zinc-500">Fill in variables:</p>
              {selectedTemplate.variables.map((v) => (
                <div key={v}>
                  <label className="block text-xs text-zinc-400 mb-0.5">{`{{${v}}}`}</label>
                  <input
                    type="text"
                    value={variableValues[v] || ''}
                    onChange={(e) => setVariableValues((prev) => ({ ...prev, [v]: e.target.value }))}
                    placeholder={`Enter ${v.replace(/_/g, ' ')}`}
                    className="w-full px-2 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-violet-500"
                  />
                </div>
              ))}
            </div>
          )}

          {/* Preview */}
          <div className="p-2 bg-black/20 rounded-lg mb-3">
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Preview</p>
            <p className="text-xs text-zinc-300 whitespace-pre-wrap">
              {renderPreview(selectedTemplate)}
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-2">
            <button
              onClick={() => setSelectedTemplate(null)}
              className="px-3 py-1.5 text-xs text-zinc-500 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleInsert}
              className="px-3 py-1.5 bg-violet-500 hover:bg-violet-600 rounded-lg text-xs font-medium text-white transition-colors"
            >
              Insert Template
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
