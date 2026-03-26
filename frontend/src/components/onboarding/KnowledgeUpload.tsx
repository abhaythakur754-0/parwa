"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import { Upload, X, FileText, File, AlertCircle, CheckCircle2 } from "lucide-react";

export interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  progress: number;
  status: "uploading" | "success" | "error";
  error?: string;
}

export interface KnowledgeUploadProps {
  onFilesChange?: (files: UploadedFile[]) => void;
  maxFileSize?: number; // in bytes
  maxFiles?: number;
  acceptedFormats?: string[];
  className?: string;
  disabled?: boolean;
}

const DEFAULT_ACCEPTED_FORMATS = [".pdf", ".csv", ".json", ".txt"];
const DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const DEFAULT_MAX_FILES = 10;

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const getFileIcon = (type: string) => {
  if (type.includes("pdf")) return <FileText className="h-5 w-5 text-red-500" />;
  if (type.includes("csv")) return <FileText className="h-5 w-5 text-green-500" />;
  if (type.includes("json")) return <FileText className="h-5 w-5 text-yellow-500" />;
  return <File className="h-5 w-5 text-gray-500" />;
};

export function KnowledgeUpload({
  onFilesChange,
  maxFileSize = DEFAULT_MAX_FILE_SIZE,
  maxFiles = DEFAULT_MAX_FILES,
  acceptedFormats = DEFAULT_ACCEPTED_FORMATS,
  className,
  disabled = false,
}: KnowledgeUploadProps) {
  const [files, setFiles] = React.useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = React.useState(false);
  const [dragError, setDragError] = React.useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    if (file.size > maxFileSize) {
      return `File size exceeds ${formatFileSize(maxFileSize)} limit`;
    }

    const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;
    if (!acceptedFormats.includes(extension)) {
      return `File format not supported. Accepted: ${acceptedFormats.join(", ")}`;
    }

    return null;
  };

  const addFiles = async (newFiles: FileList | File[]) => {
    const fileArray = Array.from(newFiles);
    const remainingSlots = maxFiles - files.length;

    if (remainingSlots <= 0) {
      setDragError(`Maximum ${maxFiles} files allowed`);
      return;
    }

    const filesToAdd = fileArray.slice(0, remainingSlots);

    for (const file of filesToAdd) {
      const error = validateFile(file);
      const uploadedFile: UploadedFile = {
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        name: file.name,
        size: file.size,
        type: file.type,
        progress: 0,
        status: error ? "error" : "uploading",
        error: error || undefined,
      };

      setFiles((prev) => {
        const updated = [...prev, uploadedFile];
        onFilesChange?.(updated);
        return updated;
      });

      if (!error) {
        // Simulate upload progress
        for (let progress = 0; progress <= 100; progress += 20) {
          await new Promise((resolve) => setTimeout(resolve, 100));
          setFiles((prev) =>
            prev.map((f) =>
              f.id === uploadedFile ? { ...f, progress } : f
            )
          );
        }

        setFiles((prev) => {
          const updated = prev.map((f) =>
            f.id === uploadedFile.id ? { ...f, status: "success" as const, progress: 100 } : f
          );
          onFilesChange?.(updated);
          return updated;
        });
      }
    }
  };

  const removeFile = (id: string) => {
    setFiles((prev) => {
      const updated = prev.filter((f) => f.id !== id);
      onFilesChange?.(updated);
      return updated;
    });
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) {
      setIsDragging(true);
      setDragError(null);
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

    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles.length > 0) {
      addFiles(droppedFiles);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files);
    }
  };

  const handleClick = () => {
    if (!disabled) {
      fileInputRef.current?.click();
    }
  };

  return (
    <div className={cn("space-y-4", className)}>
      {/* Drop Zone */}
      <div
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={handleClick}
        className={cn(
          "relative border-2 border-dashed rounded-lg p-8 text-center transition-all cursor-pointer",
          isDragging && "border-primary bg-primary/5",
          dragError && "border-destructive bg-destructive/5",
          disabled && "opacity-50 cursor-not-allowed",
          !isDragging && !dragError && "border-muted-foreground/25 hover:border-primary/50"
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={acceptedFormats.join(",")}
          onChange={handleFileInput}
          className="hidden"
          disabled={disabled}
        />

        <div className="flex flex-col items-center gap-4">
          <div
            className={cn(
              "w-12 h-12 rounded-full flex items-center justify-center",
              isDragging ? "bg-primary/10" : "bg-muted"
            )}
          >
            <Upload
              className={cn(
                "h-6 w-6",
                isDragging ? "text-primary" : "text-muted-foreground"
              )}
            />
          </div>

          <div>
            <p className="text-sm font-medium">
              {isDragging ? "Drop files here" : "Drag and drop files here"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              or click to browse
            </p>
          </div>

          <div className="text-xs text-muted-foreground space-y-1">
            <p>
              Supported formats: {acceptedFormats.join(", ").replace(/\./g, "").toUpperCase()}
            </p>
            <p>
              Max file size: {formatFileSize(maxFileSize)} | Max files: {maxFiles}
            </p>
          </div>
        </div>
      </div>

      {/* Drag Error */}
      {dragError && (
        <div className="flex items-center gap-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          {dragError}
        </div>
      )}

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">
            Uploaded Files ({files.length}/{maxFiles})
          </p>
          <div className="space-y-2">
            {files.map((file) => (
              <div
                key={file.id}
                className={cn(
                  "flex items-center gap-3 p-3 rounded-lg border",
                  file.status === "error" ? "border-destructive/50 bg-destructive/5" : "border-border"
                )}
              >
                {getFileIcon(file.type)}

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium truncate">{file.name}</p>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      {formatFileSize(file.size)}
                    </span>
                  </div>

                  {file.status === "uploading" && (
                    <div className="mt-2 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary transition-all"
                        style={{ width: `${file.progress}%` }}
                      />
                    </div>
                  )}

                  {file.status === "error" && file.error && (
                    <p className="text-xs text-destructive mt-1">{file.error}</p>
                  )}

                  {file.status === "success" && (
                    <div className="flex items-center gap-1 text-xs text-green-600 mt-1">
                      <CheckCircle2 className="h-3 w-3" />
                      Uploaded successfully
                    </div>
                  )}
                </div>

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => removeFile(file.id)}
                  className="h-8 w-8 shrink-0"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default KnowledgeUpload;
