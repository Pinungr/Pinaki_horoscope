from typing import List, Dict, Set
from app.models.domain import Rule

class InterpreterEngine:
    """Combines rules, avoids duplicates, and scores predictions."""

    def interpret(self, raw_predictions: List[str], all_rules: List[Rule]) -> List[Dict[str, str]]:
        """
        Takes raw string predictions from RuleEngine and cross-references them against all_rules 
        to recover Categories and Priorities dynamically without breaking Phase 1.
        """
        seen_texts: Set[str] = set()
        interpretations = []

        # Build a lookup table from all_rules
        rule_lookup = {}
        for r in all_rules:
            norm_txt = r.result_text.strip().lower()
            if norm_txt not in rule_lookup:
                rule_lookup[norm_txt] = r

        for raw_text in raw_predictions:
            normalized_text = raw_text.strip().lower()
            
            # Avoid exact duplicates
            if normalized_text in seen_texts:
                continue
            seen_texts.add(normalized_text)
            
            # Lookup metadata
            matched_rule = rule_lookup.get(normalized_text)
            score = matched_rule.priority if matched_rule else 0
            cat = matched_rule.category.strip() if matched_rule and matched_rule.category else "General"
            
            interpretations.append({
                "text": raw_text,
                "category": cat,
                "score": score
            })

        # Sort by priority descending (highest score first)
        sorted_interpretations = sorted(interpretations, key=lambda i: i["score"], reverse=True)

        return sorted_interpretations
