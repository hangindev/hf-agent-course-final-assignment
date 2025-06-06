import subprocess
import json
import os
import tempfile
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from utils import load_prompt
import shutil # Added for shutil.which

# It's good practice to define the system prompt loading once if it's static
# Assuming we reuse the same prompt as query_resource for now
CONTENT_QUERY_SYSTEM_PROMPT = load_prompt("content_query_system_prompt.md")

@tool(parse_docstring=True)
def analyze_video(uri: str, query: str) -> str:
    """Analyzes a video from a given URI by downloading its metadata and captions,
    then uses an AI model to answer a query about the video.

    Args:
        uri: The URI of the video resource (e.g., YouTube link).
        query: The question or query to ask about the video content.

    Returns:
        A string containing the answer to the query based on the video's content.
    """
    # Placeholder for actual implementation
    # TODO: Implement YouTube video processing (download metadata and captions)
    if not uri.startswith("https://www.youtube.com/watch?v="):
        raise NotImplementedError("Video analysis for this URI is not implemented. TODO: Add support for other video platforms/URIs.")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Download video metadata and captions using yt-dlp
            # We'll ask for the output to be in JSON format
            # We'll also ask for english captions
            cmd = [
                "yt-dlp",
                "--skip-download",  # Don't download the video itself
                "--write-auto-sub", # Write automatic captions
                "--sub-lang", "en", # Download english captions
                "--sub-format", "vtt", # Download captions in vtt format
                "-o", os.path.join(tmpdir, "video_info"), # Output template for downloaded files
                "--dump-json", # Dump metadata to stdout
                "--encoding", "utf-8", # Specify UTF-8 encoding
                uri,
            ]
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            video_metadata = json.loads(process.stdout)

            # Find the downloaded captions file
            # yt-dlp might name it video_info.en.vtt or video_info.vtt
            caption_file_path_vtt = os.path.join(tmpdir, "video_info.en.vtt")
            if not os.path.exists(caption_file_path_vtt):
                caption_file_path_vtt = os.path.join(tmpdir, "video_info.vtt")

            if os.path.exists(caption_file_path_vtt):
                with open(caption_file_path_vtt, "r") as f:
                    captions = f.read()
            else:
                captions = "No captions found for this video."

            # Prepare content for the AI model
            # Combine metadata and captions into a single text block
            video_content = f"Video Title: {video_metadata.get('title', 'N/A')}\n"
            video_content += f"Video Description: {video_metadata.get('description', 'N/A')}\n\n"
            video_content += f"Video Captions:\n{captions}"

            # Invoke the AI model
            # Ensure OPENAI_API_KEY is set in the environment
            if not os.getenv("OPENAI_API_KEY"):
                return "Error: OPENAI_API_KEY environment variable not set."

            llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0) # Or any other suitable model

            messages = [
                SystemMessage(content=CONTENT_QUERY_SYSTEM_PROMPT),
                HumanMessage(content=f"Video URI: {uri}\nVideo Content:\n{video_content}\n\nQuery: {query}")
            ]

            try:
                ai_response = llm.invoke(messages)
                return ai_response.content
            except Exception as e:
                return f"Error invoking AI model: {str(e)}"

    except subprocess.CalledProcessError as e:
        return f"Error processing video: {e.stderr}"
    except FileNotFoundError:
        # This can happen if yt-dlp is not installed
        return "Error: yt-dlp command not found. Please ensure yt-dlp is installed and in your PATH."
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


if __name__ == '__main__':
    # Example usage (will require more setup for a real test)
    # Example usage:
    # You would need to have yt-dlp installed and OPENAI_API_KEY set in your environment.
    # Create a dummy utils.py and content_query_system_prompt.md for this example to run.

    # Create dummy utils.py
    if not os.path.exists("utils.py"):
        with open("utils.py", "w") as f:
            f.write("def load_prompt(filename: str) -> str:\n")
            f.write("    # In a real scenario, this would load from a file.\n")
            f.write("    # For this example, return a generic prompt.\n")
            f.write("    if filename == 'content_query_system_prompt.md':\n")
            f.write("        return 'You are an AI assistant that answers questions based on the provided video content.'\n")
            f.write("    return ''\n")

    # Create dummy content_query_system_prompt.md
    if not os.path.exists("content_query_system_prompt.md"):
        with open("content_query_system_prompt.md", "w") as f:
            f.write("You are an AI assistant that answers questions based on the provided video content.")

    # Note: Replace with a real YouTube link and ensure OPENAI_API_KEY is set.
    # For automated testing, it's better to mock the subprocess and OpenAI calls.
    test_uri = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Example: Rick Astley
    test_query = "What is the singer's name and the main theme of the song?"

    print(f"Attempting to analyze video: {test_uri}")
    print(f"Query: {test_query}")

    # It's good practice to check for API key before calling
    if not os.getenv("OPENAI_API_KEY"):
        print("\nError: OPENAI_API_KEY is not set. Please set it to run the example.")
        print("Skipping analyze_video call.")
    elif shutil.which("yt-dlp") is None:
        print("\nError: yt-dlp command not found. Please install yt-dlp to run the example.")
        print("Skipping analyze_video call.")
    else:
        try:
            # Reload the module to ensure it picks up the dummy utils.py if it was just created
            # This is a bit of a hack for the __main__ example.
            import importlib
            import sys
            if 'utils' in sys.modules:
                importlib.reload(sys.modules['utils'])
            if 'tools.analyze_video' in sys.modules: # Assuming it might be imported elsewhere if part of a package
                 importlib.reload(sys.modules['tools.analyze_video'])

            # Re-import CONTENT_QUERY_SYSTEM_PROMPT in case utils was reloaded
            from utils import load_prompt as lp_main
            CONTENT_QUERY_SYSTEM_PROMPT = lp_main("content_query_system_prompt.md")

            # The tool function needs to be callable directly for this example
            # If it's part of a larger system, it would be registered and called via Langchain
            answer = analyze_video(uri=test_uri, query=test_query)
            print("\n--- Analysis Result ---")
            print(answer)
            print("-----------------------")
        except NotImplementedError as nie:
            print(f"NotImplementedError: {nie}")
        except Exception as e:
            print(f"An unexpected error occurred during the example run: {e}")

    # Clean up dummy files
    if os.path.exists("utils.py") and "In a real scenario" in open("utils.py").read():
        os.remove("utils.py")
    if os.path.exists("content_query_system_prompt.md") and "You are an AI assistant" in open("content_query_system_prompt.md").read():
        os.remove("content_query_system_prompt.md")
