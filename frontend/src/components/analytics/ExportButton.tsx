"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import { Download, FileSpreadsheet, FileText, File, Loader2, Check, X } from "lucide-react";

export type ExportFormat = "csv" | "pdf" | "excel";

export interface ExportButtonProps {
  onExport?: (format: ExportFormat) => Promise<void> | void;
  formats?: ExportFormat[];
  dateRange?: {
    start: Date;
    end: Date;
  };
  disabled?: boolean;
  className?: string;
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg" | "icon";
}

interface ExportOption {
  id: ExportFormat;
  name: string;
  description: string;
  icon: React.ReactNode;
  extension: string;
}

const EXPORT_OPTIONS: ExportOption[] = [
  {
    id: "csv",
    name: "CSV",
    description: "Spreadsheet compatible format",
    icon: <FileSpreadsheet className="h-4 w-4" />,
    extension: ".csv",
  },
  {
    id: "pdf",
    name: "PDF",
    description: "Print-ready document",
    icon: <FileText className="h-4 w-4" />,
    extension: ".pdf",
  },
  {
    id: "excel",
    name: "Excel",
    description: "Microsoft Excel format",
    icon: <File className="h-4 w-4" />,
    extension: ".xlsx",
  },
];

export function ExportButton({
  onExport,
  formats = ["csv", "pdf", "excel"],
  dateRange,
  disabled = false,
  className,
  variant = "outline",
  size = "default",
}: ExportButtonProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [exporting, setExporting] = React.useState<ExportFormat | null>(null);
  const [status, setStatus] = React.useState<"idle" | "success" | "error">("idle");
  const containerRef = React.useRef<HTMLDivElement>(null);

  const availableOptions = EXPORT_OPTIONS.filter((opt) => formats.includes(opt.id));

  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleExport = async (format: ExportFormat) => {
    setExporting(format);
    setStatus("idle");

    try {
      await onExport?.(format);
      setStatus("success");

      // Reset after showing success
      setTimeout(() => {
        setStatus("idle");
        setExporting(null);
        setIsOpen(false);
      }, 2000);
    } catch (error) {
      setStatus("error");
      setTimeout(() => {
        setStatus("idle");
        setExporting(null);
      }, 3000);
    }
  };

  const formatDateRange = () => {
    if (!dateRange) return "";
    const start = dateRange.start.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
    const end = dateRange.end.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
    return `${start} - ${end}`;
  };

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <Button
        variant={variant}
        size={size}
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled || exporting !== null}
      >
        {exporting ? (
          <>
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            Exporting...
          </>
        ) : status === "success" ? (
          <>
            <Check className="h-4 w-4 mr-2 text-green-500" />
            Exported!
          </>
        ) : status === "error" ? (
          <>
            <X className="h-4 w-4 mr-2 text-red-500" />
            Failed
          </>
        ) : (
          <>
            <Download className="h-4 w-4 mr-2" />
            Export
          </>
        )}
      </Button>

      {isOpen && (
        <div className="absolute z-50 right-0 mt-2 w-64 bg-background border rounded-lg shadow-lg overflow-hidden">
          {/* Date Range Header */}
          {dateRange && (
            <div className="px-4 py-2 bg-muted/50 border-b text-sm text-muted-foreground">
              Date Range: {formatDateRange()}
            </div>
          )}

          {/* Export Options */}
          <div className="py-1">
            {availableOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => handleExport(option.id)}
                disabled={exporting !== null}
                className={cn(
                  "w-full px-4 py-3 flex items-center gap-3 text-left",
                  "hover:bg-muted/50 transition-colors",
                  "disabled:opacity-50 disabled:cursor-not-allowed"
                )}
              >
                <div
                  className={cn(
                    "p-2 rounded",
                    exporting === option.id
                      ? "bg-primary/10"
                      : "bg-muted"
                  )}
                >
                  {exporting === option.id ? (
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  ) : (
                    option.icon
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium flex items-center gap-2">
                    {option.name}
                    {status === "success" && exporting === option.id && (
                      <Check className="h-3 w-3 text-green-500" />
                    )}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {option.description}
                  </p>
                </div>
              </button>
            ))}
          </div>

          {/* Footer */}
          <div className="px-4 py-2 bg-muted/30 border-t text-xs text-muted-foreground text-center">
            Click to download file
          </div>
        </div>
      )}
    </div>
  );
}

export default ExportButton;
