import subprocess
# import json # No longer needed as --dump-json is removed
import os
import tempfile
from langchain_core.tools import tool
# from langchain_openai import ChatOpenAI # Commented out as LLM call is removed
# from langchain_core.messages import SystemMessage, HumanMessage # Commented out
# from utils import load_prompt # Commented out
import shutil # Keep for shutil.which in __main__

# It's good practice to define the system prompt loading once if it's static
# Assuming we reuse the same prompt as query_resource for now
# CONTENT_QUERY_SYSTEM_PROMPT = load_prompt("content_query_system_prompt.md") # Commented out

@tool(parse_docstring=True)
def analyze_youtube(uri: str, query: str) -> str: # Query might be unused now, consider removing later if not needed for frame processing
    """Analyzes a YouTube video from a given URI by downloading it and extracting frames.

    Args:
        uri: The URI of the YouTube video (e.g., https://www.youtube.com/watch?v=...).
        query: The question or query to ask about the video content. (Currently unused in this version)

    Returns:
        A string indicating success and the number of extracted frames, or an error message.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            video_filename = "video.mp4"
            video_path = os.path.join(tmpdir, video_filename)

            # Download video using yt-dlp
            yt_dlp_cmd = [
                "yt-dlp",
                "--format", "best[ext=mp4]/best", # Download best MP4 format
                "-o", video_path,
                uri,
            ]
            # Using check=False to manually handle errors and get stderr
            yt_dlp_process = subprocess.run(yt_dlp_cmd, capture_output=True, text=True, check=False)

            if yt_dlp_process.returncode != 0:
                return f"Error downloading video with yt-dlp: {yt_dlp_process.stderr}"

            # It's possible yt-dlp succeeds but the file isn't what we expect (e.g. not mp4, or named differently)
            # For this example, we assume if yt-dlp returns 0, the file at video_path is the correct one.
            # A more robust check would inspect the file.
            if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
                return f"Error: yt-dlp reported success but video file not found or is empty at {video_path}. Stderr: {yt_dlp_process.stderr}"


            # Create subdirectory for frames
            frames_dir = os.path.join(tmpdir, 'frames')
            os.makedirs(frames_dir)

            # Extract frames using ffmpeg
            ffmpeg_cmd = [
                "ffmpeg",
                "-i", video_path,
                "-vf", "fps=1/2",  # Extract 1 frame every 2 seconds
                os.path.join(frames_dir, "frame_%04d.png"),
            ]
            # Using check=False to manually handle errors and get stderr
            ffmpeg_process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=False)

            if ffmpeg_process.returncode != 0:
                return f"Error extracting frames with ffmpeg: {ffmpeg_process.stderr}"

            # Count extracted frames
            num_frames = len([name for name in os.listdir(frames_dir) if os.path.isfile(os.path.join(frames_dir, name)) and name.startswith("frame_") and name.endswith(".png")])

            # TODO: Implement processing of extracted frames.

            return f"Successfully downloaded video and extracted {num_frames} frames to {frames_dir}."

            # --- Old logic commented out ---
            # process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            # video_metadata = json.loads(process.stdout)

            # # Find the downloaded captions file
            # # yt-dlp might name it video_info.en.vtt or video_info.vtt
            # caption_file_path_vtt = os.path.join(tmpdir, "video_info.en.vtt")
            # if not os.path.exists(caption_file_path_vtt):
            #     caption_file_path_vtt = os.path.join(tmpdir, "video_info.vtt")

            # if os.path.exists(caption_file_path_vtt):
            #     with open(caption_file_path_vtt, "r") as f:
            #         captions = f.read()
            # else:
            #     captions = "No captions found for this video."

            # # Prepare content for the AI model
            # # Combine metadata and captions into a single text block
            # video_content = f"Video Title: {video_metadata.get('title', 'N/A')}\n"
            # video_content += f"Video Description: {video_metadata.get('description', 'N/A')}\n\n"
            # video_content += f"Video Captions:\n{captions}"

            # # Invoke the AI model
            # # Ensure OPENAI_API_KEY is set in the environment
            # if not os.getenv("OPENAI_API_KEY"):
            #     return "Error: OPENAI_API_KEY environment variable not set."

            # llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0) # Or any other suitable model

            # messages = [
            #     SystemMessage(content=CONTENT_QUERY_SYSTEM_PROMPT),
            #     HumanMessage(content=f"Video URI: {uri}\nVideo Content:\n{video_content}\n\nQuery: {query}")
            # ]

            # try:
            #     ai_response = llm.invoke(messages)
            #     return ai_response.content
            # except Exception as e:
            #     return f"Error invoking AI model: {str(e)}"

    except subprocess.CalledProcessError as e: # Should not be reached if check=False for all subprocess.run
        return f"Error during subprocess execution (should not happen with check=False): {e.stderr}"
    except FileNotFoundError as e:
        # This can happen if yt-dlp or ffmpeg is not installed
        # e.filename will contain the name of the command not found
        return f"Error: Command '{e.filename}' not found. Please ensure it is installed and in your PATH."
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


if __name__ == '__main__':
    # Example usage:
    # You would need to have yt-dlp and ffmpeg installed.
    # The OPENAI_API_KEY and utils/prompt related setup is no longer needed for this version's core functionality.

    # The dummy utils.py and content_query_system_prompt.md are no longer strictly necessary
    # for this script's __main__ as analyze_youtube does not use load_prompt or OPENAI_API_KEY.
    # However, if other parts of the project still expect them for other tools,
    # they might be created by a more general test setup.
    # For clarity, their creation is commented out here.

    # # Create dummy utils.py
    # if not os.path.exists("utils.py"):
    #     with open("utils.py", "w") as f:
    #         f.write("def load_prompt(filename: str) -> str:\n")
    #         f.write("    # In a real scenario, this would load from a file.\n")
    #         f.write("    # For this example, return a generic prompt.\n")
    #         f.write("    if filename == 'content_query_system_prompt.md':\n")
    #         f.write("        return 'You are an AI assistant that answers questions based on the provided video content.'\n")
    #         f.write("    return ''\n")

    # # Create dummy content_query_system_prompt.md
    # if not os.path.exists("content_query_system_prompt.md"):
    #     with open("content_query_system_prompt.md", "w") as f:
    #         f.write("You are an AI assistant that answers questions based on the provided video content.")


    test_uri = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Example: Rick Astley
    test_query = "What is this video about?" # Query is unused in current version

    print(f"Attempting to analyze YouTube video: {test_uri}")
    print(f"Query (currently unused): {test_query}")

    # Check for yt-dlp and ffmpeg
    if shutil.which("yt-dlp") is None:
        print("\nError: yt-dlp command not found. Please install yt-dlp to run the example.")
    elif shutil.which("ffmpeg") is None:
        print("\nError: ffmpeg command not found. Please install ffmpeg to run the example.")
    else:
        try:
            # The tool function needs to be callable directly for this example
            answer = analyze_youtube(uri=test_uri, query=test_query)
            print("\n--- Analysis Result ---")
            print(answer)
            print("-----------------------")
        except Exception as e:
            print(f"An unexpected error occurred during the example run: {e}")

    # Clean up dummy files (no longer created by this __main__)
    # if os.path.exists("utils.py") and "In a real scenario" in open("utils.py").read():
    #     os.remove("utils.py")
    # if os.path.exists("content_query_system_prompt.md") and "You are an AI assistant" in open("content_query_system_prompt.md").read():
    #     os.remove("content_query_system_prompt.md")
