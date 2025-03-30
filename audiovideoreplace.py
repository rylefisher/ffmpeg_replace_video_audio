import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import json

# Define constants for frequently used filenames
CODEC_INFO_FILENAME = "codec_info.json"
EXTRACTED_AUDIO_WAV = "extracted_audio.wav"
CONVERTED_AUDIO_AAC = "converted_audio.aac"

# --- Function to load codec info ---
def _load_codec_info():
    app_work_dir = os.getcwd()
    codec_info_path = os.path.join(app_work_dir, CODEC_INFO_FILENAME)
    if not os.path.exists(codec_info_path):
        messagebox.showerror("Error", f"{CODEC_INFO_FILENAME} not found. Please complete previous steps.")
        return None, None
    try:
        with open(codec_info_path, "r") as f:
            info = json.load(f)
        return info, codec_info_path
    except (json.JSONDecodeError, FileNotFoundError) as e:
         messagebox.showerror("Error", f"Failed to load codec info.\n{e}")
         return None, None

# --- Function to save codec info ---
def _save_codec_info(info, path):
    try:
        with open(path, "w") as f:
            json.dump(info, f, indent=4) # Use indent for readability
        return True
    except IOError as e:
        messagebox.showerror("Error", f"Failed to save codec info to {path}.\n{e}")
        return False


def select_video_and_get_info(): # Renamed function for clarity
    video_path = filedialog.askopenfilename(
        filetypes=[
            (
                "Video files",
                "*.mp4 *.mkv *.avi *.mov *.flv *.wmv *.webm *.ogg *.ts *.m4v",
            )
        ]
    )
    if not video_path:
        return

    app_work_dir = os.getcwd()
    codec_info_path = os.path.join(app_work_dir, CODEC_INFO_FILENAME)
    # audio_path_wav = os.path.join(app_work_dir, EXTRACTED_AUDIO_WAV) # Define wav path but don't use yet

    try:
        # Remove audio extraction from this step
        # --- Get video codec info ---
        ffprobe_codec_command = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=nw=1:nk=1",
            video_path,
        ]
        codec_name = subprocess.check_output(ffprobe_codec_command).strip().decode("utf-8")

        # --- Get container format info ---
        ffprobe_format_command = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=format_name",
            "-of", "default=nk=1:nw=1",
            "-i", video_path,
        ]
        format_names = subprocess.check_output(ffprobe_format_command).strip().decode("utf-8").split(',')
        format_name = format_names[0]

        # --- Get start time (potential delay) ---
        ffprobe_delay_command = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=start_time",
            "-of", "default=nk=1:nw=1",
            "-i", video_path,
        ]
        start_time_str = subprocess.check_output(ffprobe_delay_command).strip().decode("utf-8")
        start_time = 0.0
        try:
            start_time = float(start_time_str)
        except ValueError:
            print(f"Warning: Could not parse start_time '{start_time_str}'. Defaulting to 0.0.")


        info = {
            "video_path": video_path,
            # "audio_path_wav": audio_path_wav, # Do not save audio path yet
            "codec_name": codec_name,
            "format_name": format_name,
            "start_time": start_time,
        }

        # Save codec information
        if _save_codec_info(info, codec_info_path):
            messagebox.showinfo(
                "Success", f"Video selected and codec information saved to {CODEC_INFO_FILENAME}." # Updated message
            )
    except subprocess.CalledProcessError as e:
        error_message = f"Failed get video info.\nFFprobe Error:\n{e.stderr.decode() if e.stderr else str(e)}" # Updated message
        messagebox.showerror("Error", error_message)
    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred: {e}")

def extract_audio_from_video(): # New function for audio extraction
    info, codec_info_path = _load_codec_info() # Load existing info
    if info is None:
        return

    video_path = info.get("video_path")
    if not video_path or not os.path.exists(video_path):
         messagebox.showerror("Error", f"Video path not found in {CODEC_INFO_FILENAME} or file missing. Please select video first.")
         return

    app_work_dir = os.getcwd()
    audio_path_wav = os.path.join(app_work_dir, EXTRACTED_AUDIO_WAV) # Define extraction target

    try:
        # Perform audio extraction using loaded video path
        extract_command = [
            "ffmpeg",
            "-i", video_path,
            "-vn",                # Disable video recording
            "-acodec", "pcm_s16le", # Use signed 16-bit little-endian PCM for quality WAV
            "-ar", "44100",       # Standard sample rate
            "-ac", "2",           # Stereo audio channels
            audio_path_wav,
            '-y',                 # Overwrite output file without asking
        ]
        subprocess.run(extract_command, check=True, capture_output=True) # Capture output, check errors

        # Update info dictionary with the path of the extracted audio
        info["audio_path_wav"] = audio_path_wav

        # Re-save the updated info to the JSON file
        if _save_codec_info(info, codec_info_path):
             messagebox.showinfo("Success", f"Audio extracted to {EXTRACTED_AUDIO_WAV} and info updated.")

    except subprocess.CalledProcessError as e:
        error_message = f"Failed to extract audio.\nFFmpeg Error:\n{e.stderr.decode() if e.stderr else str(e)}"
        messagebox.showerror("Error", error_message)
    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred during audio extraction: {e}")


def select_audio_and_merge(): # Renamed function for clarity
    # Prompt user for the (potentially edited) WAV file
    audio_path_wav_input = filedialog.askopenfilename(filetypes=[("Audio files", "*.wav")]) # Keep prompting for edited wav
    if not audio_path_wav_input:
        return

    app_work_dir = os.getcwd()
    # codec_info_path = os.path.join(app_work_dir, CODEC_INFO_FILENAME) # Path generation moved to helper
    converted_audio_path = os.path.join(app_work_dir, CONVERTED_AUDIO_AAC)

    info, codec_info_path = _load_codec_info() # Load existing info
    if info is None:
        return

    video_path = info.get("video_path")
    if not video_path or not os.path.exists(video_path):
         messagebox.showerror("Error", f"Original video path not found in {CODEC_INFO_FILENAME} or file missing.")
         return
    # Note: We ignore info.get("audio_path_wav") as the user provides the potentially edited WAV

    try:
        # Convert the SELECTED WAV (not necessarily the originally extracted one) to high-quality AAC
        convert_aac_command = [
            "ffmpeg",
            "-i", audio_path_wav_input, # Use the user-selected WAV file
            "-c:a", "aac",      # Specify AAC codec
            "-q:a", "2",        # High quality VBR setting
            converted_audio_path,
            "-y",               # Overwrite output file without asking
        ]
        subprocess.run(convert_aac_command, check=True, capture_output=True) # Capture output, check errors

        # --- Merging logic remains the same ---
        extension_mapping = {
            "mp4": "mp4", "mov": "mov", "mkv": "mkv", "flv": "flv",
            "avi": "avi", "webm": "mkv", "wmv": "wmv", "mpegts": "ts",
        }
        output_extension = extension_mapping.get(info.get("format_name", "mp4"), "mp4")

        final_video_name = (
            os.path.splitext(os.path.basename(video_path))[0]
            + "_with_new_audio."
            + output_extension
        )
        final_video_path = os.path.join(app_work_dir, final_video_name)

        merge_command = [
            "ffmpeg",
            "-i", video_path,
            "-i", converted_audio_path,
            "-c:v", "copy",
            "-c:a", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            "-y",
            final_video_path,
        ]
        # Optional start_time offset logic (remains same)
        # if info.get("start_time", 0.0) != 0.0:
        #     merge_command.insert(4, "-itsoffset")
        #     merge_command.insert(5, str(info["start_time"]))

        subprocess.run(merge_command, check=True, capture_output=True) # Capture output, check errors

        messagebox.showinfo(
            "Success",
            f"High-quality audio re-encoded and merged.\nFinal video saved as: {final_video_path}",
        )
    # Error handling remains largely the same, adjusted message for JSON loading
    except (json.JSONDecodeError, FileNotFoundError) as e:
         messagebox.showerror("Error", f"Failed to load codec info or find file.\n{e}")
    except subprocess.CalledProcessError as e:
        error_message = f"Failed to process or merge audio.\nFFmpeg Error:\n{e.stderr.decode() if e.stderr else str(e)}"
        messagebox.showerror("Error", error_message)
    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred during merging: {e}")


# --- GUI Setup ---
root = tk.Tk()
root.title("FFmpeg Audio/Video Processor")
root.geometry("350x200") # Adjusted height for the extra button

# Button 1: Select Video and Get Info
select_video_info_btn = tk.Button(root, text="1. Select Video & Get Info", command=select_video_and_get_info) # Updated command
select_video_info_btn.pack(pady=5, padx=10, fill=tk.X) # Adjusted padding

# Button 2: Extract Audio
extract_audio_btn = tk.Button(root, text="2. Extract Audio (WAV)", command=extract_audio_from_video) # New button
extract_audio_btn.pack(pady=5, padx=10, fill=tk.X) # Adjusted padding

# Button 3: Select Edited Audio and Merge
select_merge_audio_btn = tk.Button(root, text="3. Select Edited WAV & Merge", command=select_audio_and_merge) # Updated command and text
select_merge_audio_btn.pack(pady=5, padx=10, fill=tk.X) # Adjusted padding

root.mainloop()
