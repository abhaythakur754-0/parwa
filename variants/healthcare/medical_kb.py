"""
Medical Knowledge Base.
Week 33, Builder 4: Healthcare HIPAA + Logistics

Medical terminology intelligence, ICD/CPT code lookup, and healthcare knowledge.
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from datetime import datetime

logger = logging.getLogger(__name__)


class MedicalTermCategory(Enum):
    """Categories of medical terminology."""
    CONDITION = "condition"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    ANATOMY = "anatomy"
    SYMPTOM = "symptom"
    DIAGNOSTIC = "diagnostic"
    TREATMENT = "treatment"
    SPECIALTY = "specialty"
    ABBREVIATION = "abbreviation"


@dataclass
class MedicalTerm:
    """Medical terminology entry."""
    term_id: str
    name: str
    category: MedicalTermCategory
    definition: str
    aliases: List[str] = field(default_factory=list)
    icd_codes: List[str] = field(default_factory=list)
    cpt_codes: List[str] = field(default_factory=list)
    related_terms: List[str] = field(default_factory=list)
    patient_friendly_name: Optional[str] = None
    urgency_level: str = "routine"  # routine, urgent, emergency
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'term_id': self.term_id,
            'name': self.name,
            'category': self.category.value,
            'definition': self.definition,
            'aliases': self.aliases,
            'icd_codes': self.icd_codes,
            'cpt_codes': self.cpt_codes,
            'related_terms': self.related_terms,
            'patient_friendly_name': self.patient_friendly_name,
            'urgency_level': self.urgency_level,
            'metadata': self.metadata,
        }


@dataclass
class CodeLookupResult:
    """Result of medical code lookup."""
    code: str
    code_type: str  # icd-10, icd-9, cpt
    description: str
    category: Optional[str] = None
    parent_code: Optional[str] = None
    child_codes: List[str] = field(default_factory=list)
    is_billable: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class MedicalKnowledgeBase:
    """
    Medical Knowledge Base for healthcare terminology intelligence.

    Provides medical term recognition, code lookup, and patient-friendly
    explanations for healthcare support scenarios.
    """

    # Common medical abbreviations
    ABBREVIATIONS = {
        "BP": "Blood Pressure",
        "HR": "Heart Rate",
        "Temp": "Temperature",
        "RR": "Respiratory Rate",
        "SOB": "Shortness of Breath",
        "N/V": "Nausea and Vomiting",
        "Hx": "History",
        "Dx": "Diagnosis",
        "Tx": "Treatment",
        "Rx": "Prescription",
        "PRN": "As Needed",
        "BID": "Twice Daily",
        "TID": "Three Times Daily",
        "QID": "Four Times Daily",
        "QD": "Once Daily",
        "STAT": "Immediately",
        "NPO": "Nothing by Mouth",
        "PO": "By Mouth",
        "IV": "Intravenous",
        "IM": "Intramuscular",
        "SC": "Subcutaneous",
        "DNR": "Do Not Resuscitate",
        "DNI": "Do Not Intubate",
        "CPR": "Cardiopulmonary Resuscitation",
        "ER": "Emergency Room",
        "ICU": "Intensive Care Unit",
        "OR": "Operating Room",
        "ED": "Emergency Department",
        "OPD": "Outpatient Department",
        "GP": "General Practitioner",
        "MD": "Medical Doctor",
        "RN": "Registered Nurse",
        "PA": "Physician Assistant",
        "NP": "Nurse Practitioner",
    }

    # ICD-10 Common codes
    ICD10_CODES = {
        # Respiratory
        "J18.9": {"desc": "Pneumonia, unspecified organism", "category": "respiratory"},
        "J45.909": {"desc": "Unspecified asthma, uncomplicated", "category": "respiratory"},
        "J06.9": {"desc": "Acute upper respiratory infection, unspecified", "category": "respiratory"},
        "J20.9": {"desc": "Acute bronchitis, unspecified", "category": "respiratory"},
        # Cardiovascular
        "I10": {"desc": "Essential (primary) hypertension", "category": "cardiovascular"},
        "I25.10": {"desc": "Atherosclerotic heart disease of native coronary artery", "category": "cardiovascular"},
        "I50.9": {"desc": "Heart failure, unspecified", "category": "cardiovascular"},
        # Endocrine
        "E11.9": {"desc": "Type 2 diabetes mellitus without complications", "category": "endocrine"},
        "E10.9": {"desc": "Type 1 diabetes mellitus without complications", "category": "endocrine"},
        "E03.9": {"desc": "Hypothyroidism, unspecified", "category": "endocrine"},
        # Musculoskeletal
        "M54.5": {"desc": "Low back pain", "category": "musculoskeletal"},
        "M79.3": {"desc": "Panniculitis, unspecified", "category": "musculoskeletal"},
        "G47.00": {"desc": "Insomnia, unspecified", "category": "neurological"},
        # Digestive
        "K21.0": {"desc": "Gastro-esophageal reflux disease with esophagitis", "category": "digestive"},
        "K29.70": {"desc": "Gastritis, unspecified, without bleeding", "category": "digestive"},
        "K59.00": {"desc": "Constipation, unspecified", "category": "digestive"},
        # Mental Health
        "F32.9": {"desc": "Major depressive disorder, single episode, unspecified", "category": "mental_health"},
        "F41.9": {"desc": "Anxiety disorder, unspecified", "category": "mental_health"},
        # Infections
        "A09": {"desc": "Infectious gastroenteritis and colitis, unspecified", "category": "infectious"},
        "Z20.828": {"desc": "Contact with and (suspected) exposure to COVID-19", "category": "infectious"},
    }

    # CPT Common codes
    CPT_CODES = {
        "99213": {"desc": "Office/outpatient visit, established patient, low complexity", "category": "evaluation"},
        "99214": {"desc": "Office/outpatient visit, established patient, moderate complexity", "category": "evaluation"},
        "99215": {"desc": "Office/outpatient visit, established patient, high complexity", "category": "evaluation"},
        "99203": {"desc": "Office/outpatient visit, new patient, low complexity", "category": "evaluation"},
        "99204": {"desc": "Office/outpatient visit, new patient, moderate complexity", "category": "evaluation"},
        "99285": {"desc": "Emergency department visit, high complexity", "category": "emergency"},
        "36415": {"desc": "Routine venipuncture", "category": "laboratory"},
        "80053": {"desc": "Comprehensive metabolic panel", "category": "laboratory"},
        "85025": {"desc": "Complete blood count", "category": "laboratory"},
        "71046": {"desc": "Chest X-ray, 2 views", "category": "radiology"},
        "93000": {"desc": "Electrocardiogram, routine ECG", "category": "cardiac"},
    }

    # Urgency keywords
    EMERGENCY_KEYWORDS = [
        "chest pain", "difficulty breathing", "severe bleeding", "stroke",
        "heart attack", "unconscious", "seizure", "anaphylaxis", "suicide",
        "overdose", "severe allergic", "unable to breathe",
    ]

    URGENT_KEYWORDS = [
        "high fever", "severe pain", "vomiting blood", "sudden vision",
        "severe headache", "persistent vomiting", "dehydration", "infection",
        "swelling", "rash spreading", "high blood pressure",
    ]

    def __init__(
        self,
        client_id: str,
        enable_code_lookup: bool = True,
    ):
        """
        Initialize Medical Knowledge Base.

        Args:
            client_id: Client identifier
            enable_code_lookup: Enable ICD/CPT code lookup
        """
        self.client_id = client_id
        self.enable_code_lookup = enable_code_lookup

        # Term storage
        self._terms: Dict[str, MedicalTerm] = {}
        self._category_index: Dict[MedicalTermCategory, Set[str]] = {
            cat: set() for cat in MedicalTermCategory
        }

        # Metrics
        self._lookup_count = 0
        self._term_count = 0

        # Initialize with common terms
        self._initialize_common_terms()

        logger.info({
            "event": "medical_kb_initialized",
            "client_id": client_id,
            "terms_loaded": len(self._terms),
        })

    def _initialize_common_terms(self):
        """Initialize with common medical terms."""
        common_terms = [
            MedicalTerm(
                term_id="term_hypertension",
                name="Hypertension",
                category=MedicalTermCategory.CONDITION,
                definition="High blood pressure, a common condition where the force of blood against artery walls is too high",
                aliases=["high blood pressure", "HTN", "elevated BP"],
                icd_codes=["I10"],
                patient_friendly_name="High Blood Pressure",
                urgency_level="routine",
            ),
            MedicalTerm(
                term_id="term_diabetes",
                name="Diabetes Mellitus",
                category=MedicalTermCategory.CONDITION,
                definition="A group of diseases that result in too much sugar in the blood (high blood glucose)",
                aliases=["diabetes", "DM", "high blood sugar"],
                icd_codes=["E11.9", "E10.9"],
                patient_friendly_name="Diabetes",
                urgency_level="routine",
            ),
            MedicalTerm(
                term_id="term_asthma",
                name="Asthma",
                category=MedicalTermCategory.CONDITION,
                definition="A condition where airways narrow and swell and may produce extra mucus",
                aliases=["reactive airway disease"],
                icd_codes=["J45.909"],
                urgency_level="routine",
            ),
            MedicalTerm(
                term_id="term_pneumonia",
                name="Pneumonia",
                category=MedicalTermCategory.CONDITION,
                definition="Infection that inflames air sacs in one or both lungs",
                aliases=["lung infection"],
                icd_codes=["J18.9"],
                urgency_level="urgent",
            ),
            MedicalTerm(
                term_id="term_mri",
                name="Magnetic Resonance Imaging",
                category=MedicalTermCategory.DIAGNOSTIC,
                definition="A medical imaging technique using magnetic fields to create detailed images",
                aliases=["MRI scan", "magnetic resonance"],
                patient_friendly_name="MRI Scan",
                urgency_level="routine",
            ),
            MedicalTerm(
                term_id="term_ct_scan",
                name="Computed Tomography Scan",
                category=MedicalTermCategory.DIAGNOSTIC,
                definition="An imaging procedure that uses X-rays to create cross-sectional images",
                aliases=["CT", "CAT scan"],
                patient_friendly_name="CT Scan",
                urgency_level="routine",
            ),
        ]

        for term in common_terms:
            self._terms[term.term_id] = term
            self._category_index[term.category].add(term.term_id)
            self._term_count += 1

    def lookup_term(self, query: str) -> List[MedicalTerm]:
        """
        Look up medical terms by name or alias.

        Args:
            query: Search query

        Returns:
            List of matching terms
        """
        query_lower = query.lower()
        results = []

        for term in self._terms.values():
            # Check name
            if query_lower in term.name.lower():
                results.append(term)
                continue

            # Check aliases
            for alias in term.aliases:
                if query_lower in alias.lower():
                    results.append(term)
                    break

        self._lookup_count += 1
        return results

    def lookup_code(self, code: str) -> Optional[CodeLookupResult]:
        """
        Look up ICD or CPT code.

        Args:
            code: Medical code to look up

        Returns:
            Code lookup result or None
        """
        code_upper = code.upper().replace(".", "")

        # Check ICD-10
        for icd_code, info in self.ICD10_CODES.items():
            if icd_code.replace(".", "") == code_upper or icd_code.upper() == code.upper():
                self._lookup_count += 1
                return CodeLookupResult(
                    code=icd_code,
                    code_type="icd-10",
                    description=info["desc"],
                    category=info.get("category"),
                )

        # Check CPT
        for cpt_code, info in self.CPT_CODES.items():
            if cpt_code == code_upper or cpt_code == code:
                self._lookup_count += 1
                return CodeLookupResult(
                    code=cpt_code,
                    code_type="cpt",
                    description=info["desc"],
                    category=info.get("category"),
                    is_billable=True,
                )

        return None

    def expand_abbreviation(self, abbr: str) -> Optional[str]:
        """
        Expand a medical abbreviation.

        Args:
            abbr: Abbreviation to expand

        Returns:
            Full term or None
        """
        return self.ABBREVIATIONS.get(abbr.upper())

    def assess_urgency(self, text: str) -> Dict[str, Any]:
        """
        Assess urgency level from text.

        Args:
            text: Text to analyze

        Returns:
            Urgency assessment
        """
        text_lower = text.lower()

        # Check for emergency keywords
        for keyword in self.EMERGENCY_KEYWORDS:
            if keyword in text_lower:
                return {
                    "level": "emergency",
                    "reason": f"Emergency keyword detected: {keyword}",
                    "recommended_action": "Immediate medical attention required. Call emergency services.",
                }

        # Check for urgent keywords
        for keyword in self.URGENT_KEYWORDS:
            if keyword in text_lower:
                return {
                    "level": "urgent",
                    "reason": f"Urgent keyword detected: {keyword}",
                    "recommended_action": "Seek medical attention within 24 hours.",
                }

        return {
            "level": "routine",
            "reason": "No urgent indicators detected",
            "recommended_action": "Schedule appointment as needed.",
        }

    def get_patient_friendly_explanation(
        self,
        term_or_code: str,
    ) -> Dict[str, Any]:
        """
        Get patient-friendly explanation.

        Args:
            term_or_code: Medical term or code

        Returns:
            Explanation dictionary
        """
        # Try as code first
        code_result = self.lookup_code(term_or_code)
        if code_result:
            return {
                "input": term_or_code,
                "type": "code",
                "code_type": code_result.code_type,
                "medical_term": code_result.description,
                "explanation": code_result.description,
                "category": code_result.category,
            }

        # Try as term
        terms = self.lookup_term(term_or_code)
        if terms:
            term = terms[0]
            return {
                "input": term_or_code,
                "type": "term",
                "medical_term": term.name,
                "explanation": term.definition,
                "patient_friendly_name": term.patient_friendly_name,
                "urgency": term.urgency_level,
                "related_codes": term.icd_codes[:3] if term.icd_codes else [],
            }

        return {
            "input": term_or_code,
            "type": "unknown",
            "explanation": f"No medical information found for '{term_or_code}'",
        }

    def get_terms_by_category(
        self,
        category: MedicalTermCategory,
    ) -> List[MedicalTerm]:
        """Get all terms in a category."""
        term_ids = self._category_index.get(category, set())
        return [self._terms[tid] for tid in term_ids]

    def add_term(self, term: MedicalTerm) -> MedicalTerm:
        """Add a medical term to the knowledge base."""
        self._terms[term.term_id] = term
        self._category_index[term.category].add(term.term_id)
        self._term_count += 1

        logger.info({
            "event": "medical_term_added",
            "term_id": term.term_id,
            "name": term.name,
        })

        return term

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        return {
            "client_id": self.client_id,
            "term_count": self._term_count,
            "lookup_count": self._lookup_count,
            "categories": {
                cat.value: len(terms)
                for cat, terms in self._category_index.items()
            },
            "icd_codes_available": len(self.ICD10_CODES),
            "cpt_codes_available": len(self.CPT_CODES),
            "abbreviations_available": len(self.ABBREVIATIONS),
        }
