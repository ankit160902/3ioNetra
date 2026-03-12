import yaml
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PromptManager:
    """Service to manage and load external LLM prompts."""
    
    def __init__(self, prompt_dir: str):
        self.prompt_dir = prompt_dir
        self.cache: Dict[str, Any] = {}
        self._load_all()

    def _load_all(self):
        """Pre-load all YAML prompts in the directory."""
        if not os.path.exists(self.prompt_dir):
            logger.warning(f"Prompt directory {self.prompt_dir} does not exist")
            return

        for filename in os.listdir(self.prompt_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                try:
                    with open(os.path.join(self.prompt_dir, filename), 'r') as f:
                        name = os.path.splitext(filename)[0]
                        self.cache[name] = yaml.safe_load(f)
                        logger.info(f"Loaded prompt file: {filename}")
                except Exception as e:
                    logger.error(f"Failed to load prompt file {filename}: {e}")

    def get_prompt_group(self, group_name: str) -> Dict[str, Any]:
        """Get a group of prompts (e.g., 'spiritual_mitra')."""
        return self.cache.get(group_name, {})

    def get_prompt(self, group_name: str, key_path: str, default: str = "") -> str:
        """
        Retrieve a specific prompt using dot notation for nested keys.
        Example: get_prompt('spiritual_mitra', 'persona.name')
        """
        group = self.get_prompt_group(group_name)
        keys = key_path.split('.')
        
        val = group
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
                
        return str(val) if val is not None else default

_prompt_manager: Optional[PromptManager] = None

def get_prompt_manager() -> PromptManager:
    global _prompt_manager
    if _prompt_manager is None:
        # Resolve absolute path to backend/prompts
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompt_dir = os.path.join(base_dir, "prompts")
        _prompt_manager = PromptManager(prompt_dir)
    return _prompt_manager
