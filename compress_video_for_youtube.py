import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import threading
import os
import shutil
import queue # Not strictly needed with 'after', but good practice

class VideoConverterApp:
	def __init__(self, root_window):
		self.root = root_window
		self.root.title("Video Converter")
		self.root.geometry("600x300") # Adjusted size

		self.ffmpeg_path = self._find_ffmpeg()
		self.has_cuda = self._check_cuda_support() if self.ffmpeg_path else False

		self.input_var = tk.StringVar()
		self.output_var = tk.StringVar()
		self.status_var = tk.StringVar()
		self.status_var.set("Ready. Select files.")

		self._create_widgets()

		if not self.ffmpeg_path:
			self.status_var.set("Error: FFmpeg not found in PATH.")
			messagebox.showerror("Setup Error", "FFmpeg not found. Please install it and add to PATH.")
			self.start_button.config(state=tk.DISABLED)
		elif self.has_cuda:
			self.status_var.set("Ready (CUDA available).")
		else:
			self.status_var.set("Ready (CUDA not found, using CPU).")


	def _find_ffmpeg(self):
		# Find ffmpeg executable
		return shutil.which("ffmpeg")

	def _check_cuda_support(self):
		# Check for h264_nvenc
		try:
			startupinfo = None
			if os.name == 'nt': # Hide console on Win
				startupinfo = subprocess.STARTUPINFO()
				startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
				startupinfo.wShowWindow = subprocess.SW_HIDE

			result = subprocess.run(
				[self.ffmpeg_path, "-encoders"],
				capture_output=True, text=True, check=True,
				encoding='utf-8', errors='ignore', # Be robust
				startupinfo=startupinfo
			)
			return "h264_nvenc" in result.stdout
		except (subprocess.CalledProcessError, FileNotFoundError, OSError):
			return False # FFmpeg error or not found

	def _create_widgets(self):
		# Setup GUI elements
		main_frame = ttk.Frame(self.root, padding="10")
		main_frame.pack(fill=tk.BOTH, expand=True)

		# Input Row
		input_frame = ttk.Frame(main_frame)
		input_frame.pack(fill=tk.X, pady=5)
		ttk.Label(input_frame, text="Input File:").pack(side=tk.LEFT, padx=(0, 5))
		ttk.Entry(input_frame, textvariable=self.input_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
		ttk.Button(input_frame, text="Browse...", command=self._select_input).pack(side=tk.LEFT, padx=(5, 0))

		# Output Row
		output_frame = ttk.Frame(main_frame)
		output_frame.pack(fill=tk.X, pady=5)
		ttk.Label(output_frame, text="Output File:").pack(side=tk.LEFT, padx=(0, 5))
		ttk.Entry(output_frame, textvariable=self.output_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
		ttk.Button(output_frame, text="Browse...", command=self._select_output).pack(side=tk.LEFT, padx=(5, 0))

		# Start Button
		self.start_button = ttk.Button(main_frame, text="Start Conversion", command=self._start_conversion_thread)
		self.start_button.pack(pady=15)

		# Progress Bar
		self.progress_bar = ttk.Progressbar(main_frame, mode='indeterminate')
		self.progress_bar.pack(fill=tk.X, pady=5)

		# Status Label
		status_label = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
		status_label.pack(fill=tk.X, pady=(10, 0), ipady=2)

	def _select_input(self):
		# Handle input file dialog
		file_path = filedialog.askopenfilename(
			title="Select Input HEVC Video",
			filetypes=[("HEVC Video Files", "*.mkv *.mp4 *.mov"), ("All Files", "*.*")]
		)
		if file_path:
			self.input_var.set(file_path)
			# Auto-suggest output name
			if not self.output_var.get():
				base, _ = os.path.splitext(file_path)
				self.output_var.set(base + "_converted.mp4")

	def _select_output(self):
		# Handle output file dialog
		file_path = filedialog.asksaveasfilename(
			title="Save Converted File As",
			defaultextension=".mp4",
			filetypes=[("MP4 Video Files", "*.mp4"), ("All Files", "*.*")]
		)
		if file_path:
			self.output_var.set(file_path)

	def _update_status(self, message):
		# Update status bar (thread-safe)
		self.root.after(0, self.status_var.set, message)

	def _show_message(self, title, message, msg_type="info"):
		# Show messagebox (thread-safe)
		if msg_type == "error":
			self.root.after(0, lambda: messagebox.showerror(title, message))
		elif msg_type == "warning":
			self.root.after(0, lambda: messagebox.showwarning(title, message))
		else:
			self.root.after(0, lambda: messagebox.showinfo(title, message))

	def _start_conversion_thread(self):
		# Disable button, start progress
		self.start_button.config(state=tk.DISABLED)
		self.progress_bar.start(10) # Start indeterminate progress
		self._update_status("Starting...")

		# Run conversion in a thread
		conversion_thread = threading.Thread(target=self._run_conversion, daemon=True)
		conversion_thread.start()

	def _run_conversion(self):
		# Core conversion logic
		in_file = self.input_var.get()
		out_file = self.output_var.get()

		# --- Input Validation ---
		if not in_file or not os.path.exists(in_file):
			self._update_status("Error: Input file invalid.")
			self._show_message("Error", "Please select a valid input file.", "error")
			self._reset_gui_state()
			return
		if not out_file:
			self._update_status("Error: Output file not specified.")
			self._show_message("Error", "Please specify an output file path.", "error")
			self._reset_gui_state()
			return

		# Create output directory if needed
		out_dir = os.path.dirname(out_file)
		if out_dir and not os.path.exists(out_dir):
			try:
				os.makedirs(out_dir, exist_ok=True)
			except OSError as e:
				self._update_status(f"Error: Cannot create output directory: {e}")
				self._show_message("Error", f"Failed to create directory:\n{out_dir}\n{e}", "error")
				self._reset_gui_state()
				return

		# --- Build FFmpeg Command ---
		try:
			# Base command
			# -y: overwrite without asking
			# -hide_banner: less verbose
			# -stats: show progress info
			ffmpeg_cmd = [self.ffmpeg_path, "-y", "-hide_banner", "-stats", "-i", in_file]

			# Stream mapping (first video, first audio)
			ffmpeg_cmd.extend(["-map", "0:v:0", "-map", "0:a:0"])

			# Video encoding settings
			if self.has_cuda:
				# Use CUDA NVENC
				# p6: fast preset
				# cq 23: good quality
				# rc vbr: variable bitrate (often better with cq)
				ffmpeg_cmd.extend(["-c:v", "h264_nvenc", "-preset", "p6", "-rc", "vbr", "-cq", "23", "-qmin", "18", "-qmax", "28"])
				self._update_status("Encoding video with CUDA (h264_nvenc)...")
			else:
				# Use CPU x264
				# ultrafast: fastest preset
				# crf 23: good quality
				ffmpeg_cmd.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"])
				self._update_status("Encoding video with CPU (libx264)...")

			# Audio encoding settings
			# aac: target codec
			# b:a 192k: good stereo quality
			ffmpeg_cmd.extend(["-c:a", "aac", "-b:a", "192k"])

			# Pixel format for compatibility
			ffmpeg_cmd.extend(["-pix_fmt", "yuv420p"])

			# Output file
			ffmpeg_cmd.append(out_file)

			# --- Execute FFmpeg ---
			self._update_status(f"Running FFmpeg...") # Command hidden now
			# print(f"Executing: {' '.join(ffmpeg_cmd)}") # DEBUG: Show command

			startupinfo = None
			creationflags = 0
			if os.name == 'nt': # Windows specific settings
				startupinfo = subprocess.STARTUPINFO()
				startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
				startupinfo.wShowWindow = subprocess.SW_HIDE # Hide console
				creationflags = subprocess.CREATE_NO_WINDOW # Another way to hide

			process = subprocess.Popen(
				ffmpeg_cmd,
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT, # Combine stderr with stdout
				text=True,
				encoding='utf-8',
				errors='replace', # Handle encoding issues
				startupinfo=startupinfo,
				creationflags=creationflags
			)

			# Process FFmpeg output line by line (for potential future progress parsing)
			full_output = ""
			while True:
				line = process.stdout.readline()
				if not line and process.poll() is not None:
					break # Process finished
				if line:
					full_output += line
					# Basic status update to show activity
					# More complex parsing needed for real progress %
					if "frame=" in line or "size=" in line:
						# Update status infrequently
						if len(full_output) % 1000 < 100: # Throttle updates
							self._update_status(f"Processing: {line.strip()}")
			
			# Wait for completion and check result
			retcode = process.wait()

			if retcode == 0:
				self._update_status(f"Success: Conversion complete!")
				self._show_message("Success", f"File saved as:\n{out_file}")
			else:
				self._update_status(f"Error: FFmpeg failed (code {retcode}). See logs.")
				# Show last 10 lines of output in message box
				error_summary = "\n".join(full_output.strip().split('\n')[-10:])
				self._show_message("Error", f"FFmpeg conversion failed (code {retcode}).\n\nOutput summary:\n{error_summary}", "error")
				print(f"FFMPEG ERROR:\n{full_output}") # Log full output

		except FileNotFoundError:
			# Should be caught by initial check, but safeguard
			self._update_status("Fatal Error: FFmpeg not found during execution.")
			self._show_message("Error", "FFmpeg executable not found. Please ensure it's installed and in PATH.", "error")
		except Exception as e:
			# Catch unexpected errors
			error_details = str(e)
			self._update_status(f"Error: An unexpected error occurred: {error_details}")
			self._show_message("Error", f"An unexpected error occurred:\n{error_details}", "error")
			print(f"PYTHON ERROR: {e}") # Log Python error
		finally:
			# Always reset GUI state
			self._reset_gui_state()

	def _reset_gui_state(self):
		# Re-enable button, stop progress (thread-safe)
		self.root.after(0, self._do_reset_gui_state)

	def _do_reset_gui_state(self):
		# Actual GUI reset logic
		self.progress_bar.stop()
		self.progress_bar['value'] = 0
		self.start_button.config(state=tk.NORMAL if self.ffmpeg_path else tk.DISABLED)
		# Keep last status message unless it was just 'Starting...'
		if self.status_var.get() == "Starting...":
			self.status_var.set("Ready.")


if __name__ == "__main__":
	root = tk.Tk()
	app = VideoConverterApp(root)
	root.mainloop()
