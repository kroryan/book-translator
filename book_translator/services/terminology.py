"""
Terminology Manager
===================
Manages consistent terminology across translation chunks.
"""
import re
from typing import Dict, List, Optional, Set


class TerminologyManager:
    """Manages consistent terminology across translation chunks."""
    
    def __init__(self):
        self.terms: Dict[str, str] = {}  # {original_term: translated_term}
        self.proper_nouns: Set[str] = set()
    
    def extract_proper_nouns(self, text: str) -> List[str]:
        """
        Extract proper nouns (capitalized words/phrases) from text.
        
        Args:
            text: Text to analyze
        
        Returns:
            List of unique proper nouns
        """
        # Match capitalized words that are not at sentence start
        pattern = r'(?<!^)(?<![.!?]\s)\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        nouns = re.findall(pattern, text, re.MULTILINE)
        unique_nouns = list(set(nouns))
        self.proper_nouns.update(unique_nouns)
        return unique_nouns
    
    def add_term(self, original: str, translated: str):
        """
        Add a term to the terminology dictionary.
        
        Args:
            original: Original term
            translated: Translated term
        """
        self.terms[original] = translated
    
    def get_term(self, original: str) -> Optional[str]:
        """
        Get translated term if it exists.
        
        Args:
            original: Original term
        
        Returns:
            Translated term or None
        """
        return self.terms.get(original)
    
    def ensure_consistency(self, text: str, chunk_terms: Dict[str, str]) -> str:
        """
        Apply consistent terminology to text.
        
        Args:
            text: Text to process
            chunk_terms: Terms found in current chunk
        
        Returns:
            Text with consistent terminology
        """
        for original, translated in chunk_terms.items():
            if original in self.terms and self.terms[original] != translated:
                # Use consistent term from previous chunks
                text = text.replace(translated, self.terms[original])
            else:
                self.terms[original] = translated
        return text
    
    def get_glossary(self) -> Dict[str, str]:
        """Get the current terminology glossary."""
        return dict(self.terms)
    
    def clear(self):
        """Clear all stored terminology."""
        self.terms.clear()
        self.proper_nouns.clear()
    
    def get_context_for_prompt(self, max_terms: int = 20) -> str:
        """
        Generate terminology context for inclusion in prompts.
        
        Args:
            max_terms: Maximum number of terms to include
        
        Returns:
            Formatted terminology list
        """
        if not self.terms:
            return ""
        
        # Get most recent/important terms
        terms_list = list(self.terms.items())[-max_terms:]
        
        lines = ["TERMINOLOGY (use these translations consistently):"]
        for orig, trans in terms_list:
            lines.append(f"  - {orig} → {trans}")
        
        return "\n".join(lines)
