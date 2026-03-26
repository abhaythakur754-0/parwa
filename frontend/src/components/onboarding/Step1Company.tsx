"use client";

import * as React from "react";
import { cn } from "@/utils/utils";

interface Step1CompanyProps {
  data: {
    companyName: string;
    industry: string;
    companySize: string;
    website: string;
  };
  updateData: (updates: Partial<{
    companyName: string;
    industry: string;
    companySize: string;
    website: string;
  }>) => void;
  onValidate?: (isValid: boolean) => void;
}

const industries = [
  { value: "ecommerce", label: "E-commerce" },
  { value: "saas", label: "SaaS / Software" },
  { value: "healthcare", label: "Healthcare" },
  { value: "logistics", label: "Logistics & Shipping" },
  { value: "finance", label: "Finance & Banking" },
  { value: "education", label: "Education" },
  { value: "retail", label: "Retail" },
  { value: "hospitality", label: "Hospitality & Travel" },
  { value: "manufacturing", label: "Manufacturing" },
  { value: "other", label: "Other" },
];

const companySizes = [
  { value: "1-10", label: "1-10 employees" },
  { value: "11-50", label: "11-50 employees" },
  { value: "51-200", label: "51-200 employees" },
  { value: "201-500", label: "201-500 employees" },
  { value: "501-1000", label: "501-1000 employees" },
  { value: "1000+", label: "1000+ employees" },
];

export function Step1Company({ data, updateData, onValidate }: Step1CompanyProps) {
  const [errors, setErrors] = React.useState<Record<string, string>>({});

  React.useEffect(() => {
    const newErrors: Record<string, string> = {};

    if (data.companyName && data.companyName.length < 2) {
      newErrors.companyName = "Company name must be at least 2 characters";
    }

    if (data.website && !isValidUrl(data.website)) {
      newErrors.website = "Please enter a valid URL";
    }

    setErrors(newErrors);
    onValidate?.(Object.keys(newErrors).length === 0);
  }, [data, onValidate]);

  const isValidUrl = (url: string): boolean => {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center mb-6">
        <h2 className="text-lg font-semibold">Tell us about your company</h2>
        <p className="text-sm text-muted-foreground">
          This helps us customize your PARWA experience
        </p>
      </div>

      {/* Company Name */}
      <div className="space-y-2">
        <label htmlFor="companyName" className="text-sm font-medium">
          Company Name <span className="text-destructive">*</span>
        </label>
        <input
          id="companyName"
          type="text"
          placeholder="Acme Inc."
          value={data.companyName}
          onChange={(e) => updateData({ companyName: e.target.value })}
          className={cn(
            "flex h-10 w-full rounded-md border bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            errors.companyName ? "border-destructive" : "border-input"
          )}
        />
        {errors.companyName && (
          <p className="text-sm text-destructive">{errors.companyName}</p>
        )}
      </div>

      {/* Industry */}
      <div className="space-y-2">
        <label htmlFor="industry" className="text-sm font-medium">
          Industry <span className="text-destructive">*</span>
        </label>
        <select
          id="industry"
          value={data.industry}
          onChange={(e) => updateData({ industry: e.target.value })}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <option value="">Select an industry</option>
          {industries.map((industry) => (
            <option key={industry.value} value={industry.value}>
              {industry.label}
            </option>
          ))}
        </select>
      </div>

      {/* Company Size */}
      <div className="space-y-2">
        <label htmlFor="companySize" className="text-sm font-medium">
          Company Size <span className="text-destructive">*</span>
        </label>
        <select
          id="companySize"
          value={data.companySize}
          onChange={(e) => updateData({ companySize: e.target.value })}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <option value="">Select company size</option>
          {companySizes.map((size) => (
            <option key={size.value} value={size.value}>
              {size.label}
            </option>
          ))}
        </select>
      </div>

      {/* Website */}
      <div className="space-y-2">
        <label htmlFor="website" className="text-sm font-medium">
          Website <span className="text-muted-foreground">(optional)</span>
        </label>
        <input
          id="website"
          type="url"
          placeholder="https://example.com"
          value={data.website}
          onChange={(e) => updateData({ website: e.target.value })}
          className={cn(
            "flex h-10 w-full rounded-md border bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            errors.website ? "border-destructive" : "border-input"
          )}
        />
        {errors.website && (
          <p className="text-sm text-destructive">{errors.website}</p>
        )}
      </div>
    </div>
  );
}

export default Step1Company;
