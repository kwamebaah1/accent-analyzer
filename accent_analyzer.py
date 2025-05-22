import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional, Union, Tuple
import requests
import streamlit as st
from dotenv import load_dotenv
from pydub import AudioSegment
import yt_dlp
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()
ASSEMBLYAI_API_KEY: Union[str, None] = os.getenv("ASSEMBLYAI_API_KEY")
if not ASSEMBLYAI_API_KEY:
    raise ValueError("ASSEMBLYAI_API_KEY not found in .env file")

MAX_AUDIO_SIZE_MB = 5  # AssemblyAI free tier limit
MAX_VIDEO_LENGTH_MINUTES = 3  # Recommended max length for accurate analysis

class VideoProcessingError(Exception):
    """Custom exception for video processing errors."""
    pass

def validate_url(url: str) -> Optional[str]:
    """Validate and classify the video URL."""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None
        
        netloc = parsed.netloc.lower()
        path = parsed.path.lower()
        
        if 'youtube.com' in netloc or 'youtu.be' in netloc:
            return 'youtube'
        if 'loom.com' in netloc and '/share/' in path:
            return 'loom'
        if path.endswith('.mp4'):
            return 'mp4'
        
        return None
    except Exception as e:
        logging.error(f"Error validating URL {url}: {e}")
        return None

def download_youtube_video(url: str, output_path: str) -> bool:
    """Download a YouTube video using yt-dlp."""
    try:
        logging.info(f"Downloading YouTube video from {url}")
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': str(output_path),
            'quiet': True,
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        logging.info(f"YouTube video downloaded to {output_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to download YouTube video: {e}")
        return False

def get_loom_video_url(loom_url: str) -> Optional[str]:
    """Extract the direct MP4 URL from a Loom share URL."""
    try:
        api_url = f"https://www.loom.com/v1/oembed?url={loom_url}"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'html' in data:
            html = data['html']
            match = re.search(r'src="([^"]+)"', html)
            if match:
                video_src = match.group(1)
                if video_src.endswith('.mp4'):
                    return video_src
                
                iframe_response = requests.get(video_src, timeout=10)
                iframe_match = re.search(r'"video":{"url":"([^"]+)"', iframe_response.text)
                if iframe_match:
                    return iframe_match.group(1).replace('\\', '')
        
        response = requests.get(loom_url, timeout=10)
        patterns = [
            r'"video":{"url":"([^"]+)"',
            r'src="(https://cdn\.loom\.com/sessions/[^"]+\.mp4)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response.text)
            if match:
                url = match.group(1).replace('\\', '')
                if url.startswith('http'):
                    return url
        
        return None
    except Exception as e:
        logging.error(f"Error extracting Loom video URL: {e}")
        return None

def download_loom_video(url: str, output_path: str) -> bool:
    """Download a Loom video to the specified path."""
    try:
        mp4_url = get_loom_video_url(url)
        if not mp4_url:
            raise VideoProcessingError("Could not extract MP4 URL from Loom page")
        
        with requests.get(mp4_url, stream=True, timeout=30) as response:
            response.raise_for_status()
            with open(output_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
        return True
    except Exception as e:
        logging.error(f"Failed to download Loom video: {e}")
        return False

def download_video(url: str, output_path: str) -> bool:
    """Download a video based on its platform."""
    platform = validate_url(url)
    if not platform:
        logging.error(f"Unsupported URL: {url}")
        return False
    
    try:
        if platform == 'youtube':
            return download_youtube_video(url, output_path)
        elif platform == 'loom':
            return download_loom_video(url, output_path)
        elif platform == 'mp4':
            with requests.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()
                with open(output_path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            file.write(chunk)
            return True
    except Exception as e:
        logging.error(f"Failed to download {platform} video: {e}")
        return False

def extract_audio(video_path: str, audio_path: str, max_duration: Optional[int] = None) -> bool:
    """Extract audio from video, optionally trimming to max_duration seconds."""
    try:
        audio = AudioSegment.from_file(video_path, format="mp4")
        
        if max_duration:
            # Convert minutes to milliseconds
            max_ms = max_duration * 60 * 1000
            if len(audio) > max_ms:
                audio = audio[:max_ms]
                logging.info(f"Trimmed audio to {max_duration} minutes")
        
        audio = audio.normalize().set_channels(1)
        audio.export(audio_path, format="wav", parameters=["-ar", "16000"])
        return True
    except Exception as e:
        logging.error(f"Error extracting audio: {e}")
        return False

def check_audio_size(audio_path: str) -> Tuple[bool, float]:
    """Check if audio file is within size limits."""
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    return (file_size_mb <= MAX_AUDIO_SIZE_MB, file_size_mb)

def analyze_accent(audio_path: str) -> Dict[str, Union[str, float]]:
    """Analyze the speaker's accent using AssemblyAI API."""
    try:
        # Check file size
        is_valid_size, file_size = check_audio_size(audio_path)
        if not is_valid_size:
            raise VideoProcessingError(
                f"Audio file too large ({file_size:.2f}MB). "
                f"Max {MAX_AUDIO_SIZE_MB}MB allowed. "
                "Please try a shorter video (under 3 minutes)."
            )
        
        headers = {'authorization': ASSEMBLYAI_API_KEY}
        
        with open(audio_path, 'rb') as file:
            upload_response = requests.post(
                'https://api.assemblyai.com/v2/upload',
                headers=headers,
                data=file,
                timeout=30
            )
            upload_response.raise_for_status()
            audio_url = upload_response.json()['upload_url']
        
        transcript_response = requests.post(
            'https://api.assemblyai.com/v2/transcript',
            json={
                'audio_url': audio_url,
                'language_detection': True,
                'speech_model': 'best'
            },
            headers=headers,
            timeout=30
        )
        transcript_response.raise_for_status()
        transcript_id = transcript_response.json()['id']
        
        polling_endpoint = f'https://api.assemblyai.com/v2/transcript/{transcript_id}'
        start_time = time.time()
        timeout = 300
        
        while time.time() - start_time < timeout:
            result = requests.get(polling_endpoint, headers=headers, timeout=30).json()
            
            if result['status'] == 'completed':
                # Fixed the issue here - properly accessing the language detection results
                language_code = result.get('language_code', 'Unknown')
                confidence = result.get('confidence', 0.0) * 100
                
                return {
                    'accent': language_code,
                    'confidence': confidence,
                    'summary': f"Detected {language_code} accent with {confidence:.2f}% confidence."
                }
            elif result['status'] == 'error':
                raise VideoProcessingError(f"Transcription failed: {result.get('error', 'Unknown error')}")
            
            time.sleep(5)
        
        raise VideoProcessingError("Transcription timed out")
    except requests.exceptions.RequestException as e:
        logging.error(f"API request failed: {e}")
        return {
            'accent': 'Unknown',
            'confidence': 0.0,
            'summary': f"API request failed: {str(e)}"
        }
    except Exception as e:
        logging.error(f"Error analyzing accent: {e}")
        return {
            'accent': 'Unknown',
            'confidence': 0.0,
            'summary': f"Error during analysis: {str(e)}"
        }

def main() -> None:
    """Run the Streamlit app for accent analysis."""
    st.set_page_config(page_title="REM Waste Accent Analyzer", layout="wide")
    st.title("REM Waste Accent Analyzer")
    st.markdown(f"""
        Enter a public video URL (YouTube, or direct MP4, under {MAX_VIDEO_LENGTH_MINUTES} minutes) 
        with clear English audio to analyze the speaker's accent.
        Max audio size: {MAX_AUDIO_SIZE_MB}MB.
    """)
    
    with st.form("video_form"):
        video_url = st.text_input(
            "Video URL",
            placeholder="e.g., https://www.youtube.com/watch?v=VIDEO_ID"
        )
        auto_trim = st.checkbox(
            f"Automatically trim long videos (to {MAX_VIDEO_LENGTH_MINUTES} minutes)",
            value=True,
            help="Will analyze only the first part of videos longer than the limit"
        )
        submitted = st.form_submit_button("Analyze")
        
        if submitted:
            if not video_url:
                st.error("Please provide a valid video URL.")
                return
                
            platform = validate_url(video_url)
            if not platform:
                st.error("Invalid URL. Use a public YouTube, Loom, or direct MP4 link.")
                return
            
            with st.spinner(f"Processing {platform} video..."):
                status = st.empty()
                progress_bar = st.progress(0)
                
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        # Download video
                        status.markdown("🔍 Downloading video...")
                        progress_bar.progress(10)
                        video_path = os.path.join(tmpdir, "video.mp4")
                        
                        if not download_video(video_url, video_path):
                            st.error("Failed to download video. Please check the URL and try again.")
                            return
                        
                        # Extract audio
                        status.markdown("🎵 Extracting audio...")
                        progress_bar.progress(50)
                        audio_path = os.path.join(tmpdir, "audio.wav")
                        
                        max_duration = MAX_VIDEO_LENGTH_MINUTES if auto_trim else None
                        if not extract_audio(video_path, audio_path, max_duration):
                            st.error("Failed to extract audio. Please try another video.")
                            return
                        
                        # Check size before analysis
                        is_valid_size, file_size = check_audio_size(audio_path)
                        if not is_valid_size:
                            st.error(
                                f"Audio file too large ({file_size:.2f}MB). "
                                f"Max {MAX_AUDIO_SIZE_MB}MB allowed. "
                                "Please try a shorter video or enable auto-trim."
                            )
                            return
                        
                        # Analyze accent
                        status.markdown("🔊 Analyzing accent...")
                        progress_bar.progress(75)
                        result = analyze_accent(audio_path)
                        
                        # Display results
                        progress_bar.progress(100)
                        status.markdown("✅ Analysis Complete!")
                        
                        st.success("Analysis Complete!")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Detected Accent", result['accent'])
                        with col2:
                            st.metric("Confidence Score", f"{result['confidence']:.2f}%")
                        
                        st.info(result['summary'])
                        
                except VideoProcessingError as e:
                    st.error(str(e))
                except Exception as e:
                    logging.error(f"Processing error: {e}")
                    st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()