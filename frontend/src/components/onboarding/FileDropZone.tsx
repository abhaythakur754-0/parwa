'use client';

import React, { useState, useCallback, useRef } from 'react';
import { Upload, UploadCloud } from 'lucide-react';

interface FileDropZoneProps {
  onFilesSelected: (files: File[]) => void;
  acceptedTypes?: string; // e.g. '.pdf,.docx,.doc,.txt,.csv,.md,.json'
  maxSizeBytes?: number; // default 50MB
  maxFiles?: number; // default 10
  disabled?: boolean;
  isUploading?: boolean;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
}

export function FileDropZone({
  onFilesSelected,
  acceptedTypes = '.pdf,.docx,.doc,.txt,.csv,.md,.json',
  maxSizeBytes = 50 * 1024 * 1024,
  maxFiles = 10,
  disabled = false,
  isUploading = false,
}: FileDropZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const dismissError = useCallback(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  const validateFiles = useCallback(
    (files: File[]): File[] => {
      const allowedList = acceptedTypes.split(',').map((t) => t.trim().toLowerCase());
      const valid: File[] = [];
      const errors: string[] = [];

      for (const file of files) {
        const parts = file.name.split('.');
        const ext = parts.length > 1 ? '.' + parts.pop()?.toLowerCase() : '';
        const dotExt = ext.startsWith('.') ? ext : '.' + ext;

        if (!allowedList.includes(dotExt)) {
          errors.push(`"${file.name}" has unsupported type (${ext || 'unknown'}).`);
          continue;
        }

        // D13-P9: Reject dangerous double extensions (e.g. .pdf.exe)
        const DANGEROUS_EXTENSIONS = ['.exe', '.bat', '.cmd', '.sh', '.ps1', '.vbs'];
        const remaining = parts.join('.');
        if (remaining.includes('.') && DANGEROUS_EXTENSIONS.some((d) => remaining.toLowerCase().endsWith(d))) {
          errors.push(`"${file.name}" has a dangerous double extension and was rejected.`);
          continue;
        }

        // D13-P12: Reject empty files and folders (0-byte entries)
        if (file.size === 0) {
          errors.push(`"${file.name}" is empty. Empty files and folders are not supported.`);
          continue;
        }

        if (file.size > maxSizeBytes) {
          errors.push(`"${file.name}" exceeds ${formatFileSize(maxSizeBytes)} limit.`);
          continue;
        }
        valid.push(file);
      }

      // D13-P10: Report which files were dropped when exceeding maxFiles
      if (valid.length > maxFiles) {
        const dropped = valid.splice(maxFiles).map((f) => f.name);
        errors.push(`Maximum ${maxFiles} files allowed. Dropped: ${dropped.join(', ')}`);
      }

      if (errors.length > 0) {
        setError(errors.join(' '));
        dismissError();
      }

      return valid;
    },
    [acceptedTypes, maxSizeBytes, maxFiles, dismissError],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(false);

      if (disabled || isUploading) return;

      const files = Array.from(e.dataTransfer.files);
      const valid = validateFiles(files);
      if (valid.length > 0) onFilesSelected(valid);
    },
    [disabled, isUploading, validateFiles, onFilesSelected],
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!disabled && !isUploading) setDragOver(true);
    },
    [disabled, isUploading],
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.key === 'Enter' || e.key === ' ') && !disabled && !isUploading) {
        e.preventDefault();
        inputRef.current?.click();
      }
    },
    [disabled, isUploading],
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      const valid = validateFiles(files);
      if (valid.length > 0) onFilesSelected(valid);
      e.target.value = '';
    },
    [validateFiles, onFilesSelected],
  );

  const formatList = acceptedTypes
    .split(',')
    .map((t) => t.trim().toUpperCase().replace('.', ''))
    .join(', ');

  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={disabled || isUploading ? -1 : 0}
        aria-label={
          disabled || isUploading
            ? 'File upload disabled while uploading'
            : 'Upload files by dragging and dropping or clicking to browse'
        }
        aria-disabled={disabled || isUploading}
        className={`
          relative flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed
          p-8 text-center transition-all duration-200 cursor-pointer select-none
          ${
            disabled || isUploading
              ? 'cursor-not-allowed opacity-60 border-muted-foreground/25 bg-muted/30'
              : dragOver
                ? 'border-primary bg-primary/5 scale-[1.01]'
                : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50'
          }
          ${error ? 'border-destructive/60 bg-destructive/5' : ''}
        `}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => {
          if (!disabled && !isUploading) inputRef.current?.click();
        }}
        onKeyDown={handleKeyDown}
      >
        {isUploading ? (
          <UploadCloud className="h-10 w-10 text-muted-foreground animate-pulse" />
        ) : dragOver ? (
          <UploadCloud className="h-10 w-10 text-primary" />
        ) : (
          <Upload className="h-10 w-10 text-muted-foreground" />
        )}

        <div>
          <p className="font-medium">
            {isUploading
              ? 'Uploading...'
              : 'Drag & drop files here, or '}
            {!isUploading && !disabled && (
              <span className="text-primary hover:underline">browse</span>
            )}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {formatList} — up to {formatFileSize(maxSizeBytes)} each (max {maxFiles} files)
          </p>
        </div>

        <input
          ref={inputRef}
          type="file"
          className="hidden"
          multiple
          accept={acceptedTypes}
          onChange={handleInputChange}
          disabled={disabled || isUploading}
          tabIndex={-1}
          aria-hidden="true"
        />
      </div>

      {error && (
        <p className="text-sm text-destructive animate-in fade-in-0 slide-in-from-top-1 duration-300">
          {error}
        </p>
      )}
    </div>
  );
}
