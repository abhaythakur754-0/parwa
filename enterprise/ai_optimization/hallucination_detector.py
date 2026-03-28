"""
Hallucination Detection Module

This module provides comprehensive hallucination detection for AI-generated responses.
It identifies factual, logical, and consistency-based hallucinations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from datetime import datetime
import re


class HallucinationType(Enum):
    """Enumeration of hallucination types."""
    FACTUAL = "factual"          # Incorrect facts or claims
    LOGICAL = "logical"          # Logical inconsistencies or fallacies
    INCONSISTENCY = "inconsistency"  # Internal contradictions


class HallucinationSeverity(Enum):
    """Severity level of hallucinations."""
    CRITICAL = "critical"    # Completely false/misleading
    HIGH = "high"           # Significant inaccuracy
    MEDIUM = "medium"       # Moderate inaccuracy
    LOW = "low"             # Minor inaccuracy
    MINIMAL = "minimal"     # Barely noticeable


@dataclass
class Evidence:
    """
    Evidence supporting or contradicting a claim.
    
    Attributes:
        claim: The claim being evaluated
        evidence_type: Type of evidence (supporting, contradicting, neutral)
        source: Source of the evidence
        confidence: Confidence in the evidence (0-1)
        details: Additional details about the evidence
    """
    claim: str
    evidence_type: str  # "supporting", "contradicting", "neutral"
    source: str
    confidence: float = 0.5
    details: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert evidence to dictionary."""
        return {
            "claim": self.claim,
            "evidence_type": self.evidence_type,
            "source": self.source,
            "confidence": self.confidence,
            "details": self.details
        }


@dataclass
class HallucinationResult:
    """
    Result of hallucination detection.
    
    Attributes:
        is_hallucination: Whether hallucination was detected
        hallucination_type: Type of hallucination detected
        confidence: Confidence in the detection (0-1)
        evidence: List of evidence supporting the detection
        severity: Severity level of the hallucination
        location: Location in text where hallucination was found
        suggestion: Suggested correction if available
        timestamp: When the detection was performed
    """
    is_hallucination: bool
    hallucination_type: Optional[HallucinationType] = None
    confidence: float = 0.0
    evidence: List[Evidence] = field(default_factory=list)
    severity: HallucinationSeverity = HallucinationSeverity.MINIMAL
    location: Tuple[int, int] = (0, 0)
    suggestion: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "is_hallucination": self.is_hallucination,
            "hallucination_type": self.hallucination_type.value if self.hallucination_type else None,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "severity": self.severity.value,
            "location": self.location,
            "suggestion": self.suggestion,
            "timestamp": self.timestamp.isoformat()
        }
    
    def add_evidence(self, evidence: Evidence) -> None:
        """Add evidence to the result."""
        self.evidence.append(evidence)


@dataclass
class FactCheckResult:
    """Result from fact-checking a claim."""
    claim: str
    is_verified: bool
    confidence: float
    sources: List[str] = field(default_factory=list)
    correction: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "claim": self.claim,
            "is_verified": self.is_verified,
            "confidence": self.confidence,
            "sources": self.sources,
            "correction": self.correction
        }


class FactChecker:
    """
    Fact-checking integration stub.
    
    This class provides a placeholder for integration with external
    fact-checking services.
    """
    
    def __init__(self):
        """Initialize the fact checker."""
        self._verified_facts: Dict[str, FactCheckResult] = {}
        self._known_facts: Dict[str, bool] = {
            # Sample known facts for demonstration
            "the earth is round": True,
            "the earth is flat": False,
            "water boils at 100 degrees celsius at sea level": True,
            "the sun rises in the west": False,
            "paris is the capital of france": True,
            "london is the capital of france": False,
            "the human body has 206 bones": True,
            "the human body has 1000 bones": False,
            "python was created by guido van rossum": True,
            "python was created by bill gates": False,
        }
        self._fact_check_calls = 0
    
    def check_fact(self, claim: str) -> FactCheckResult:
        """
        Check if a claim is factually correct.
        
        Args:
            claim: The claim to check
            
        Returns:
            FactCheckResult with verification status
        """
        self._fact_check_calls += 1
        claim_lower = claim.lower().strip()
        
        # Check if we have a known fact
        for known_fact, is_true in self._known_facts.items():
            if known_fact in claim_lower or claim_lower in known_fact:
                result = FactCheckResult(
                    claim=claim,
                    is_verified=is_true,
                    confidence=0.95,
                    sources=["internal_knowledge_base"],
                    correction="" if is_true else f"This claim is incorrect."
                )
                self._verified_facts[claim] = result
                return result
        
        # Return unverified for unknown claims
        return FactCheckResult(
            claim=claim,
            is_verified=False,
            confidence=0.5,
            sources=[],
            correction=""
        )
    
    def add_known_fact(self, fact: str, is_true: bool) -> None:
        """Add a known fact to the database."""
        self._known_facts[fact.lower()] = is_true
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get fact-checking statistics."""
        return {
            "total_checks": self._fact_check_calls,
            "verified_facts": len(self._verified_facts),
            "known_facts": len(self._known_facts)
        }


class HallucinationDetector:
    """
    Main class for detecting hallucinations in AI-generated responses.
    
    This class identifies factual inaccuracies, logical inconsistencies,
    and internal contradictions in text.
    """
    
    def __init__(self, fact_checker: Optional[FactChecker] = None):
        """
        Initialize the hallucination detector.
        
        Args:
            fact_checker: Optional fact-checker instance for fact verification
        """
        self.fact_checker = fact_checker or FactChecker()
        self._detection_history: List[HallucinationResult] = []
        self._patterns = self._initialize_patterns()
    
    def _initialize_patterns(self) -> Dict[str, List[str]]:
        """Initialize hallucination detection patterns."""
        return {
            "certainty_markers": [
                "definitely", "certainly", "absolutely", "undoubtedly",
                "without a doubt", "guaranteed", "always", "never"
            ],
            "hedging_markers": [
                "possibly", "maybe", "perhaps", "might", "could",
                "sometimes", "often", "usually", "typically"
            ],
            "contradiction_markers": [
                "however", "but", "on the other hand", "conversely",
                "in contrast", "despite", "although"
            ],
            "numerical_patterns": [
                r'\d+%',
                r'\d+\s*(?:million|billion|trillion)',
                r'\d+\s*(?:percent|percentage)',
            ],
            "temporal_patterns": [
                r'\d{4}',  # Years
                r'\d{1,2}/\d{1,2}/\d{2,4}',  # Dates
                r'(?:january|february|march|april|may|june|july|august|september|october|november|december)',
            ]
        }
    
    def detect(
        self,
        response: str,
        context: Optional[str] = None,
        known_facts: Optional[Dict[str, bool]] = None,
        detection_types: Optional[List[HallucinationType]] = None
    ) -> List[HallucinationResult]:
        """
        Detect hallucinations in a response.
        
        Args:
            response: The AI-generated response to analyze
            context: Optional context for consistency checking
            known_facts: Optional dictionary of known facts for fact checking
            detection_types: Optional list of hallucination types to check
            
        Returns:
            List of HallucinationResult objects
        """
        if not response or not response.strip():
            return []
        
        results: List[HallucinationResult] = []
        types_to_check = detection_types or list(HallucinationType)
        
        # Add known facts to fact checker if provided
        if known_facts:
            for fact, is_true in known_facts.items():
                self.fact_checker.add_known_fact(fact, is_true)
        
        for h_type in types_to_check:
            if h_type == HallucinationType.FACTUAL:
                results.extend(self._detect_factual_hallucinations(response))
            elif h_type == HallucinationType.LOGICAL:
                results.extend(self._detect_logical_hallucinations(response))
            elif h_type == HallucinationType.INCONSISTENCY:
                results.extend(self._detect_inconsistencies(response, context))
        
        self._detection_history.extend(results)
        return results
    
    def _detect_factual_hallucinations(self, response: str) -> List[HallucinationResult]:
        """Detect factual hallucinations by checking claims against known facts."""
        results: List[HallucinationResult] = []
        sentences = self._extract_claims(response)
        
        for sentence, start, end in sentences:
            # Skip very short or trivial sentences
            if len(sentence.split()) < 3:
                continue
            
            # Check for certainty markers that might indicate overconfidence
            has_certainty = any(
                marker in sentence.lower() 
                for marker in self._patterns["certainty_markers"]
            )
            
            # Fact check the claim
            fact_result = self.fact_checker.check_fact(sentence)
            
            if fact_result.confidence > 0.7 and not fact_result.is_verified:
                # Claim is likely false
                evidence = Evidence(
                    claim=sentence,
                    evidence_type="contradicting",
                    source="fact_checker",
                    confidence=fact_result.confidence,
                    details="Claim contradicts known facts"
                )
                
                result = HallucinationResult(
                    is_hallucination=True,
                    hallucination_type=HallucinationType.FACTUAL,
                    confidence=fact_result.confidence,
                    evidence=[evidence],
                    severity=HallucinationSeverity.HIGH if has_certainty else HallucinationSeverity.MEDIUM,
                    location=(start, end),
                    suggestion=fact_result.correction
                )
                results.append(result)
            elif has_certainty and fact_result.confidence < 0.5:
                # Overconfident statement about unknown fact
                evidence = Evidence(
                    claim=sentence,
                    evidence_type="neutral",
                    source="pattern_analysis",
                    confidence=0.6,
                    details="Certainty marker used for unverified claim"
                )
                
                result = HallucinationResult(
                    is_hallucination=True,
                    hallucination_type=HallucinationType.FACTUAL,
                    confidence=0.6,
                    evidence=[evidence],
                    severity=HallucinationSeverity.LOW,
                    location=(start, end),
                    suggestion="Consider using hedging language for uncertain claims"
                )
                results.append(result)
        
        return results
    
    def _detect_logical_hallucinations(self, response: str) -> List[HallucinationResult]:
        """Detect logical inconsistencies and fallacies."""
        results: List[HallucinationResult] = []
        
        # Check for circular reasoning
        circular = self._check_circular_reasoning(response)
        results.extend(circular)
        
        # Check for false cause fallacies
        false_cause = self._check_false_cause(response)
        results.extend(false_cause)
        
        # Check for unsupported generalizations
        generalizations = self._check_generalizations(response)
        results.extend(generalizations)
        
        return results
    
    def _detect_inconsistencies(
        self, 
        response: str, 
        context: Optional[str]
    ) -> List[HallucinationResult]:
        """Detect internal and contextual inconsistencies."""
        results: List[HallucinationResult] = []
        
        # Check for internal contradictions
        internal = self._check_internal_contradictions(response)
        results.extend(internal)
        
        # Check for context contradictions if context provided
        if context:
            contextual = self._check_context_contradictions(response, context)
            results.extend(contextual)
        
        return results
    
    def _extract_claims(self, text: str) -> List[Tuple[str, int, int]]:
        """Extract potential claims from text with their positions."""
        claims = []
        sentences = re.split(r'([.!?]+)', text)
        
        current_pos = 0
        current_sentence = ""
        
        for part in sentences:
            if part.strip() in '.!?':
                full_sentence = current_sentence.strip()
                if full_sentence:
                    start = text.find(full_sentence, current_pos)
                    end = start + len(full_sentence)
                    claims.append((full_sentence, start, end))
                    current_pos = end
                current_sentence = ""
            else:
                current_sentence += part
        
        # Handle remaining text
        if current_sentence.strip():
            start = text.find(current_sentence.strip(), current_pos)
            if start != -1:
                claims.append((current_sentence.strip(), start, start + len(current_sentence.strip())))
        
        return claims
    
    def _check_circular_reasoning(self, response: str) -> List[HallucinationResult]:
        """Check for circular reasoning patterns."""
        results = []
        sentences = [s.strip() for s in re.split(r'[.!?]+', response) if s.strip()]
        
        for i, sentence in enumerate(sentences):
            words = set(re.findall(r'\b\w+\b', sentence.lower()))
            for j, other in enumerate(sentences):
                if i != j:
                    other_words = set(re.findall(r'\b\w+\b', other.lower()))
                    overlap = words & other_words
                    # High overlap might indicate circular reasoning
                    if len(overlap) > min(len(words), len(other_words)) * 0.8:
                        if len(words) > 5 and len(other_words) > 5:
                            evidence = Evidence(
                                claim=sentence,
                                evidence_type="contradicting",
                                source="logical_analysis",
                                confidence=0.5,
                                details=f"Potential circular reasoning with sentence {j+1}"
                            )
                            result = HallucinationResult(
                                is_hallucination=True,
                                hallucination_type=HallucinationType.LOGICAL,
                                confidence=0.5,
                                evidence=[evidence],
                                severity=HallucinationSeverity.LOW,
                                location=(0, len(sentence)),
                                suggestion="Review for circular reasoning"
                            )
                            results.append(result)
        
        return results
    
    def _check_false_cause(self, response: str) -> List[HallucinationResult]:
        """Check for false cause fallacies."""
        results = []
        # Pattern: "because", "therefore", "caused by", etc.
        causal_patterns = [
            (r'(.+?)\s+because\s+(.+)', "because"),
            (r'(.+?)\s+therefore\s+(.+)', "therefore"),
            (r'(.+?)\s+caused\s+(.+)', "caused"),
            (r'(.+?)\s+leads\s+to\s+(.+)', "leads to"),
        ]
        
        response_lower = response.lower()
        for pattern, marker in causal_patterns:
            matches = re.finditer(pattern, response_lower)
            for match in matches:
                cause, effect = match.groups()
                # Simple heuristic: if cause and effect are very similar
                # it might be a false cause
                cause_words = set(cause.split())
                effect_words = set(effect.split())
                similarity = len(cause_words & effect_words) / max(len(cause_words), len(effect_words), 1)
                
                if similarity > 0.7:
                    evidence = Evidence(
                        claim=match.group(0),
                        evidence_type="neutral",
                        source="logical_analysis",
                        confidence=0.4,
                        details=f"Potential false cause fallacy using '{marker}'"
                    )
                    result = HallucinationResult(
                        is_hallucination=True,
                        hallucination_type=HallucinationType.LOGICAL,
                        confidence=0.4,
                        evidence=[evidence],
                        severity=HallucinationSeverity.LOW,
                        location=(match.start(), match.end()),
                        suggestion="Verify causal relationship"
                    )
                    results.append(result)
        
        return results
    
    def _check_generalizations(self, response: str) -> List[HallucinationResult]:
        """Check for unsupported generalizations."""
        results = []
        
        generalization_markers = [
            "all", "every", "always", "never", "none", "nobody",
            "everyone", "everything", "everywhere"
        ]
        
        sentences = self._extract_claims(response)
        for sentence, start, end in sentences:
            for marker in generalization_markers:
                if f" {marker} " in f" {sentence.lower()} ":
                    # Check if there's supporting evidence
                    if "because" not in sentence.lower() and "for example" not in sentence.lower():
                        evidence = Evidence(
                            claim=sentence,
                            evidence_type="neutral",
                            source="pattern_analysis",
                            confidence=0.5,
                            details=f"Generalization with '{marker}' without support"
                        )
                        result = HallucinationResult(
                            is_hallucination=True,
                            hallucination_type=HallucinationType.LOGICAL,
                            confidence=0.5,
                            evidence=[evidence],
                            severity=HallucinationSeverity.LOW,
                            location=(start, end),
                            suggestion="Consider providing evidence or using qualified language"
                        )
                        results.append(result)
                        break
        
        return results
    
    def _check_internal_contradictions(self, response: str) -> List[HallucinationResult]:
        """Check for contradictions within the response."""
        results = []
        sentences = [s.strip() for s in re.split(r'[.!?]+', response) if s.strip()]
        
        # Pairs of contradicting words
        contradicting_pairs = [
            ("always", "never"),
            ("all", "none"),
            ("increase", "decrease"),
            ("rise", "fall"),
            ("expand", "shrink"),
            ("true", "false"),
            ("yes", "no"),
        ]
        
        for i, sentence1 in enumerate(sentences):
            for j, sentence2 in enumerate(sentences):
                if i >= j:
                    continue
                
                s1_lower = sentence1.lower()
                s2_lower = sentence2.lower()
                
                for word1, word2 in contradicting_pairs:
                    if (word1 in s1_lower and word2 in s2_lower) or \
                       (word2 in s1_lower and word1 in s2_lower):
                        # Check if they're talking about the same subject
                        s1_subjects = set(re.findall(r'\b[a-z]+\b', s1_lower[:50]))
                        s2_subjects = set(re.findall(r'\b[a-z]+\b', s2_lower[:50]))
                        subject_overlap = s1_subjects & s2_subjects
                        
                        if len(subject_overlap) >= 2:
                            evidence = Evidence(
                                claim=f"{sentence1} vs {sentence2}",
                                evidence_type="contradicting",
                                source="contradiction_analysis",
                                confidence=0.7,
                                details=f"Found contradicting words '{word1}' and '{word2}'"
                            )
                            result = HallucinationResult(
                                is_hallucination=True,
                                hallucination_type=HallucinationType.INCONSISTENCY,
                                confidence=0.7,
                                evidence=[evidence],
                                severity=HallucinationSeverity.MEDIUM,
                                location=(0, len(response)),
                                suggestion="Review for internal contradiction"
                            )
                            results.append(result)
        
        return results
    
    def _check_context_contradictions(
        self, 
        response: str, 
        context: str
    ) -> List[HallucinationResult]:
        """Check for contradictions with the provided context."""
        results = []
        
        # Extract key facts from context
        context_sentences = [s.strip() for s in re.split(r'[.!?]+', context) if s.strip()]
        response_lower = response.lower()
        
        # Check for negations of context facts
        negation_patterns = [
            (r'not\s+(\w+)', "not"),
            (r'never\s+(\w+)', "never"),
            (r"doesn't\s+(\w+)", "doesn't"),
            (r"isn't\s+(\w+)", "isn't"),
        ]
        
        for sentence in context_sentences:
            sentence_lower = sentence.lower()
            for pattern, _ in negation_patterns:
                # Check if response negates something from context
                context_matches = re.findall(pattern, sentence_lower)
                for word in context_matches:
                    if f"not {word}" in response_lower or f"never {word}" in response_lower:
                        evidence = Evidence(
                            claim=sentence,
                            evidence_type="contradicting",
                            source="context_analysis",
                            confidence=0.6,
                            details="Response contradicts provided context"
                        )
                        result = HallucinationResult(
                            is_hallucination=True,
                            hallucination_type=HallucinationType.INCONSISTENCY,
                            confidence=0.6,
                            evidence=[evidence],
                            severity=HallucinationSeverity.HIGH,
                            location=(0, len(response)),
                            suggestion="Align response with provided context"
                        )
                        results.append(result)
        
        return results
    
    def get_detection_history(self, limit: int = 10) -> List[HallucinationResult]:
        """Get recent detection history."""
        return self._detection_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear detection history."""
        self._detection_history = []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detection statistics."""
        if not self._detection_history:
            return {
                "total_detections": 0,
                "by_type": {},
                "by_severity": {},
                "average_confidence": 0.0
            }
        
        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        total_confidence = 0.0
        
        for result in self._detection_history:
            if result.is_hallucination:
                h_type = result.hallucination_type.value if result.hallucination_type else "unknown"
                by_type[h_type] = by_type.get(h_type, 0) + 1
                
                severity = result.severity.value
                by_severity[severity] = by_severity.get(severity, 0) + 1
                
                total_confidence += result.confidence
        
        hallucination_count = sum(by_type.values())
        
        return {
            "total_detections": len(self._detection_history),
            "hallucination_count": hallucination_count,
            "by_type": by_type,
            "by_severity": by_severity,
            "average_confidence": total_confidence / max(hallucination_count, 1),
            "fact_checker_stats": self.fact_checker.get_statistics()
        }
    
    def add_custom_pattern(
        self, 
        category: str, 
        patterns: List[str]
    ) -> None:
        """
        Add custom detection patterns.
        
        Args:
            category: Pattern category name
            patterns: List of patterns to add
        """
        if category not in self._patterns:
            self._patterns[category] = []
        self._patterns[category].extend(patterns)
    
    def get_hallucination_score(self, response: str, **kwargs) -> float:
        """
        Get an overall hallucination score for a response.
        
        Args:
            response: The response to score
            **kwargs: Additional arguments passed to detect()
            
        Returns:
            Score from 0.0 (no hallucinations) to 1.0 (high hallucination)
        """
        results = self.detect(response, **kwargs)
        if not results:
            return 0.0
        
        # Weight by severity
        severity_weights = {
            HallucinationSeverity.CRITICAL: 1.0,
            HallucinationSeverity.HIGH: 0.8,
            HallucinationSeverity.MEDIUM: 0.5,
            HallucinationSeverity.LOW: 0.3,
            HallucinationSeverity.MINIMAL: 0.1,
        }
        
        weighted_sum = 0.0
        for result in results:
            weight = severity_weights.get(result.severity, 0.5)
            weighted_sum += result.confidence * weight
        
        # Normalize to 0-1
        max_possible = len(results) * 1.0
        return min(1.0, weighted_sum / max_possible) if max_possible > 0 else 0.0
