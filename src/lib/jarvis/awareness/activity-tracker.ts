/**
 * JARVIS Customer Activity Tracker (Week 2 - Phase 1)
 *
 * Tracks customer interactions, detects patterns, and monitors sentiment changes.
 * Handles: message tracking, sentiment monitoring, churn risk detection
 */

import type {
  AwarenessEvent,
  AwarenessEventType,
  CustomerActivity,
  CustomerActivitySummary,
  CustomerTrackerConfig,
  ActivityPattern,
  SentimentAnalysis,
  SentimentLabel,
} from '@/types/awareness';

// ── Event Emitter Interface ──────────────────────────────────────────

export interface EventEmitter {
  emit(event: AwarenessEvent): Promise<void>;
}

// ── Customer Activity Data Types ─────────────────────────────────────

export interface CustomerActivityData {
  customer_id: string;
  tenant_id: string;
  activity_type: 'message' | 'ticket' | 'call' | 'chat' | 'email';
  channel: string;
  ticket_id?: string;
  agent_id?: string;
  content?: string;
  metadata?: Record<string, unknown>;
}

// ── Activity Tracker Class ───────────────────────────────────────────

export class CustomerActivityTracker {
  private config: CustomerTrackerConfig;
  private eventEmitter: EventEmitter;
  private activityBuffer: Map<string, CustomerActivity[]> = new Map();
  private sentimentHistory: Map<string, SentimentAnalysis[]> = new Map();
  private churnRiskCache: Map<string, number> = new Map();

  constructor(config: CustomerTrackerConfig, emitter: EventEmitter) {
    this.config = config;
    this.eventEmitter = emitter;
  }

  /**
   * Track a customer activity
   */
  async trackActivity(data: CustomerActivityData): Promise<CustomerActivity> {
    const activity: CustomerActivity = {
      id: this.generateActivityId(),
      tenant_id: data.tenant_id,
      customer_id: data.customer_id,
      activity_type: data.activity_type,
      channel: data.channel,
      timestamp: new Date(),
      ticket_id: data.ticket_id,
      agent_id: data.agent_id,
      metadata: data.metadata || {},
    };

    // Analyze sentiment if content provided and tracking enabled
    if (this.config.track_sentiment && data.content) {
      activity.sentiment = await this.analyzeSentiment(data.content);
    }

    // Store in buffer
    this.bufferActivity(activity);

    // Check for sentiment change
    if (activity.sentiment) {
      await this.checkSentimentChange(activity);
    }

    // Update churn risk
    if (this.config.track_patterns) {
      await this.updateChurnRisk(data.customer_id);
    }

    return activity;
  }

  /**
   * Get customer activity summary
   */
  async getActivitySummary(customerId: string): Promise<CustomerActivitySummary> {
    const activities = this.activityBuffer.get(customerId) || [];
    const sentiments = this.sentimentHistory.get(customerId) || [];
    const now = new Date();

    // Calculate time-based counts
    const last24h = activities.filter(
      (a) => now.getTime() - a.timestamp.getTime() < 24 * 60 * 60 * 1000
    ).length;
    const last7d = activities.filter(
      (a) => now.getTime() - a.timestamp.getTime() < 7 * 24 * 60 * 60 * 1000
    ).length;
    const last30d = activities.filter(
      (a) => now.getTime() - a.timestamp.getTime() < 30 * 24 * 60 * 60 * 1000
    ).length;

    // Determine primary channel
    const channelCounts: Record<string, number> = {};
    for (const a of activities) {
      channelCounts[a.channel] = (channelCounts[a.channel] || 0) + 1;
    }
    const primaryChannel =
      Object.entries(channelCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'unknown';

    // Calculate average sentiment
    const avgSentiment =
      sentiments.length > 0
        ? sentiments.reduce((sum, s) => sum + s.score, 0) / sentiments.length
        : 0;

    // Determine sentiment trend
    const sentimentTrend = this.calculateSentimentTrend(sentiments);

    // Extract top issues
    const topIssues = this.extractTopIssues(activities);

    // Get churn risk
    const churnRiskScore = this.churnRiskCache.get(customerId) || 0;

    return {
      customer_id: customerId,
      total_interactions: activities.length,
      last_24h: last24h,
      last_7d: last7d,
      last_30d: last30d,
      primary_channel: primaryChannel,
      avg_sentiment: avgSentiment,
      sentiment_trend: sentimentTrend,
      top_issues: topIssues,
      churn_risk_score: churnRiskScore,
    };
  }

  /**
   * Detect patterns in customer behavior
   */
  async detectPatterns(customerId: string): Promise<ActivityPattern[]> {
    if (!this.config.track_patterns) return [];

    const activities = this.activityBuffer.get(customerId) || [];
    const patterns: ActivityPattern[] = [];

    // Detect peak hours pattern
    const peakHoursPattern = this.detectPeakHours(activities);
    if (peakHoursPattern) {
      patterns.push(peakHoursPattern);
    }

    // Detect frequent issues pattern
    const issuesPattern = this.detectFrequentIssues(activities);
    if (issuesPattern) {
      patterns.push(issuesPattern);
    }

    // Detect sentiment trend pattern
    const sentiments = this.sentimentHistory.get(customerId) || [];
    const sentimentPattern = this.detectSentimentTrend(sentiments);
    if (sentimentPattern) {
      patterns.push(sentimentPattern);
    }

    // Detect channel preference pattern
    const channelPattern = this.detectChannelPreference(activities);
    if (channelPattern) {
      patterns.push(channelPattern);
    }

    return patterns;
  }

  /**
   * Analyze sentiment of text content
   */
  private async analyzeSentiment(content: string): Promise<SentimentAnalysis> {
    // Simple sentiment analysis implementation
    // In production, this would use an AI model or external service
    const negativeWords = [
      'angry', 'frustrated', 'disappointed', 'terrible', 'awful',
      'hate', 'worst', 'never', 'bad', 'poor', 'unhappy', 'upset',
      'cancel', 'refund', 'complaint', 'issue', 'problem', 'broken',
    ];
    const positiveWords = [
      'great', 'excellent', 'amazing', 'wonderful', 'fantastic',
      'love', 'best', 'happy', 'pleased', 'satisfied', 'thank',
      'perfect', 'awesome', 'brilliant', 'outstanding', 'helpful',
    ];

    const lowerContent = content.toLowerCase();
    let negativeCount = 0;
    let positiveCount = 0;

    for (const word of negativeWords) {
      if (lowerContent.includes(word)) negativeCount++;
    }
    for (const word of positiveWords) {
      if (lowerContent.includes(word)) positiveCount++;
    }

    const total = negativeCount + positiveCount;
    let score = 0;
    let label: SentimentLabel = 'neutral';

    if (total > 0) {
      score = (positiveCount - negativeCount) / Math.max(total, 1);
    }

    if (score > 0.3) {
      label = 'positive';
    } else if (score < -0.3) {
      label = 'negative';
    } else if (total > 0) {
      label = 'mixed';
    }

    return {
      label,
      score,
      confidence: Math.min(Math.abs(score) + 0.5, 1),
      detected_at: new Date(),
    };
  }

  /**
   * Buffer activity for later analysis
   */
  private bufferActivity(activity: CustomerActivity): void {
    const customerId = activity.customer_id;
    const buffer = this.activityBuffer.get(customerId) || [];
    buffer.push(activity);

    // Limit buffer size based on config
    const limit = this.config.history_limit;
    if (buffer.length > limit) {
      buffer.shift();
    }

    this.activityBuffer.set(customerId, buffer);
  }

  /**
   * Check for significant sentiment change
   */
  private async checkSentimentChange(activity: CustomerActivity): Promise<void> {
    if (!activity.sentiment) return;

    const customerId = activity.customer_id;
    const history = this.sentimentHistory.get(customerId) || [];
    history.push(activity.sentiment);
    this.sentimentHistory.set(customerId, history);

    // Check if we have enough history
    if (history.length < 2) return;

    // Get previous sentiment
    const previous = history[history.length - 2];
    const current = activity.sentiment;

    // Check for significant negative shift
    const threshold = this.config.sentiment_threshold_negative;
    if (
      previous.score > threshold &&
      current.score < threshold &&
      current.label === 'negative'
    ) {
      // Emit sentiment change event
      const event = this.createEvent('customer_sentiment_changed', {
        tenant_id: activity.tenant_id,
        customer_id: activity.customer_id,
        previous_sentiment: previous,
        current_sentiment: current,
        ticket_id: activity.ticket_id,
      });
      await this.eventEmitter.emit(event);
    }
  }

  /**
   * Update churn risk score for a customer
   */
  private async updateChurnRisk(customerId: string): Promise<void> {
    const activities = this.activityBuffer.get(customerId) || [];
    const sentiments = this.sentimentHistory.get(customerId) || [];

    let riskScore = 0;

    // Factor 1: Negative sentiment trend (0-30 points)
    if (sentiments.length >= 3) {
      const recent = sentiments.slice(-3);
      const trend = recent[2].score - recent[0].score;
      if (trend < -0.3) {
        riskScore += 30;
      } else if (trend < -0.1) {
        riskScore += 15;
      }
    }

    // Factor 2: High interaction frequency (0-20 points)
    const recentActivities = activities.filter(
      (a) => Date.now() - a.timestamp.getTime() < 7 * 24 * 60 * 60 * 1000
    );
    if (recentActivities.length > 10) {
      riskScore += 20;
    } else if (recentActivities.length > 5) {
      riskScore += 10;
    }

    // Factor 3: Channel switching (0-15 points)
    const channels = new Set(recentActivities.map((a) => a.channel));
    if (channels.size >= 3) {
      riskScore += 15;
    } else if (channels.size >= 2) {
      riskScore += 8;
    }

    // Factor 4: Escalation (0-25 points)
    const escalations = activities.filter(
      (a) => a.metadata?.escalated === true
    );
    if (escalations.length > 0) {
      riskScore += Math.min(escalations.length * 10, 25);
    }

    // Factor 5: Reopened tickets (0-10 points)
    const reopened = activities.filter(
      (a) => a.metadata?.reopened === true
    );
    if (reopened.length > 0) {
      riskScore += Math.min(reopened.length * 5, 10);
    }

    this.churnRiskCache.set(customerId, Math.min(riskScore, 100));

    // Emit churn risk event if threshold exceeded
    if (
      riskScore >= this.config.churn_risk_threshold &&
      (this.churnRiskCache.get(customerId) || 0) < this.config.churn_risk_threshold
    ) {
      const event = this.createEvent('customer_churn_risk', {
        tenant_id: activities[0]?.tenant_id,
        customer_id: customerId,
        risk_score: riskScore,
        contributing_factors: {
          sentiment_trend: sentiments.length >= 3 ? sentiments.slice(-3) : [],
          recent_activity_count: recentActivities.length,
          channels_used: Array.from(channels),
          escalation_count: escalations.length,
          reopened_count: reopened.length,
        },
      });
      await this.eventEmitter.emit(event);
    }
  }

  /**
   * Calculate sentiment trend direction
   */
  private calculateSentimentTrend(
    sentiments: SentimentAnalysis[]
  ): 'improving' | 'stable' | 'declining' {
    if (sentiments.length < 3) return 'stable';

    const recent = sentiments.slice(-5);
    const firstHalf = recent.slice(0, Math.floor(recent.length / 2));
    const secondHalf = recent.slice(Math.floor(recent.length / 2));

    const firstAvg =
      firstHalf.reduce((sum, s) => sum + s.score, 0) / firstHalf.length;
    const secondAvg =
      secondHalf.reduce((sum, s) => sum + s.score, 0) / secondHalf.length;

    const diff = secondAvg - firstAvg;
    if (diff > 0.1) return 'improving';
    if (diff < -0.1) return 'declining';
    return 'stable';
  }

  /**
   * Extract top issues from activities
   */
  private extractTopIssues(activities: CustomerActivity[]): string[] {
    const issues: Record<string, number> = {};

    for (const activity of activities) {
      const issue = activity.metadata?.issue_type as string;
      if (issue) {
        issues[issue] = (issues[issue] || 0) + 1;
      }
    }

    return Object.entries(issues)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([issue]) => issue);
  }

  /**
   * Detect peak hours pattern
   */
  private detectPeakHours(activities: CustomerActivity[]): ActivityPattern | null {
    if (activities.length < 10) return null;

    const hourCounts: Record<number, number> = {};
    for (const activity of activities) {
      const hour = activity.timestamp.getHours();
      hourCounts[hour] = (hourCounts[hour] || 0) + 1;
    }

    const peakHour = Object.entries(hourCounts).sort((a, b) => b[1] - a[1])[0];
    if (peakHour && peakHour[1] > activities.length * 0.2) {
      return {
        customer_id: activities[0].customer_id,
        pattern_type: 'peak_hours',
        pattern_data: {
          peak_hour: parseInt(peakHour[0]),
          percentage: (peakHour[1] / activities.length) * 100,
        },
        confidence: 0.7,
        detected_at: new Date(),
      };
    }

    return null;
  }

  /**
   * Detect frequent issues pattern
   */
  private detectFrequentIssues(activities: CustomerActivity[]): ActivityPattern | null {
    if (activities.length < 5) return null;

    const issues: Record<string, number> = {};
    for (const activity of activities) {
      const category = activity.metadata?.category as string;
      if (category) {
        issues[category] = (issues[category] || 0) + 1;
      }
    }

    const topIssue = Object.entries(issues).sort((a, b) => b[1] - a[1])[0];
    if (topIssue && topIssue[1] >= 3) {
      return {
        customer_id: activities[0].customer_id,
        pattern_type: 'frequent_issues',
        pattern_data: {
          issue: topIssue[0],
          count: topIssue[1],
        },
        confidence: 0.8,
        detected_at: new Date(),
      };
    }

    return null;
  }

  /**
   * Detect sentiment trend pattern
   */
  private detectSentimentTrend(sentiments: SentimentAnalysis[]): ActivityPattern | null {
    if (sentiments.length < 5) return null;

    const trend = this.calculateSentimentTrend(sentiments);
    if (trend === 'stable') return null;

    return {
      customer_id: '', // Will be set by caller
      pattern_type: 'sentiment_trend',
      pattern_data: {
        trend,
        recent_avg:
          sentiments.slice(-3).reduce((sum, s) => sum + s.score, 0) / 3,
      },
      confidence: 0.75,
      detected_at: new Date(),
    };
  }

  /**
   * Detect channel preference pattern
   */
  private detectChannelPreference(activities: CustomerActivity[]): ActivityPattern | null {
    if (activities.length < 5) return null;

    const channelCounts: Record<string, number> = {};
    for (const activity of activities) {
      channelCounts[activity.channel] = (channelCounts[activity.channel] || 0) + 1;
    }

    const primary = Object.entries(channelCounts).sort((a, b) => b[1] - a[1])[0];
    if (primary && primary[1] > activities.length * 0.5) {
      return {
        customer_id: activities[0].customer_id,
        pattern_type: 'channel_preference',
        pattern_data: {
          preferred_channel: primary[0],
          percentage: (primary[1] / activities.length) * 100,
        },
        confidence: 0.85,
        detected_at: new Date(),
      };
    }

    return null;
  }

  /**
   * Create an awareness event
   */
  private createEvent(
    type: AwarenessEventType,
    data: Record<string, unknown>
  ): AwarenessEvent {
    return {
      id: this.generateEventId(),
      type,
      timestamp: new Date(),
      tenant_id: data.tenant_id as string,
      variant: this.config.variant,
      source: 'activity_tracker',
      payload: data,
      metadata: {},
    };
  }

  /**
   * Generate unique IDs
   */
  private generateEventId(): string {
    return `evt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private generateActivityId(): string {
    return `act_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Update tracker configuration
   */
  updateConfig(config: Partial<CustomerTrackerConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * Clear buffers for a customer
   */
  clearCustomer(customerId: string): void {
    this.activityBuffer.delete(customerId);
    this.sentimentHistory.delete(customerId);
    this.churnRiskCache.delete(customerId);
  }

  /**
   * Get buffered activities for debugging
   */
  getBufferedActivities(customerId: string): CustomerActivity[] {
    return this.activityBuffer.get(customerId) || [];
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createActivityTracker(
  config: CustomerTrackerConfig,
  emitter: EventEmitter
): CustomerActivityTracker {
  return new CustomerActivityTracker(config, emitter);
}

// ── Default Configuration by Variant ─────────────────────────────────

export const DEFAULT_ACTIVITY_TRACKER_CONFIG: Record<
  string,
  Omit<CustomerTrackerConfig, 'tenant_id'>
> = {
  mini_parwa: {
    variant: 'mini_parwa',
    track_sentiment: true,
    track_patterns: false,
    sentiment_threshold_negative: -0.3,
    churn_risk_threshold: 70,
    history_limit: 10,
  },
  parwa: {
    variant: 'parwa',
    track_sentiment: true,
    track_patterns: true,
    sentiment_threshold_negative: -0.25,
    churn_risk_threshold: 60,
    history_limit: 50,
  },
  parwa_high: {
    variant: 'parwa_high',
    track_sentiment: true,
    track_patterns: true,
    sentiment_threshold_negative: -0.2,
    churn_risk_threshold: 50,
    history_limit: 100,
  },
};
