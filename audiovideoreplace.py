import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import json

def select_video():
    # Select video file, now including .mov format
    video_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mkv *.avi *.mov")])
    if not video_path:
        return
    work_dir = os.path.dirname(video_path)
    codec_info_path = os.path.join(work_dir, "codec_info.json")
    
    audio_path = os.path.join(work_dir, "extracted_audio.aac")  # Adjust the format if needed
    try:
        # Export audio
        subprocess.run(['ffmpeg', '-i', video_path, '-vn', '-acodec', 'copy', audio_path], check=True)
        
        # Get codec information
        ffprobe_command = [
            'ffprobe', '-v', 'error', '-select_streams', 'a:0',
            '-show_entries', 'stream=codec_name', '-of', 'default=nw=1:nk=1', video_path
        ]
        codec_name = subprocess.check_output(ffprobe_command).strip().decode('utf-8')

        # Get audio delay information
        delay_command = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=start_time',
            '-of', 'default=nk=1:nw=1', '-i', video_path
        ]
        start_time = float(subprocess.check_output(delay_command).strip().decode('utf-8'))
        
        info = {
            'video_path': video_path,
            'audio_path': audio_path,
            'codec_name': codec_name,
            'start_time': start_time
        }
        
        with open(codec_info_path, 'w') as f:
            json.dump(info, f)

        messagebox.showinfo("Success", "Audio extracted and codec information saved.")
    except subprocess.CalledProcessError:
        messagebox.showerror("Error", "Failed to extract audio from the video.")

def select_audio():
    # Select edited audio file
    audio_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.aac *.mp3 *.wav")])
    if not audio_path:
        return
    work_dir = os.path.dirname(audio_path)
    codec_info_path = os.path.join(work_dir, "codec_info.json")
    
    try:
        # Load codec info
        with open(codec_info_path, 'r') as f:
            info = json.load(f)
        
        # Convert audio to original codec
        converted_audio_path = os.path.join(work_dir, "converted_audio.aac")
        subprocess.run(['ffmpeg', '-i', audio_path, '-acodec', info['codec_name'], converted_audio_path], check=True)
        
        # Ensure audio alignment with the beginning of the video
        final_video_name = os.path.splitext(os.path.basename(info['video_path']))[0] + "_final.mov"
        final_video_path = os.path.join(work_dir, final_video_name)
        subprocess.run([
            'ffmpeg', '-i', info['video_path'], '-i', converted_audio_path,
            '-c:v', 'copy', '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
            '-af', f"adelay={int(info['start_time'] * 1000)}|delays={int(info['start_time'] * 1000)}", # Convert start time to milliseconds
            '-shortest', '-y', final_video_path
        ], check=True)
        
        messagebox.showinfo("Success", f"Audio re-encoded and merged.\nFinal video saved as: {final_video_path}")
    except (json.JSONDecodeError, subprocess.CalledProcessError):
        messagebox.showerror("Error", "Failed to process audio with ffmpeg.")

# Set up tkinter window
root = tk.Tk()
root.title("FFmpeg Audio/Video Process")

select_video_btn = tk.Button(root, text="Select Video", command=select_video)
select_video_btn.pack(pady=10)

select_audio_btn = tk.Button(root, text="Select Audio", command=select_audio)
select_audio_btn.pack(pady=10)

root.mainloop()
