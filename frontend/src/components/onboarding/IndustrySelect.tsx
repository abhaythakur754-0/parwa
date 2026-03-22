"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import { Check, ChevronDown, Building2 } from "lucide-react";

export interface IndustryPreset {
  id: string;
  name: string;
  description: string;
  icon: string;
  faqCount: number;
  workflowCount: number;
  features: string[];
}

export interface IndustrySelectProps {
  value?: string;
  onChange?: (value: string, preset: IndustryPreset | null) => void;
  className?: string;
  disabled?: boolean;
}

const INDUSTRY_PRESETS: IndustryPreset[] = [
  {
    id: "ecommerce",
    name: "E-commerce",
    description: "Online retail and marketplace businesses",
    icon: "🛒",
    faqCount: 45,
    workflowCount: 12,
    features: [
      "Order tracking workflows",
      "Refund automation",
      "Product FAQ templates",
      "Cart abandonment handling",
    ],
  },
  {
    id: "saas",
    name: "SaaS",
    description: "Software as a Service companies",
    icon: "💻",
    faqCount: 38,
    workflowCount: 10,
    features: [
      "Subscription management",
      "Trial conversion flows",
      "Feature request handling",
      "Technical support templates",
    ],
  },
  {
    id: "healthcare",
    name: "Healthcare",
    description: "Medical practices and health services",
    icon: "🏥",
    faqCount: 52,
    workflowCount: 15,
    features: [
      "HIPAA-compliant workflows",
      "Appointment scheduling",
      "Insurance verification",
      "Patient intake forms",
    ],
  },
  {
    id: "logistics",
    name: "Logistics",
    description: "Shipping, delivery, and supply chain",
    icon: "🚚",
    faqCount: 40,
    workflowCount: 14,
    features: [
      "Shipment tracking",
      "Delivery notifications",
      "Route optimization",
      "Inventory management",
    ],
  },
  {
    id: "finance",
    name: "Finance",
    description: "Banking, fintech, and financial services",
    icon: "💰",
    faqCount: 48,
    workflowCount: 16,
    features: [
      "Transaction inquiries",
      "Account management",
      "Fraud detection alerts",
      "Loan application flows",
    ],
  },
  {
    id: "other",
    name: "Other",
    description: "Custom industry configuration",
    icon: "⚙️",
    faqCount: 0,
    workflowCount: 0,
    features: [
      "Start from scratch",
      "Custom FAQ creation",
      "Flexible workflows",
      "Manual configuration",
    ],
  },
];

export function IndustrySelect({
  value,
  onChange,
  className,
  disabled = false,
}: IndustrySelectProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [selectedId, setSelectedId] = React.useState<string | undefined>(value);
  const containerRef = React.useRef<HTMLDivElement>(null);

  const selectedPreset = INDUSTRY_PRESETS.find((p) => p.id === selectedId);

  React.useEffect(() => {
    setSelectedId(value);
  }, [value]);

  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (preset: IndustryPreset) => {
    setSelectedId(preset.id);
    setIsOpen(false);
    onChange?.(preset.id, preset);
  };

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={cn(
          "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm ring-offset-background",
          "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-50",
          isOpen && "ring-2 ring-ring ring-offset-2"
        )}
      >
        <div className="flex items-center gap-2">
          {selectedPreset ? (
            <>
              <span className="text-lg">{selectedPreset.icon}</span>
              <span className="font-medium">{selectedPreset.name}</span>
            </>
          ) : (
            <>
              <Building2 className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">Select your industry</span>
            </>
          )}
        </div>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform",
            isOpen && "transform rotate-180"
          )}
        />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-2 bg-background border rounded-lg shadow-lg overflow-hidden">
          <div className="max-h-80 overflow-y-auto">
            {INDUSTRY_PRESETS.map((preset) => (
              <div
                key={preset.id}
                onClick={() => handleSelect(preset)}
                className={cn(
                  "p-4 cursor-pointer transition-colors",
                  "hover:bg-muted/50",
                  selectedId === preset.id && "bg-primary/5"
                )}
              >
                <div className="flex items-start gap-3">
                  <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-muted text-xl">
                    {preset.icon}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium">{preset.name}</p>
                      {selectedId === preset.id && (
                        <Check className="h-4 w-4 text-primary" />
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {preset.description}
                    </p>

                    {preset.faqCount > 0 && (
                      <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                        <span>{preset.faqCount} FAQs</span>
                        <span>{preset.workflowCount} workflows</span>
                      </div>
                    )}

                    {/* Preview Features */}
                    {selectedId === preset.id && (
                      <div className="mt-3 pt-3 border-t">
                        <p className="text-xs font-medium text-muted-foreground mb-2">
                          Includes:
                        </p>
                        <ul className="space-y-1">
                          {preset.features.map((feature, index) => (
                            <li
                              key={index}
                              className="text-xs flex items-center gap-2"
                            >
                              <Check className="h-3 w-3 text-green-500" />
                              {feature}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Selected Preview */}
      {selectedPreset && !isOpen && selectedPreset.faqCount > 0 && (
        <div className="mt-4 p-4 rounded-lg bg-muted/50">
          <p className="text-sm font-medium mb-2">Configuration Preview</p>
          <div className="flex gap-6 text-sm">
            <div>
              <span className="text-2xl font-bold text-primary">
                {selectedPreset.faqCount}
              </span>
              <p className="text-xs text-muted-foreground">Sample FAQs</p>
            </div>
            <div>
              <span className="text-2xl font-bold text-primary">
                {selectedPreset.workflowCount}
              </span>
              <p className="text-xs text-muted-foreground">Workflows</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export { INDUSTRY_PRESETS };

export default IndustrySelect;
