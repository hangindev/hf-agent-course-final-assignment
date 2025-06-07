import unittest
from unittest.mock import patch, MagicMock
import os
import subprocess
# import json # No longer needed for mock setup unless metadata was part of output

# Adjust the import path based on your project structure
from tools.analyze_youtube import analyze_youtube
# from langchain_core.messages import AIMessage # No longer needed

# Helper to create a mock subprocess.CompletedProcess
def mock_completed_process(stdout_data="", stderr_data="", returncode=0): # Default stdout to empty string
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout_data
    process.stderr = stderr_data
    process.returncode = returncode
    return process

class TestAnalyzeYoutube(unittest.TestCase):

    # No longer need setUp and tearDown for OPENAI_API_KEY
    # def setUp(self):
    #     self.original_openai_api_key = os.environ.get("OPENAI_API_KEY")
    #     if "OPENAI_API_KEY" in os.environ:
    #         del os.environ["OPENAI_API_KEY"]

    # def tearDown(self):
    #     if self.original_openai_api_key is not None:
    #         os.environ["OPENAI_API_KEY"] = self.original_openai_api_key
    #     elif "OPENAI_API_KEY" in os.environ:
    #         del os.environ["OPENAI_API_KEY"]

    @patch('tools.analyze_youtube.os.listdir')
    @patch('tools.analyze_youtube.os.makedirs')
    @patch('tools.analyze_youtube.os.path.getsize')
    @patch('tools.analyze_youtube.os.path.exists')
    @patch('tools.analyze_youtube.subprocess.run')
    def test_analyze_youtube_success(self, mock_subprocess_run, mock_os_path_exists, mock_os_path_getsize, mock_os_makedirs, mock_os_listdir):
        # --- MOCK SETUP ---
        # Mock yt-dlp success
        mock_yt_dlp_result = mock_completed_process(returncode=0)
        # Mock ffmpeg success
        mock_ffmpeg_result = mock_completed_process(returncode=0)
        mock_subprocess_run.side_effect = [mock_yt_dlp_result, mock_ffmpeg_result]

        # Mock os.path.exists for video file
        mock_os_path_exists.return_value = True # Simulate video file exists after download
        # Mock os.path.getsize for video file
        mock_os_path_getsize.return_value = 1024 # Simulate non-empty file

        # Mock os.makedirs - no specific return value needed, just ensure it's callable
        mock_os_makedirs.return_value = None

        # Mock os.listdir to simulate N extracted frames
        mock_num_frames = 5
        mock_frame_files = [f"frame_{i:04d}.png" for i in range(1, mock_num_frames + 1)]
        mock_os_listdir.return_value = mock_frame_files

        uri = "https://www.youtube.com/watch?v=testvideo"
        query = "What is this video about?" # Query is currently unused by the main function

        # --- CALL THE FUNCTION ---
        result = analyze_youtube(uri, query)

        # --- ASSERTIONS ---
        # Assert subprocess.run calls
        self.assertEqual(mock_subprocess_run.call_count, 2)

        # yt-dlp call assertions
        yt_dlp_call_args = mock_subprocess_run.call_args_list[0][0][0]
        self.assertEqual(yt_dlp_call_args[0], "yt-dlp")
        self.assertIn("--format", yt_dlp_call_args)
        self.assertIn("best[ext=mp4]/best", yt_dlp_call_args)
        self.assertIn("-o", yt_dlp_call_args)
        self.assertTrue(yt_dlp_call_args[-2].endswith("video.mp4")) # Check output path
        self.assertEqual(yt_dlp_call_args[-1], uri)

        # ffmpeg call assertions
        ffmpeg_call_args = mock_subprocess_run.call_args_list[1][0][0]
        self.assertEqual(ffmpeg_call_args[0], "ffmpeg")
        self.assertIn("-i", ffmpeg_call_args)
        self.assertTrue(ffmpeg_call_args[ffmpeg_call_args.index("-i") + 1].endswith("video.mp4")) # Check input path
        self.assertIn("-vf", ffmpeg_call_args)
        self.assertEqual(ffmpeg_call_args[ffmpeg_call_args.index("-vf") + 1], "fps=1/2")
        self.assertTrue(ffmpeg_call_args[-1].endswith("frame_%04d.png")) # Check output pattern

        # Assert os.makedirs call
        mock_os_makedirs.assert_called_once()
        self.assertTrue(mock_os_makedirs.call_args[0][0].endswith("/frames"))

        # Assert os.listdir call
        mock_os_listdir.assert_called_once()
        self.assertTrue(mock_os_listdir.call_args[0][0].endswith("/frames"))

        # Assert success message
        # The frames_dir path is dynamic (inside tempfile.TemporaryDirectory)
        # So we check for the beginning and end of the string.
        self.assertTrue(result.startswith(f"Successfully downloaded video and extracted {mock_num_frames} frames to "))
        self.assertTrue(result.endswith("/frames."))


    @patch('tools.analyze_youtube.subprocess.run')
    def test_yt_dlp_download_error(self, mock_subprocess_run):
        mock_subprocess_run.return_value = mock_completed_process(returncode=1, stderr="yt-dlp download error")

        result = analyze_youtube("https://www.youtube.com/watch?v=fail_dl", "Query")
        self.assertEqual(result, "Error downloading video with yt-dlp: yt-dlp download error")

    @patch('tools.analyze_youtube.os.path.exists', return_value=False) # Simulate video not found after yt-dlp "success"
    @patch('tools.analyze_youtube.subprocess.run')
    def test_yt_dlp_file_not_found_after_download(self, mock_subprocess_run, mock_path_exists):
        mock_subprocess_run.return_value = mock_completed_process(returncode=0, stderr="some yt-dlp noise") # yt-dlp claims success

        result = analyze_youtube("https://www.youtube.com/watch?v=filemissing", "Query")
        self.assertTrue(result.startswith("Error: yt-dlp reported success but video file not found or is empty"))
        self.assertIn("some yt-dlp noise", result)

    @patch('tools.analyze_youtube.os.makedirs') # Mock makedirs
    @patch('tools.analyze_youtube.os.path.getsize', return_value=1024) # Mock getsize
    @patch('tools.analyze_youtube.os.path.exists', return_value=True) # Mock path.exists for video
    @patch('tools.analyze_youtube.subprocess.run')
    def test_ffmpeg_command_error(self, mock_subprocess_run, mock_path_exists, mock_getsize, mock_makedirs):
        mock_yt_dlp_result = mock_completed_process(returncode=0)
        mock_ffmpeg_result = mock_completed_process(returncode=1, stderr="ffmpeg processing error")
        mock_subprocess_run.side_effect = [mock_yt_dlp_result, mock_ffmpeg_result]

        result = analyze_youtube("https://www.youtube.com/watch?v=ffmpeg_fail", "Query")
        self.assertEqual(result, "Error extracting frames with ffmpeg: ffmpeg processing error")

    @patch('tools.analyze_youtube.subprocess.run')
    def test_yt_dlp_not_found_error(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = FileNotFoundError("No such file or directory: 'yt-dlp'", filename='yt-dlp')

        result = analyze_youtube("https://www.youtube.com/watch?v=no_ytdlp", "Query")
        self.assertEqual(result, "Error: Command 'yt-dlp' not found. Please ensure it is installed and in your PATH.")

    @patch('tools.analyze_youtube.os.path.getsize', return_value=1024)
    @patch('tools.analyze_youtube.os.path.exists', return_value=True)
    @patch('tools.analyze_youtube.subprocess.run')
    def test_ffmpeg_not_found_error(self, mock_subprocess_run, mock_path_exists, mock_getsize):
        mock_yt_dlp_result = mock_completed_process(returncode=0)
        # Simulate FileNotFoundError for the ffmpeg call
        mock_subprocess_run.side_effect = [
            mock_yt_dlp_result,
            FileNotFoundError("No such file or directory: 'ffmpeg'", filename='ffmpeg')
        ]

        result = analyze_youtube("https://www.youtube.com/watch?v=no_ffmpeg", "Query")
        self.assertEqual(result, "Error: Command 'ffmpeg' not found. Please ensure it is installed and in your PATH.")


if __name__ == '__main__':
    # This allows running the tests directly from the command line
    # The dummy utils.py and prompts directory are no longer needed for these tests
    # as the tested function does not use load_prompt or OpenAI functionality.

    # Need to make `tools` a package for `from tools.analyze_youtube import ...` to work
    # This part is primarily for running the test file standalone.
    if not os.path.exists("tools"): # Ensure tools directory exists for dummy __init__
        os.makedirs("tools")
    if not os.path.exists("tools/__init__.py"):
        with open("tools/__init__.py", "w") as f:
            # This assumes analyze_youtube.py is in the tools directory
            f.write("from .analyze_youtube import analyze_youtube\n__all__= ['analyze_youtube']")

    unittest.main()
