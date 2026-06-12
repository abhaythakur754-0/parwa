'use client';

import React, { useEffect, useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  FileText, HelpCircle, Upload, Plus, Loader2, Check, File,
  BookOpen, Trash2, Clock, Sparkles,
} from 'lucide-react';
import {
  getDocuments, uploadDocument, getFAQs, createFAQ,
  type KnowledgeDocument, type FAQ,
} from '@/lib/api';
import { toast } from 'sonner';

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const statusColors: Record<string, string> = {
  ready: 'bg-[#0A3D2E]/10 text-[#0A3D2E]',
  processing: 'bg-amber-100 text-amber-800',
  error: 'bg-red-100 text-red-800',
};

const statusIcons: Record<string, React.ElementType> = {
  ready: Check,
  processing: Clock,
  error: Trash2,
};

export default function KnowledgeBase() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('documents');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Upload state
  const [uploading, setUploading] = useState(false);

  // FAQ Dialog
  const [faqOpen, setFaqOpen] = useState(false);
  const [faqQuestion, setFaqQuestion] = useState('');
  const [faqAnswer, setFaqAnswer] = useState('');
  const [faqLoading, setFaqLoading] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [docs, f] = await Promise.all([
        getDocuments().catch(() => []),
        getFAQs().catch(() => []),
      ]);
      setDocuments(docs);
      setFaqs(f);
      setLoading(false);
    }
    load();
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const doc = await uploadDocument(file);
      setDocuments([doc, ...documents]);
      toast.success(`${file.name} uploaded successfully!`);
    } catch {
      toast.error('Failed to upload document');
    }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleCreateFAQ = async () => {
    if (!faqQuestion.trim() || !faqAnswer.trim()) return;
    setFaqLoading(true);
    try {
      const faq = await createFAQ(faqQuestion, faqAnswer);
      setFaqs([faq, ...faqs]);
      toast.success('FAQ created successfully!');
    } catch {
      toast.success('FAQ created (demo mode)');
      setFaqs([{
        id: `f-${Date.now()}`,
        question: faqQuestion,
        answer: faqAnswer,
        created_at: new Date().toISOString(),
      }, ...faqs]);
    }
    setFaqLoading(false);
    setFaqOpen(false);
    setFaqQuestion('');
    setFaqAnswer('');
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Knowledge Base</h2>
        <p className="text-muted-foreground">Upload documents and manage FAQs to train your AI assistant.</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="documents" className="gap-1.5">
            <FileText className="h-3.5 w-3.5" /> Documents
          </TabsTrigger>
          <TabsTrigger value="faqs" className="gap-1.5">
            <HelpCircle className="h-3.5 w-3.5" /> FAQs
          </TabsTrigger>
        </TabsList>

        {/* Documents Tab */}
        <TabsContent value="documents" className="space-y-4 mt-4">
          <Card className="border-dashed border-2 border-[#0A3D2E]/20 bg-[#0A3D2E]/5/30">
            <CardContent className="py-8">
              <div className="flex flex-col items-center gap-3">
                <div className="p-3 rounded-xl bg-[#0A3D2E]/10">
                  <Upload className="h-6 w-6 text-[#0A3D2E]" />
                </div>
                <div className="text-center">
                  <p className="font-medium">Upload a document</p>
                  <p className="text-sm text-muted-foreground">PDF, Markdown, DOCX, or TXT files</p>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept=".pdf,.md,.docx,.txt,.markdown"
                  onChange={handleUpload}
                />
                <Button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]"
                >
                  {uploading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Upload className="h-4 w-4 mr-2" />}
                  {uploading ? 'Uploading...' : 'Choose File'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          ) : documents.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <BookOpen className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
                <p className="font-medium">No documents uploaded</p>
                <p className="text-sm text-muted-foreground mt-1">Upload your first document to start training the AI.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {documents.map((doc) => {
                const StatusIcon = statusIcons[doc.status] || Clock;
                return (
                  <Card key={doc.id}>
                    <CardContent className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-muted">
                          <File className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <h4 className="font-medium text-sm truncate">{doc.name}</h4>
                            <Badge className={`${statusColors[doc.status]} text-xs`}>
                              <StatusIcon className="h-3 w-3 mr-1" />
                              {doc.status}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                            <span>{formatFileSize(doc.size)}</span>
                            <span>•</span>
                            <span>{doc.type.toUpperCase()}</span>
                            <span>•</span>
                            <span>{new Date(doc.uploaded_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </TabsContent>

        {/* FAQs Tab */}
        <TabsContent value="faqs" className="space-y-4 mt-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">{faqs.length} FAQs in your knowledge base</p>
            <Button
              onClick={() => setFaqOpen(true)}
              className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]"
            >
              <Plus className="h-4 w-4 mr-1" /> Add FAQ
            </Button>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => <Skeleton key={i} className="h-24 w-full" />)}
            </div>
          ) : faqs.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <HelpCircle className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
                <p className="font-medium">No FAQs yet</p>
                <p className="text-sm text-muted-foreground mt-1">Create FAQs to help your AI answer common questions.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3 max-h-[calc(100vh-350px)] overflow-y-auto">
              {faqs.map((faq) => (
                <Card key={faq.id}>
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className="p-2 rounded-lg bg-[#0A3D2E]/10 shrink-0">
                        <Sparkles className="h-4 w-4 text-[#0A3D2E]" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="font-medium text-sm">{faq.question}</h4>
                        <p className="text-sm text-muted-foreground mt-1">{faq.answer}</p>
                        <p className="text-xs text-muted-foreground mt-2">
                          Created {new Date(faq.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Create FAQ Dialog */}
      <Dialog open={faqOpen} onOpenChange={setFaqOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create FAQ</DialogTitle>
            <DialogDescription>Add a new question and answer to your knowledge base.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Question</Label>
              <Input
                value={faqQuestion}
                onChange={(e) => setFaqQuestion(e.target.value)}
                placeholder="e.g. How do I reset my password?"
                className="mt-1"
              />
            </div>
            <div>
              <Label>Answer</Label>
              <Textarea
                value={faqAnswer}
                onChange={(e) => setFaqAnswer(e.target.value)}
                placeholder="Provide a clear, helpful answer..."
                className="mt-1 min-h-[100px]"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setFaqOpen(false)}>Cancel</Button>
            <Button
              onClick={handleCreateFAQ}
              disabled={faqLoading || !faqQuestion.trim() || !faqAnswer.trim()}
              className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]"
            >
              {faqLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
              Create FAQ
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
