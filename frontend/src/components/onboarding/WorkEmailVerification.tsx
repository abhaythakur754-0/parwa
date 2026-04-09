'use client';

import React from 'react';
import { Mail, CheckCircle, AlertCircle, Send, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { userDetailsApi, getErrorMessage } from '@/lib/api';
import toast from 'react-hot-toast';

interface WorkEmailVerificationProps {
  workEmail: string;
  isVerified: boolean;
  onVerified?: () => void;
  disabled?: boolean;
  className?: string;
}

/**
 * WorkEmailVerification Component
 * 
 * Handles work email verification flow:
 * 1. Display current verification status
 * 2. Send verification email
 * 3. Show verification pending state
 * 4. Display verified status
 */
export function WorkEmailVerification({
  workEmail,
  isVerified,
  onVerified,
  disabled = false,
  className,
}: WorkEmailVerificationProps) {
  const [isSending, setIsSending] = React.useState(false);
  const [emailSent, setEmailSent] = React.useState(false);
  const [cooldown, setCooldown] = React.useState(0);
  
  // Cooldown timer
  React.useEffect(() => {
    if (cooldown > 0) {
      const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [cooldown]);
  
  /**
   * Send verification email.
   * GAP-002: Uses safe error message handling.
   */
  const handleSendVerification = async () => {
    if (!workEmail || isSending || cooldown > 0) return;
    
    setIsSending(true);
    
    try {
      await userDetailsApi.sendVerification(workEmail);
      setEmailSent(true);
      setCooldown(60); // 60 second cooldown
      toast.success('Verification email sent! Check your inbox.');
    } catch (error) {
      console.error('Failed to send verification:', error);
      // GAP-002: Use safe error message handling
      const errorMessage = getErrorMessage(error);
      toast.error(errorMessage);
    } finally {
      setIsSending(false);
    }
  };
  
  // No work email provided
  if (!workEmail) {
    return (
      <div className={cn('p-4 rounded-lg bg-secondary-50 border border-secondary-200', className)}>
        <p className="text-sm text-secondary-500">
          No work email provided. You can add one later in your account settings.
        </p>
      </div>
    );
  }
  
  // Email is verified
  if (isVerified) {
    return (
      <div className={cn('p-4 rounded-lg bg-emerald-50 border border-emerald-200', className)}>
        <div className="flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-success-500" />
          <div>
            <p className="text-sm font-medium text-success-600">Email Verified</p>
            <p className="text-xs text-success-500">{workEmail}</p>
          </div>
        </div>
      </div>
    );
  }
  
  // Email is not verified
  return (
    <div className={cn('p-4 rounded-lg border', className)}>
      {/* Status Banner */}
      <div className={cn(
        'flex items-center gap-2 mb-3',
        emailSent ? 'bg-warning-50 border-warning-200' : 'bg-secondary-50 border-secondary-200'
      )}>
        {emailSent ? (
          <AlertCircle className="w-5 h-5 text-warning-500" />
        ) : (
          <Mail className="w-5 h-5 text-secondary-500" />
        )}
        <div>
          <p className={cn(
            'text-sm font-medium',
            emailSent ? 'text-warning-600' : 'text-secondary-600'
          )}>
            {emailSent ? 'Verification Pending' : 'Email Not Verified'}
          </p>
          <p className="text-xs text-secondary-500">{workEmail}</p>
        </div>
      </div>
      
      {/* Instructions */}
      {emailSent ? (
        <div className="space-y-2 mb-3">
          <p className="text-sm text-secondary-600">
            We&apos;ve sent a verification link to <strong>{workEmail}</strong>. 
            Please check your inbox and click the link to verify your email.
          </p>
          <p className="text-xs text-secondary-500">
            Didn&apos;t receive the email? Check your spam folder or wait 60 seconds to resend.
          </p>
        </div>
      ) : (
        <p className="text-sm text-secondary-600 mb-3">
          Verify your work email to unlock all features and ensure account security.
        </p>
      )}
      
      {/* Send/Resend Button */}
      <button
        type="button"
        onClick={handleSendVerification}
        disabled={disabled || isSending || cooldown > 0}
        className={cn(
          'btn',
          emailSent ? 'btn-secondary' : 'btn-primary'
        )}
      >
        {isSending ? (
          <>
            <div className="spinner-sm mr-2" />
            Sending...
          </>
        ) : cooldown > 0 ? (
          <>
            <RefreshCw className="w-4 h-4 mr-2" />
            Resend in {cooldown}s
          </>
        ) : (
          <>
            <Send className="w-4 h-4 mr-2" />
            {emailSent ? 'Resend Verification' : 'Send Verification Email'}
          </>
        )}
      </button>
    </div>
  );
}

export default WorkEmailVerification;
