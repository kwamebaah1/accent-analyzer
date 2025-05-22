import pytest
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env')

from accent_analyzer import download_video, extract_audio, analyze_accent

# Test with this small MP4 (public domain)
TEST_MP4_URL = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"

def test_download_video(tmp_path):
    """Test video downloading functionality"""
    output_path = tmp_path / "test_video.mp4"
    assert download_video(TEST_MP4_URL, str(output_path)) is True
    assert output_path.exists()
    assert output_path.stat().st_size > 0

def test_extract_audio(tmp_path):
    """Test audio extraction"""
    video_path = tmp_path / "video.mp4"
    if download_video(TEST_MP4_URL, str(video_path)):
        audio_path = tmp_path / "audio.wav"
        assert extract_audio(str(video_path), str(audio_path)) is True
        assert audio_path.exists()
        assert audio_path.stat().st_size > 0

@pytest.mark.skipif(not os.getenv("ASSEMBLYAI_API_KEY"), 
                   reason="AssemblyAI API key required in .env file")
def test_analyze_accent(tmp_path):
    """Test accent analysis with real API call"""
    # Setup test files
    video_path = tmp_path / "analysis_video.mp4"
    audio_path = tmp_path / "analysis_audio.wav"
    
    # Download and extract
    assert download_video(TEST_MP4_URL, str(video_path)) is True
    assert extract_audio(str(video_path), str(audio_path)) is True
    
    # Analyze
    result = analyze_accent(str(audio_path))
    
    # Validate response structure
    assert isinstance(result, dict)
    assert 'accent' in result
    assert isinstance(result['accent'], str)
    assert 'confidence' in result
    assert isinstance(result['confidence'], float)
    assert 0 <= result['confidence'] <= 100
    assert 'summary' in result
    assert isinstance(result['summary'], str)
    
    # Verify English was detected (since our test video is in English)
    assert 'en' in result['accent'].lower() or 'english' in result['summary'].lower()