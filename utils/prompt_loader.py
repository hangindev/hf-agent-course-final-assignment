"""
Utility functions for loading prompt files.
"""

import os


def load_prompt(filename: str) -> str:
    """Load a prompt file from the prompts directory."""
    prompt_path = os.path.join("prompts", filename)
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()
