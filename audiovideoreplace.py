import subprocess
import tkinter as tk
from tkinter import filedialog
import os
import json

def select_video():
    # Select video file
    video_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mkv *.avi")])
    if not video_path:
        return
    work_dir = os.path.dirname(video_path)
    codec_info_path = os.path.join(work_dir, "codec_info.json")
    
    # Export audio
    audio_path = os.path.join(work_dir, "extracted_audio.aac")  # Adjust the format if needed
    subprocess.run(['ffmpeg', '-i', video_path, '-vn', '-acodec', 'copy', audio_path], check=True)
    
    # Get codec information
    ffprobe_command = [
        'ffprobe', '-v', 'error', '-select_streams', 'a:0',
        '-show_entries', 'stream=codec_name', '-of', 'default=nw=1:nk=1', video_path
    ]
    codec_name = subprocess.check_output(ffprobe_command).strip().decode('utf-8')
    
    info = {
        'video_path': video_path,
        'audio_path': audio_path,
        'codec_name': codec_name
    }
    
    # Save codec info to JSON file
    with open(codec_info_path, 'w') as f:
        json.dump(info, f)

def select_audio():
    # Select edited audio file
    audio_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.aac *.mp3 *.wav")])
    if not audio_path:
        return
    work_dir = os.path.dirname(audio_path)
    codec_info_path = os.path.join(work_dir, "codec_info.json")
    
    # Load codec info
    with open(codec_info_path, 'r') as f:
        info = json.load(f)
    
    # Convert audio to original codec
    converted_audio_path = os.path.join(work_dir, "converted_audio.aac")
    subprocess.run(['ffmpeg', '-i', audio_path, '-acodec', info['codec_name'], converted_audio_path], check=True)
    
    # Merge audio with the original video
    final_video_path = os.path.join(work_dir, "final_video.mp4")
    subprocess.run([
        'ffmpeg', '-i', info['video_path'], '-i', converted_audio_path,
        '-c:v', 'copy', '-map', '0:v:0', '-map', '1:a:0', '-y', final_video_path
    ], check=True)

# Set up tkinter window
root = tk.Tk()
root.title("FFmpeg Audio/Video Process")

select_video_btn = tk.Button(root, text="Select Video", command=select_video)
select_video_btn.pack(pady=10)

select_audio_btn = tk.Button(root, text="Select Audio", command=select_audio)
select_audio_btn.pack(pady=10)

root.mainloop()
