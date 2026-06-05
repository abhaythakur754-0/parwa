/**
 * PARWA DemoKnowledgeBasePanel — KB Upload & Pre-built Selection
 *
 * Upload documents or select pre-built industry knowledge bases.
 * Matches ORANGE design system.
 */

'use client';

import { useState, useRef } from 'react';
import { Upload, BookOpen, FileText, Check, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DemoKnowledgeBase } from '@/types/demo-variant';
import { uploadKnowledgeBase } from '@/lib/demo-variant-api';

interface DemoKnowledgeBasePanelProps {
  prebuiltKBs: DemoKnowledgeBase[];
  uploadedKBs: DemoKnowledgeBase[];
  selectedKBs: string[];
  onSelectKB: (kbId: string) => void;
  onDeselectKB: (kbId: string) => void;
  onUploadComplete?: () => void;
}

export function DemoKnowledgeBasePanel({
  prebuiltKBs,
  uploadedKBs,
  selectedKBs,
  onSelectKB,
  onDeselectKB,
  onUploadComplete,
}: DemoKnowledgeBasePanelProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const result = await uploadKnowledgeBase(file);
      setUploadSuccess(result.message);
      onUploadComplete?.();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const toggleKB = (kbId: string) => {
    if (selectedKBs.includes(kbId)) {
      onDeselectKB(kbId);
    } else {
      onSelectKB(kbId);
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-white/60 flex items-center gap-2">
        <BookOpen className="w-4 h-4 text-orange-400/60" />
        Knowledge Base
      </h3>

      {/* Upload area */}
      <div
        onClick={() => fileInputRef.current?.click()}
        className={cn(
          'relative rounded-xl border-2 border-dashed p-4 text-center cursor-pointer transition-all duration-300',
          isUploading
            ? 'border-orange-500/30 bg-orange-500/5'
            : 'border-white/10 bg-white/[0.02] hover:border-orange-500/30 hover:bg-orange-500/5',
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.csv,.md,.pdf,.json,.docx"
          onChange={handleFileUpload}
          className="sr-only"
        />

        {isUploading ? (
          <div className="flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-orange-400" />
            <span className="text-xs text-orange-300">Processing...</span>
          </div>
        ) : (
          <>
            <Upload className="w-5 h-5 text-white/20 mx-auto mb-2" />
            <p className="text-xs text-white/40">Upload your knowledge base</p>
            <p className="text-[10px] text-white/20 mt-1">.txt, .csv, .md, .pdf, .json, .docx (max 10MB)</p>
          </>
        )}
      </div>

      {/* Upload status */}
      {uploadSuccess && (
        <div className="flex items-center gap-2 p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/10">
          <Check className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-[11px] text-emerald-300">{uploadSuccess}</span>
        </div>
      )}
      {uploadError && (
        <div className="flex items-center gap-2 p-2 rounded-lg bg-red-500/10 border border-red-500/10">
          <span className="text-[11px] text-red-300">{uploadError}</span>
        </div>
      )}

      {/* Pre-built KBs */}
      {prebuiltKBs.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] text-white/30 uppercase tracking-wider font-medium">Pre-built Knowledge Bases</p>
          <div className="space-y-1.5">
            {prebuiltKBs.map((kb) => {
              const isSelected = selectedKBs.includes(kb.id);
              return (
                <button
                  key={kb.id}
                  onClick={() => toggleKB(kb.id)}
                  className={cn(
                    'w-full flex items-center gap-3 p-2.5 rounded-lg border transition-all duration-200 text-left',
                    isSelected
                      ? 'border-orange-500/30 bg-orange-500/10'
                      : 'border-white/[0.04] bg-white/[0.02] hover:border-white/10',
                  )}
                >
                  <FileText className={cn('w-4 h-4 shrink-0', isSelected ? 'text-orange-400' : 'text-white/20')} />
                  <div className="flex-1 min-w-0">
                    <p className={cn('text-xs font-medium', isSelected ? 'text-orange-300' : 'text-white/50')}>
                      {kb.name}
                    </p>
                    <p className="text-[10px] text-white/25 truncate">{kb.description}</p>
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-orange-400 shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Uploaded KBs */}
      {uploadedKBs.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] text-white/30 uppercase tracking-wider font-medium">Your Uploads</p>
          <div className="space-y-1.5">
            {uploadedKBs.map((kb) => {
              const isSelected = selectedKBs.includes(kb.id);
              return (
                <button
                  key={kb.id}
                  onClick={() => toggleKB(kb.id)}
                  className={cn(
                    'w-full flex items-center gap-3 p-2.5 rounded-lg border transition-all duration-200 text-left',
                    isSelected
                      ? 'border-orange-500/30 bg-orange-500/10'
                      : 'border-white/[0.04] bg-white/[0.02] hover:border-white/10',
                  )}
                >
                  <FileText className={cn('w-4 h-4 shrink-0', isSelected ? 'text-orange-400' : 'text-white/20')} />
                  <div className="flex-1 min-w-0">
                    <p className={cn('text-xs font-medium', isSelected ? 'text-orange-300' : 'text-white/50')}>
                      {kb.name}
                    </p>
                    <p className="text-[10px] text-white/25 truncate">{kb.description}</p>
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-orange-400 shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
