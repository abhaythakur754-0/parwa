"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import { Calendar, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";

export interface DateRange {
  start: Date;
  end: Date;
}

export interface DateRangePickerProps {
  value?: DateRange;
  onChange?: (range: DateRange) => void;
  presets?: DateRangePreset[];
  className?: string;
  disabled?: boolean;
}

interface DateRangePreset {
  id: string;
  name: string;
  getRange: () => DateRange;
}

const DEFAULT_PRESETS: DateRangePreset[] = [
  {
    id: "today",
    name: "Today",
    getRange: () => {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      return { start: today, end: today };
    },
  },
  {
    id: "yesterday",
    name: "Yesterday",
    getRange: () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      yesterday.setHours(0, 0, 0, 0);
      return { start: yesterday, end: yesterday };
    },
  },
  {
    id: "last7days",
    name: "Last 7 Days",
    getRange: () => {
      const end = new Date();
      const start = new Date();
      start.setDate(start.getDate() - 6);
      start.setHours(0, 0, 0, 0);
      end.setHours(23, 59, 59, 999);
      return { start, end };
    },
  },
  {
    id: "last30days",
    name: "Last 30 Days",
    getRange: () => {
      const end = new Date();
      const start = new Date();
      start.setDate(start.getDate() - 29);
      start.setHours(0, 0, 0, 0);
      end.setHours(23, 59, 59, 999);
      return { start, end };
    },
  },
  {
    id: "last90days",
    name: "Last 90 Days",
    getRange: () => {
      const end = new Date();
      const start = new Date();
      start.setDate(start.getDate() - 89);
      start.setHours(0, 0, 0, 0);
      end.setHours(23, 59, 59, 999);
      return { start, end };
    },
  },
  {
    id: "thismonth",
    name: "This Month",
    getRange: () => {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), 1);
      const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59, 999);
      return { start, end };
    },
  },
  {
    id: "lastmonth",
    name: "Last Month",
    getRange: () => {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const end = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59, 999);
      return { start, end };
    },
  },
];

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const DAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

export function DateRangePicker({
  value,
  onChange,
  presets = DEFAULT_PRESETS,
  className,
  disabled = false,
}: DateRangePickerProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [viewMonth, setViewMonth] = React.useState(new Date());
  const [tempRange, setTempRange] = React.useState<DateRange | null>(value || null);
  const [selecting, setSelecting] = React.useState<"start" | "end">("start");
  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    setTempRange(value || null);
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

  const formatDate = (date: Date) => {
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  const formatDisplayRange = () => {
    if (!tempRange) return "Select date range";
    return `${formatDate(tempRange.start)} - ${formatDate(tempRange.end)}`;
  };

  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDay = firstDay.getDay();

    const days: (Date | null)[] = [];

    // Add empty slots for days before the first
    for (let i = 0; i < startingDay; i++) {
      days.push(null);
    }

    // Add all days in the month
    for (let i = 1; i <= daysInMonth; i++) {
      days.push(new Date(year, month, i));
    }

    return days;
  };

  const handleDateClick = (date: Date) => {
    if (selecting === "start") {
      setTempRange({ start: date, end: date });
      setSelecting("end");
    } else {
      if (date < tempRange!.start) {
        setTempRange({ start: date, end: tempRange!.start });
      } else {
        setTempRange({ ...tempRange!, end: date });
      }
      setSelecting("start");
    }
  };

  const handlePresetClick = (preset: DateRangePreset) => {
    const range = preset.getRange();
    setTempRange(range);
    setSelecting("start");
  };

  const handleApply = () => {
    if (tempRange) {
      onChange?.(tempRange);
    }
    setIsOpen(false);
  };

  const handleCancel = () => {
    setTempRange(value || null);
    setSelecting("start");
    setIsOpen(false);
  };

  const isDateInRange = (date: Date) => {
    if (!tempRange) return false;
    return date >= tempRange.start && date <= tempRange.end;
  };

  const isDateSelected = (date: Date) => {
    if (!tempRange) return false;
    return (
      date.toDateString() === tempRange.start.toDateString() ||
      date.toDateString() === tempRange.end.toDateString()
    );
  };

  const prevMonth = () => {
    setViewMonth(new Date(viewMonth.getFullYear(), viewMonth.getMonth() - 1, 1));
  };

  const nextMonth = () => {
    setViewMonth(new Date(viewMonth.getFullYear(), viewMonth.getMonth() + 1, 1));
  };

  const days = getDaysInMonth(viewMonth);

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      {/* Trigger */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={cn(
          "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
          "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-50"
        )}
      >
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <span>{formatDisplayRange()}</span>
        </div>
        <ChevronDown className="h-4 w-4 text-muted-foreground" />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 mt-2 bg-background border rounded-lg shadow-lg overflow-hidden">
          <div className="flex">
            {/* Presets */}
            <div className="w-40 border-r bg-muted/30">
              <div className="p-2 border-b">
                <span className="text-xs font-medium text-muted-foreground">Presets</span>
              </div>
              <div className="py-1">
                {presets.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => handlePresetClick(preset)}
                    className={cn(
                      "w-full px-3 py-2 text-sm text-left hover:bg-muted/50 transition-colors",
                      tempRange &&
                        JSON.stringify(preset.getRange().start) ===
                          JSON.stringify(tempRange.start) &&
                        "bg-primary/10 text-primary"
                    )}
                  >
                    {preset.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Calendar */}
            <div className="p-3">
              {/* Header */}
              <div className="flex items-center justify-between mb-3">
                <button
                  type="button"
                  onClick={prevMonth}
                  className="p-1 hover:bg-muted rounded"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="text-sm font-medium">
                  {MONTHS[viewMonth.getMonth()]} {viewMonth.getFullYear()}
                </span>
                <button
                  type="button"
                  onClick={nextMonth}
                  className="p-1 hover:bg-muted rounded"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>

              {/* Days Header */}
              <div className="grid grid-cols-7 gap-1 mb-1">
                {DAYS.map((day) => (
                  <div
                    key={day}
                    className="w-8 h-6 flex items-center justify-center text-xs text-muted-foreground"
                  >
                    {day}
                  </div>
                ))}
              </div>

              {/* Days Grid */}
              <div className="grid grid-cols-7 gap-1">
                {days.map((date, index) => (
                  <div
                    key={index}
                    className="w-8 h-8 flex items-center justify-center"
                  >
                    {date && (
                      <button
                        type="button"
                        onClick={() => handleDateClick(date)}
                        className={cn(
                          "w-7 h-7 rounded text-sm transition-colors",
                          isDateSelected(date)
                            ? "bg-primary text-primary-foreground"
                            : isDateInRange(date)
                            ? "bg-primary/20"
                            : "hover:bg-muted"
                        )}
                      >
                        {date.getDate()}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-2 p-3 border-t bg-muted/30">
            <Button variant="outline" size="sm" onClick={handleCancel}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleApply}>
              Apply
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default DateRangePicker;
