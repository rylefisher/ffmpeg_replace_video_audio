import tkinter as tk
import tkinter.filedialog as fd
import tkinter.messagebox as mb
import subprocess
import json
import os
import sys
import shutil
 
class FfmpegApp:
  def __init__(self, master):
   self.master = master
   self.master.title("Simple FFmpeg GUI")
   self.master.geometry("350x250")
 
   self.info_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_info.json")
   self.video_info = {}
 
   self.check_ffmpeg()
   self.load_video_info()
 
   self.status_label = tk.Label(master, text="Status: Idle", fg="grey")
   self.status_label.pack(pady=5)
 
   self.extract_info_button = tk.Button(master, text="1. Select Video & Extract Info", command=self.extract_info)
   self.extract_info_button.pack(pady=10, fill=tk.X, padx=20)
 
   self.extract_audio_button = tk.Button(master, text="2. Extract Audio to WAV", command=self.extract_audio)
   self.extract_audio_button.pack(pady=10, fill=tk.X, padx=20)
 
   self.replace_audio_button = tk.Button(master, text="3. Replace Audio with WAV", command=self.replace_audio)
   self.replace_audio_button.pack(pady=10, fill=tk.X, padx=20)
 
  def check_ffmpeg(self):
   # check if ffmpeg and ffprobe are available
   if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
    mb.showerror("Error", "ffmpeg or ffprobe not found in system PATH. Please install FFmpeg.")
    sys.exit(1)
 
  def set_status(self, message, color="blue"):
   self.status_label.config(text=f"Status: {message}", fg=color)
   self.master.update_idletasks()
 
  def load_video_info(self):
   # load video info from json if exists
   if os.path.exists(self.info_file_path):
    try:
     with open(self.info_file_path, 'r') as f:
      self.video_info = json.load(f)
     self.set_status(f"Loaded info for: {os.path.basename(self.video_info.get('path', 'N/A'))}", "green")
    except json.JSONDecodeError:
     self.set_status("Error reading info file.", "red")
     self.video_info = {} # reset if file is corrupted
    except Exception as e:
     self.set_status(f"Failed to load info: {e}", "red")
     self.video_info = {}
 
  def save_video_info(self):
   # save video info to json
   try:
    with open(self.info_file_path, 'w') as f:
     json.dump(self.video_info, f, indent=4)
   except Exception as e:
    self.set_status(f"Failed to save info: {e}", "red")
    mb.showerror("Error", f"Could not save video info to {self.info_file_path}:\n{e}")
 
  def run_command(self, command, success_msg, error_msg_prefix):
   # execute ffmpeg/ffprobe commands
   try:
    self.set_status("Processing...", "orange")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    stdout, stderr = process.communicate()
 
    if process.returncode == 0:
     self.set_status(success_msg, "green")
     mb.showinfo("Success", success_msg)
     return stdout
    else:
     self.set_status(f"{error_msg_prefix}: Error", "red")
     print("FFmpeg Error Output:\n", stderr) # log stderr for debugging
     mb.showerror("Error", f"{error_msg_prefix}:\n{stderr.strip().splitlines()[-1]}") # show last line of error
     return None
   except FileNotFoundError:
    self.set_status("ffmpeg/ffprobe not found.", "red")
    mb.showerror("Error", "ffmpeg or ffprobe not found. Ensure FFmpeg is installed and in PATH.")
    return None
   except Exception as e:
    self.set_status(f"Command execution failed: {e}", "red")
    mb.showerror("Error", f"An unexpected error occurred:\n{e}")
    return None
 
  def extract_info(self):
   # open file dialog to select video
   file_path = fd.askopenfilename(
    title="Select Video File",
    filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv"), ("All Files", "*.*")]
   )
   if not file_path:
    self.set_status("No video selected.", "grey")
    return
 
   self.set_status("Extracting video info...", "orange")
   # use ffprobe to get stream info as json
   command = [
    "ffprobe",
    "-v", "quiet",
    "-print_format", "json",
    "-show_streams",
    file_path
   ]
 
   info_json_str = self.run_command(command, "Video info extracted.", "Info extraction failed")
 
   if info_json_str:
    try:
     info = json.loads(info_json_str)
     streams = info.get('streams', [])
     video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
     audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
 
     if not video_stream:
      self.set_status("No video stream found.", "red")
      mb.showerror("Error", "Could not find a video stream in the selected file.")
      return
     if not audio_stream:
      self.set_status("No audio stream found.", "red")
      mb.showwarning("Warning", "Could not find an audio stream in the selected file.")
      # allow proceeding without audio info if needed, storing None
 
     self.video_info = {
      'path': file_path,
      'video_codec': video_stream.get('codec_name'),
      'audio_codec': audio_stream.get('codec_name') if audio_stream else None
     }
     self.save_video_info()
     self.set_status(f"Info saved for: {os.path.basename(file_path)}", "green")
 
    except json.JSONDecodeError:
     self.set_status("Failed to parse video info.", "red")
     mb.showerror("Error", "Could not parse video information from ffprobe.")
    except Exception as e:
     self.set_status(f"Error processing info: {e}", "red")
     mb.showerror("Error", f"An unexpected error occurred while processing info:\n{e}")
 
  def extract_audio(self):
   # check if video info is loaded
   if not self.video_info or 'path' not in self.video_info:
    self.set_status("No video info loaded. Select video first.", "red")
    mb.showerror("Error", "Please select a video and extract info first (Button 1).")
    return
 
   video_path = self.video_info['path']
   video_dir = os.path.dirname(video_path)
   output_wav_path = os.path.join(video_dir, "output_audio.wav")
 
   self.set_status("Extracting audio to WAV...", "orange")
   # ffmpeg command to extract audio as uncompressed pcm_s16le wav
   command = [
    "ffmpeg",
    "-i", video_path,
    "-vn",             # no video output
    "-acodec", "pcm_s16le", # uncompressed 16-bit signed little-endian PCM
    "-ar", "44100",      # sample rate (common standard)
    "-ac", "2",          # channels (stereo)
    "-y",              # overwrite output file without asking
    output_wav_path
   ]
 
   self.run_command(command, f"Audio extracted to {output_wav_path}", "Audio extraction failed")
 
  def replace_audio(self):
   # check if video info is loaded
   if not self.video_info or 'path' not in self.video_info:
    self.set_status("No video info loaded. Select video first.", "red")
    mb.showerror("Error", "Please select a video and extract info first (Button 1).")
    return
 
   # open file dialog to select modified wav
   wav_path = fd.askopenfilename(
    title="Select Modified WAV File",
    filetypes=[("WAV Files", "*.wav"), ("All Files", "*.*")],
    initialdir=os.path.dirname(self.video_info['path']) # start in original video's dir
   )
   if not wav_path:
    self.set_status("No WAV file selected.", "grey")
    return
 
   video_path = self.video_info['path']
   video_codec = self.video_info.get('video_codec', 'copy') # default to copy if somehow missing
   audio_codec = self.video_info.get('audio_codec') # get original audio codec
 
   video_dir = os.path.dirname(video_path)
   base_name, ext = os.path.splitext(os.path.basename(video_path))
   output_video_path = os.path.join(video_dir, f"{base_name}_newaudio{ext}")
 
   self.set_status("Replacing audio...", "orange")
 
   # Determine audio codec for output. Try original, fallback to aac if problematic/missing.
   # Using the original codec directly with WAV input might fail. AAC is safer.
   # However, the request was to use the stored codec. Let's try it.
   # If audio_codec is None (e.g., original had no audio), default to AAC.
   output_audio_codec = audio_codec if audio_codec else 'aac'
   # a common safe fallback: output_audio_codec = 'aac'
 
   # ffmpeg command to replace audio
   command = [
    "ffmpeg",
    "-hwaccel", "auto", # attempt hardware acceleration for decoding
    "-i", video_path,    # input 0: original video
    "-i", wav_path,      # input 1: new audio
    "-map", "0:v:0",     # map video stream from input 0
    "-map", "1:a:0",     # map audio stream from input 1
    "-c:v", "copy",      # copy video stream without re-encoding (fast)
    "-c:a", output_audio_codec, # use original audio codec (or fallback)
    # Optional: add bitrate if needed, e.g. "-b:a", "192k" if using aac
    "-shortest",         # finish encoding when the shortest input stream ends (usually video)
    "-y",                # overwrite output file without asking
    output_video_path
   ]
   # if falling back to aac, add bitrate
   if output_audio_codec == 'aac':
     command.insert(-3, "-b:a") # insert before -shortest
     command.insert(-3, "192k") # standard quality bitrate
 
   success_msg = f"Video with new audio saved to {output_video_path}"
   error_msg = "Audio replacement failed"
   
   # Run command, handle potential codec issues
   if not self.run_command(command, success_msg, error_msg):
       # Try again with a safer codec like AAC if the first attempt failed and wasn't already AAC
       if output_audio_codec != 'aac':
           mb.showwarning("Codec Warning", f"Encoding with '{output_audio_codec}' might have failed. Retrying with 'aac'.")
           self.set_status("Retrying audio replacement with AAC codec...", "orange")
           command[command.index("-c:a") + 1] = "aac" # change codec in command list
           # ensure bitrate is set for aac if not already there
           if "-b:a" not in command:
               command.insert(-3, "-b:a") 
               command.insert(-3, "192k")
           else: # update bitrate if it exists but codec changed
                aac_bitrate_index = command.index("-b:a") + 1
                command[aac_bitrate_index] = "192k"
                
           self.run_command(command, success_msg, error_msg + " (AAC fallback)")
       # if it still fails, the previous error message stands
 
if __name__ == "__main__":
  root = tk.Tk()
  app = FfmpegApp(root)
  root.mainloop()