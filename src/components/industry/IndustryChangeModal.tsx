"use client";

import { useState, useEffect } from "react";
import { AlertTriangle, ArrowRight, Check } from "lucide-react";

interface OutsideIntegration {
  integration_id: string;
  name: string;
  status: string;
  in_new_industry: boolean;
  message?: string;
}

interface PreviewData {
  current_industry: string;
  proposed_industry: string;
  proposed_industry_name: string;
  primary_categories: string[];
  changes: Record<string, string>;
  integrations: {
    recommended: { integration_id: string; name: string; status: string }[];
    outside_industry: OutsideIntegration[];
    total_connected: number;
    total_outside: number;
  };
  warning: string | null;
}

interface IndustryChangeModalProps {
  currentIndustry: string;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (newIndustry: string) => void;
}

const INDUSTRIES = [
  { id: "saas", name: "SaaS", description: "Software as a Service" },
  { id: "ecommerce", name: "E-commerce", description: "Online retail" },
  { id: "logistics", name: "Logistics", description: "Shipping & freight" },
  { id: "other", name: "Other", description: "Shows all integrations" },
];

/**
 * IndustryChangeModal — GAP 10 industry change with preservation guarantees.
 */
export function IndustryChangeModal({
  currentIndustry,
  isOpen,
  onClose,
  onConfirm,
}: IndustryChangeModalProps) {
  const [selectedIndustry, setSelectedIndustry] = useState("");
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [loading, setLoading] = useState(false);
  const [changing, setChanging] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (selectedIndustry && selectedIndustry !== currentIndustry) {
      fetchPreview(selectedIndustry);
    } else {
      setPreview(null);
    }
  }, [selectedIndustry, currentIndustry]);

  const fetchPreview = async (industry: string) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/industry/preview-change", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ industry }),
      });
      const data = await res.json();
      setPreview(data);
    } catch {
      setError("Failed to preview changes");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!selectedIndustry) return;
    setChanging(true);
    try {
      const res = await fetch("/api/industry/change", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ industry: selectedIndustry }),
      });
      if (res.ok) {
        onConfirm(selectedIndustry);
        onClose();
      } else {
        const data = await res.json();
        setError(data.detail || "Failed to change industry");
      }
    } catch {
      setError("Network error");
    } finally {
      setChanging(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-2">Change Industry</h2>
          <p className="text-sm text-gray-600 mb-4">
            Current: <span className="font-medium capitalize">{currentIndustry}</span>
          </p>
          <div className="grid grid-cols-2 gap-3 mb-6">
            {INDUSTRIES.map((ind) => (
              <button
                key={ind.id}
                onClick={() => setSelectedIndustry(ind.id)}
                disabled={ind.id === currentIndustry}
                className={`p-4 rounded-lg border-2 text-left transition-colors ${
                  ind.id === currentIndustry
                    ? "border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed"
                    : ind.id === selectedIndustry
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <p className="font-medium text-gray-900">{ind.name}</p>
                <p className="text-xs text-gray-500">{ind.description}</p>
                {ind.id === currentIndustry && <span className="text-xs text-gray-400 mt-1 block">Current</span>}
              </button>
            ))}
          </div>
          {loading && <div className="text-center py-4 text-sm text-gray-500">Loading preview...</div>}
          {preview && !loading && (
            <div className="space-y-4 mb-6">
              {preview.warning && (
                <div className="bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded-r-md">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 text-yellow-500 mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-yellow-700">{preview.warning}</p>
                  </div>
                </div>
              )}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">What changes:</h3>
                <div className="space-y-2">
                  {Object.entries(preview.changes).map(([key, value]) => (
                    <div key={key} className="flex items-start gap-2">
                      <Check className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                      <div>
                        <span className="text-sm text-gray-600 capitalize">{key.replace(/_/g, " ")}:</span>{" "}
                        <span className="text-sm text-gray-900">{value}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              {preview.integrations.outside_industry.length > 0 && (
                <div className="bg-orange-50 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-orange-800 mb-2">Integrations outside {preview.proposed_industry_name}:</h3>
                  <div className="space-y-1">
                    {preview.integrations.outside_industry.map((i) => (
                      <div key={i.integration_id} className="flex items-center gap-2 text-sm">
                        <ArrowRight className="h-3 w-3 text-orange-400" />
                        <span className="text-gray-900">{i.name}</span>
                        <span className="text-xs text-orange-600">({i.message})</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {error && <p className="text-sm text-red-600 mb-4">{error}</p>}
          <div className="flex items-center justify-end gap-3">
            <button onClick={onClose} className="px-4 py-2 text-sm text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors">Cancel</button>
            <button onClick={handleConfirm} disabled={!selectedIndustry || selectedIndustry === currentIndustry || changing} className="px-6 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
              {changing ? "Changing..." : "Confirm Change"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
