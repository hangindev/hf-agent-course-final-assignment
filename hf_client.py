"""
API client for Hugging Face Agents Course evaluation system.

This module handles all interactions with the evaluation API including:
- Fetching questions and random questions
- Downloading associated files
- Submitting answers and scores
"""

import requests
import json
import os
from typing import List, Dict, Any, Union, TypedDict, Optional


class APIQuestion(TypedDict):
    """Type definition for API question response."""

    task_id: str
    question: str
    Level: str
    file_name: str


class Question(TypedDict):
    """Simplified question format for local use."""

    task_id: str
    question: str
    file_path: str
    answer: Optional[str]
    skip: Optional[bool]


class HFClient:
    """Client for interacting with the Hugging Face Agents Course API."""

    def __init__(
        self,
        base_url: str,
        questions_json_path: str,
        attachments_dir: str,
    ):
        """
        Initialize the API client.

        Args:
            base_url: The base URL for the API
            questions_json_path: Path to the questions JSON file
            attachments_dir: Directory for storing downloaded files
        """
        self.base_url = base_url
        self.questions_json_path = questions_json_path
        self.attachments_dir = attachments_dir

    def get_questions(self) -> List[Question]:
        """
        Retrieve the full list of filtered evaluation questions, using cache if available.
        Downloads associated files and returns simplified Question format.

        Returns:
            List[Question]: List of questions with question text and file_path

        Raises:
            requests.RequestException: If the API request fails
        """
        # Check if cached questions.json exists
        if os.path.exists(self.questions_json_path):
            print(f"Loading questions from cache: {self.questions_json_path}")
            with open(self.questions_json_path, "r", encoding="utf-8") as f:
                return json.load(f)

        # Otherwise, fetch from API, process files, and cache
        try:
            response = requests.get(f"{self.base_url}/questions")
            response.raise_for_status()
            api_questions = response.json()
            print(f"Fetched {len(api_questions)} questions from API")

            # Process each question and download files if needed
            processed_questions: List[Question] = []
            for i, api_question in enumerate(api_questions, 1):
                task_id = api_question["task_id"]
                question_text = api_question["question"]
                file_name = api_question["file_name"]

                print(f"Processing question {i}/{len(api_questions)}: {task_id}")

                file_path = ""
                if file_name and file_name != "":
                    try:
                        file_path = self.get_file(task_id, file_name)
                        print(f"  File ready: {file_name}")
                    except Exception as e:
                        print(f"  Error downloading file for {task_id}: {e}")

                # Create simplified Question object
                question = Question(
                    task_id=task_id, question=question_text, file_path=file_path
                )
                processed_questions.append(question)

            # Cache the processed questions
            os.makedirs(os.path.dirname(self.questions_json_path), exist_ok=True)
            with open(self.questions_json_path, "w", encoding="utf-8") as f:
                json.dump(processed_questions, f, indent=2, ensure_ascii=False)
            print(f"Cached processed questions to {self.questions_json_path}")

            return processed_questions
        except requests.exceptions.RequestException as e:
            print(f"Error fetching questions: {e}")
            raise

    def get_random_question(self) -> Question:
        """
        Fetch a single random question from the list and download any associated file.

        Returns:
            Question: A single random question with question text and file_path

        Raises:
            requests.RequestException: If the API request fails
        """
        try:
            response = requests.get(f"{self.base_url}/random-question")
            response.raise_for_status()
            api_question = response.json()

            # Extract data from API response
            task_id = api_question["task_id"]
            question_text = api_question["question"]
            file_name = api_question["file_name"]

            # Download file if it exists
            file_path = ""
            if file_name and file_name != "":
                try:
                    file_path = self.get_file(task_id, file_name)
                    print(f"Downloaded file for random question: {file_name}")
                except Exception as e:
                    print(f"Error downloading file for random question {task_id}: {e}")

            # Return simplified Question object
            return Question(question=question_text, file_path=file_path)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching random question: {e}")
            raise

    def get_file(self, task_id: str, file_name: str) -> str:
        """
        Download a specific file associated with a given task ID, using cache if available.

        Args:
            task_id: The task ID to download the file for
            file_name: The file name to use for caching

        Returns:
            str: The local file path where the file is stored

        Raises:
            requests.RequestException: If the API request fails
        """
        os.makedirs(self.attachments_dir, exist_ok=True)
        file_path = os.path.join(self.attachments_dir, file_name)
        absolute_path = os.path.abspath(file_path)

        # Check if file already exists
        if os.path.exists(file_path):
            print(f"File already cached: {absolute_path}")
            return absolute_path

        # Otherwise, fetch from API and cache
        try:
            response = requests.get(f"{self.base_url}/files/{task_id}")
            response.raise_for_status()
            file_content = response.content
            with open(file_path, "wb") as f:
                f.write(file_content)
            print(f"Fetched and cached file to {absolute_path}")
            return absolute_path
        except requests.exceptions.RequestException as e:
            print(f"Error downloading file for task {task_id}: {e}")
            raise

    def submit_answers(
        self,
        username: str,
        agent_code: str,
        answers: List[Dict[str, Union[str, int, float]]],
    ) -> Dict[str, Any]:
        """
        Submit agent answers, calculate the score, and update the leaderboard.

        Args:
            username: Hugging Face username
            agent_code: The Python class code for the agent (minimum 10 characters)
            answers: List of answers with task_id and submitted_answer fields

        Returns:
            Dict: Score response containing username, score, correct_count, total_attempted, message, timestamp

        Raises:
            requests.RequestException: If the API request fails
        """
        submission_data = {
            "username": username,
            "agent_code": agent_code,
            "answers": answers,
        }

        try:
            response = requests.post(f"{self.base_url}/submit", json=submission_data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error submitting answers: {e}")
            raise
