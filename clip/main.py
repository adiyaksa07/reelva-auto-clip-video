import yt_dlp
import os
import dotenv
import json
import subprocess
import random
import math
import re
import time
import assemblyai as aai

from openai import OpenAI
from gradient import Gradient

from prompt.system_prompt import SYSTEM_PROMPT_REELVA_PRO
from prompt.sonar_system_prompt import SYSTEM_PROMPT_REELVA_PRO as SONAR_SYSTEM_PROMPT_REELVA_PRO

dotenv.load_dotenv()

using_openai = False

if using_openai:
    client = OpenAI(
        api_key=os.getenv("ai_api"),
        base_url="https://api.perplexity.ai"
    )
else:
    client_gradient = Gradient(
        model_access_key=os.getenv("MODEL_ACCESS_KEY")
    )

# AssemblyAI setup
aai.settings.api_key = os.getenv("assemblyai_api_key")

config = aai.TranscriptionConfig(
    speaker_labels=True,
    format_text=True,
    punctuate=True,
    speech_model="universal",
    language_detection=True
)

transcriber = aai.Transcriber()

if not os.path.exists('clip/result') or not os.path.exists("clip/transcripts") or not os.path.exists("clip/subtitles") or not os.path.exists("clip/audio"):
    os.makedirs('clip/result', exist_ok=True)
    os.makedirs("clip/transcripts", exist_ok=True)
    os.makedirs("clip/subtitles", exist_ok=True)
    os.makedirs("clip/audio", exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# YOUTUBE SHORTS SUBTITLE FUNCTIONS (OPTIMIZED & SYNCED)
# ═══════════════════════════════════════════════════════════════

def seconds_to_ass_time(seconds):
    """Convert seconds to ASS time format: H:MM:SS.CS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

def get_word_level_segments(transcript):
    """Extract word-level timestamps dari AssemblyAI"""
    word_segments = []

    for word in transcript.words:
        word_segments.append({
            "start_time": word.start / 1000.0,
            "end_time": word.end / 1000.0,
            "text": word.text,
            "confidence": word.confidence
        })

    return word_segments

def generate_clean_highlight_ass(output_path, words, clip_start_time=0):
    """
    Subtitle static: semua kata tetap terlihat (highlight hanya current word)
    Siap untuk Reelva vertical 1080x1920
    """
    FONT_SIZE = 72
    header = f"""[Script Info]
Title: ReelvA Pro - Clean Highlight Subtitle
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Highlight,Arial Black,{FONT_SIZE},&H00FFFF,&HFFFFFF,&H000000,&H80000000,1,0,0,0,100,100,0,0,1,7,5,2,40,40,620,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    def seconds_to_ass_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds - int(seconds)) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        wpl = 3
        for i in range(0, len(words), wpl):
            line_words = words[i:i + wpl]
            for word_idx, word in enumerate(line_words):
                word_start = word['start_time'] - clip_start_time
                if word_idx < len(line_words) - 1:
                    word_end = line_words[word_idx + 1]['start_time'] - clip_start_time
                else:
                    word_end = line_words[-1]['end_time'] - clip_start_time
                # Validasi timing
                if word_start < 0 or word_end <= word_start: continue
                start_fmt = seconds_to_ass_time(word_start)
                end_fmt = seconds_to_ass_time(word_end)
                text_parts = []
                for idx, w in enumerate(line_words):
                    txt = w['text'].upper()
                    if idx == word_idx:
                        text_parts.append(f"{{\\c&H00FFFF&\\b1}}{txt}{{\\r}}")
                    else:
                        text_parts.append(f"{{\\c&HFFFFFF&\\b1}}{txt}{{\\r}}")
                full_text = " ".join(text_parts)
                f.write(f"Dialogue: 0,{start_fmt},{end_fmt},Highlight,,40,40,620,,{full_text}\n")

def add_subtitles_to_clip(video_path, ass_path, output_path):
    """Add ASS subtitles ke video dengan FFmpeg"""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"ass={ass_path}",
        "-c:a", "copy",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "veryfast",
        output_path
    ]
    subprocess.run(cmd, check=True)

# ═══════════════════════════════════════════════════════════════
# ORIGINAL FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def download_youtube_video(video_url, output_path='clip/videos'):
    filename_video_id = str(video_url).split("watch?v=")[-1].split("&")[0] if "watch?v=" in str(video_url) else None
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': os.path.join(output_path, f'{filename_video_id}.%(ext)s'),
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'ignoreerrors': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            video_title = info_dict.get('title', 'Unknown Title')
            channel_name = info_dict.get('uploader', 'Unknown Channel')
            categories = info_dict.get('categories', [])
            tags = info_dict.get('tags', [])
            description = info_dict.get('description', '')
            os.makedirs(f'clip/result/{filename_video_id}', exist_ok=True)
            return {
                "status": True,
                "video_title": video_title,
                "channel_name": channel_name,
                "filename_video_id": f"{filename_video_id}",
                "categories": categories,
                "tags": tags,
                "description": description
            }
    except Exception as e:
        print(f"Terjadi kesalahan saat mengunduh video: {e}")
        return None

def ffmpeg_convert_to_mp3(input_video_path, output_audio_path):
    if not os.path.exists(input_video_path):
        print(f"File video tidak ditemukan: {input_video_path}")
        return False
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", input_video_path,
        output_audio_path
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print("FFmpeg error:", p.stderr.strip())
        return False
    return True

def normalize_transcript_timestamps(segments):
    """
    Fix overlaps dan gaps di transcript
    """
    for i in range(len(segments) - 1):
        current_end = segments[i]["end_time"]
        next_start = segments[i + 1]["start_time"]
        
        # If overlap: snap to middle point
        if next_start < current_end:
            midpoint = (current_end + next_start) / 2
            segments[i]["end_time"] = midpoint
            segments[i + 1]["start_time"] = midpoint
        
        # If large gap (>1s): might indicate missing segment
        if next_start - current_end > 1.0:
            print(f"⚠️ Large gap: {current_end} → {next_start}")
    
    return segments

# ═══════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════

input_youtube_url = input("Masukkan URL video YouTube yang ingin diunduh: ")
video_id = str(input_youtube_url).split("watch?v=")[-1].split("&")[0] if "watch?v=" in str(input_youtube_url) else None

downloaded_file = download_youtube_video(input_youtube_url)

if True:
    input_video_path = f"clip/videos/{downloaded_file.get('filename_video_id')}.mp4"
    output_audio_path = f"clip/audio/{downloaded_file.get('filename_video_id')}.mp3"

    print("🎬 Mengonversi video ke format audio MP3...")
    ffmpeg_convert_to_mp3(input_video_path, output_audio_path)

    print("🎤 Memulai proses transkripsi...")

    try:
        transcript = transcriber.transcribe(output_audio_path, config=config)

        if transcript.status == aai.TranscriptStatus.error:
            print(f"❌ Transcription failed: {transcript.error}")
            exit(1)
    except Exception as e:
        print(f"⚠️ Transcription error: {e}. Retrying...")
        time.sleep(5)
        transcript = transcriber.transcribe(output_audio_path, config=config)
        if transcript.status == aai.TranscriptStatus.error:
            print(f"❌ Transcription failed: {transcript.error}")
            exit(1)

    word_segments = get_word_level_segments(transcript)
    print(f"✅ Extracted {len(word_segments)} words dengan timestamp SEMPURNA")

    transcript_segments = []
    num_speakers = len({u.speaker for u in transcript.utterances if getattr(u, "speaker", None)})
    total_utterances = len(transcript.utterances)
    avg_utterance_len = sum(len(u.text.split()) for u in transcript.utterances) / max(1, total_utterances)

    if num_speakers <= 1 or avg_utterance_len > 80:  
        mode = "sentences"
    else:
        mode = "utterances"

    if mode == "sentences":
        sentences = transcript.get_sentences()
        for sentence in sentences:
            transcript_segments.append({
                "start_time": max(0, round(sentence.start / 1000.0, 2)),
                "end_time": round((sentence.end / 1000.0), 2), 
                "text": sentence.text,
                "speaker": sentence.speaker,
                "confidence": sentence.confidence
            })
    else:
        for utterance in transcript.utterances:
            transcript_segments.append({
                "start_time": max(0, round(utterance.start / 1000.0, 2)),
                "end_time": round(utterance.end / 1000.0, 2),
                "text": utterance.text,
                "speaker": utterance.speaker,
                "confidence": utterance.confidence
            })

    transcript_segments = normalize_transcript_timestamps(transcript_segments)
    
    if mode == "sentences":
        note = "Single speaker monolog - segments are short sentences that need merging into coherent 15-180s clips"
    else:
        note = "Multi-speaker conversation - segments are speaker turns, preserve Q&A pairs and dialogue flow"


    with open(f"clip/transcripts/{downloaded_file.get('filename_video_id')}_transcript.ndjson", "w", encoding="utf-8") as f:
        for obj in transcript_segments:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    video_duration_seconds = transcript_segments[-1]["end_time"]
    video_duration_minutes = math.ceil(video_duration_seconds / 60.0)

    if using_openai:
        prompt_content = SONAR_SYSTEM_PROMPT_REELVA_PRO
        response = client.chat.completions.create(
            model="sonar",
            messages=[
                {"role": "system", "content": prompt_content},
                {"role": "user", "content": json.dumps(transcript_segments, ensure_ascii=False)}
            ],
            temperature=0.3
        )
    else:
        VIDEO_NAME = downloaded_file.get("video_title", "Unknown Title")
        CHANNEL_NAME = downloaded_file.get("channel_name", "Unknown Channel")
        VIDEO_DESCRIPTION = downloaded_file.get("description", "")
        CATEGORIES = downloaded_file.get("categories", [])
        TAGS = downloaded_file.get("tags", [])

        response = client_gradient.chat.completions.create(
            model="openai-gpt-oss-120b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_REELVA_PRO},
                {
                    "role": "user",
                    "content": json.dumps({
                        "segmentation_mode": mode,
                        "segmentation_note": note,
                        "video_metadata": { 
                            "title": VIDEO_NAME,
                            "channel": CHANNEL_NAME,
                            "description": VIDEO_DESCRIPTION, 
                            "categories": CATEGORIES,
                            "tags": TAGS,
                        },
                        "transcript_segments": transcript_segments,
                    })
                }
            ]
        )

        with open("clip/debug_response.txt", "w", encoding="utf-8") as f:
            f.write(str(response))

    raw_response = response.choices[0].message.content
    raw = re.sub(r"<think>[\s\S]*?</think>", "", raw_response)
    m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", raw)
    if not m: 
        m = re.search(r"(\{[\s\S]*\})", raw)
    json_str = m.group(1).strip().rstrip(".") if m else "{}"
    data_clip = json.loads(json_str)

    index_generate_video = 0
    for cp in data_clip.get("clips", []):
        index_generate_video += 1
        start_time = cp.get("start_time")
        end_time = cp.get("end_time")
        video_title = cp.get("video_title")

        print(f"\n🎬 Generating clip {index_generate_video}: {video_title}")
        print(f"   ⏱️  Time: {start_time}s - {end_time}s")

        # Step 1: Generate clip WITHOUT subtitles
        clip_no_sub = f"temp_{video_title}.mp4"

        subprocess.run([
            "ffmpeg", "-y",
            "-ss", f"{start_time}",
            "-to", f"{end_time}",
            "-i", f"clip/videos/{downloaded_file.get('filename_video_id')}.mp4",
            "-filter_complex",
            (
                f"[0:v]crop=ih*9/16:ih:(iw-ow)/2:0,"
                f"scale=1080:1920:flags=bicubic,"
                f"tpad=stop_mode=clone:stop_duration=0.25[v];"
                f"apad=pad_dur=0.25,loudnorm=I=-16:TP=-1.5:LRA=11[a]"
            ),
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-crf", "19",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            clip_no_sub
        ], check=True)

        # Step 2: Get words untuk clip ini
        clip_words = [
            w for w in word_segments
            if w['start_time'] >= start_time and w['end_time'] <= end_time
        ]

        if clip_words:
            print(f"   📝 Generating YouTube Shorts subtitles ({len(clip_words)} words)...")

            # Step 3: Generate ASS file dengan PERFECT TIMING SYNC
            ass_path = f"clip/subtitles/{video_title}_shorts.ass"
            generate_clean_highlight_ass(ass_path, clip_words, clip_start_time=start_time)

            # Step 4: Add subtitles to video
            final_output = f"clip/result/{downloaded_file.get('filename_video_id')}/{video_title}_{random.randint(1, 1000)}.mp4"
            print(f"   ✨ Adding YouTube Shorts subtitles dengan TIMING SYNC...")
            add_subtitles_to_clip(clip_no_sub, ass_path, final_output)

            # Cleanup
            os.remove(clip_no_sub)
            print(f"   ✅ Done: {final_output}")
        else:
            # No words, save without subtitles
            final_output = f"clip/result/{downloaded_file.get('filename_video_id')}/{video_title}_{random.randint(1, 1000)}.mp4"
            os.rename(clip_no_sub, final_output)
            print(f"   ⚠️  No words found, saved without subtitles")

    print("\n" + "="*70)
    print("✅ REELVA PRO - COMPLETE!")
    print("="*70)
    print(f"📊 Generated {index_generate_video} clips dengan YouTube Shorts subtitles")
    print("   • Subtitle position: YouTube Shorts safe zone (540, 1300)")
    print("   • Font: Arial Black 72px")
    print("   • Text: UPPERCASE + YELLOW highlight")
    print("   • Timing: PERFECTLY SYNCED dari AssemblyAI")
    print("\n🚀 Ready untuk upload!")