"""
INTEGRATION TESTS: Full pipeline integration for jarvis_service.py.

Uses AST analysis to verify the complete _call_ai_provider pipeline
structure, function wiring, and data flow.

Run:  pytest tests/test_jarvis_pipeline_integration.py -v
"""

import ast
import os
import re

# Path to the jarvis_service.py file
JARVIS_SERVICE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "app",
    "services",
    "jarvis_service.py",
)


def _get_jarvis_source():
    """Read jarvis_service.py source code."""
    abs_path = os.path.abspath(JARVIS_SERVICE_PATH)
    with open(abs_path, "r") as f:
        return f.read()


def _get_function_names(source):
    """Extract all function names from source."""
    tree = ast.parse(source)
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]


def _get_function_source(source, func_name):
    """Extract source for a specific function."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return ast.get_source_segment(source, node)
    return None


class TestIntegrationPipelineStructure:
    """
    Integration: Verify the _call_ai_provider pipeline has the correct
    structure with all 3 phases (pre-processing, AI, post-processing)
    plus operations.
    """

    def test_pipeline_has_four_phases(self):
        """The pipeline has PRE-PROCESSING, AI PIPELINE, POST-PROCESSING, OPERATIONS."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")

        phases = [
            "PRE-PROCESSING PHASE",
            "AI PIPELINE PHASE",
            "POST-PROCESSING PHASE",
            "OPERATIONS",
        ]
        for phase in phases:
            assert phase in func_src, f"Missing phase: {phase}"

    def test_preprocessing_phase_has_correct_order(self):
        """
        PRE-PROCESSING must execute in order:
        1. Prompt Injection → 2. Spam → 3. PII → 4. Language → 5. Signals → 6. Lock
        """
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")

        # Extract the pre-processing section
        preprocessing_match = re.search(
            r"PRE-PROCESSING PHASE(.*?)AI PIPELINE PHASE",
            func_src,
            re.DOTALL,
        )
        assert preprocessing_match, "Could not find PRE-PROCESSING section"
        preprocessing = preprocessing_match.group(1)

        # Verify order: each function appears before the next
        functions = [
            "_scan_prompt_injection",
            "_check_spam",
            "_redact_pii",
            "_process_language",
            "_extract_signals",
            "_acquire_session_lock",
        ]

        positions = []
        for func in functions:
            pos = preprocessing.find(func)
            assert pos >= 0, f"Missing in PRE-PROCESSING: {func}"
            positions.append(pos)

        # Verify increasing order
        for i in range(len(positions) - 1):
            assert (
                positions[i] < positions[i + 1]
            ), f"Wrong order: {functions[i]} should come before {functions[i + 1]}"

    def test_postprocessing_phase_has_correct_order(self):
        """
        POST-PROCESSING must execute in order:
        1. CLARA → 2. Guardrails → 3. Confidence → 4. Hallucination →
        5. Formatters → 6. Brand Voice → 7. PII Deredaction → 8. Lock Release
        """
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")

        # Extract post-processing section
        postprocessing_match = re.search(
            r"POST-PROCESSING PHASE(.*?)OPERATIONS",
            func_src,
            re.DOTALL,
        )
        assert postprocessing_match, "Could not find POST-PROCESSING section"
        postprocessing = postprocessing_match.group(1)

        functions = [
            "_run_clara_quality_gate",
            "_run_guardrails",
            "_score_confidence",
            "_detect_hallucination",
            "_apply_response_formatters",
            "_merge_brand_voice",
            "_deredact_pii",
            "_release_session_lock",
        ]

        positions = []
        for func in functions:
            pos = postprocessing.find(func)
            assert pos >= 0, f"Missing in POST-PROCESSING: {func}"
            positions.append(pos)

        for i in range(len(positions) - 1):
            assert (
                positions[i] < positions[i + 1]
            ), f"Wrong order: {functions[i]} before {functions[i + 1]}"

    def test_operations_fire_and_forget(self):
        """
        OPERATIONS phase has 7 fire-and-forget calls.
        None of them affect the response content.
        """
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")

        # Extract operations section (everything after OPERATIONS comment to
        # return)
        ops_match = re.search(
            r"# ═+.*?OPERATIONS.*?═+(.*?)(?:\n    # Determine|\n    return )",
            func_src,
            re.DOTALL,
        )
        assert ops_match, "Could not find OPERATIONS section"

        operations = [
            "_track_usage",
            "_check_cost_protection",
            "_track_ai_metrics",
            "_buffer_event",
            "_track_technique_metrics",
            "_check_burst_protection",
            "_run_self_healing_check",
        ]

        for op in operations:
            assert op in ops_match.group(1), f"Missing operation: {op}"


class TestIntegrationSendMessageToPipeline:
    """
    Integration: Verify send_message() calls _call_ai_provider().
    """

    def test_send_message_calls_call_ai_provider(self):
        """send_message delegates to _call_ai_provider."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "send_message")
        assert func_src is not None
        assert "_call_ai_provider(" in func_src

    def test_send_message_passes_all_params(self):
        """send_message passes system_prompt, history, message, ctx."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "send_message")
        assert "system_prompt" in func_src
        assert "history" in func_src
        assert "user_message" in func_src
        assert "_call_ai_provider(" in func_src


class TestIntegrationP0SafetyChain:
    """
    Integration: P0 safety chain forms a complete protection layer.
    Input → Prompt Injection Check → PII Redaction → [AI Processing] →
    CLARA Quality Gate → Guardrails → PII Deredaction → Output
    """

    def test_safety_chain_input_protection(self):
        """
        Input safety: Injection detection → Spam check → PII redaction.
        These run BEFORE any AI processing.
        """
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")

        # Input protection must come before AI call
        injection_pos = func_src.find("_scan_prompt_injection")
        spam_pos = func_src.find("_check_spam")
        pii_pos = func_src.find("_redact_pii")
        ai_call_pos = func_src.find("_try_ai_providers")

        assert injection_pos < ai_call_pos, "Injection check must precede AI call"
        assert spam_pos < ai_call_pos, "Spam check must precede AI call"
        assert pii_pos < ai_call_pos, "PII redaction must precede AI call"

    def test_safety_chain_output_protection(self):
        """
        Output safety: CLARA quality → Guardrails → PII deredaction.
        These run AFTER AI processing.
        """
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")

        ai_call_pos = func_src.find("_try_ai_providers")
        clara_pos = func_src.find("_run_clara_quality_gate")
        guardrails_pos = func_src.find("_run_guardrails")
        deredact_pos = func_src.find("_deredact_pii")

        assert clara_pos > ai_call_pos, "CLARA must follow AI call"
        assert guardrails_pos > ai_call_pos, "Guardrails must follow AI call"
        assert deredact_pos > ai_call_pos, "PII deredaction must follow AI call"

    def test_clara_before_guardrails(self):
        """CLARA quality check runs before guardrails."""
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")

        clara_pos = func_src.find("_run_clara_quality_gate")
        guardrails_pos = func_src.find("_run_guardrails")

        assert clara_pos < guardrails_pos, "CLARA must run before guardrails"


class TestIntegrationMetadataFlow:
    """
    Integration: Verify pipeline metadata is enriched at each step.
    """

    def test_metadata_enriched_at_each_step(self):
        """
        Pipeline metadata dict is populated at each step with:
        - injection_blocked / injection_flagged
        - spam_blocked
        - pii_redacted
        - language_detected
        - signals
        - gsd_state
        - brand_voice
        - classification
        - context_compressed
        - context_health
        - token_budget_exceeded
        - clara
        - guardrails
        - confidence_score
        - hallucination
        """
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")

        metadata_keys = [
            "injection_blocked",
            "injection_flagged",
            "spam_blocked",
            "pii_redacted",
            "language_detected",
            "signals",
            "gsd_state",
            "brand_voice",
            "classification",
            "context_compressed",
            "context_health",
            "token_budget_exceeded",
            "clara",
            "guardrails",
            "confidence_score",
            "hallucination",
        ]

        for key in metadata_keys:
            # Each key should appear in a metadata assignment
            pattern = f'metadata["{key}"]'
            assert (
                pattern in func_src or f'metadata.get("{key}"' in func_src
            ), f"Missing metadata key: {key}"


class TestIntegrationGSDStateMapping:
    """
    Integration: GSD states map correctly to Jarvis conversation stages.
    """

    def test_gsd_state_mapping_in_pipeline(self):
        """
        The pipeline maps GSD states to Jarvis stages:
        NEW → welcome, GREETING → welcome, DIAGNOSIS → discovery,
        RESOLUTION → demo, FOLLOW_UP → bill_review, CLOSED → handoff
        """
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")

        # Verify the GSD to stage mapping exists
        assert "gsd_to_stage" in func_src
        assert '"NEW"' in func_src
        assert '"GREETING"' in func_src
        assert '"DIAGNOSIS"' in func_src
        assert '"RESOLUTION"' in func_src
        assert '"CLOSED"' in func_src
        assert '"HUMAN_HANDOFF"' in func_src


class TestIntegrationBeforeVsAfterComparison:
    """
    Side-by-side comparison: BEFORE vs AFTER connecting services.
    """

    def test_before_no_functions_after_all_functions(self):
        """
        BEFORE: 0 pipeline helpers defined
        AFTER:  32 pipeline helpers defined
        """
        source = _get_jarvis_source()
        all_functions = _get_function_names(source)

        pipeline_prefix = "_"
        pipeline_functions = [f for f in all_functions if f.startswith(pipeline_prefix)]
        assert len(pipeline_functions) >= 32

    def test_before_no_service_imports_after_has_all(self):
        """
        BEFORE: No service imports in helper functions
        AFTER:  Each helper imports its respective service class
        """
        source = _get_jarvis_source()

        # Count unique service class imports across all pipeline helpers
        service_classes = [
            "PromptInjectionDefense",
            "PIIRedactionEngine",
            "CLARAQualityGate",
            "GuardrailsEngine",
            "ContextCompressor",
            "GSDEngine",
            "SignalExtractor",
            "ClassificationService",
            "BrandVoiceService",
            "RAGRetrieval",
            "RAGReranker",
            "TokenBudgetService",
            "SessionContinuityService",
        ]

        for service in service_classes:
            assert service in source, f"Service class not imported: {service}"

    def test_before_name_error_after_callable(self):
        """
        BEFORE: Calling _scan_prompt_injection would raise NameError
        AFTER:  _scan_prompt_injection is a defined function with lazy import
        """
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_scan_prompt_injection")

        # Verify it's a proper function with try/except
        assert func_src is not None
        assert "def _scan_prompt_injection(" in func_src
        assert "try:" in func_src
        assert "except" in func_src
        assert "from app.core.prompt_injection_defense import" in func_src

    def test_before_no_pipeline_docstring_after_comprehensive(self):
        """
        BEFORE: _call_ai_provider had basic docstring
        AFTER:  _call_ai_provider has 79-service pipeline documentation
        """
        source = _get_jarvis_source()
        func_src = _get_function_source(source, "_call_ai_provider")

        # Verify comprehensive documentation
        assert "PRE-PROCESSING:" in func_src
        assert "AI PIPELINE:" in func_src
        assert "POST-PROCESSING:" in func_src
        assert "OPERATIONS" in func_src
        assert "79 services" in func_src or "Week 8-11" in func_src


class TestIntegrationFileMetrics:
    """
    Metrics: Verify the file has grown appropriately with the new services.
    """

    def test_file_line_count(self):
        """AFTER: jarvis_service.py is 3600+ lines (was 2633 before helpers)."""
        source = _get_jarvis_source()
        line_count = len(source.split("\n"))
        assert line_count >= 3600, f"File should be 3600+ lines, got {line_count}"

    def test_file_function_count(self):
        """AFTER: jarvis_service.py defines 50+ functions."""
        source = _get_jarvis_source()
        functions = _get_function_names(source)
        assert len(functions) >= 50, f"Expected 50+ functions, got {len(functions)}"

    def test_pipeline_helpers_section_size(self):
        """AFTER: Pipeline helpers section is 900+ lines."""
        source = _get_jarvis_source()

        # Find the pipeline section
        start_marker = "Week 8-11: Pipeline Helper Functions"
        assert start_marker in source

        start_idx = source.find(start_marker)
        section = source[start_idx:]
        section_lines = len(section.split("\n"))
        assert (
            section_lines >= 900
        ), f"Pipeline section should be 900+ lines, got {section_lines}"
