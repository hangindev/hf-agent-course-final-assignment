import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import subprocess
import json

# Adjust the import path based on your project structure
# This assumes tools and utils are sibling directories or configured in PYTHONPATH
from tools.analyze_video import analyze_video, CONTENT_QUERY_SYSTEM_PROMPT
from langchain_core.messages import AIMessage # For mocking AI response

# Helper to create a mock subprocess.CompletedProcess
def mock_completed_process(stdout_data=None, stderr_data=None, returncode=0):
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout_data
    process.stderr = stderr_data
    process.returncode = returncode
    return process

class TestAnalyzeVideo(unittest.TestCase):

    def setUp(self):
        # Store original OPENAI_API_KEY and clear it for most tests
        self.original_openai_api_key = os.environ.get("OPENAI_API_KEY")
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

    def tearDown(self):
        # Restore original OPENAI_API_KEY
        if self.original_openai_api_key is not None:
            os.environ["OPENAI_API_KEY"] = self.original_openai_api_key
        elif "OPENAI_API_KEY" in os.environ: # If it was set to None but key existed
            del os.environ["OPENAI_API_KEY"]

    @patch('tools.analyze_video.os.path.exists')
    @patch('tools.analyze_video.subprocess.run')
    @patch('tools.analyze_video.ChatOpenAI')
    @patch('tools.analyze_video.open', new_callable=mock_open, read_data="Sample VTT captions")
    def test_analyze_youtube_video_success(self, mock_file_open, mock_chat_openai, mock_subprocess_run, mock_os_path_exists):
        # --- MOCK SETUP ---
        # Mock OPENAI_API_KEY presence
        os.environ["OPENAI_API_KEY"] = "test_key"

        # Mock yt-dlp metadata output
        mock_metadata = {
            "title": "Test Video Title",
            "description": "Test video description."
        }
        mock_subprocess_run.return_value = mock_completed_process(stdout_data=json.dumps(mock_metadata))

        # Mock os.path.exists to simulate caption file found
        # First call for general tmpdir path (doesn't matter), second for specific caption file
        mock_os_path_exists.side_effect = [True, True] # tmpdir exists, caption_file.en.vtt exists

        # Mock OpenAI response
        mock_llm_instance = mock_chat_openai.return_value
        mock_llm_instance.invoke.return_value = AIMessage(content="Mocked AI response")

        # --- CALL THE FUNCTION ---
        uri = "https://www.youtube.com/watch?v=testvideo"
        query = "What is this video about?"
        result = analyze_video(uri, query)

        # --- ASSERTIONS ---
        self.assertEqual(result, "Mocked AI response")

        # Check if yt-dlp was called correctly
        expected_yt_dlp_cmd_start = [
            "yt-dlp", "--skip-download", "--write-auto-sub", "--sub-lang", "en",
            "--sub-format", "vtt", "-o"
        ]
        # self.assertTrue(mock_subprocess_run.call_args[0][0].startswith(tuple(expected_yt_dlp_cmd_start)))
        # Instead of startswith, check individual elements for robustness if order is fixed
        called_cmd = mock_subprocess_run.call_args[0][0]
        for i, part in enumerate(expected_yt_dlp_cmd_start):
            self.assertEqual(called_cmd[i], part)
        self.assertEqual(called_cmd[-1], uri) # Last arg is URI

        # Check if OpenAI was called with expected content
        human_message_content = mock_llm_instance.invoke.call_args[0][0][1].content
        self.assertIn("Test Video Title", human_message_content)
        self.assertIn("Test video description.", human_message_content)
        self.assertIn("Sample VTT captions", human_message_content)
        self.assertIn(query, human_message_content)

        # Check if caption file was opened
        # The path will be dynamic due to tempfile.TemporaryDirectory, check for .vtt
        opened_file_path = mock_file_open.call_args[0][0]
        self.assertTrue(opened_file_path.endswith(".en.vtt") or opened_file_path.endswith(".vtt"))


    @patch('tools.analyze_video.os.path.exists')
    @patch('tools.analyze_video.subprocess.run')
    @patch('tools.analyze_video.ChatOpenAI')
    @patch('tools.analyze_video.open', new_callable=mock_open) # mock_open without read_data for no captions
    def test_analyze_youtube_video_no_captions(self, mock_file_open, mock_chat_openai, mock_subprocess_run, mock_os_path_exists):
        os.environ["OPENAI_API_KEY"] = "test_key"
        mock_metadata = {"title": "No Caption Video", "description": "Desc."}
        mock_subprocess_run.return_value = mock_completed_process(stdout_data=json.dumps(mock_metadata))

        # os.path.exists: tmpdir (True), video_info.en.vtt (False), video_info.vtt (False)
        mock_os_path_exists.side_effect = [True, False, False]

        mock_llm_instance = mock_chat_openai.return_value
        mock_llm_instance.invoke.return_value = AIMessage(content="AI response for no captions")

        result = analyze_video("https://www.youtube.com/watch?v=nocaps", "Query?")
        self.assertEqual(result, "AI response for no captions")

        human_message_content = mock_llm_instance.invoke.call_args[0][0][1].content
        self.assertIn("No Caption Video", human_message_content)
        self.assertIn("No captions found for this video.", human_message_content)
        mock_file_open.assert_not_called() # open should not be called if os.path.exists is false for captions

    def test_non_youtube_uri(self):
        with self.assertRaisesRegex(NotImplementedError, "Video analysis for this URI is not implemented"):
            analyze_video("https://www.vimeo.com/12345", "Query?")

    @patch('tools.analyze_video.subprocess.run')
    def test_yt_dlp_command_error(self, mock_subprocess_run):
        os.environ["OPENAI_API_KEY"] = "test_key" # Needed to get past API key check
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="yt-dlp", stderr="yt-dlp error"
        )
        result = analyze_video("https://www.youtube.com/watch?v=fail", "Query?")
        self.assertEqual(result, "Error processing video: yt-dlp error")

    @patch('tools.analyze_video.subprocess.run')
    def test_yt_dlp_not_found(self, mock_subprocess_run):
        os.environ["OPENAI_API_KEY"] = "test_key"
        mock_subprocess_run.side_effect = FileNotFoundError("yt-dlp not found")
        result = analyze_video("https://www.youtube.com/watch?v=nofile", "Query?")
        self.assertEqual(result, "Error: yt-dlp command not found. Please ensure yt-dlp is installed and in your PATH.")

    def test_missing_openai_api_key(self):
        # OPENAI_API_KEY is already removed in setUp for this test
        # Need to mock subprocess.run to avoid it running if key is not there first
        with patch('tools.analyze_video.subprocess.run') as mock_sub_run:
            # Make sure yt-dlp doesn't actually run or error out before the API key check
            mock_sub_run.return_value = mock_completed_process(stdout_data=json.dumps({"title": "t"}))
            with patch('tools.analyze_video.os.path.exists', return_value=False) as mock_path_exists: # No captions
                 result = analyze_video("https://www.youtube.com/watch?v=keymissing", "Query?")
            self.assertEqual(result, "Error: OPENAI_API_KEY environment variable not set.")

    @patch('tools.analyze_video.os.path.exists')
    @patch('tools.analyze_video.subprocess.run')
    @patch('tools.analyze_video.ChatOpenAI')
    def test_openai_api_error(self, mock_chat_openai, mock_subprocess_run, mock_os_path_exists):
        os.environ["OPENAI_API_KEY"] = "test_key"
        mock_metadata = {"title": "AI Error Test"}
        mock_subprocess_run.return_value = mock_completed_process(stdout_data=json.dumps(mock_metadata))
        mock_os_path_exists.side_effect = [True, False, False] # No captions

        mock_llm_instance = mock_chat_openai.return_value
        mock_llm_instance.invoke.side_effect = Exception("OpenAI API error")

        result = analyze_video("https://www.youtube.com/watch?v=aierror", "Query?")
        self.assertEqual(result, "Error invoking AI model: OpenAI API error")


if __name__ == '__main__':
    # This allows running the tests directly from the command line
    # Create dummy utils.py and prompt file for tests to be able to import analyze_video
    # In a real CI environment, these would exist or paths would be set up.

    # Dummy utils.py
    if not os.path.exists("utils"):
        os.makedirs("utils")
    if not os.path.exists("utils/__init__.py"):
         with open("utils/__init__.py", "w") as f:
            f.write("") # empty init

    if not os.path.exists("utils/load_prompt.py"): # Assuming load_prompt is in a file
        with open("utils/load_prompt.py", "w") as f:
            f.write("def load_prompt(filename: str) -> str:\n")
            f.write("    return 'System Prompt for testing'\n")

    # Dummy prompt file (referenced by tools.analyze_video)
    if not os.path.exists("prompts"):
        os.makedirs("prompts")
    if not os.path.exists("prompts/content_query_system_prompt.md"):
        with open("prompts/content_query_system_prompt.md", "w") as f:
            f.write("System Prompt for testing")

    # Need to make `tools` a package for `from tools.analyze_video import ...` to work
    if not os.path.exists("tools/__init__.py"):
        with open("tools/__init__.py", "w") as f:
            # If this is run standalone, analyze_video might not be in __all__ yet
            # For the test, it's directly imported so this can be minimal
            f.write("from .analyze_video import analyze_video\n__all__= ['analyze_video']")


    unittest.main()
