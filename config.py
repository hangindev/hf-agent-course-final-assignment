"""
Configuration settings for the Hugging Face Agents Course Final Assignment.
"""

import os
from dotenv import load_dotenv

# Environment variables
load_dotenv()
USERNAME = os.getenv("HF_USERNAME")
AGENT_CODE = os.getenv("REPOSITORY_URL")

LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST")

BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY")

# API Configuration
BASE_URL = "https://agents-course-unit4-scoring.hf.space"

# Local storage paths
CACHE_DIR = "cache"
PREVIOUS_ANSWERS_JSON_PATH = os.path.join(CACHE_DIR, "previous_answers.json")
QUESTIONS_JSON_PATH = os.path.join(CACHE_DIR, "questions.json")
ATTACHMENTS_DIR = os.path.join(CACHE_DIR, "attachments")
