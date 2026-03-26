"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import { Upload, RotateCcw, Palette, Image, Check } from "lucide-react";

export interface BrandingConfig {
  logo?: string | null;
  primaryColor: string;
  secondaryColor: string;
  companyName?: string;
}

export interface BrandingSetupProps {
  value?: BrandingConfig;
  onChange?: (config: BrandingConfig) => void;
  className?: string;
  disabled?: boolean;
}

const DEFAULT_CONFIG: BrandingConfig = {
  logo: null,
  primaryColor: "#3b82f6", // blue-500
  secondaryColor: "#64748b", // slate-500
};

const PRESET_COLORS = [
  { name: "Blue", primary: "#3b82f6", secondary: "#64748b" },
  { name: "Green", primary: "#22c55e", secondary: "#6b7280" },
  { name: "Purple", primary: "#a855f7", secondary: "#71717a" },
  { name: "Orange", primary: "#f97316", secondary: "#78716c" },
  { name: "Red", primary: "#ef4444", secondary: "#71717a" },
  { name: "Teal", primary: "#14b8a6", secondary: "#6b7280" },
];

export function BrandingSetup({
  value = DEFAULT_CONFIG,
  onChange,
  className,
  disabled = false,
}: BrandingSetupProps) {
  const [config, setConfig] = React.useState<BrandingConfig>(value);
  const [isDragging, setIsDragging] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    setConfig(value);
  }, [value]);

  const updateConfig = (updates: Partial<BrandingConfig>) => {
    const newConfig = { ...config, ...updates };
    setConfig(newConfig);
    onChange?.(newConfig);
  };

  const handleLogoUpload = (file: File) => {
    if (!file.type.startsWith("image/")) {
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      updateConfig({ logo: e.target?.result as string });
    };
    reader.readAsDataURL(file);
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (disabled) return;

    const file = e.dataTransfer.files[0];
    if (file) {
      handleLogoUpload(file);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleLogoUpload(file);
    }
  };

  const removeLogo = () => {
    updateConfig({ logo: null });
  };

  const resetToDefaults = () => {
    setConfig(DEFAULT_CONFIG);
    onChange?.(DEFAULT_CONFIG);
  };

  return (
    <div className={cn("space-y-6", className)}>
      {/* Logo Upload */}
      <div className="space-y-3">
        <label className="text-sm font-medium flex items-center gap-2">
          <Image className="h-4 w-4" />
          Company Logo
        </label>

        <div
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={() => !disabled && !config.logo && fileInputRef.current?.click()}
          className={cn(
            "relative border-2 border-dashed rounded-lg p-6 text-center transition-all",
            config.logo ? "border-primary/30 bg-primary/5" : "cursor-pointer",
            isDragging && "border-primary bg-primary/5",
            disabled && "opacity-50 cursor-not-allowed"
          )}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileInput}
            className="hidden"
            disabled={disabled}
          />

          {config.logo ? (
            <div className="flex flex-col items-center gap-3">
              <img
                src={config.logo}
                alt="Company logo"
                className="h-20 w-auto object-contain rounded"
              />
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                  disabled={disabled}
                >
                  Replace
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeLogo();
                  }}
                  disabled={disabled}
                >
                  Remove
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                <Upload className="h-5 w-5 text-muted-foreground" />
              </div>
              <p className="text-sm text-muted-foreground">
                Drag and drop your logo or click to browse
              </p>
              <p className="text-xs text-muted-foreground">
                PNG, JPG, SVG (max 2MB)
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Color Pickers */}
      <div className="space-y-4">
        <label className="text-sm font-medium flex items-center gap-2">
          <Palette className="h-4 w-4" />
          Brand Colors
        </label>

        <div className="grid sm:grid-cols-2 gap-4">
          {/* Primary Color */}
          <div className="space-y-2">
            <label className="text-xs text-muted-foreground">Primary Color</label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={config.primaryColor}
                onChange={(e) => updateConfig({ primaryColor: e.target.value })}
                disabled={disabled}
                className="w-10 h-10 rounded-md border cursor-pointer disabled:opacity-50"
              />
              <input
                type="text"
                value={config.primaryColor}
                onChange={(e) => updateConfig({ primaryColor: e.target.value })}
                disabled={disabled}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm uppercase disabled:opacity-50"
              />
            </div>
          </div>

          {/* Secondary Color */}
          <div className="space-y-2">
            <label className="text-xs text-muted-foreground">Secondary Color</label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={config.secondaryColor}
                onChange={(e) => updateConfig({ secondaryColor: e.target.value })}
                disabled={disabled}
                className="w-10 h-10 rounded-md border cursor-pointer disabled:opacity-50"
              />
              <input
                type="text"
                value={config.secondaryColor}
                onChange={(e) => updateConfig({ secondaryColor: e.target.value })}
                disabled={disabled}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm uppercase disabled:opacity-50"
              />
            </div>
          </div>
        </div>

        {/* Color Presets */}
        <div className="space-y-2">
          <label className="text-xs text-muted-foreground">Presets</label>
          <div className="flex flex-wrap gap-2">
            {PRESET_COLORS.map((preset) => (
              <button
                key={preset.name}
                type="button"
                onClick={() =>
                  !disabled &&
                  updateConfig({
                    primaryColor: preset.primary,
                    secondaryColor: preset.secondary,
                  })
                }
                disabled={disabled}
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs transition-all",
                  "hover:border-primary/50 disabled:opacity-50",
                  config.primaryColor === preset.primary &&
                    "border-primary bg-primary/5"
                )}
              >
                <span
                  className="w-4 h-4 rounded-full"
                  style={{ backgroundColor: preset.primary }}
                />
                {preset.name}
                {config.primaryColor === preset.primary && (
                  <Check className="h-3 w-3 text-primary" />
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Preview */}
      <div className="space-y-3">
        <label className="text-sm font-medium">Preview</label>
        <div
          className="rounded-lg border p-4 space-y-4"
          style={{ borderColor: config.secondaryColor }}
        >
          {/* Header Preview */}
          <div
            className="flex items-center gap-3 p-3 rounded-lg"
            style={{ backgroundColor: config.primaryColor + "10" }}
          >
            {config.logo ? (
              <img
                src={config.logo}
                alt="Logo preview"
                className="h-8 w-auto object-contain"
              />
            ) : (
              <div
                className="h-8 w-8 rounded flex items-center justify-center text-white font-bold text-sm"
                style={{ backgroundColor: config.primaryColor }}
              >
                {config.companyName?.charAt(0) || "A"}
              </div>
            )}
            <span className="font-semibold" style={{ color: config.primaryColor }}>
              {config.companyName || "Your Company"}
            </span>
          </div>

          {/* Button Preview */}
          <div className="flex gap-2">
            <button
              className="px-4 py-2 rounded-md text-white text-sm font-medium"
              style={{ backgroundColor: config.primaryColor }}
            >
              Primary Button
            </button>
            <button
              className="px-4 py-2 rounded-md border text-sm font-medium"
              style={{
                borderColor: config.secondaryColor,
                color: config.secondaryColor,
              }}
            >
              Secondary
            </button>
          </div>

          {/* Text Preview */}
          <div className="space-y-1">
            <p className="text-sm font-medium">Regular text color</p>
            <p className="text-sm" style={{ color: config.secondaryColor }}>
              Secondary text color
            </p>
          </div>
        </div>
      </div>

      {/* Reset Button */}
      <Button
        variant="outline"
        onClick={resetToDefaults}
        disabled={disabled}
        className="w-full"
      >
        <RotateCcw className="h-4 w-4 mr-2" />
        Reset to Defaults
      </Button>
    </div>
  );
}

export default BrandingSetup;
