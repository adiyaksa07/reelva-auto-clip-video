# Reelva Auto Clip Video

Reelva Auto Clip Video is a Python tool that automatically clips YouTube videos into short highlight segments using smart scene detection. Ideal for creating short-form content like Shorts, Reels, and TikTok.

## Features
- Automatic scene detection
- Splits long YouTube videos into short clips
- Customizable minimum clip duration
- Fast processing using OpenCV + FFmpeg
- Output clips are clean and ready to upload

## Installation
1. Clone the repository:
   git clone https://github.com/adiyaksa07/reelva-auto-clip-video.git
2. Enter the folder:
   cd reelva-auto-clip-video
3. Install dependencies:
   pip install -r requirements.txt
4. Ensure FFmpeg is installed on your system.

## Usage
Run the script:
   python clip/main.py --input video.mp4 --output clips/ --min-duration 4

### Arguments
- --input : Source YouTube video file
- --output : Output folder for clips
- --min-duration : Minimum duration per clip (in seconds)

## Example Output
clips/
  clip_001.mp4
  clip_002.mp4
  clip_003.mp4

## Roadmap
- Auto-download YouTube videos (yt-dlp)
- Auto captioning
- AI highlight scoring
- GUI version

## License
MIT License
