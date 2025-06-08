import os
import shutil
import subprocess
import tempfile
import time
import traceback
from typing import Optional, Iterator

import yt_dlp


class YouTubeVideo:
    def __init__(self, youtube_url: str):
        self.youtube_url = youtube_url

        self._temp_dir: Optional[str] = None
        self._video_path: Optional[str] = None
        self._title: Optional[str] = None
        self._description: Optional[str] = None
        self._caption: Optional[str] = None
        self._audio_path: Optional[str] = None

    def __enter__(self):
        self._temp_dir = tempfile.mkdtemp()
        try:
            # Download video and get metadata
            self._video_path, self._title, self._description = self._download_youtube(
                self.youtube_url, self._temp_dir
            )

            # Get caption content
            self._caption = self._find_caption(self._temp_dir)

            return self
        except Exception as e:
            # Ensure cleanup happens on error during __enter__
            self.__exit__(type(e), e, e.__traceback__)
            raise

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir)

        # Reset state
        self._temp_dir = None
        self._video_path = None
        self._title = None
        self._description = None
        self._caption = None
        self._audio_path = None

    @property
    def title(self) -> Optional[str]:
        return self._title

    @property
    def description(self) -> Optional[str]:
        return self._description

    @property
    def caption(self) -> Optional[str]:
        return self._caption

    @property
    def audio_path(self) -> Optional[str]:
        if not self._video_path or not self._temp_dir:
            raise RuntimeError(
                "Video not available. Use this method within the 'with' statement."
            )

        if self._audio_path and os.path.exists(self._audio_path):
            return self._audio_path

        self._audio_path = self._extract_audio(self._video_path, self._temp_dir)
        return self._audio_path

    def generate_frames(self, fps: float) -> Iterator[tuple[str, str, int]]:
        """
        A generator that extracts frames from the video at a specified frame rate,
        yields them as file paths, and cleans up the frame files afterward.

        Args:
            fps: The number of frames to extract per second.

        Yields:
            A tuple of (frame_path, timestamp, total_frames).

        Raises:
            RuntimeError: If the video is not available (i.e., not used within a 'with' statement).
        """
        if not self._video_path or not self._temp_dir:
            raise RuntimeError(
                "Video not available. Use this method within the 'with' statement."
            )

        frames_dir = os.path.join(
            self._temp_dir, f"frames_fps_{str(fps).replace('.', '_')}"
        )
        os.makedirs(frames_dir, exist_ok=True)

        ffmpeg_cmd = [
            "ffmpeg",
            "-i",
            self._video_path,
            "-vf",
            f"fps={fps}",
            os.path.join(frames_dir, "frame_%04d.png"),
            "-y",
            "-loglevel",
            "error",
        ]

        process = subprocess.run(
            ffmpeg_cmd, capture_output=True, text=True, check=False
        )

        if process.returncode != 0:
            print(f"Warning: Error extracting frames with ffmpeg: {process.stderr}")
            return

        frame_files = [
            f
            for f in os.listdir(frames_dir)
            if f.startswith("frame_") and f.endswith(".png")
        ]
        frame_files.sort(key=lambda x: int(x[6:-4]))

        total_number_of_frames = len(frame_files)

        for file in frame_files:
            frame_path = os.path.join(frames_dir, file)
            try:
                frame_num_str = file[6:-4]
                frame_num = int(frame_num_str)
                total_seconds = frame_num / fps
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = total_seconds % 60
                timestamp = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

                yield frame_path, timestamp, total_number_of_frames
            except (IOError, ValueError) as e:
                print(f"Warning: Could not process frame file {frame_path}: {e}")
                continue

    def _extract_audio(self, video_path: str, destination_dir: str) -> Optional[str]:
        """Extract audio from video file.

        Returns:
            Optional[str]: Path to extracted audio file, None if extraction failed
        """
        audio_path = os.path.join(destination_dir, "audio.mp3")
        audio_cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-vn",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            audio_path,
            "-y",
            "-loglevel",
            "error",
        ]

        process = subprocess.run(audio_cmd, capture_output=True, text=True, check=False)

        if process.returncode != 0:
            print(f"Warning: Error extracting audio: {process.stderr}")
            return None
        elif not os.path.exists(audio_path):
            print("Warning: Audio file was not created")
            return None

        return audio_path

    def _download_youtube(self, uri: str, destination_dir: str) -> tuple[str, str, str]:
        video_filename = "video.%(ext)s"

        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "outtmpl": os.path.join(destination_dir, video_filename),
            "writeinfojson": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "en-US"],
            "quiet": True,
            "no_warnings": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(uri, download=False)
            title = info.get("title", "Unknown Title")
            description = info.get("description", "No description available")
            ydl.download([uri])

        video_path = None
        for file in os.listdir(destination_dir):
            if file.startswith("video.") and not file.endswith(
                (".json", ".vtt", ".srt")
            ):
                video_path = os.path.join(destination_dir, file)
                break

        if not video_path or not os.path.exists(video_path):
            raise FileNotFoundError("Downloaded video file not found")

        return video_path, title, description

    def _find_caption(self, destination_dir: str) -> Optional[str]:
        caption_files = [
            f for f in os.listdir(destination_dir) if f.endswith((".vtt", ".srt"))
        ]

        if not caption_files:
            return None

        caption_file = sorted(caption_files, key=lambda x: "auto" not in x.lower())[0]
        caption_path = os.path.join(destination_dir, caption_file)

        try:
            with open(caption_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not read caption file {caption_file}: {e}")
            return None


if __name__ == "__main__":
    # Example usage:
    video_url = "https://www.youtube.com/watch?v=2rk78RAY4xg"
    print(f"Testing with video URL: {video_url}")

    try:
        with YouTubeVideo(video_url) as video:
            print(f"Title: {video.title}")
            print(f"Description: {video.description[:200]}...")

            # Test caption
            caption = video.caption
            if caption:
                print(f"Caption found (first 250 chars): {caption[:250]}...")
            else:
                print("No caption found.")

            # Test audio extraction
            audio_file = video.audio_path
            if audio_file:
                print(f"Audio extracted to: {audio_file}")
            else:
                print("Audio extraction failed.")

            # Test frame generation
            print("Generating frames at 1 fps...")
            frame_count = 0
            for frame_path, timestamp, total_frames in video.generate_frames(fps=1):
                frame_count += 1
                print(
                    f"  - Frame {frame_count}/{total_frames} at {timestamp}, size: {os.path.getsize(frame_path)} bytes"
                )
                if frame_count >= 5:  # Limit to 5 frames for the test
                    time.sleep(60)
                    print("  - ... stopping after 5 frames for testing.")
                    break
            print(f"Successfully generated {frame_count} frames.")

            print(
                "\nSleeping for 60 seconds to allow for manual inspection of temp files..."
            )
            print(f"Temp directory: {video._temp_dir}")

    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
