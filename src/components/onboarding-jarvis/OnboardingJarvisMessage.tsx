/**
 * Onboarding Jarvis — Chat Message Component
 *
 * Renders individual messages in the onboarding chat.
 * User messages right-aligned, Jarvis messages left-aligned,
 * system messages centered. Rich cards rendered inline.
 */

'use client';

import { OnboardingMessage, MessageType } from '@/types/onboarding-jarvis';
import { BillSummaryCard } from './cards/BillSummaryCard';
import { PaymentCard } from './cards/PaymentCard';
import { OtpVerificationCard } from './cards/OtpVerificationCard';
import { DemoCallCard } from './cards/DemoCallCard';
import { HandoffCard } from './cards/HandoffCard';
import { LimitReachedCard } from './cards/LimitReachedCard';
import { PackExpiredCard } from './cards/PackExpiredCard';
import { DemoPackCTA } from './cards/DemoPackCTA';

interface Props {
  message: OnboardingMessage;
}

export function OnboardingJarvisMessage({ message }: Props) {
  const { role, content, message_type, metadata } = message;

  // Render rich cards for special message types
  if (role === 'jarvis' && message_type !== 'text' && message_type !== 'error') {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] w-full">
          {renderCardContent(message_type, metadata)}
          {/* Also render text content if present alongside card */}
          {content && message_type !== 'text' && (
            <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3 mb-2">
              <p className="text-gray-200 text-sm leading-relaxed whitespace-pre-wrap">{content}</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  // User message
  if (role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="bg-emerald-600/90 rounded-2xl rounded-tr-sm px-4 py-3 max-w-[80%]">
          <p className="text-white text-sm leading-relaxed whitespace-pre-wrap">{content}</p>
        </div>
      </div>
    );
  }

  // System message
  if (role === 'system') {
    return (
      <div className="flex justify-center">
        <p className="text-gray-500 text-xs italic">{content}</p>
      </div>
    );
  }

  // Jarvis text message (default)
  return (
    <div className="flex justify-start gap-2">
      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-xs flex-shrink-0 mt-1">
        🤖
      </div>
      <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3 max-w-[80%]">
        <p className="text-gray-200 text-sm leading-relaxed whitespace-pre-wrap">{content}</p>
      </div>
    </div>
  );
}

function renderCardContent(type: MessageType, data: Record<string, any>) {
  switch (type) {
    case 'bill_summary':
      return <BillSummaryCard data={data} />;
    case 'payment_card':
      return <PaymentCard data={data} />;
    case 'otp_card':
      return <OtpVerificationCard data={data} />;
    case 'demo_call_card':
      return <DemoCallCard data={data} />;
    case 'handoff_card':
      return <HandoffCard data={data} />;
    case 'limit_reached':
      return <LimitReachedCard />;
    case 'pack_expired':
      return <PackExpiredCard />;
    case 'recharge_cta':
      return <DemoPackCTA remaining={data.remaining_today ?? 0} onPurchase={() => {}} />;
    default:
      return null;
  }
}
