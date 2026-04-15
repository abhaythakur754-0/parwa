'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import { TicketDetail } from '@/components/dashboard/tickets';

export default function TicketDetailPage() {
  const params = useParams();
  const ticketId = params.id as string;

  return <TicketDetail ticketId={ticketId} />;
}
