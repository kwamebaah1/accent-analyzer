# REM Waste Accent Analyzer

A tool that analyzes English accents from video URLs (YouTube, Loom, or direct MP4) using AssemblyAI's speech recognition API.

## Features

- Supports YouTube, and direct MP4 URLs
- Accent classification with confidence scores
- Automatic video trimming for long files
- Clean Streamlit UI with progress tracking

## Prerequisites

- Python 3.8+
- FFmpeg (for audio processing)
- AssemblyAI API key (free tier available)

## Setup

### 1. Install FFmpeg (Required for Audio Processing)

#### Windows:

# Using Chocolatey (recommended)

choco install ffmpeg

# Manual installation:

1. Download from https://github.com/BtbN/FFmpeg-Binaries (ffmpeg-release-full.zip)
2. Scroll to the latest release and download the Windows 64-bit binary (e.g., ffmpeg-nX.X-latest-win64-gpl.zip).
3. Extract to C:\ffmpeg
4. Add C:\ffmpeg\bin to your PATH

#### macOS/Linux:

# macOS

brew install ffmpeg

# Linux (Debian/Ubuntu)

sudo apt-get install ffmpeg

git clone https://github.com/kwamebaah1/rem-waste-accent-analyzer.git
cd rem-waste-accent-analyzer

# Install Python dependencies

pip install -r requirements.txt

# Set up environment variables

echo "ASSEMBLYAI_API_KEY=your_api_key_here" > .env

- Go to https://www.assemblyai.com and get your API KEY

#### Usage

streamlit run accent_analyzer.py

## Test Videos

Try these sample URLs:

YouTube - https://www.youtube.com/watch?v=aO1-6X_f74M - 1:12
MP4 (Public) - https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4 - 0:15

# Run tests

pytest test_accent_analyzer.py
