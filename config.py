"""
Configuration settings for the Hugging Face Agents Course Final Assignment.
"""

import os
from dotenv import load_dotenv

# Environment variables
load_dotenv()
USERNAME = os.getenv("HF_USERNAME")
AGENT_CODE = os.getenv("REPOSITORY_URL")

# API Configuration
BASE_URL = "https://agents-course-unit4-scoring.hf.space"

# Local storage paths
QUESTIONS_DIR = "questions"
QUESTIONS_JSON_PATH = os.path.join(QUESTIONS_DIR, "questions.json")
ATTACHMENTS_DIR = os.path.join(QUESTIONS_DIR, "attachments")

