/**
 * JARVIS Sentiment Data Pipeline (Week 2 - Phase 1)
 *
 * Processes sentiment data from customer interactions.
 * Handles: sentiment analysis, trend detection, aspect extraction
 */

import type {
  SentimentAnalysis,
  SentimentLabel,
  SentimentAspect,
  SentimentTrend,
  SentimentBreakdown,
  AwarenessEvent,
} from '@/types/awareness';

// ── Pipeline Configuration ───────────────────────────────────────────

export interface SentimentPipelineConfig {
  tenant_id: string;
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
  enable_aspect_analysis: boolean;
  enable_trend_detection: boolean;
  cache_size: number;
  min_confidence: number;
}

// ── Sentiment Input ──────────────────────────────────────────────────

export interface SentimentInput {
  text: string;
  customer_id?: string;
  ticket_id?: string;
  channel?: string;
  timestamp?: Date;
  metadata?: Record<string, unknown>;
}

// ── Sentiment Pipeline Class ─────────────────────────────────────────

export class SentimentPipeline {
  private config: SentimentPipelineConfig;
  private sentimentCache: Map<string, SentimentAnalysis[]> = new Map();
  private aspectKeywords: Map<string, string[]> = this.getDefaultAspectKeywords();

  constructor(config: SentimentPipelineConfig) {
    this.config = config;
  }

  /**
   * Analyze sentiment of text
   */
  async analyze(input: SentimentInput): Promise<SentimentAnalysis> {
    const text = input.text.toLowerCase();

    // Calculate base sentiment
    const { score, confidence } = this.calculateSentimentScore(text);
    const label = this.scoreToLabel(score);

    // Extract aspects if enabled
    let aspects: SentimentAspect[] | undefined;
    if (this.config.enable_aspect_analysis) {
      aspects = this.extractAspects(text);
    }

    const result: SentimentAnalysis = {
      label,
      score,
      confidence,
      aspects,
      detected_at: new Date(),
    };

    // Cache result for customer if customer_id provided
    if (input.customer_id) {
      this.cacheSentiment(input.customer_id, result);
    }

    return result;
  }

  /**
   * Analyze batch of inputs
   */
  async analyzeBatch(inputs: SentimentInput[]): Promise<SentimentAnalysis[]> {
    return Promise.all(inputs.map((input) => this.analyze(input)));
  }

  /**
   * Get sentiment history for a customer
   */
  getSentimentHistory(customerId: string): SentimentAnalysis[] {
    return this.sentimentCache.get(customerId) || [];
  }

  /**
   * Get sentiment trend for a customer
   */
  getSentimentTrend(customerId: string): 'improving' | 'stable' | 'declining' {
    const history = this.sentimentCache.get(customerId) || [];

    if (history.length < 3) return 'stable';

    const recent = history.slice(-5);
    const firstHalf = recent.slice(0, Math.floor(recent.length / 2));
    const secondHalf = recent.slice(Math.floor(recent.length / 2));

    const firstAvg = firstHalf.reduce((sum, s) => sum + s.score, 0) / firstHalf.length;
    const secondAvg = secondHalf.reduce((sum, s) => sum + s.score, 0) / secondHalf.length;

    const diff = secondAvg - firstAvg;

    if (diff > 0.15) return 'improving';
    if (diff < -0.15) return 'declining';
    return 'stable';
  }

  /**
   * Calculate aggregate sentiment trend
   */
  calculateAggregateTrend(
    period: 'hour' | 'day' | 'week' = 'day'
  ): SentimentTrend | null {
    // Collect all sentiments from cache
    const allSentiments: SentimentAnalysis[] = [];
    for (const sentiments of this.sentimentCache.values()) {
      allSentiments.push(...sentiments);
    }

    if (allSentiments.length === 0) return null;

    const now = new Date();
    const periodMs: Record<string, number> = {
      hour: 60 * 60 * 1000,
      day: 24 * 60 * 60 * 1000,
      week: 7 * 24 * 60 * 60 * 1000,
    };

    const periodStart = new Date(now.getTime() - periodMs[period]);

    // Filter by period
    const periodSentiments = allSentiments.filter(
      (s) => s.detected_at >= periodStart
    );

    if (periodSentiments.length === 0) return null;

    // Calculate averages and breakdown
    const avgScore =
      periodSentiments.reduce((sum, s) => sum + s.score, 0) / periodSentiments.length;

    const breakdown = this.calculateBreakdown(periodSentiments);
    const trendDirection = this.determineTrendDirection(periodSentiments);

    return {
      tenant_id: this.config.tenant_id,
      period,
      start_date: periodStart,
      end_date: now,
      avg_score: avgScore,
      trend_direction: trendDirection,
      sample_size: periodSentiments.length,
      breakdown,
    };
  }

  /**
   * Detect sentiment anomalies (sudden changes)
   */
  detectAnomalies(threshold: number = 0.5): Array<{
    customer_id: string;
    previous_score: number;
    current_score: number;
    change: number;
  }> {
    const anomalies: Array<{
      customer_id: string;
      previous_score: number;
      current_score: number;
      change: number;
    }> = [];

    for (const [customerId, sentiments] of this.sentimentCache) {
      if (sentiments.length < 2) continue;

      const recent = sentiments.slice(-2);
      const change = recent[1].score - recent[0].score;

      if (Math.abs(change) >= threshold) {
        anomalies.push({
          customer_id: customerId,
          previous_score: recent[0].score,
          current_score: recent[1].score,
          change,
        });
      }
    }

    return anomalies.sort((a, b) => Math.abs(b.change) - Math.abs(a.change));
  }

  /**
   * Clear cache for a customer
   */
  clearCustomer(customerId: string): void {
    this.sentimentCache.delete(customerId);
  }

  /**
   * Clear all cache
   */
  clearAll(): void {
    this.sentimentCache.clear();
  }

  /**
   * Get statistics
   */
  getStats(): {
    customersTracked: number;
    totalAnalyses: number;
    avgSentiment: number;
    sentimentDistribution: Record<SentimentLabel, number>;
  } {
    let totalAnalyses = 0;
    let totalScore = 0;
    const distribution: Record<SentimentLabel, number> = {
      positive: 0,
      neutral: 0,
      negative: 0,
      mixed: 0,
    };

    for (const sentiments of this.sentimentCache.values()) {
      for (const s of sentiments) {
        totalAnalyses++;
        totalScore += s.score;
        distribution[s.label]++;
      }
    }

    return {
      customersTracked: this.sentimentCache.size,
      totalAnalyses,
      avgSentiment: totalAnalyses > 0 ? totalScore / totalAnalyses : 0,
      sentimentDistribution: distribution,
    };
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Calculate sentiment score from text
   */
  private calculateSentimentScore(text: string): { score: number; confidence: number } {
    // Expanded word lists for sentiment analysis
    const positiveWords = [
      'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'love',
      'best', 'happy', 'pleased', 'satisfied', 'thank', 'thanks', 'perfect',
      'awesome', 'brilliant', 'outstanding', 'helpful', 'friendly', 'quick',
      'fast', 'easy', 'smooth', 'impressive', 'recommend', 'appreciate',
    ];

    const negativeWords = [
      'angry', 'frustrated', 'disappointed', 'terrible', 'awful', 'hate',
      'worst', 'never', 'bad', 'poor', 'unhappy', 'upset', 'cancel',
      'refund', 'complaint', 'issue', 'problem', 'broken', 'slow',
      'difficult', 'complicated', 'confused', 'waste', 'unacceptable',
      'horrible', 'annoying', 'useless', 'disgusted', 'furious',
    ];

    const intensifiers = ['very', 'really', 'extremely', 'absolutely', 'totally'];
    const negators = ['not', "n't", 'never', 'no', 'dont', "don't"];

    const words = text.split(/\s+/);
    let positiveCount = 0;
    let negativeCount = 0;
    let totalSentimentWords = 0;

    for (let i = 0; i < words.length; i++) {
      const word = words[i];
      const prevWord = i > 0 ? words[i - 1] : '';
      const isNegated = negators.includes(prevWord);
      const isIntensified = intensifiers.includes(prevWord);

      const multiplier = isIntensified ? 1.5 : 1;

      if (positiveWords.includes(word)) {
        if (isNegated) {
          negativeCount += multiplier;
        } else {
          positiveCount += multiplier;
        }
        totalSentimentWords++;
      }

      if (negativeWords.includes(word)) {
        if (isNegated) {
          positiveCount += multiplier;
        } else {
          negativeCount += multiplier;
        }
        totalSentimentWords++;
      }
    }

    // Calculate score (-1 to 1)
    const total = positiveCount + negativeCount;
    let score = 0;
    if (total > 0) {
      score = (positiveCount - negativeCount) / Math.max(total, 1);
      // Normalize to -1 to 1 range
      score = Math.tanh(score * 2);
    }

    // Calculate confidence based on number of sentiment words found
    const confidence = Math.min(0.3 + (totalSentimentWords / words.length) * 0.7, 1);

    return { score, confidence };
  }

  /**
   * Convert score to label
   */
  private scoreToLabel(score: number): SentimentLabel {
    if (score > 0.25) return 'positive';
    if (score < -0.25) return 'negative';
    if (Math.abs(score) > 0.1) return 'mixed';
    return 'neutral';
  }

  /**
   * Extract aspects from text
   */
  private extractAspects(text: string): SentimentAspect[] {
    const aspects: SentimentAspect[] = [];

    for (const [aspectName, keywords] of this.aspectKeywords) {
      const foundKeywords: string[] = [];
      let hasMatch = false;

      for (const keyword of keywords) {
        if (text.includes(keyword)) {
          foundKeywords.push(keyword);
          hasMatch = true;
        }
      }

      if (hasMatch) {
        // Analyze sentiment around the aspect
        const aspectSentiment = this.analyzeAspectSentiment(text, foundKeywords);

        aspects.push({
          name: aspectName,
          sentiment: aspectSentiment.label,
          score: aspectSentiment.score,
          keywords: foundKeywords,
        });
      }
    }

    return aspects;
  }

  /**
   * Analyze sentiment around specific keywords
   */
  private analyzeAspectSentiment(
    text: string,
    keywords: string[]
  ): { label: SentimentLabel; score: number } {
    // Get context around keywords
    const words = text.split(/\s+/);
    const contextWords: string[] = [];

    for (let i = 0; i < words.length; i++) {
      for (const keyword of keywords) {
        if (words[i].includes(keyword)) {
          // Get surrounding words (±3)
          const start = Math.max(0, i - 3);
          const end = Math.min(words.length, i + 4);
          contextWords.push(...words.slice(start, end));
        }
      }
    }

    if (contextWords.length === 0) {
      return { label: 'neutral', score: 0 };
    }

    // Analyze sentiment of context
    const contextText = contextWords.join(' ');
    const { score } = this.calculateSentimentScore(contextText);

    return {
      label: this.scoreToLabel(score),
      score,
    };
  }

  /**
   * Get default aspect keywords
   */
  private getDefaultAspectKeywords(): Map<string, string[]> {
    return new Map([
      ['service', ['service', 'support', 'help', 'assistance', 'agent', 'staff', 'team']],
      ['product', ['product', 'item', 'quality', 'condition', 'defect', 'broken']],
      ['delivery', ['delivery', 'shipping', 'arrived', 'package', 'shipment', 'courier']],
      ['price', ['price', 'cost', 'expensive', 'cheap', 'value', 'money', 'refund']],
      ['communication', ['response', 'reply', 'communication', 'contact', 'email', 'message']],
      ['experience', ['experience', 'process', 'easy', 'difficult', 'simple', 'complicated']],
    ]);
  }

  /**
   * Cache sentiment for customer
   */
  private cacheSentiment(customerId: string, sentiment: SentimentAnalysis): void {
    if (!this.sentimentCache.has(customerId)) {
      this.sentimentCache.set(customerId, []);
    }

    const history = this.sentimentCache.get(customerId)!;
    history.push(sentiment);

    // Limit cache size
    while (history.length > this.config.cache_size) {
      history.shift();
    }
  }

  /**
   * Calculate sentiment breakdown
   */
  private calculateBreakdown(sentiments: SentimentAnalysis[]): SentimentBreakdown[] {
    const counts: Record<SentimentLabel, number> = {
      positive: 0,
      neutral: 0,
      negative: 0,
      mixed: 0,
    };

    for (const s of sentiments) {
      counts[s.label]++;
    }

    const total = sentiments.length;
    const labels: SentimentLabel[] = ['positive', 'neutral', 'negative', 'mixed'];

    return labels.map((label) => ({
      label,
      count: counts[label],
      percentage: (counts[label] / total) * 100,
    }));
  }

  /**
   * Determine trend direction
   */
  private determineTrendDirection(
    sentiments: SentimentAnalysis[]
  ): 'up' | 'down' | 'stable' {
    if (sentiments.length < 5) return 'stable';

    const midPoint = Math.floor(sentiments.length / 2);
    const firstHalf = sentiments.slice(0, midPoint);
    const secondHalf = sentiments.slice(midPoint);

    const firstAvg = firstHalf.reduce((sum, s) => sum + s.score, 0) / firstHalf.length;
    const secondAvg = secondHalf.reduce((sum, s) => sum + s.score, 0) / secondHalf.length;

    const diff = secondAvg - firstAvg;

    if (diff > 0.1) return 'up';
    if (diff < -0.1) return 'down';
    return 'stable';
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createSentimentPipeline(config: SentimentPipelineConfig): SentimentPipeline {
  return new SentimentPipeline(config);
}

// ── Default Configuration by Variant ─────────────────────────────────

export const DEFAULT_SENTIMENT_PIPELINE_CONFIG: Record<
  string,
  Omit<SentimentPipelineConfig, 'tenant_id'>
> = {
  mini_parwa: {
    variant: 'mini_parwa',
    enable_aspect_analysis: false,
    enable_trend_detection: false,
    cache_size: 10,
    min_confidence: 0.5,
  },
  parwa: {
    variant: 'parwa',
    enable_aspect_analysis: true,
    enable_trend_detection: true,
    cache_size: 50,
    min_confidence: 0.4,
  },
  parwa_high: {
    variant: 'parwa_high',
    enable_aspect_analysis: true,
    enable_trend_detection: true,
    cache_size: 100,
    min_confidence: 0.3,
  },
};
