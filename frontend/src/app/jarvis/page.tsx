'use client';

import React, { useState } from 'react';
import { JarvisChat } from '@/components/jarvis/JarvisChat';

/**
 * Jarvis Chat Page
 *
 * Full-page Jarvis chat interface for onboarding.
 * Initializes the chat and manages open/close state.
 */
export default function JarvisPage() {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <JarvisChat isOpen={isOpen} onClose={() => window.history.back()} />
  );
}
