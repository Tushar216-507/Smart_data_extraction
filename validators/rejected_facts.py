import json
from pathlib import Path

class RejectedFactsLogger:
    """Archives rejected facts for audit trails."""
    
    def __init__(self, workspace_dir: Path):
        self.log_file = workspace_dir / "rejected_facts.jsonl"
        
    def log(self, program_id: str, fact: dict, reason: str, details: str = ""):
        entry = {
            "program_id": program_id,
            "reason": reason,
            "details": details,
            "fact": fact
        }
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
