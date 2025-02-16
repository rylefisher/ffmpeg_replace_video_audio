import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import json

def select_video():
    # Select video file, supporting multiple formats
    video_path = filedialog.askopenfilename(filetypes=[
        ("Video files", "*.mp4 *.mkv *.avi *.mov *.flv *.wmv *.webm *.ogg *.ts *.m4v")
    ])
    if not video_path:
        return
    
    app_work_dir = os.getcwd()
    codec_info_path = os.path.join(app_work_dir, "codec_info.json")
    audio_path_wav = os.path.join(app_work_dir, "extracted_audio.wav")
    
    try:
        # Extract audio in WAV format
        subprocess.run(['ffmpeg', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', audio_path_wav], check=True)
        
        # Get codec and format information
        ffprobe_command = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name', '-of', 'default=nw=1:nk=1', video_path
        ]
        codec_name = subprocess.check_output(ffprobe_command).strip().decode('utf-8')
        
        format_command = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=format_name',
            '-of', 'default=nk=1:nw=1', '-i', video_path
        ]
        format_name = subprocess.check_output(format_command).strip().decode('utf-8')

        # Get audio delay information
        delay_command = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=start_time',
            '-of', 'default=nk=1:nw=1', '-i', video_path
        ]
        start_time = float(subprocess.check_output(delay_command).strip().decode('utf-8'))
        
        info = {
            'video_path': video_path,
            'audio_path_wav': audio_path_wav,
            'codec_name': codec_name,
            'format_name': format_name,
            'start_time': start_time
        }
        
        with open(codec_info_path, 'w') as f:
            json.dump(info, f)

        messagebox.showinfo("Success", "Audio extracted in WAV format and codec information saved.")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Failed to extract audio.\n{e}")

def select_audio():
    # Select edited audio file
    audio_path_wav = filedialog.askopenfilename(filetypes=[("Audio files", "*.wav")])
    if not audio_path_wav:
        return

    app_work_dir = os.getcwd()
    codec_info_path = os.path.join(app_work_dir, "codec_info.json")
    
    try:
        # Load codec info
        with open(codec_info_path, 'r') as f:
            info = json.load(f)
        
        # Convert the edited WAV audio to the same format as the original video
        audio_codec = 'aac' if info['codec_name'] == 'h264' else info['codec_name']
        converted_audio_path = os.path.join(app_work_dir, f"converted_audio.aac")
        subprocess.run(['ffmpeg', '-i', audio_path_wav, '-acodec', audio_codec, converted_audio_path], check=True)

        # Determine proper file extension from the original format
        extension_mapping = {
            'mp4': 'mp4',
            'mov': 'mov',
            'mkv': 'mkv',
            'flv': 'flv',
            'avi': 'avi',
            'webm': 'webm',
            'wmv': 'wmv'
        }
        output_extension = extension_mapping.get(info['format_name'], 'mp4')

        # Replace the audio in the original video
        final_video_name = os.path.splitext(os.path.basename(info['video_path']))[0] + "_with_new_audio." + output_extension
        final_video_path = os.path.join(app_work_dir, final_video_name)

        subprocess.run([
            'ffmpeg', '-i', info['video_path'], '-i', converted_audio_path,
            '-c:v', 'copy', '-map', '0:v:0', '-map', '1:a:0',
            '-shortest', '-y', final_video_path
        ], check=True)
        
        messagebox.showinfo("Success", f"Audio re-encoded and merged.\nFinal video saved as: {final_video_path}")
    except (json.JSONDecodeError, subprocess.CalledProcessError) as e:
        messagebox.showerror("Error", f"Failed to process re-merge audio.\n{e}")

# Set up tkinter window
root = tk.Tk()
root.title("FFmpeg Audio/Video Process")

select_video_btn = tk.Button(root, text="Select Video", command=select_video)
select_video_btn.pack(pady=10)

select_audio_btn = tk.Button(root, text="Select Edited Audio", command=select_audio)
select_audio_btn.pack(pady=10)

root.mainloop()
