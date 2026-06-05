/**
 * PARWA Demo Knowledge Base API
 *
 * GET  /api/demo/knowledge-base — List pre-built and uploaded knowledge bases
 * POST /api/demo/knowledge-base — Upload a file to the knowledge base
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAllKnowledgeBases, addUploadedKB, generateId } from '@/lib/demo-store';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const industry = searchParams.get('industry');

    const allKBs = getAllKnowledgeBases();

    // Filter by industry if specified
    if (industry) {
      return NextResponse.json({
        prebuilt: allKBs.prebuilt.filter((kb) => kb.industry === industry),
        uploaded: allKBs.uploaded.filter((kb) => kb.industry === industry || !kb.industry),
      });
    }

    return NextResponse.json(allKBs);
  } catch (error) {
    return NextResponse.json(
      { error: { code: 'KB_LIST_ERROR', message: 'Failed to list knowledge bases' } },
      { status: 500 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File | null;
    const industry = formData.get('industry') as string | null;

    if (!file) {
      return NextResponse.json(
        { error: { code: 'MISSING_FILE', message: 'No file uploaded' } },
        { status: 400 },
      );
    }

    // Validate file size (max 10MB for demo)
    if (file.size > 10 * 1024 * 1024) {
      return NextResponse.json(
        { error: { code: 'FILE_TOO_LARGE', message: 'File must be under 10MB' } },
        { status: 400 },
      );
    }

    // Validate file type
    const allowedTypes = [
      'text/plain', 'text/csv', 'text/markdown',
      'application/pdf', 'application/json',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ];
    const allowedExtensions = ['.txt', '.csv', '.md', '.pdf', '.json', '.docx'];

    const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExt)) {
      return NextResponse.json(
        { error: { code: 'INVALID_FILE_TYPE', message: 'Supported formats: .txt, .csv, .md, .pdf, .json, .docx' } },
        { status: 400 },
      );
    }

    // Simulate processing (in production, this would chunk and embed the document)
    const chunksCount = Math.max(1, Math.floor(file.size / 500));

    const kb = {
      id: generateId('kb'),
      name: file.name.replace(/\.[^/.]+$/, ''),
      description: `Uploaded document: ${file.name} (${(file.size / 1024).toFixed(1)}KB)`,
      industry: industry || '',
      document_count: 1,
      is_prebuilt: false,
      created_at: new Date().toISOString(),
    };

    addUploadedKB(kb);

    return NextResponse.json({
      id: kb.id,
      name: kb.name,
      status: 'ready' as const,
      chunks_count: chunksCount,
      message: `Successfully processed "${file.name}" — ${chunksCount} chunks created.`,
    });
  } catch (error) {
    return NextResponse.json(
      { error: { code: 'KB_UPLOAD_ERROR', message: error instanceof Error ? error.message : 'Failed to upload knowledge base' } },
      { status: 500 },
    );
  }
}
