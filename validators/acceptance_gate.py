from knowledge.billing.usage_tracker import UsageTracker
from config import Config
from validators.project_law import enforce_on_collection
from typing import List, Dict

class AcceptanceGate:
    """
    Stage 8 - Run-level Acceptance Gate.
    Ensures the final output meets all required standards before shipping.
    """
    
    @staticmethod
    def verify_run(
        discovery_results: dict,
        all_facts: List[dict],
        usage_tracker: UsageTracker,
        expected_range: dict
    ) -> Dict[str, any]:
        
        failures = []
        
        # 1. Budget Checks
        if usage_tracker.total_calls > Config.MAX_LLM_CALLS_PER_RUN:
            failures.append(f"Budget exceeded: {usage_tracker.total_calls} > {Config.MAX_LLM_CALLS_PER_RUN} calls")
        if usage_tracker.total_cost > Config.MAX_COST_PER_RUN_USD:
            failures.append(f"Budget exceeded: ${usage_tracker.total_cost:.2f} > ${Config.MAX_COST_PER_RUN_USD:.2f}")
            
        # 2. Programme Count
        program_count = discovery_results.get("total_working_program_urls", 0)
        if expected_range:
            min_prog = expected_range.get("min", 0)
            max_prog = expected_range.get("max", float('inf'))
            if program_count < min_prog or program_count > max_prog:
                failures.append(f"Programme count {program_count} outside expected range [{min_prog}, {max_prog}]")
                
        # 3. Discovery Quality
        # Check if any negative scored candidates snuck through
        for prog in discovery_results.get("program_urls", []):
            if prog.get("score", 0) <= 0:
                failures.append(f"Negative scored programme included: {prog.get('url')} (score: {prog.get('score')})")
                
        # 4. Law Enforcement on final facts
        clean, rejected = enforce_on_collection(all_facts)
        if rejected:
            failures.append(f"{len(rejected)} facts violated Project Law (e.g., missing source URL).")
            
        passed = len(failures) == 0
        
        return {
            "passed": passed,
            "failures": failures,
            "total_facts_checked": len(all_facts),
            "clean_facts": len(clean),
            "rejected_facts": len(rejected),
            "cost": usage_tracker.total_cost
        }
