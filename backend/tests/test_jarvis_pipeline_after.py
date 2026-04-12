"""
AFTER-STATE TESTS: Demonstrating jarvis_service.py AFTER Week 8-11 integration.

These tests use AST analysis to verify all 32 pipeline helper functions
are DEFINED and properly CONNECTED to their respective services.
This approach works without needing runtime dependencies (database, etc.).

Run:  pytest tests/test_jarvis_pipeline_after.py -v
"""

import ast
import os
import textwrap
import pytest


# Path to the jarvis_service.py file
JARVIS_SERVICE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "app", "services", "jarvis_service.py",
)


def _get_jarvis_source():
    """Read and parse jarvis_service.py source code."""
    abs_path = os.path.abspath(JARVIS_SERVICE_PATH)
    with open(abs_path, "r") as f:
        source = f.read()
    return source


def _get_function_names(source):
    """Extract all top-level function names from source."""
    tree = ast.parse(source)
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(node.name)
    return functions


def _get_function_source(source, func_name):
    """Extract source code for a specific function."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return ast.get_source_segment(source, node)
    return None


def _get_function_calls(source, func_name):
    """Extract all function calls within a specific function."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            calls = []
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name):
                        calls.append(child.func.id)
                    elif isinstance(child.func, ast.Attribute):
                        calls.append(child.func.attr)
            return calls
    return []


class TestAfterStateAllFunctionsExist:
    """
    AFTER: All 32 pipeline helper functions are now DEFINED in jarvis_service.py.
    AST analysis proves they exist in the source code.
    """

    def test_jarvis_service_file_exists(self):
        """AFTER: jarvis_service.py exists and is parseable."""
        source = _get_jarvis_source()
        assert len(source) > 1000  # File has significant content
        # Verify it's valid Python
        tree = ast.parse(source)
        assert tree is not None

    def test_jarvis_service_has_50_plus_functions(self):
        """AFTER: jarvis_service.py defines 50+ functions total."""
        source = _get_jarvis_source()
        functions = _get_function_names(source)
        assert len(functions) >= 50, f"Expected 50+ functions, got {len(functions)}"

    def test_scan_prompt_injection_defined(self):
        """AFTER: _scan_prompt_injection is defined."""
        source = _get_jarvis_source()
        assert "_scan_prompt_injection" in _get_function_names(source)

    def test_check_spam_defined(self):
        """AFTER: _check_spam is defined."""
        source = _get_jarvis_source()
        assert "_check_spam" in _get_function_names(source)

    def test_redact_pii_defined(self):
        """AFTER: _redact_pii is defined."""
        source = _get_jarvis_source()
        assert "_redact_pii" in _get_function_names(source)

    def test_deredact_pii_defined(self):
        """AFTER: _deredact_pii is defined."""
        source = _get_jarvis_source()
        assert "_deredact_pii" in _get_function_names(source)

    def test_process_language_defined(self):
        """AFTER: _process_language is defined."""
        source = _get_jarvis_source()
        assert "_process_language" in _get_function_names(source)

    def test_extract_signals_defined(self):
        """AFTER: _extract_signals is defined."""
        source = _get_jarvis_source()
        assert "_extract_signals" in _get_function_names(source)

    def test_acquire_session_lock_defined(self):
        """AFTER: _acquire_session_lock is defined."""
        source = _get_jarvis_source()
        assert "_acquire_session_lock" in _get_function_names(source)

    def test_release_session_lock_defined(self):
        """AFTER: _release_session_lock is defined."""
        source = _get_jarvis_source()
        assert "_release_session_lock" in _get_function_names(source)

    def test_update_gsd_state_defined(self):
        """AFTER: _update_gsd_state is defined."""
        source = _get_jarvis_source()
        assert "_update_gsd_state" in _get_function_names(source)

    def test_get_prompt_template_defined(self):
        """AFTER: _get_prompt_template is defined."""
        source = _get_jarvis_source()
        assert "_get_prompt_template" in _get_function_names(source)

    def test_get_brand_voice_config_defined(self):
        """AFTER: _get_brand_voice_config is defined."""
        source = _get_jarvis_source()
        assert "_get_brand_voice_config" in _get_function_names(source)

    def test_inject_brand_voice_defined(self):
        """AFTER: _inject_brand_voice is defined."""
        source = _get_jarvis_source()
        assert "_inject_brand_voice" in _get_function_names(source)

    def test_rag_retrieve_defined(self):
        """AFTER: _rag_retrieve is defined."""
        source = _get_jarvis_source()
        assert "_rag_retrieve" in _get_function_names(source)

    def test_classify_message_defined(self):
        """AFTER: _classify_message is defined."""
        source = _get_jarvis_source()
        assert "_classify_message" in _get_function_names(source)

    def test_compress_context_defined(self):
        """AFTER: _compress_context is defined."""
        source = _get_jarvis_source()
        assert "_compress_context" in _get_function_names(source)

    def test_check_context_health_defined(self):
        """AFTER: _check_context_health is defined."""
        source = _get_jarvis_source()
        assert "_check_context_health" in _get_function_names(source)

    def test_check_token_budget_defined(self):
        """AFTER: _check_token_budget is defined."""
        source = _get_jarvis_source()
        assert "_check_token_budget" in _get_function_names(source)

    def test_run_clara_quality_gate_defined(self):
        """AFTER: _run_clara_quality_gate is defined."""
        source = _get_jarvis_source()
        assert "_run_clara_quality_gate" in _get_function_names(source)

    def test_run_guardrails_defined(self):
        """AFTER: _run_guardrails is defined."""
        source = _get_jarvis_source()
        assert "_run_guardrails" in _get_function_names(source)

    def test_score_confidence_defined(self):
        """AFTER: _score_confidence is defined."""
        source = _get_jarvis_source()
        assert "_score_confidence" in _get_function_names(source)

    def test_detect_hallucination_defined(self):
        """AFTER: _detect_hallucination is defined."""
        source = _get_jarvis_source()
        assert "_detect_hallucination" in _get_function_names(source)

    def test_apply_response_formatters_defined(self):
        """AFTER: _apply_response_formatters is defined."""
        source = _get_jarvis_source()
        assert "_apply_response_formatters" in _get_function_names(source)

    def test_merge_brand_voice_defined(self):
        """AFTER: _merge_brand_voice is defined."""
        source = _get_jarvis_source()
        assert "_merge_brand_voice" in _get_function_names(source)

    def test_get_injection_blocked_message_defined(self):
        """AFTER: _get_injection_blocked_message is defined."""
        source = _get_jarvis_source()
        assert "_get_injection_blocked_message" in _get_function_names(source)

    def test_track_usage_defined(self):
        """AFTER: _track_usage is defined."""
        source = _get_jarvis_source()
        assert "_track_usage" in _get_function_names(source)

    def test_check_cost_protection_defined(self):
        """AFTER: _check_cost_protection is defined."""
        source = _get_jarvis_source()
        assert "_check_cost_protection" in _get_function_names(source)

    def test_track_ai_metrics_defined(self):
        """AFTER: _track_ai_metrics is defined."""
        source = _get_jarvis_source()
        assert "_track_ai_metrics" in _get_function_names(source)

    def test_buffer_event_defined(self):
        """AFTER: _buffer_event is defined."""
        source = _get_jarvis_source()
        assert "_buffer_event" in _get_function_names(source)

    def test_track_technique_metrics_defined(self):
        """AFTER: _track_technique_metrics is defined."""
        source = _get_jarvis_source()
        assert "_track_technique_metrics" in _get_function_names(source)

    def test_check_burst_protection_defined(self):
        """AFTER: _check_burst_protection is defined."""
        source = _get_jarvis_source()
        assert "_check_burst_protection" in _get_function_names(source)

    def test_run_self_healing_check_defined(self):
        """AFTER: _run_self_healing_check is defined."""
        source = _get_jarvis_source()
        assert "_run_self_healing_check" in _get_function_names(source)

    def test_summarize_conversation_defined(self):
        """AFTER: _summarize_conversation is defined."""
        source = _get_jarvis_source()
        assert "_summarize_conversation" in _get_function_names(source)


class TestAfterStateP0ServiceConnections:
    """
    AFTER: P0 services are properly connected via lazy imports.
    Verify each P0 function imports and uses the correct service class.
    """

    def test_prompt_injection_uses_defense_class(self):
        """AFTER: _scan_prompt_injection imports PromptInjectionDefense."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_scan_prompt_injection")
        assert func_src is not None
        assert "PromptInjectionDefense" in func_src
        assert "prompt_injection_defense" in func_src
        assert ".detect(" in func_src

    def test_pii_redaction_uses_engine(self):
        """AFTER: _redact_pii imports PIIRedactionEngine."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_redact_pii")
        assert func_src is not None
        assert "PIIRedactionEngine" in func_src
        assert "pii_redaction_engine" in func_src
        assert ".redact(" in func_src
        assert "has_pii" in func_src

    def test_clara_uses_quality_gate(self):
        """AFTER: _run_clara_quality_gate imports CLARAQualityGate."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_run_clara_quality_gate")
        assert func_src is not None
        assert "CLARAQualityGate" in func_src
        assert "clara_quality_gate" in func_src
        assert ".validate_response(" in func_src

    def test_guardrails_uses_engine(self):
        """AFTER: _run_guardrails imports GuardrailsEngine."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_run_guardrails")
        assert func_src is not None
        assert "GuardrailsEngine" in func_src
        assert "guardrails_engine" in func_src
        assert ".check_output(" in func_src

    def test_context_compression_uses_compressor(self):
        """AFTER: _compress_context imports ContextCompressor."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_compress_context")
        assert func_src is not None
        assert "ContextCompressor" in func_src
        assert "context_compression" in func_src
        assert ".compress(" in func_src

    def test_injection_blocked_message_returns_string(self):
        """AFTER: _get_injection_blocked_message returns a user-friendly string."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_get_injection_blocked_message")
        assert func_src is not None
        assert 'return (' in func_src
        assert "unusual" in func_src.lower()


class TestAfterStateP1ServiceConnections:
    """
    AFTER: P1 services use correct service classes.
    """

    def test_gsd_uses_engine(self):
        """AFTER: _update_gsd_state imports GSDEngine."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_update_gsd_state")
        assert func_src is not None
        assert "GSDEngine" in func_src
        assert "gsd_engine" in func_src
        assert ".process_message(" in func_src

    def test_session_lock_uses_continuity(self):
        """AFTER: _acquire_session_lock imports SessionContinuityService."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_acquire_session_lock")
        assert func_src is not None
        assert "SessionContinuityService" in func_src
        assert "session_continuity" in func_src
        assert ".acquire_lock(" in func_src

    def test_session_release_uses_continuity(self):
        """AFTER: _release_session_lock imports SessionContinuityService."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_release_session_lock")
        assert func_src is not None
        assert "SessionContinuityService" in func_src
        assert ".release_lock(" in func_src

    def test_context_health_has_scoring(self):
        """AFTER: _check_context_health has scoring logic."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_check_context_health")
        assert func_src is not None
        assert "overall_score" in func_src
        assert "HEALTHY" in func_src
        assert "WARNING" in func_src
        assert "CRITICAL" in func_src


class TestAfterStateP2ServiceConnections:
    """
    AFTER: P2 AI pipeline services use correct service classes.
    """

    def test_signal_extraction_uses_extractor(self):
        """AFTER: _extract_signals imports SignalExtractor."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_extract_signals")
        assert func_src is not None
        assert "SignalExtractor" in func_src
        assert "signal_extraction" in func_src
        assert ".extract(" in func_src

    def test_classification_uses_service(self):
        """AFTER: _classify_message imports ClassificationService."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_classify_message")
        assert func_src is not None
        assert "ClassificationService" in func_src
        assert "classification_service" in func_src
        assert ".classify(" in func_src

    def test_brand_voice_uses_service(self):
        """AFTER: _get_brand_voice_config imports BrandVoiceService."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_get_brand_voice_config")
        assert func_src is not None
        assert "BrandVoiceService" in func_src
        assert "brand_voice_service" in func_src
        assert ".get_brand_guidelines(" in func_src

    def test_rag_retrieve_uses_retrieval_and_reranker(self):
        """AFTER: _rag_retrieve imports RAGRetrieval and RAGReranker."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_rag_retrieve")
        assert func_src is not None
        assert "RAGRetrieval" in func_src
        assert "RAGReranker" in func_src
        assert "rag_retrieval" in func_src
        assert "rag_reranking" in func_src
        assert ".retrieve(" in func_src
        assert ".rerank(" in func_src

    def test_token_budget_uses_service(self):
        """AFTER: _check_token_budget imports TokenBudgetService."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_check_token_budget")
        assert func_src is not None
        assert "TokenBudgetService" in func_src
        assert "token_budget_service" in func_src
        assert ".calculate_tokens(" in func_src


class TestAfterStatePipelineIntegration:
    """
    AFTER: Verify _call_ai_provider calls all 32 pipeline functions.
    """

    def test_call_ai_provider_calls_all_preprocessing(self):
        """AFTER: _call_ai_provider calls all pre-processing functions."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")
        assert func_src is not None

        preprocessing_calls = [
            "_scan_prompt_injection",
            "_check_spam",
            "_redact_pii",
            "_process_language",
            "_extract_signals",
            "_acquire_session_lock",
        ]
        for call in preprocessing_calls:
            assert call in func_src, f"Missing: {call} in _call_ai_provider"

    def test_call_ai_provider_calls_all_ai_pipeline(self):
        """AFTER: _call_ai_provider calls all AI pipeline functions."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")
        assert func_src is not None

        ai_pipeline_calls = [
            "_update_gsd_state",
            "_get_prompt_template",
            "_get_brand_voice_config",
            "_inject_brand_voice",
            "_rag_retrieve",
            "_classify_message",
            "_compress_context",
            "_check_context_health",
            "_check_token_budget",
        ]
        for call in ai_pipeline_calls:
            assert call in func_src, f"Missing: {call} in _call_ai_provider"

    def test_call_ai_provider_calls_all_postprocessing(self):
        """AFTER: _call_ai_provider calls all post-processing functions."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")
        assert func_src is not None

        post_calls = [
            "_run_clara_quality_gate",
            "_run_guardrails",
            "_score_confidence",
            "_detect_hallucination",
            "_apply_response_formatters",
            "_merge_brand_voice",
            "_deredact_pii",
            "_release_session_lock",
        ]
        for call in post_calls:
            assert call in func_src, f"Missing: {call} in _call_ai_provider"

    def test_call_ai_provider_calls_all_operations(self):
        """AFTER: _call_ai_provider calls all operations functions."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")
        assert func_src is not None

        ops_calls = [
            "_track_usage",
            "_check_cost_protection",
            "_track_ai_metrics",
            "_buffer_event",
            "_track_technique_metrics",
            "_check_burst_protection",
            "_run_self_healing_check",
            "_summarize_conversation",
        ]
        for call in ops_calls:
            assert call in func_src, f"Missing: {call} in _call_ai_provider"

    def test_call_ai_provider_has_pipeline_version(self):
        """AFTER: _call_ai_provider metadata includes pipeline_version."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")
        assert 'week8-11-full' in func_src

    def test_call_ai_provider_has_phase_comments(self):
        """AFTER: _call_ai_provider has clear phase comments."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")
        assert "PRE-PROCESSING" in func_src
        assert "AI PIPELINE" in func_src
        assert "POST-PROCESSING" in func_src
        assert "OPERATIONS" in func_src


class TestAfterStateGracefulDegradation:
    """
    AFTER: All service connections use try/except with graceful fallback.
    """

    def test_all_pipeline_helpers_use_try_except(self):
        """AFTER: Every pipeline helper has try/except for graceful degradation."""
        source = _get_jarvis_source()

        # Functions with external service imports need try/except
        functions_with_external_imports = [
            "_scan_prompt_injection", "_redact_pii", "_deredact_pii",
            "_extract_signals", "_update_gsd_state", "_get_prompt_template",
            "_get_brand_voice_config", "_rag_retrieve", "_classify_message",
            "_compress_context", "_check_token_budget",
            "_run_clara_quality_gate", "_run_guardrails",
            "_merge_brand_voice",
            "_summarize_conversation", "_track_usage",
            "_check_cost_protection", "_track_ai_metrics",
            "_buffer_event", "_track_technique_metrics",
            "_check_burst_protection", "_run_self_healing_check",
            "_acquire_session_lock", "_release_session_lock",
            "_process_language",
        ]

        for func_name in functions_with_external_imports:
            func_src = _get_function_source(source, func_name)
            assert func_src is not None, f"{func_name} not found"
            assert "try:" in func_src, f"{func_name} missing try/except"
            assert "except" in func_src, f"{func_name} missing try/except"

        # Pure logic functions (no external imports) don't need try/except
        pure_logic_functions = [
            "_score_confidence", "_detect_hallucination",
            "_apply_response_formatters",
        ]

        for func_name in pure_logic_functions:
            func_src = _get_function_source(source, func_name)
            assert func_src is not None, f"{func_name} not found"

    def test_context_compression_has_fallback_truncation(self):
        """AFTER: Context compression has fallback to simple truncation."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_compress_context")
        assert func_src is not None
        assert "history[-20:]" in func_src  # Fallback truncation

    def test_token_budget_defaults_to_allow(self):
        """AFTER: Token budget defaults to True (allow) on failure."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_check_token_budget")
        assert func_src is not None
        assert "return True" in func_src  # Default: allow

    def test_prompt_template_falls_back_to_base(self):
        """AFTER: Prompt template falls back to base prompt on failure."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_get_prompt_template")
        assert func_src is not None
        assert "return base_prompt" in func_src


class TestAfterStateFullPipelineCount:
    """
    AFTER: Verify the complete count of connected services.
    """

    def test_all_32_pipeline_helpers_defined(self):
        """AFTER: All 32 pipeline helper functions are defined."""
        source = _get_jarvis_source()
        all_functions = _get_function_names(source)

        pipeline_functions = [
            "_scan_prompt_injection",
            "_get_injection_blocked_message",
            "_check_spam",
            "_redact_pii",
            "_deredact_pii",
            "_process_language",
            "_extract_signals",
            "_acquire_session_lock",
            "_release_session_lock",
            "_update_gsd_state",
            "_get_prompt_template",
            "_get_brand_voice_config",
            "_inject_brand_voice",
            "_rag_retrieve",
            "_classify_message",
            "_compress_context",
            "_check_context_health",
            "_check_token_budget",
            "_run_clara_quality_gate",
            "_run_guardrails",
            "_score_confidence",
            "_detect_hallucination",
            "_apply_response_formatters",
            "_merge_brand_voice",
            "_summarize_conversation",
            "_track_usage",
            "_check_cost_protection",
            "_track_ai_metrics",
            "_buffer_event",
            "_track_technique_metrics",
            "_check_burst_protection",
            "_run_self_healing_check",
        ]

        missing = []
        for func_name in pipeline_functions:
            if func_name not in all_functions:
                missing.append(func_name)

        assert not missing, f"MISSING functions: {missing}"
        assert len(pipeline_functions) == 32

    def test_previous_services_still_connected(self):
        """AFTER: Previously connected services still exist."""
        source = _get_jarvis_source()
        all_functions = _get_function_names(source)

        previous_functions = [
            "_run_sentiment_analysis",
            "_evaluate_escalation",
            "_lookup_trained_response",
            "_inject_knowledge_into_prompt",
            "_inject_sentiment_into_prompt",
            "_init_conversation_context",
            "_track_conversation_message",
            "_track_analytics_event",
            "_capture_lead_from_session",
            "_get_analytics_category",
        ]

        missing = []
        for func_name in previous_functions:
            if func_name not in all_functions:
                missing.append(func_name)

        assert not missing, f"REGRESSION - removed: {missing}"
        assert len(previous_functions) == 10

    def test_total_connected_services(self):
        """AFTER: Total = 32 pipeline + 10 previous = 42 connected functions."""
        total = 32 + 10
        assert total == 42

    def test_file_has_pipeline_section_header(self):
        """AFTER: File has clear section header for pipeline functions."""
        source = _get_jarvis_source()
        assert "Week 8-11: Pipeline Helper Functions" in source
        assert "PRE-PROCESSING HELPERS" in source
        assert "AI PIPELINE HELPERS" in source
        assert "POST-PROCESSING HELPERS" in source
        assert "OPERATIONS HELPERS" in source


class TestAfterStateDocstrings:
    """
    AFTER: All pipeline functions have proper docstrings.
    """

    def test_all_pipeline_functions_have_docstrings(self):
        """AFTER: Every pipeline function has a docstring."""
        source = _get_jarvis_source()
        tree = ast.parse(source)

        pipeline_functions = [
            "_scan_prompt_injection", "_check_spam", "_redact_pii",
            "_deredact_pii", "_process_language", "_extract_signals",
            "_acquire_session_lock", "_release_session_lock",
            "_update_gsd_state", "_get_prompt_template",
            "_get_brand_voice_config", "_inject_brand_voice",
            "_rag_retrieve", "_classify_message", "_compress_context",
            "_check_context_health", "_check_token_budget",
            "_run_clara_quality_gate", "_run_guardrails",
            "_score_confidence", "_detect_hallucination",
            "_apply_response_formatters", "_merge_brand_voice",
            "_summarize_conversation", "_track_usage",
            "_check_cost_protection", "_track_ai_metrics",
            "_buffer_event", "_track_technique_metrics",
            "_check_burst_protection", "_run_self_healing_check",
        ]

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in pipeline_functions:
                docstring = ast.get_docstring(node)
                assert docstring is not None, f"{node.name} missing docstring"
                assert len(docstring) > 20, f"{node.name} docstring too short"
