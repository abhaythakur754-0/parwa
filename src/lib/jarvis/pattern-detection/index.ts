/**
 * JARVIS Pattern Detection Index - Week 8 (Phase 2)
 *
 * Public exports for the Pattern Detection system.
 */

export { PatternDetectionManager, createPatternDetectionManager, getPatternDetectionManager, shutdownPatternDetectionManager } from './pattern-detection-manager';
export { DEFAULT_PATTERN_DETECTION_CONFIG, PATTERN_DETECTION_VARIANT_LIMITS } from './types';
export type {
  Pattern,
  PatternCategory,
  PatternType,
  PatternStatus,
  PatternConfidence,
  PatternCondition,
  PatternInstance,
  PatternPrediction,
  Anomaly,
  AnomalyThreshold,
  Trend,
  TrendDataPoint,
  PatternDetectionConfig,
  PatternDetectionVariantLimits,
  PatternDetectionStats,
  PatternEvent,
  PatternEventType,
  DetectPatternsRequest,
  DetectPatternsResponse,
  GetPatternsRequest,
  GetPatternsResponse,
} from './types';
