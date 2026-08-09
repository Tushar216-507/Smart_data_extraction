import hashlib
import json
from pathlib import Path
from typing import Any, Optional


class LLMCache:
    """
    Disk-based cache for LLM responses.
    
    Persists identical LLM requests across pipeline restarts and
    multiple universities.
    """

    def __init__(self, cache_dir: str | Path = "data/.cache/llm"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _compute_hash(
        self,
        provider_name: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: Any,
        temperature: float,
    ) -> str:
        """Compute a deterministic hash for the LLM request."""
        
        schema_str = json.dumps(response_schema, sort_keys=True) if response_schema else ""
        
        payload = (
            f"{provider_name}|{model}|{temperature}|"
            f"{system_prompt}|{user_prompt}|{schema_str}"
        )
        
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(
        self,
        provider_name: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: Any,
        temperature: float,
    ) -> Optional[dict]:
        """Retrieve a cached response if it exists."""
        
        request_hash = self._compute_hash(
            provider_name,
            model,
            system_prompt,
            user_prompt,
            response_schema,
            temperature,
        )
        
        cache_file = self.cache_dir / f"{request_hash}.json"
        
        if cache_file.exists():
            try:
                with cache_file.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                # If cache is corrupted, treat as a miss
                return None
                
        return None

    def set(
        self,
        provider_name: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: Any,
        temperature: float,
        result: dict,
    ) -> None:
        """Store an LLM response in the cache."""
        
        request_hash = self._compute_hash(
            provider_name,
            model,
            system_prompt,
            user_prompt,
            response_schema,
            temperature,
        )
        
        cache_file = self.cache_dir / f"{request_hash}.json"
        
        # Write atomically
        temp_file = cache_file.with_suffix(".tmp")
        try:
            with temp_file.open("w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            temp_file.replace(cache_file)
        except Exception:
            if temp_file.exists():
                temp_file.unlink()
