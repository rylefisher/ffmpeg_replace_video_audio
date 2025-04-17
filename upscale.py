import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import json
import os
import threading
import sys

# // --- Constants ---
RESOLUTIONS = {
    "Source": None,
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4k": (3840, 2160),
}
FRAME_RATES = {
    "Source": None,
    "30fps": 30,
    "60fps": 60,
}
FFMPEG_PATH = "ffmpeg"  # // Assume in PATH
FFPROBE_PATH = "ffprobe" # // Assume in PATH

# // --- Helper Functions ---
def check_ffmpeg():
    """Checks if ffmpeg and ffprobe are accessible."""
    try:
        subprocess.run([FFMPEG_PATH, "-version"], capture_output=True, check=True, startupinfo=get_startup_info())
        subprocess.run([FFPROBE_PATH, "-version"], capture_output=True, check=True, startupinfo=get_startup_info())
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        messagebox.showerror("Error", "ffmpeg or ffprobe not found. Please install ffmpeg and ensure it's in your system's PATH.")
        return False

def get_startup_info():
    """Hides console window on Windows when running subprocess."""
    if sys.platform == "win32":
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = subprocess.SW_HIDE
        return info
    return None

def get_video_info(filepath):
    """Queries video resolution and framerate using ffprobe."""
    if not filepath:
        return None, None, None
    try:
        command = [
            FFPROBE_PATH,
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            filepath
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True, startupinfo=get_startup_info())
        data = json.loads(result.stdout)

        video_stream = next((stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"), None)

        if not video_stream:
            return None, None, "No video stream"

        width = video_stream.get("width")
        height = video_stream.get("height")

        # // Get frame rate
        fr_str = video_stream.get("avg_frame_rate", "0/1")
        if fr_str == "0/0": # // Fallback if avg is 0/0
             fr_str = video_stream.get("r_frame_rate", "0/1")

        num, den = map(int, fr_str.split('/'))
        frame_rate = float(num) / float(den) if den != 0 else 0.0

        return width, height, frame_rate

    except subprocess.CalledProcessError as e:
        return None, None, f"ffprobe error: {e.stderr}"
    except Exception as e:
        return None, None, f"Error parsing info: {e}"

# // --- GUI Application ---
class VideoUpscalerApp:
    def __init__(self, master):
        self.master = master
        master.title("Video Upscaler")
        master.geometry("550x400")

        self.filepath = tk.StringVar()
        self.source_resolution = tk.StringVar(value="N/A")
        self.source_framerate = tk.StringVar(value="N/A")
        self.target_resolution = tk.StringVar(value=list(RESOLUTIONS.keys())[0])
        self.target_framerate = tk.StringVar(value=list(FRAME_RATES.keys())[0])
        self.status = tk.StringVar(value="Ready. Select a video file.")
        self.processing_thread = None
        self.source_info = {'width': None, 'height': None, 'fps': None}

        # // --- Widgets ---
        # // File Selection
        tk.Label(master, text="Video File:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        tk.Entry(master, textvariable=self.filepath, width=50, state="readonly").grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(master, text="Browse...", command=self.select_file).grid(row=0, column=2, padx=5, pady=5)

        # // Source Info Display
        info_frame = ttk.LabelFrame(master, text="Source Video Info")
        info_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        tk.Label(info_frame, text="Resolution:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        tk.Label(info_frame, textvariable=self.source_resolution).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        tk.Label(info_frame, text="Frame Rate:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        tk.Label(info_frame, textvariable=self.source_framerate).grid(row=1, column=1, padx=5, pady=2, sticky="w")

        # // Target Settings
        settings_frame = ttk.LabelFrame(master, text="Target Settings")
        settings_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        tk.Label(settings_frame, text="Target Resolution:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.res_dropdown = ttk.Combobox(settings_frame, textvariable=self.target_resolution, values=list(RESOLUTIONS.keys()), state="readonly")
        self.res_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        tk.Label(settings_frame, text="Target Frame Rate:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.fps_dropdown = ttk.Combobox(settings_frame, textvariable=self.target_framerate, values=list(FRAME_RATES.keys()), state="readonly")
        self.fps_dropdown.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # // Action Button
        self.process_button = tk.Button(master, text="Start Processing", command=self.start_processing, state="disabled")
        self.process_button.grid(row=3, column=0, columnspan=3, padx=10, pady=15)

        # // Status Bar
        status_bar = tk.Label(master, textvariable=self.status, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=4, column=0, columnspan=3, sticky="ew")

        # // Configure grid weights
        master.columnconfigure(1, weight=1)
        settings_frame.columnconfigure(1, weight=1)

    def select_file(self):
        """Opens file dialog to select video."""
        fpath = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=(("Video Files", "*.mp4 *.mkv *.avi *.mov *.webm"), ("All Files", "*.*"))
        )
        if fpath:
            self.filepath.set(fpath)
            self.status.set("Querying video info...")
            self.master.update_idletasks() # // Update GUI now
            width, height, fps = get_video_info(fpath)
            if width and height and fps:
                self.source_info = {'width': width, 'height': height, 'fps': fps}
                self.source_resolution.set(f"{width}x{height}")
                self.source_framerate.set(f"{fps:.2f} fps")
                self.status.set(f"Ready. File: {os.path.basename(fpath)}")
                self.process_button.config(state="normal")
                # // Reset dropdowns to source on new file select
                self.target_resolution.set("Source")
                self.target_framerate.set("Source")
            else:
                self.source_resolution.set("N/A")
                self.source_framerate.set("N/A")
                self.status.set(f"Error: Could not read video info ({fps})")
                self.process_button.config(state="disabled")
                messagebox.showerror("Error", f"Failed to get video information.\nDetails: {fps}")
        else:
            self.filepath.set("")
            self.source_resolution.set("N/A")
            self.source_framerate.set("N/A")
            self.status.set("File selection canceled.")
            self.process_button.config(state="disabled")


    def start_processing(self):
        """Initiates the video processing in a separate thread."""
        input_file = self.filepath.get()
        if not input_file or not os.path.exists(input_file):
            messagebox.showerror("Error", "Invalid or missing input file.")
            return

        res_key = self.target_resolution.get()
        fps_key = self.target_framerate.get()

        if res_key == "Source" and fps_key == "Source":
             messagebox.showinfo("Info", "Source resolution and frame rate selected. No changes needed.")
             return

        # // Prepare output filename
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_upscaled_{res_key}_{fps_key}{ext}"

        # // Disable button, update status
        self.process_button.config(state="disabled")
        self.status.set("Processing... Please wait.")

        # // Run in thread
        self.processing_thread = threading.Thread(
            target=self.run_ffmpeg,
            args=(input_file, output_file, res_key, fps_key),
            daemon=True
        )
        self.processing_thread.start()
        self.master.after(100, self.check_thread) # // Check thread status periodically

    def check_thread(self):
        """Checks if the processing thread is still running."""
        if self.processing_thread and self.processing_thread.is_alive():
            self.master.after(100, self.check_thread) # // Check again later
        else:
            # // Thread finished (or wasn't started properly)
            # // Status update is handled by run_ffmpeg on success/failure
            self.process_button.config(state="normal") # // Re-enable button


    def run_ffmpeg(self, input_file, output_file, res_key, fps_key):
        """Constructs and executes the ffmpeg command."""
        target_res = RESOLUTIONS.get(res_key)
        target_fps = FRAME_RATES.get(fps_key)

        if output_file == input_file:
             messagebox.showerror("Error", "Output file cannot be the same as input file.")
             self.status.set("Error: Output file conflict.")
             return

        command = [FFMPEG_PATH, "-hide_banner", "-y"] # // -y overwrites

        # // --- Input and Hardware Acceleration (Attempt) ---
        # // Simple attempt, may need specific checks per platform/build
        # // Add '-hwaccel cuda', '-hwaccel qsv', etc. *before* -i if desired
        # // command.extend(["-hwaccel", "cuda"]) # // Example: uncomment if needed
        command.extend(["-i", input_file])

        # // --- Video Filters ---
        vf_options = []
        # // Scaling
        if target_res:
            # // Only scale up
            if target_res[0] > self.source_info['width'] or target_res[1] > self.source_info['height']:
                 # // Simple scale to fit within target, may add bars depending on source aspect ratio
                 # // To force exact dimensions and potentially crop/distort: scale={target_res[0]}:{target_res[1]}
                 # // To letter/pillarbox: scale=w={target_res[0]}:h={target_res[1]}:force_original_aspect_ratio=decrease,pad={target_res[0]}:{target_res[1]}:(ow-iw)/2:(oh-ih)/2:color=black
                 scale_filter = f"scale={target_res[0]}:{target_res[1]}"
                 vf_options.append(scale_filter)
            else:
                 print(f"Skipping resolution change: Target {res_key} is not larger than source.")


        if vf_options:
            command.extend(["-vf", ",".join(vf_options)])

        # // --- Frame Rate ---
        if target_fps:
             # // Only change if different and greater than source (optional check)
             if target_fps != self.source_info['fps']: # and target_fps > self.source_info['fps']:
                 command.extend(["-r", str(target_fps)])


        # // --- Encoding ---
        # // Try hardware encoder first (NVIDIA example)
        encoder = "h264_nvenc" # // NVIDIA HW encoder
        # // encoder = "h264_qsv" # // Intel HW encoder
        # // encoder = "hevc_nvenc" # // NVIDIA HEVC HW encoder
        # // encoder = "libx264" # // Software fallback
        # // Need a way to check availability, falling back to libx264 for now if HW fails
        command.extend(["-c:v", encoder])
        command.extend(["-preset", "fast"]) # // Adjust preset as needed
        command.extend(["-cq", "23"])       # // Adjust quality as needed

        # // --- Audio ---
        command.extend(["-c:a", "copy"]) # // Copy audio stream

        # // --- Output ---
        command.append(output_file)

        # // --- Execute ---
        try:
            print("Executing FFmpeg command:")
            print(" ".join(command)) # // For debugging
            process = subprocess.Popen(command,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                                     startupinfo=get_startup_info())

            # // Simple wait, no live progress yet
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                self.status.set(f"Processing complete! Saved as {os.path.basename(output_file)}")
                messagebox.showinfo("Success", f"Video processed successfully!\nOutput: {output_file}")
            else:
                # // Try fallback encoder if specific HW encoder failed? (more complex)
                # // For now, just report error.
                error_message = f"FFmpeg Error (code {process.returncode}):\n{stderr[-500:]}" # // Show last bit of stderr
                print(error_message)
                self.status.set("Error during processing.")
                messagebox.showerror("FFmpeg Error", error_message)

        except FileNotFoundError:
             self.status.set("Error: ffmpeg command not found.")
             messagebox.showerror("Error", f"'{FFMPEG_PATH}' not found. Ensure ffmpeg is installed and in PATH.")
        except Exception as e:
            self.status.set(f"Error: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred:\n{e}")


# // --- Main Execution ---
if __name__ == "__main__":
    if not check_ffmpeg():
        sys.exit(1) # // Exit if ffmpeg/ffprobe missing

    root = tk.Tk()
    app = VideoUpscalerApp(root)
    root.mainloop()
