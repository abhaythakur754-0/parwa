import { redirect } from 'next/navigation';

/** /dashboard/channels — REMOVED (channel is captured at ticket creation time) */
export default function ChannelsPageRedirect() {
  redirect('/dashboard/tickets');
}
