import re
from typing import List, Tuple
from urllib.parse import urlparse
from validators.rejected_facts import RejectedFactsLogger
from config import Config

class ClaimValidator:
    """
    Stage 4 - The only write path for facts before canonicalization.
    Enforces page-type contamination checks, plausibility bounds,
    forbidden domains, and confidence thresholds.
    """
    
    def __init__(self, logger: RejectedFactsLogger, program_id: str, allowed_subdomains: List[str] = None):
        self.logger = logger
        self.program_id = program_id
        self.allowed_subdomains = [d.lower() for d in (allowed_subdomains or [])]
        
    def validate(self, facts: List[dict], page_metadata_lookup: dict) -> List[dict]:
        """
        Validates a list of facts. 
        Returns only the valid facts. Rejected facts are logged.
        `page_metadata_lookup` is a dict mapping url -> metadata (including page_type from discovery).
        """
        valid_facts = []
        
        for fact in facts:
            source_url = fact.get("source_url", "")
            field = fact.get("field", "")
            value = fact.get("value")
            
            # 1. Confidence Threshold
            confidence = fact.get("confidence", 1.0)
            if isinstance(confidence, (int, float)) and confidence < Config.MIN_FACT_CONFIDENCE:
                self.logger.log(self.program_id, fact, "low_confidence", f"Confidence {confidence} < {Config.MIN_FACT_CONFIDENCE}")
                continue
                
            # 2. Page-Type Contamination Check
            if source_url in page_metadata_lookup:
                page_type = page_metadata_lookup[source_url].get("page_type", "Unknown")
                if page_type in ["Navigation", "Support", "Other"]:
                    self.logger.log(self.program_id, fact, "page_type_contamination", f"Extracted from {page_type} page")
                    continue
            
            # 3. Forbidden Domain Check
            if source_url and self.allowed_subdomains:
                domain = urlparse(source_url).netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                
                is_allowed = False
                for allowed in self.allowed_subdomains:
                    if allowed.startswith("www."):
                        allowed = allowed[4:]
                    if domain == allowed or domain.endswith("." + allowed):
                        is_allowed = True
                        break
                        
                if not is_allowed:
                    self.logger.log(self.program_id, fact, "forbidden_domain", f"Domain {domain} not in allowed subdomains")
                    continue
            
            # 4. Plausibility Bounds
            if not self._check_plausibility(fact):
                continue
                
            valid_facts.append(fact)
            
        return valid_facts

    def _check_plausibility(self, fact: dict) -> bool:
        """Returns True if the fact is plausible, False if it should be rejected."""
        field = fact.get("field", "").lower()
        value = fact.get("value")
        
        if value is None:
            return True
            
        # Try to extract numbers from string values for numeric checks
        num_val = None
        if isinstance(value, (int, float)):
            num_val = float(value)
        elif isinstance(value, str):
            # Extract first number if possible
            match = re.search(r'\b(\d+(?:\.\d+)?)\b', value.replace(',', ''))
            if match:
                num_val = float(match.group(1))
                
        # IELTS Plausibility (0 - 9)
        if "ielts" in field and num_val is not None:
            if num_val < 0 or num_val > 9.0:
                self.logger.log(self.program_id, fact, "implausible_value", f"IELTS score {num_val} is out of bounds [0, 9]")
                return False
                
        # Tuition Fee Plausibility (0 - 500,000)
        if ("tuition" in field or "fee" in field) and num_val is not None:
            if num_val < 0 or num_val > 500000:
                self.logger.log(self.program_id, fact, "implausible_value", f"Tuition fee {num_val} is out of bounds [0, 500k]")
                return False
                
        # Duration Plausibility (1 - 10 years, or up to 120 months)
        if "duration" in field and num_val is not None:
            if "month" in str(value).lower():
                if num_val < 1 or num_val > 120:
                    self.logger.log(self.program_id, fact, "implausible_value", f"Duration {num_val} months is out of bounds [1, 120]")
                    return False
            elif "semester" in str(value).lower():
                if num_val < 1 or num_val > 20:
                    self.logger.log(self.program_id, fact, "implausible_value", f"Duration {num_val} semesters is out of bounds [1, 20]")
                    return False
            elif "year" in str(value).lower() or num_val <= 10: # assume years if small
                if num_val <= 0 or num_val > 10:
                    self.logger.log(self.program_id, fact, "implausible_value", f"Duration {num_val} years is out of bounds [1, 10]")
                    return False
                    
        return True
