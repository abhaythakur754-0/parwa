'use client';

import React from 'react';
import { Building2, ChevronDown } from 'lucide-react';
import { Industry } from '@/types/onboarding';
import { cn } from '@/lib/utils';

/**
 * Industry option configuration.
 */
const INDUSTRY_OPTIONS: { value: Industry; label: string; icon: string }[] = [
  { value: 'saas', label: 'SaaS / Software', icon: '💻' },
  { value: 'ecommerce', label: 'E-commerce', icon: '🛒' },
  { value: 'healthcare', label: 'Healthcare', icon: '🏥' },
  { value: 'finance', label: 'Finance / Banking', icon: '🏦' },
  { value: 'education', label: 'Education', icon: '🎓' },
  { value: 'real_estate', label: 'Real Estate', icon: '🏠' },
  { value: 'manufacturing', label: 'Manufacturing', icon: '🏭' },
  { value: 'consulting', label: 'Consulting', icon: '💼' },
  { value: 'agency', label: 'Agency / Marketing', icon: '📱' },
  { value: 'nonprofit', label: 'Non-profit', icon: '❤️' },
  { value: 'other', label: 'Other', icon: '📋' },
];

interface IndustrySelectProps {
  value: Industry | '';
  onChange: (value: Industry) => void;
  error?: string;
  disabled?: boolean;
  required?: boolean;
  className?: string;
}

/**
 * IndustrySelect Component
 * 
 * A custom select component for choosing industry type.
 * Features:
 * - Custom styled dropdown with icons
 * - Error state styling
 * - Disabled state
 * - Keyboard navigation
 */
export function IndustrySelect({
  value,
  onChange,
  error,
  disabled = false,
  required = true,
  className,
}: IndustrySelectProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const selectRef = React.useRef<HTMLDivElement>(null);
  
  // Close dropdown when clicking outside
  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (selectRef.current && !selectRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  
  // Handle keyboard navigation
  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (disabled) return;
    
    switch (event.key) {
      case 'Enter':
      case ' ':
        event.preventDefault();
        setIsOpen(!isOpen);
        break;
      case 'Escape':
        setIsOpen(false);
        break;
      case 'ArrowDown':
        event.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
        } else {
          const currentIndex = INDUSTRY_OPTIONS.findIndex(opt => opt.value === value);
          const nextIndex = Math.min(currentIndex + 1, INDUSTRY_OPTIONS.length - 1);
          onChange(INDUSTRY_OPTIONS[nextIndex].value);
        }
        break;
      case 'ArrowUp':
        event.preventDefault();
        if (isOpen) {
          const currentIndex = INDUSTRY_OPTIONS.findIndex(opt => opt.value === value);
          const prevIndex = Math.max(currentIndex - 1, 0);
          onChange(INDUSTRY_OPTIONS[prevIndex].value);
        }
        break;
    }
  };
  
  const selectedOption = INDUSTRY_OPTIONS.find(opt => opt.value === value);
  
  return (
    <div className={cn('relative', className)} ref={selectRef}>
      <label className="label">
        Industry {required && <span className="text-error-500">*</span>}
      </label>
      
      {/* Select Trigger */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        className={cn(
          'input flex items-center justify-between text-left',
          error && 'input-error',
          disabled && 'opacity-50 cursor-not-allowed bg-secondary-100',
          isOpen && 'ring-2 ring-primary-500'
        )}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-labelledby="industry-label"
      >
        <span className={cn(
          'flex items-center gap-2',
          !selectedOption && 'text-secondary-400'
        )}>
          {selectedOption ? (
            <>
              <span className="text-lg">{selectedOption.icon}</span>
              <span>{selectedOption.label}</span>
            </>
          ) : (
            <>
              <Building2 className="w-5 h-5" />
              <span>Select your industry</span>
            </>
          )}
        </span>
        <ChevronDown className={cn(
          'w-5 h-5 text-secondary-400 transition-transform duration-200',
          isOpen && 'transform rotate-180'
        )} />
      </button>
      
      {/* Dropdown Menu */}
      {isOpen && (
        <div
          className="absolute z-10 mt-1 w-full bg-white rounded-lg border border-secondary-200 shadow-lg max-h-60 overflow-auto animate-in"
          role="listbox"
          aria-labelledby="industry-label"
        >
          {INDUSTRY_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => {
                onChange(option.value);
                setIsOpen(false);
              }}
              className={cn(
                'w-full px-4 py-2.5 text-left flex items-center gap-2 hover:bg-primary-50 transition-colors',
                value === option.value && 'bg-primary-100 text-primary-700'
              )}
              role="option"
              aria-selected={value === option.value}
            >
              <span className="text-lg">{option.icon}</span>
              <span>{option.label}</span>
            </button>
          ))}
        </div>
      )}
      
      {/* Error Message */}
      {error && (
        <p className="error-text">{error}</p>
      )}
    </div>
  );
}

export default IndustrySelect;
