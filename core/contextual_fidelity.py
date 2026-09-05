"""
Phase 2.0: Contextual Fidelity Engine (Memory-Programmed ORACLE)
Filename: core/contextual_fidelity.py
"""

import re
from typing import Dict, Any, List, Optional

class ContextualFidelityEngine:
    """
    Shifts behavior from manual runtime prompt directives to automated custody management.
    Evaluates context, assigns seriousness classification, defines the execution envelope,
    and safeguards responses against drift, narrative smoothing, and fictionalized certainties.
    """
    
    # Non-negotiable triggers mapping to critical/high enforcement zones
    STRICT_KEYWORDS = [
        r"legal", r"patent", r"medical", r"health", r"money", r"billing", r"taxes",
        r"identity", r"memory\s+canon", r"email", r"delet", r"publish", r"grief",
        r"accident", r"testimony", r"crisis", r"suicide", r"self-harm", r"credential",
        r"password", r"api\s*key", r"bipolar", r"ada", r"disability", r"financial"
    ]

    @classmethod
    def classify_seriousness(cls, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Classifies interaction severity and sets parameters for permitted imagination/play.
        """
        msg_lower = message.lower()
        context = context or {}
        context_tags = str(context.get("active_tags", [])).lower()
        
        # Determine if a strict trigger is tripped by raw message or context metadata
        is_strict = any(re.search(pattern, msg_lower) for pattern in cls.STRICT_KEYWORDS) or \
                    any(re.search(pattern, context_tags) for pattern in cls.STRICT_KEYWORDS)
        
        # Check if user is explicitly driving a runtime construction or system build
        is_build = "build" in msg_lower or "test" in msg_lower or "compile" in msg_lower or context.get("lane") == "build"

        if is_strict:
            return {
                "seriousness_level": "critical",
                "fiction_allowed": False,
                "playfulness_allowed": False,
                "requires_basis_labels": True,
                "requires_open_holes": True,
                "mode_recommendation": "legal_boundary" if ("legal" in msg_lower or "patent" in msg_lower) else "financial_boundary" if ("money" in msg_lower or "billing" in msg_lower) else "health_boundary" if ("health" in msg_lower or "medical" in msg_lower) else "serious_factual",
                "reason": "Trigger matched a high-stakes operational, financial, medical, or identity domain."
            }
        elif is_build:
            return {
                "seriousness_level": "high",
                "fiction_allowed": False,
                "playfulness_allowed": False,
                "requires_basis_labels": True,
                "requires_open_holes": True,
                "mode_recommendation": "build_operator",
                "reason": "User message asks for system construction or architectural engineering execution."
            }
        elif "play" in msg_lower or "lore" in msg_lower or "story" in msg_lower:
            return {
                "seriousness_level": "low",
                "fiction_allowed": True,
                "playfulness_allowed": True,
                "requires_basis_labels": False,
                "requires_open_holes": False,
                "mode_recommendation": "playful_lore",
                "reason": "Conversational frequency indicators signal play or low-stakes narrative generation."
            }
        elif "help" in msg_lower or "feel" in msg_lower or "tired" in msg_lower:
            return {
                "seriousness_level": "medium",
                "fiction_allowed": False,
                "playfulness_allowed": True,
                "requires_basis_labels": False,
                "requires_open_holes": True,
                "mode_recommendation": "grounded_supportive",
                "reason": "Human baseline signals vulnerability or request for support."
            }
        else:
            return {
                "seriousness_level": "medium",
                "fiction_allowed": False,
                "playfulness_allowed": False,
                "requires_basis_labels": True,
                "requires_open_holes": True,
                "mode_recommendation": "passive_continuity",
                "reason": "Standard operational baseline fallback."
            }

    @classmethod
    def build_context_policy(cls, user_message: str, available_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates execution boundary rules and records missing provenance gaps.
        """
        classification = cls.classify_seriousness(user_message, available_context)
        level = classification["seriousness_level"]
        rec_mode = classification["mode_recommendation"]

        # Parse context parameters and identify presence of valid provenance chains
        sources = available_context.get("sources", [])
        has_provenance = len(sources) > 0
        
        # Identify open holes (unknown factual claims requested without contextual alignment)
        open_holes = []
        if "asserted_claim" in available_context and not has_provenance:
            open_holes.append(available_context["asserted_claim"])
            rec_mode = "uncertain_hole_preserving"

        # Structural enforcement parameters based entirely on intent classification
        max_imagination = "none" if level in ["high", "critical"] else ("light" if rec_mode == "grounded_supportive" else "mythic_labeled")
        msg_lower = user_message.lower()
        tags = [str(t).lower() for t in available_context.get("active_tags", [])]
        is_public_witness = rec_mode == "public_witness" or "publish" in tags or "external" in tags or "broadcast" in msg_lower
        must_preserve_raw = rec_mode in ["passive_continuity", "memory_recovery", "public_witness"] or is_public_witness
        must_approve = level in ["high", "critical"] or rec_mode == "build_operator"

        return {
            "response_mode": rec_mode,
            "allowed_sources": sources,
            "required_basis_labels": classification["requires_basis_labels"],
            "max_imagination_level": max_imagination,
            "must_preserve_raw_text": must_preserve_raw,
            "must_avoid_smoothing": True,
            "must_ask_approval_before_action": must_approve,
            "recall_confidence": "maximum provenance-backed recall fidelity" if has_provenance else "unprovenanced_hole",
            "open_holes": open_holes
        }

    @classmethod
    def apply_fidelity_rules(cls, draft_response: str, policy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verifies that outbound responses do not compromise truth constraints or invent memory.
        """
        violations = []
        
        # Test 1: Absolute prohibition of absolute recall fabrications
        if "100%" in draft_response and ("recall" in draft_response.lower() or "fidelity" in draft_response.lower()):
            violations.append("Prohibited claim of absolute recall capability detected. Must use 'maximum provenance-backed recall fidelity'.")
            
        # Test 2: Serious contexts disable all unauthorized fiction/hallucination metrics
        if policy["max_imagination_level"] == "none":
            # If imagination is forbidden, check for common linguistic indicators of soft fabrication or narrative smoothing
            smoothing_indicators = ["surely", "probably", "must have been", "imagine", "legendary"]
            for indicator in smoothing_indicators:
                if f" {indicator} " in f" {draft_response.lower()} ":
                    violations.append(f"Unsanctioned narrative smoothing marker '{indicator}' inside strict serious domain.")

        # Test 3: Ensure open context gaps are preserved openly rather than glossed over
        if policy["response_mode"] == "uncertain_hole_preserving" or policy["open_holes"]:
            if not any(phrase in draft_response.lower() for phrase in ["i do not know", "missing", "hole", "not available"]):
                violations.append("Response fails to preserve the structural hole defined by the missing provenance policy.")

        # Test 4: Unlabeled fictional lore assertion checks
        if policy["response_mode"] != "playful_lore" and "mythic" in draft_response.lower():
            violations.append("Mythic language found outside explicit playful_lore boundaries.")

        approved = len(violations) == 0
        return {
            "approved": approved,
            "violations": violations,
            "corrected_guidance": "Restructure output to enforce maximum provenance-backed recall fidelity, strip predictive smoothing, and expose empty gaps cleanly." if not approved else ""
        }

    @classmethod
    def memory_programming_receipt_shape(cls, policy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns a structured schema tracking runtime governance parameters. Does not execute IO mutations.
        """
        return {
            "receipt": {
                "engine_version": "2.0-ContextualFidelity",
                "targeted_mode": policy["response_mode"],
                "maximum_provenance_backed_recall_fidelity": True,
                "holes_locked": len(policy["open_holes"]),
                "mutation_performed": False,
                "isolation_verified": True
            }
        }

