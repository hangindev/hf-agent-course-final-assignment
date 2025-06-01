"""
Main application entry point for the Hugging Face Agents Course Final Assignment.
"""

from hf_client import HFClient
from config import BASE_URL, QUESTIONS_DIR, QUESTIONS_JSON_PATH, ATTACHMENTS_DIR

def main():
    """Main application function."""
    hf = HFClient(
        base_url=BASE_URL,
        questions_dir=QUESTIONS_DIR,
        questions_json_path=QUESTIONS_JSON_PATH,
        attachments_dir=ATTACHMENTS_DIR
    )
    # Example usage of the API client
    print("Fetching questions...")
    questions = hf.get_questions()
    print(f"Retrieved {len(questions)} questions")


if __name__ == "__main__":
    main()
