"use client";

import { useState } from "react";
import { useOnboardingStore } from "@/store/onboarding-store";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Upload,
  FileText,
  Plus,
  Trash2,
  CheckCircle2,
  Loader2,
  File,
} from "lucide-react";

const SUPPORTED_FORMATS = ["PDF", "DOCX", "TXT", "CSV", "HTML", "JSON", "MD"];

interface FAQEntry {
  id: string;
  question: string;
  answer: string;
  category?: string;
}

interface UploadedDoc {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: string;
}

export function KnowledgeStep() {
  const { setKbUploaded } = useOnboardingStore();
  const [faqs, setFaqs] = useState<FAQEntry[]>([]);
  const [documents, setDocuments] = useState<UploadedDoc[]>([]);
  const [uploading, setUploading] = useState(false);
  const [showFaqForm, setShowFaqForm] = useState(false);
  const [newFaq, setNewFaq] = useState({ question: "", answer: "", category: "" });
  const [saving, setSaving] = useState(false);
  const [complete, setComplete] = useState(false);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files?.length) return;

    setUploading(true);
    const newDocs: UploadedDoc[] = [];

    for (const file of Array.from(files)) {
      const ext = file.name.split(".").pop()?.toUpperCase() || "TXT";
      newDocs.push({
        id: Math.random().toString(36).substr(2, 9),
        filename: file.name,
        file_type: ext,
        file_size: file.size,
        status: "processing",
      });
    }

    setDocuments((prev) => [...prev, ...newDocs]);

    // Simulate processing
    setTimeout(() => {
      setDocuments((prev) =>
        prev.map((d) => (d.status === "processing" ? { ...d, status: "ready" } : d))
      );
      setUploading(false);
    }, 1500);
  };

  const addFaq = () => {
    if (!newFaq.question || !newFaq.answer) return;
    setFaqs((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).substr(2, 9),
        ...newFaq,
      },
    ]);
    setNewFaq({ question: "", answer: "", category: "" });
    setShowFaqForm(false);
  };

  const removeFaq = (id: string) => {
    setFaqs((prev) => prev.filter((f) => f.id !== id));
  };

  const removeDoc = (id: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== id));
  };

  const handleComplete = async () => {
    setSaving(true);
    try {
      await fetch("/api/onboarding/complete-step", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ step: 4 }),
      });
      setKbUploaded(true);
      setComplete(true);
    } catch {
      // Error handled silently
    } finally {
      setSaving(false);
    }
  };

  if (complete) {
    return (
      <Card className="border-emerald-200 dark:border-emerald-800">
        <CardContent className="p-8 text-center">
          <CheckCircle2 className="h-12 w-12 text-emerald-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">Knowledge Base Configured</h3>
          <p className="text-sm text-muted-foreground">
            {documents.length} document(s) and {faqs.length} FAQ(s) uploaded. You can add more later.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">Knowledge Base</h2>
        <p className="text-sm text-muted-foreground">
          Upload documents and add FAQs so PARWA can answer customer questions accurately.
        </p>
      </div>

      {/* File Upload */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-sm">Upload Documents</h3>
            <div className="flex gap-1">
              {SUPPORTED_FORMATS.map((f) => (
                <Badge key={f} variant="secondary" className="text-[10px] px-1.5 py-0">
                  {f}
                </Badge>
              ))}
            </div>
          </div>
          <label className="flex flex-col items-center justify-center border-2 border-dashed border-border rounded-lg p-8 cursor-pointer hover:border-emerald-300 hover:bg-emerald-50/50 dark:hover:border-emerald-700 dark:hover:bg-emerald-950/20 transition-colors">
            {uploading ? (
              <Loader2 className="h-8 w-8 text-emerald-500 animate-spin mb-2" />
            ) : (
              <Upload className="h-8 w-8 text-muted-foreground mb-2" />
            )}
            <p className="text-sm font-medium">
              {uploading ? "Uploading..." : "Drag & drop files or click to upload"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Supports PDF, DOCX, TXT, CSV, HTML, JSON, MD
            </p>
            <input
              type="file"
              className="hidden"
              multiple
              accept=".pdf,.docx,.txt,.csv,.html,.json,.md"
              onChange={handleFileUpload}
            />
          </label>

          {/* Uploaded Documents List */}
          {documents.length > 0 && (
            <div className="mt-4 space-y-2">
              {documents.map((doc) => (
                <div key={doc.id} className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                  <div className="flex items-center gap-3">
                    {doc.status === "ready" ? (
                      <FileText className="h-4 w-4 text-emerald-500" />
                    ) : (
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    )}
                    <div>
                      <p className="text-sm font-medium">{doc.filename}</p>
                      <p className="text-xs text-muted-foreground">
                        {(doc.file_size / 1024).toFixed(1)} KB • {doc.file_type}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={doc.status === "ready" ? "default" : "secondary"}
                      className="text-xs"
                    >
                      {doc.status}
                    </Badge>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={() => removeDoc(doc.id)}
                    >
                      <Trash2 className="h-3 w-3 text-destructive" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* FAQ Management */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-sm">FAQ Entries</h3>
            <Button
              variant="outline"
              size="sm"
              className="text-xs"
              onClick={() => setShowFaqForm(true)}
            >
              <Plus className="h-3 w-3 mr-1" />
              Add FAQ
            </Button>
          </div>

          {showFaqForm && (
            <div className="space-y-3 p-4 bg-muted/50 rounded-lg mb-4">
              <Input
                placeholder="Question"
                value={newFaq.question}
                onChange={(e) => setNewFaq((p) => ({ ...p, question: e.target.value }))}
              />
              <Textarea
                placeholder="Answer"
                value={newFaq.answer}
                onChange={(e) => setNewFaq((p) => ({ ...p, answer: e.target.value }))}
                rows={3}
              />
              <Input
                placeholder="Category (optional)"
                value={newFaq.category}
                onChange={(e) => setNewFaq((p) => ({ ...p, category: e.target.value }))}
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={addFaq} className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white">
                  Save FAQ
                </Button>
                <Button size="sm" variant="outline" onClick={() => setShowFaqForm(false)} className="text-xs">
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {faqs.length === 0 && !showFaqForm ? (
            <div className="text-center py-6">
              <File className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No FAQs added yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {faqs.map((faq) => (
                <div key={faq.id} className="flex items-start justify-between p-3 bg-muted/50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium">{faq.question}</p>
                    <p className="text-xs text-muted-foreground mt-1">{faq.answer}</p>
                    {faq.category && (
                      <Badge variant="secondary" className="text-[10px] mt-1">{faq.category}</Badge>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 flex-shrink-0"
                    onClick={() => removeFaq(faq.id)}
                  >
                    <Trash2 className="h-3 w-3 text-destructive" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Complete Step */}
      <div className="flex justify-end">
        <Button
          onClick={handleComplete}
          disabled={saving || (documents.length === 0 && faqs.length === 0)}
          className="bg-gradient-to-r from-emerald-500 to-teal-600 text-white"
        >
          {saving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            "Continue"
          )}
        </Button>
      </div>
    </div>
  );
}
