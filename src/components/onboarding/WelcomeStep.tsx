'use client';

import React from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Sparkles,
  ArrowRight,
  Loader2,
  User,
  Building2,
  Globe,
  Mail,
  Users,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import { userDetailsApi, getErrorMessage } from '@/lib/api';
import { Industry, CompanySize, UserDetails } from '@/types/onboarding';

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
    'nonprofit', 'logistics', 'hospitality', 'retail', 'other',
  ] as const),
  company_size: z.enum([
    '1_10', '11_50', '51_200', '201_500', '501_1000', '1000_plus',
  ] as const).optional(),
  website: z
    .string()
    .url('Please enter a valid URL')
    .optional()
    .or(z.literal('')),
});

type DetailsFormData = z.infer<typeof detailsFormSchema>;

const INDUSTRY_OPTIONS: { value: Industry; label: string }[] = [
  { value: 'saas', label: 'SaaS / Software' },
  { value: 'ecommerce', label: 'E-commerce' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'finance', label: 'Finance / Banking' },
  { value: 'education', label: 'Education' },
  { value: 'real_estate', label: 'Real Estate' },
  { value: 'manufacturing', label: 'Manufacturing' },
  { value: 'consulting', label: 'Consulting' },
  { value: 'agency', label: 'Agency / Marketing' },
  { value: 'nonprofit', label: 'Non-profit' },
  { value: 'logistics', label: 'Logistics' },
  { value: 'hospitality', label: 'Hospitality' },
  { value: 'retail', label: 'Retail' },
  { value: 'other', label: 'Other' },
];

const COMPANY_SIZE_OPTIONS: { value: CompanySize; label: string }[] = [
  { value: '1_10', label: '1-10 employees' },
  { value: '11_50', label: '11-50 employees' },
  { value: '51_200', label: '51-200 employees' },
  { value: '201_500', label: '201-500 employees' },
  { value: '501_1000', label: '501-1000 employees' },
  { value: '1000_plus', label: '1000+ employees' },
];

interface WelcomeStepProps {
  onNext: () => void;
}

export function WelcomeStep({ onNext }: WelcomeStepProps) {
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const {
    register,
    control,
    handleSubmit,
    formState: { errors, isValid },
  } = useForm<DetailsFormData>({
    resolver: zodResolver(detailsFormSchema),
    defaultValues: {
      full_name: '',
      company_name: '',
      work_email: '',
      industry: undefined,
      company_size: undefined,
      website: '',
    },
    mode: 'onChange',
  });

  const onFormSubmit = async (data: DetailsFormData) => {
    setIsSubmitting(true);
    try {
      const sanitizedData = {
        full_name: data.full_name.trim(),
        company_name: data.company_name.trim(),
        work_email: data.work_email?.trim() || undefined,
        industry: data.industry,
        company_size: data.company_size,
        website: data.website?.trim() || undefined,
      };

      await userDetailsApi.create(sanitizedData);
      toast.success('Details saved successfully!');
      onNext();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto">
      <div className="text-center mb-10">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-orange-500/10 border border-orange-500/20 mb-6">
          <Sparkles className="w-8 h-8 text-orange-400" />
        </div>
        <h1 className="text-3xl sm:text-4xl font-bold text-white mb-3">
          Welcome to PARWA
        </h1>
        <p className="text-orange-200/50 text-base">
          Let&apos;s set up your AI customer support assistant
        </p>
      </div>

      <form onSubmit={handleSubmit(onFormSubmit)} className="card-parwa p-6 space-y-6">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-white">Tell us about yourself</h2>
          <p className="text-orange-200/50 mt-2">Help us personalize your PARWA experience</p>
        </div>

        <div>
          <label htmlFor="full_name" className="label-parwa">
            Full Name <span className="text-red-400">*</span>
          </label>
          <div className="relative">
            <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-orange-200/30" />
            <input
              id="full_name"
              type="text"
              {...register('full_name')}
              placeholder="John Doe"
              className={cn('input-parwa pl-10', errors.full_name && 'border-red-500/40')}
            />
          </div>
          {errors.full_name && <p className="mt-1 text-sm text-red-400">{errors.full_name.message}</p>}
        </div>

        <div>
          <label htmlFor="company_name" className="label-parwa">
            Company Name <span className="text-red-400">*</span>
          </label>
          <div className="relative">
            <Building2 className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-orange-200/30" />
            <input
              id="company_name"
              type="text"
              {...register('company_name')}
              placeholder="Acme Corporation"
              className={cn('input-parwa pl-10', errors.company_name && 'border-red-500/40')}
            />
          </div>
          {errors.company_name && <p className="mt-1 text-sm text-red-400">{errors.company_name.message}</p>}
        </div>

        <div>
          <label htmlFor="work_email" className="label-parwa">
            Work Email <span className="text-orange-200/30">(optional)</span>
          </label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-orange-200/30" />
            <input
              id="work_email"
              type="email"
              {...register('work_email')}
              placeholder="john@company.com"
              className={cn('input-parwa pl-10', errors.work_email && 'border-red-500/40')}
            />
          </div>
          {errors.work_email && <p className="mt-1 text-sm text-red-400">{errors.work_email.message}</p>}
        </div>

        <Controller
          name="industry"
          control={control}
          render={({ field }) => (
            <div>
              <label htmlFor="industry" className="label-parwa">
                Industry <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <Building2 className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-orange-200/30" />
                <select
                  id="industry"
                  value={field.value || ''}
                  onChange={(e) => field.onChange(e.target.value || undefined)}
                  className={cn('input-parwa pl-10 appearance-none', errors.industry && 'border-red-500/40')}
                >
                  <option value="">Select your industry</option>
                  {INDUSTRY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              {errors.industry && <p className="mt-1 text-sm text-red-400">{errors.industry.message}</p>}
            </div>
          )}
        />

        <div>
          <label htmlFor="company_size" className="label-parwa">
            Company Size <span className="text-orange-200/30">(optional)</span>
          </label>
          <div className="relative">
            <Users className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-orange-200/30" />
            <select
              id="company_size"
              {...register('company_size')}
              className="input-parwa pl-10 appearance-none"
            >
              <option value="">Select company size</option>
              {COMPANY_SIZE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label htmlFor="website" className="label-parwa">
            Website <span className="text-orange-200/30">(optional)</span>
          </label>
          <div className="relative">
            <Globe className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-orange-200/30" />
            <input
              id="website"
              type="url"
              {...register('website')}
              placeholder="https://company.com"
              className={cn('input-parwa pl-10', errors.website && 'border-red-500/40')}
            />
          </div>
          {errors.website && <p className="mt-1 text-sm text-red-400">{errors.website.message}</p>}
        </div>

        <div className="pt-4">
          <button
            type="submit"
            disabled={isSubmitting || !isValid}
            className="btn-primary-parwa w-full py-3"
          >
            {isSubmitting ? (
              <><Loader2 className="w-5 h-5 mr-2 animate-spin" />Saving...</>
            ) : (
              <>Continue<ArrowRight className="w-5 h-5 ml-2" /></>
            )}
          </button>
          <p className="text-center text-xs text-orange-200/25 mt-3">
            Use the Back/Next buttons above to navigate between steps
          </p>
        </div>
      </form>
    </div>
  );
}

export default WelcomeStep;
