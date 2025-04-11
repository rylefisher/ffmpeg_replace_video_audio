import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import threading
import os
import tempfile
import shutil

class AudioCompressorApp:
	def __init__(self, master):
		self.master = master
		master.title("HEVC Audio Compressor")
		master.geometry("600x300") # Set initial size

		# Style
		style = ttk.Style()
		style.theme_use('clam') # Use a modern theme

		# --- Input File ---
		self.input_frame = ttk.Frame(master, padding="10")
		self.input_frame.pack(fill=tk.X, pady=5)

		self.input_label = ttk.Label(self.input_frame, text="Input HEVC File:")
		self.input_label.pack(side=tk.LEFT, padx=5)

		self.input_path = tk.StringVar()
		self.input_entry = ttk.Entry(self.input_frame, textvariable=self.input_path, width=50)
		self.input_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

		self.input_button = ttk.Button(self.input_frame, text="Browse...", command=self.browse_input_file)
		self.input_button.pack(side=tk.LEFT, padx=5)

		# --- Output File ---
		self.output_frame = ttk.Frame(master, padding="10")
		self.output_frame.pack(fill=tk.X, pady=5)

		self.output_label = ttk.Label(self.output_frame, text="Output MP3 File:")
		self.output_label.pack(side=tk.LEFT, padx=5)

		self.output_path = tk.StringVar()
		self.output_entry = ttk.Entry(self.output_frame, textvariable=self.output_path, width=50)
		self.output_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

		self.output_button = ttk.Button(self.output_frame, text="Browse...", command=self.browse_output_file)
		self.output_button.pack(side=tk.LEFT, padx=5)

		# --- Action Button ---
		self.action_button = ttk.Button(master, text="Compress and Replace Audio", command=self.start_compression_thread)
		self.action_button.pack(pady=15, ipady=5) # Internal padding

		# --- Progress Bar ---
		self.progress = ttk.Progressbar(master, orient=tk.HORIZONTAL, length=580, mode='determinate')
		self.progress.pack(pady=5)

		# --- Status Label ---
		self.status_label = ttk.Label(master, text="Status: Ready", anchor=tk.W)
		self.status_label.pack(fill=tk.X, padx=10, pady=5)

		# Check for ffmpeg on startup
		self.check_ffmpeg()

	def check_ffmpeg(self):
		# Verify ffmpeg exists
		if shutil.which("ffmpeg") is None:
			self.update_status("Error: ffmpeg not found in PATH.", error=True)
			self.action_button.config(state=tk.DISABLED)
			messagebox.showerror("ffmpeg Error", "ffmpeg command not found. Please install ffmpeg and ensure it's in your system's PATH.")

	def browse_input_file(self):
		# Select input video
		file_path = filedialog.askopenfilename(
			title="Select HEVC Video File",
			filetypes=[("HEVC Video Files", "*.mkv *.mp4 *.mov"), ("All Files", "*.*")]
		)
		if file_path:
			self.input_path.set(file_path)
			# Auto-suggest output name
			if not self.output_path.get():
				base, ext = os.path.splitext(file_path)
				self.output_path.set(f"{base}_AAC{ext}")

	def browse_output_file(self):
		# Select output location
		input_val = self.input_path.get()
		initial_dir = os.path.dirname(input_val) if input_val else "/"
		initial_file = os.path.basename(self.output_path.get()) if self.output_path.get() else "output.mkv"

		file_path = filedialog.asksaveasfilename(
			title="Save Compressed File As",
			initialdir=initial_dir,
			initialfile=initial_file,
			defaultextension=".mkv",
			filetypes=[("Matroska Video", "*.mkv"), ("MP4 Video", "*.mp4"), ("All Files", "*.*")]
		)
		if file_path:
			self.output_path.set(file_path)

	def update_status(self, message, progress_val=None, error=False):
		# Update GUI status safely
		self.status_label.config(text=f"Status: {message}", foreground="red" if error else "black")
		if progress_val is not None:
			self.progress['value'] = progress_val
		self.master.update_idletasks() # Refresh UI

	def set_ui_state(self, enabled):
		# Enable/disable controls
		state = tk.NORMAL if enabled else tk.DISABLED
		self.input_entry.config(state=state)
		self.input_button.config(state=state)
		self.output_entry.config(state=state)
		self.output_button.config(state=state)
		self.action_button.config(state=state)

	def start_compression_thread(self):
		# Run compression in thread
		input_p = self.input_path.get()
		output_p = self.output_path.get()

		if not input_p or not output_p:
			messagebox.showerror("Error", "Please select both input and output files.")
			return
		if not os.path.exists(input_p):
			messagebox.showerror("Error", f"Input file not found:\n{input_p}")
			return
		if os.path.dirname(output_p) and not os.path.exists(os.path.dirname(output_p)):
			messagebox.showerror("Error", f"Output directory does not exist:\n{os.path.dirname(output_p)}")
			return
		if input_p == output_p:
			messagebox.showerror("Error", "Input and output files cannot be the same.")
			return
		if shutil.which("ffmpeg") is None: # Re-check just in case
			self.check_ffmpeg()
			return

		self.set_ui_state(False)
		self.update_status("Starting compression...", 0)

		thread = threading.Thread(target=self.run_compression, args=(input_p, output_p), daemon=True)
		thread.start()

	def run_command(self, command_list):
		# Execute ffmpeg command
		process = subprocess.Popen(
			command_list,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT, # Combine output
			universal_newlines=True,
			encoding='utf-8',
			creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0 # Hide console on Win
		)
		output = ""
		for line in iter(process.stdout.readline, ''):
			output += line
			# Basic progress parsing could go here if needed
			# For simplicity, we just let it run.
		process.stdout.close()
		return_code = process.wait()
		if return_code != 0:
			# Log detailed error
			print(f"FFmpeg Error:\nCommand: {' '.join(command_list)}\nOutput:\n{output}")
			raise subprocess.CalledProcessError(return_code, command_list, output=output)
		return output

	def run_compression(self, input_path, output_path):
		# Main ffmpeg logic
		try:
			with tempfile.TemporaryDirectory() as temp_dir:
				temp_audio_raw = os.path.join(temp_dir, "temp_audio.wav") # Extracted PCM
				temp_audio_mp3 = os.path.join(temp_dir, "temp_audio.mp3") # Compressed MP3

				# 1. Extract Audio (as PCM s16le)
				self.update_status("Extracting audio...", 10)
				cmd_extract = [
					"ffmpeg", "-hide_banner", "-loglevel", "warning", # Less verbose
					"-i", input_path,
					"-vn",                 # No video
					"-acodec", "pcm_s16le", # Force specific PCM
					"-ar", "44100",        # Standard sample rate
					"-ac", "2",            # Stereo
					"-y",                  # Overwrite output
					temp_audio_raw
				]
				self.run_command(cmd_extract)

				# 2. Compress Audio to MP3 (VBR -q:a 2)
				self.update_status("Compressing audio to MP3...", 40)
				cmd_compress = [
					"ffmpeg", "-hide_banner", "-loglevel", "warning",
					"-i", temp_audio_raw,
					"-vn",                 # No video
					"-acodec", "libmp3lame",# Use LAME MP3 encoder
					"-q:a", "2",           # VBR quality (0-9, lower=better)
					"-y",                  # Overwrite output
					temp_audio_mp3
				]
				self.run_command(cmd_compress)

				# 3. Replace Audio Stream
				self.update_status("Replacing audio in video...", 70)
				cmd_replace = [
					"ffmpeg", "-hide_banner", "-loglevel", "warning",
					"-i", input_path,      # Input video
					"-i", temp_audio_mp3,  # Input compressed audio
					"-map", "0:v:0",       # Map video from first input
					"-map", "1:a:0",       # Map audio from second input
					"-c:v", "copy",        # Copy video stream (FAST)
					"-c:a", "copy",        # Copy audio stream (FAST)
					"-shortest",           # Finish when shortest stream ends
					"-y",                  # Overwrite output
					output_path
				]
				self.run_command(cmd_replace)

				self.update_status(f"Success! Output saved to {os.path.basename(output_path)}", 100)

		except FileNotFoundError:
			# Should be caught by check_ffmpeg, but belt-and-suspenders
			self.update_status("Error: ffmpeg not found.", error=True)
			messagebox.showerror("ffmpeg Error", "ffmpeg command not found. Please install ffmpeg and ensure it's in your system's PATH.")
		except subprocess.CalledProcessError as e:
			error_msg = f"FFmpeg failed (code {e.returncode}). See console/log for details."
			self.update_status(error_msg, error=True)
			messagebox.showerror("Processing Error", f"{error_msg}\n\nCommand:\n{' '.join(e.cmd)}\n\nOutput:\n{e.output[-500:]}") # Show last bit of output
		except Exception as e:
			error_msg = f"An unexpected error occurred: {type(e).__name__}"
			self.update_status(error_msg, error=True)
			messagebox.showerror("Error", f"{error_msg}\n\nDetails: {e}")
			# Log full traceback to console for debugging
			import traceback
			print("--- Full Traceback ---")
			traceback.print_exc()
			print("----------------------")
		finally:
			# Re-enable UI elements
			self.set_ui_state(True)
			# Reset progress bar if not success
			if "Success" not in self.status_label.cget("text"):
				self.progress['value'] = 0


if __name__ == "__main__":
	root = tk.Tk()
	app = AudioCompressorApp(root)
	root.mainloop()
