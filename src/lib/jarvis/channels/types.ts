/**
 * JARVIS Channels Module - Week 13 (Phase 4)
 *
 * Unified communication channels for JARVIS:
 * - Email (Brevo)
 * - SMS (Twilio)
 * - Chat (Socket.io)
 * - Social (Twitter/X, Instagram, Facebook)
 *
 * Note: Voice integration excluded per project requirements
 */

// ── Channel Types ───────────────────────────────────────────────────

export type ChannelType = 'email' | 'sms' | 'chat' | 'social_twitter' | 'social_instagram' | 'social_facebook';

export type ChannelStatus = 'connected' | 'disconnected' | 'error' | 'pending' | 'rate_limited';

export type MessageDirection = 'inbound' | 'outbound';

export type MessageStatus = 'pending' | 'sent' | 'delivered' | 'read' | 'failed' | 'bounced';

export type SocialPlatform = 'twitter' | 'instagram' | 'facebook';

// ── Message Types ────────────────────────────────────────────────────

export interface ChannelMessage {
  id: string;
  channel: ChannelType;
  direction: MessageDirection;
  status: MessageStatus;
  from: string;
  to: string;
  subject?: string;
  body: string;
  htmlBody?: string;
  attachments?: MessageAttachment[];
  metadata: Record<string, unknown>;
  createdAt: Date;
  sentAt?: Date;
  deliveredAt?: Date;
  readAt?: Date;
  error?: string;
  retryCount: number;
  ticketId?: string;
  customerId?: string;
  organizationId: string;
}

export interface MessageAttachment {
  id: string;
  filename: string;
  mimeType: string;
  size: number;
  url?: string;
  content?: Buffer | string;
}

// ── Channel Configuration ────────────────────────────────────────────

export interface EmailChannelConfig {
  enabled: boolean;
  provider: 'brevo' | 'sendgrid' | 'mailgun';
  apiKey?: string;
  fromEmail: string;
  fromName: string;
  replyTo?: string;
  webhookSecret?: string;
  rateLimitPerHour: number;
  rateLimitPerDay: number;
  bounceHandling: boolean;
  oooDetection: boolean;
  loopPrevention: boolean;
  maxRepliesPerThread: number;
}

export interface SmsChannelConfig {
  enabled: boolean;
  provider: 'twilio' | 'vonage' | 'messagebird';
  apiKey?: string;
  apiSecret?: string;
  accountSid?: string;
  fromNumber: string;
  webhookSecret?: string;
  rateLimitPerHour: number;
  rateLimitPerDay: number;
  tcpaCompliance: boolean;
  optOutHandling: boolean;
  shortCodeEnabled: boolean;
}

export interface ChatChannelConfig {
  enabled: boolean;
  provider: 'socketio' | 'pusher' | 'livekit';
  socketUrl?: string;
  socketPath?: string;
  webhookSecret?: string;
  rateLimitPerMinute: number;
  rateLimitPerHour: number;
  typingIndicator: boolean;
  readReceipts: boolean;
  fileUploads: boolean;
  maxFileSize: number;
  allowedFileTypes: string[];
  sessionTimeout: number;
  idleTimeout: number;
}

export interface SocialChannelConfig {
  enabled: boolean;
  platform: SocialPlatform;
  accessToken?: string;
  accessTokenSecret?: string;
  appId?: string;
  appSecret?: string;
  webhookSecret?: string;
  pageId?: string;
  accountId?: string;
  rateLimitPerHour: number;
  rateLimitPerDay: number;
  autoReply: boolean;
  dmHandling: boolean;
  commentHandling: boolean;
  mentionHandling: boolean;
}

export interface ChannelsConfig {
  email: EmailChannelConfig;
  sms: SmsChannelConfig;
  chat: ChatChannelConfig;
  social: SocialChannelConfig[];
}

// ── Channel Health ───────────────────────────────────────────────────

export interface ChannelHealth {
  channel: ChannelType;
  status: ChannelStatus;
  lastChecked: Date;
  latencyMs: number;
  errorRate: number;
  messagesLast24h: number;
  messagesLastHour: number;
  lastError?: string;
  lastErrorAt?: Date;
  uptimePercent: number;
}

export interface ChannelsHealthReport {
  overall: ChannelStatus;
  channels: ChannelHealth[];
  checkedAt: Date;
  alerts: ChannelAlert[];
}

export interface ChannelAlert {
  id: string;
  channel: ChannelType;
  severity: 'warning' | 'error' | 'critical';
  message: string;
  createdAt: Date;
  acknowledgedAt?: Date;
  resolvedAt?: Date;
}

// ── Channel Events ───────────────────────────────────────────────────

export type ChannelEventType =
  | 'message_received'
  | 'message_sent'
  | 'message_delivered'
  | 'message_read'
  | 'message_failed'
  | 'message_bounced'
  | 'channel_connected'
  | 'channel_disconnected'
  | 'channel_error'
  | 'rate_limit_exceeded'
  | 'opt_out_received'
  | 'typing_start'
  | 'typing_end'
  | 'customer_joined'
  | 'customer_left';

export interface ChannelEvent {
  id: string;
  type: ChannelEventType;
  channel: ChannelType;
  timestamp: Date;
  data: Record<string, unknown>;
  organizationId: string;
  sessionId?: string;
  customerId?: string;
  ticketId?: string;
}

// ── Send Options ─────────────────────────────────────────────────────

export interface SendOptions {
  priority: 'low' | 'normal' | 'high' | 'urgent';
  scheduledAt?: Date;
  templateId?: string;
  templateVariables?: Record<string, unknown>;
  replyToMessageId?: string;
  referenceId?: string;
  trackDelivery: boolean;
  trackRead: boolean;
  retryCount: number;
  maxRetries: number;
}

export interface EmailSendOptions extends SendOptions {
  cc?: string[];
  bcc?: string[];
  headers?: Record<string, string>;
}

export interface SmsSendOptions extends SendOptions {
  validityPeriod?: number;
  statusCallback?: string;
}

export interface ChatSendOptions extends SendOptions {
  ephemeral?: boolean;
  threadId?: string;
  parentMessageId?: string;
}

export interface SocialSendOptions extends SendOptions {
  inReplyToId?: string;
  mediaIds?: string[];
}

// ── Receive Payloads ─────────────────────────────────────────────────

export interface EmailReceivePayload {
  from: string;
  to: string;
  subject: string;
  textBody: string;
  htmlBody?: string;
  replyTo?: string;
  messageId: string;
  references?: string[];
  attachments?: MessageAttachment[];
  headers: Record<string, string>;
  receivedAt: Date;
}

export interface SmsReceivePayload {
  from: string;
  to: string;
  body: string;
  messageId: string;
  receivedAt: Date;
  optOut?: boolean;
  helpKeyword?: boolean;
}

export interface ChatReceivePayload {
  sessionId: string;
  customerId: string;
  message: string;
  messageId: string;
  receivedAt: Date;
  metadata?: Record<string, unknown>;
}

export interface SocialReceivePayload {
  platform: SocialPlatform;
  fromId: string;
  fromHandle: string;
  toId: string;
  message: string;
  messageId: string;
  messageType: 'dm' | 'mention' | 'comment';
  parentMessageId?: string;
  receivedAt: Date;
  mediaUrls?: string[];
}

// ── Channel Statistics ───────────────────────────────────────────────

export interface ChannelStats {
  channel: ChannelType;
  messagesSent: number;
  messagesReceived: number;
  messagesFailed: number;
  deliveryRate: number;
  readRate: number;
  avgResponseTime: number;
  avgLatency: number;
  peakHour: number;
  busierThanUsual: boolean;
  periodStart: Date;
  periodEnd: Date;
}

export interface ChannelsStatsReport {
  channels: ChannelStats[];
  totalSent: number;
  totalReceived: number;
  totalFailed: number;
  overallDeliveryRate: number;
  periodStart: Date;
  periodEnd: Date;
}

// ── Consent Management ───────────────────────────────────────────────

export interface ConsentRecord {
  customerId: string;
  channel: ChannelType;
  consented: boolean;
  consentedAt?: Date;
  revokedAt?: Date;
  source: string;
  ipAddress?: string;
}

// ── Rate Limit State ─────────────────────────────────────────────────

export interface RateLimitState {
  channel: ChannelType;
  limitPerWindow: number;
  usedInWindow: number;
  windowStart: Date;
  windowDuration: number;
  resetAt: Date;
  exceeded: boolean;
  retryAfterMs?: number;
}

// ── Template Types ───────────────────────────────────────────────────

export interface ChannelTemplate {
  id: string;
  channel: ChannelType;
  name: string;
  subject?: string;
  body: string;
  htmlBody?: string;
  variables: string[];
  category: string;
  approved: boolean;
  createdAt: Date;
  updatedAt: Date;
}

// ── Event Callback Types ─────────────────────────────────────────────

export type ChannelEventCallback = (event: ChannelEvent) => void | Promise<void>;
export type MessageCallback = (message: ChannelMessage) => void | Promise<void>;
export type HealthCallback = (health: ChannelHealth) => void | Promise<void>;
