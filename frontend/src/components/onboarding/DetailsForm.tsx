'use client';

import React from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { User, Building2, Globe, Mail, Users, ArrowRight, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';

import { cn } from '@/lib/utils';
import { 
  sanitizeInput, 
  sanitizeUrl, 
  validateEmail,
  saveFormDataToStorage,
  loadFormDataFromStorage,
  clearFormDataFromStorage 
} from '@/lib/utils';
import { userDetailsApi, getErrorMessage } from '@/lib/api';
import { Industry, CompanySize, UserDetails } from '@/types/onboarding';
import { IndustrySelect } from './IndustrySelect';
import { WorkEmailVerification } from './WorkEmailVerification';

/**
 * Form validation schema.
 */
const detailsFormSchema = z.object({
  full_name: z
    .string()
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name is too long'),
  company_name: z
    .string()
    .min(2, 'Company name must be at least 2 characters')
    .max(100, 'Company name is too long'),
  work_email: z
    .string()
    .email('Please enter a valid email address')
    .optional()
    .or(z.literal('')),
  industry: z.enum([
    'saas', 'ecommerce', 'healthcare', 'finance', 'education',
    'real_estate', 'manufacturing', 'consulting', 'agency',
    'nonprofit', 'other'
  ] as const),
  company_size: z.enum([
    '1_10', '11_50', '51_200', '201_500', '501_1000', '1000_plus'
  ] as const).optional(),
  website: z
    .string()
    .url('Please enter a valid URL')
    .optional()
    .or(z.literal('')),
});

type DetailsFormData = z.infer<typeof detailsFormSchema>;

interface DetailsFormProps {
  initialData?: UserDetails | null;
  onSubmit?: (data: UserDetails) => void;
  onNext?: () => void;
  className?: string;
}

/**
 * Company size options.
 */
const COMPANY_SIZE_OPTIONS: { value: CompanySize; label: string }[] = [
  { value: '1_10', label: '1-10 employees' },
  { value: '11_50', label: '11-50 employees' },
  { value: '51_200', label: '51-200 employees' },
  { value: '201_500', label: '201-500 employees' },
  { value: '501_1000', label: '501-1000 employees' },
  { value: '1000_plus', label: '1000+ employees' },
];

/**
 * DetailsForm Component
 * 
 * Post-payment details collection form.
 * Features:
 * - Full name and company name (required)
 * - Work email with verification (optional)
 * - Industry selection (required)
 * - Company size (optional)
 * - Website (optional)
 * 
 * Security Features (GAP-001, GAP-007):
 * - XSS sanitization on all inputs
 * - localStorage persistence for form state
 * - Safe API error handling
 */
export function DetailsForm({
  initialData,
  onSubmit,
  onNext,
  className,
}: DetailsFormProps) {
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [savedData, setSavedData] = React.useState<UserDetails | null>(initialData || null);
  
  // Load saved form data from localStorage (GAP-007)
  const storedData = React.useMemo(() => loadFormDataFromStorage<Partial<DetailsFormData>>(), []);
  
  const {
    register,
    control,
    handleSubmit,
    watch,
    formState: { errors, isValid },
  } = useForm<DetailsFormData>({
    resolver: zodResolver(detailsFormSchema),
    defaultValues: {
      full_name: initialData?.full_name || storedData?.full_name || '',
      company_name: initialData?.company_name || storedData?.company_name || '',
      work_email: initialData?.work_email || storedData?.work_email || '',
      industry: initialData?.industry as Industry || storedData?.industry as Industry || undefined,
      company_size: initialData?.company_size as CompanySize || storedData?.company_size as CompanySize || undefined,
      website: initialData?.website || storedData?.website || '',
    },
    mode: 'onChange',
  });
  
  const workEmail = watch('work_email');
  
  // Save form data to localStorage whenever it changes (GAP-007)
  React.useEffect(() => {
    const subscription = watch((value) => {
      saveFormDataToStorage(value as Record<string, unknown>);
    });
    return () => subscription.unsubscribe();
  }, [watch]);
  
  /**
   * Handle form submission with sanitization (GAP-001).
   */
  const onFormSubmit = async (data: DetailsFormData) => {
    setIsSubmitting(true);
    
    try {
      // Sanitize all inputs before sending to API (GAP-001)
      const sanitizedData = {
        full_name: sanitizeInput(data.full_name),
        company_name: sanitizeInput(data.company_name),
        work_email: data.work_email ? validateEmail(data.work_email).sanitized : undefined,
        industry: data.industry,
        company_size: data.company_size,
        website: data.website ? sanitizeUrl(data.website) : undefined,
      };
      
      // Validate email format if provided
      if (data.work_email) {
        const emailValidation = validateEmail(data.work_email);
        if (!emailValidation.isValid) {
          toast.error('Please enter a valid email address');
          setIsSubmitting(false);
          return;
        }
      }
      
      const response = await userDetailsApi.create(sanitizedData);
      
      // Clear localStorage after successful submission (GAP-007)
      clearFormDataFromStorage();
      
      setSavedData(response);
      toast.success('Details saved successfully!');
      
      onSubmit?.(response);
      onNext?.();
    } catch (error) {
      // Use safe error message handling (GAP-002)
      const errorMessage = getErrorMessage(error);
      console.error('Failed to save details:', error);
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };
  
  return (
    <form onSubmit={handleSubmit(onFormSubmit)} className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-secondary-900">
          Tell us about yourself
        </h2>
        <p className="text-secondary-500 mt-2">
          Help us personalize your PARWA experience
        </p>
      </div>
      
      {/* Full Name */}
      <div className="form-group">
        <label htmlFor="full_name" className="label">
          Full Name <span className="text-error-500">*</span>
        </label>
        <div className="relative">
          <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
          <input
            id="full_name"
            type="text"
            {...register('full_name')}
            placeholder="John Doe"
            className={cn('input pl-10', errors.full_name && 'input-error')}
          />
        </div>
        {errors.full_name && (
          <p className="error-text">{errors.full_name.message}</p>
        )}
      </div>
      
      {/* Company Name */}
      <div className="form-group">
        <label htmlFor="company_name" className="label">
          Company Name <span className="text-error-500">*</span>
        </label>
        <div className="relative">
          <Building2 className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
          <input
            id="company_name"
            type="text"
            {...register('company_name')}
            placeholder="Acme Corporation"
            className={cn('input pl-10', errors.company_name && 'input-error')}
          />
        </div>
        {errors.company_name && (
          <p className="error-text">{errors.company_name.message}</p>
        )}
      </div>
      
      {/* Work Email */}
      <div className="form-group">
        <label htmlFor="work_email" className="label">
          Work Email <span className="text-secondary-400">(optional)</span>
        </label>
        <div className="relative">
          <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
          <input
            id="work_email"
            type="email"
            {...register('work_email')}
            placeholder="john@company.com"
            className={cn('input pl-10', errors.work_email && 'input-error')}
          />
        </div>
        {errors.work_email && (
          <p className="error-text">{errors.work_email.message}</p>
        )}
        
        {/* Email Verification Status */}
        {savedData?.work_email && (
          <div className="mt-3">
            <WorkEmailVerification
              workEmail={savedData.work_email}
              isVerified={savedData.work_email_verified}
            />
          </div>
        )}
      </div>
      
      {/* Industry */}
      <Controller
        name="industry"
        control={control}
        render={({ field }) => (
          <IndustrySelect
            value={field.value || ''}
            onChange={field.onChange}
            error={errors.industry?.message}
          />
        )}
      />
      
      {/* Company Size */}
      <div className="form-group">
        <label htmlFor="company_size" className="label">
          Company Size <span className="text-secondary-400">(optional)</span>
        </label>
        <div className="relative">
          <Users className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
          <select
            id="company_size"
            {...register('company_size')}
            className={cn('input pl-10 appearance-none', errors.company_size && 'input-error')}
          >
            <option value="">Select company size</option>
            {COMPANY_SIZE_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        {errors.company_size && (
          <p className="error-text">{errors.company_size.message}</p>
        )}
      </div>
      
      {/* Website */}
      <div className="form-group">
        <label htmlFor="website" className="label">
          Website <span className="text-secondary-400">(optional)</span>
        </label>
        <div className="relative">
          <Globe className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
          <input
            id="website"
            type="url"
            {...register('website')}
            placeholder="https://company.com"
            className={cn('input pl-10', errors.website && 'input-error')}
          />
        </div>
        {errors.website && (
          <p className="error-text">{errors.website.message}</p>
        )}
      </div>
      
      {/* Submit Button */}
      <div className="pt-4">
        <button
          type="submit"
          disabled={isSubmitting || !isValid}
          className="btn-primary btn-lg w-full"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-5 h-5 mr-2 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              Continue
              <ArrowRight className="w-5 h-5 ml-2" />
            </>
          )}
        </button>
      </div>
    </form>
  );
}

export default DetailsForm;
