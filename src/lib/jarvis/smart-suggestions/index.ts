/**
 * JARVIS Smart Suggestions Index - Week 7 (Phase 2)
 *
 * Public exports for the Smart Suggestions system.
 */

export { SmartSuggestionsManager, createSmartSuggestionsManager, getSmartSuggestionsManager, shutdownSmartSuggestionsManager } from './smart-suggestions-manager';
export { DEFAULT_SMART_SUGGESTIONS_CONFIG, SMART_SUGGESTIONS_VARIANT_LIMITS } from './types';
export type {
  Suggestion,
  SuggestionType,
  SuggestionPriority,
  SuggestionTrigger,
  SuggestedAction,
  SuggestionContext,
  SuggestionRule,
  SuggestionCondition,
  SuggestionStats,
  SuggestionSummary,
  SuggestionEvent,
  SuggestionEventType,
  SmartSuggestionsConfig,
  SmartSuggestionsVariantLimits,
  GetSuggestionsRequest,
  GetSuggestionsResponse,
  FeedbackRequest,
  FeedbackResponse,
  UserState,
} from './types';
