import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import threading
import os
import shutil
import queue

class VideoConverterApp:
	def __init__(self, root_window):
		self.root = root_window
		self.root.title("Video Converter")
		self.root.geometry("600x300") # Initial size

		self.ffmpeg_path = self._find_ffmpeg()
		self.has_cuda = self._check_cuda_support() if self.ffmpeg_path else False

		self.input_var = tk.StringVar()
		self.output_var = tk.StringVar()
		self.status_var = tk.StringVar()
		self.status_var.set("Ready. Select files.")

		self._create_widgets()

		# Initial status based on FFmpeg/CUDA check
		if not self.ffmpeg_path:
			self.status_var.set("Error: FFmpeg not found in PATH.")
			messagebox.showerror("Setup Error", "FFmpeg not found. Please install it and add to PATH.")
			self.start_button.config(state=tk.DISABLED)
		elif self.has_cuda:
			self.status_var.set("Ready (CUDA available).")
		else:
			self.status_var.set("Ready (CUDA not found, using CPU).")


	def _find_ffmpeg(self):
		# Find ffmpeg exec
		return shutil.which("ffmpeg")

	def _check_cuda_support(self):
		# Check nvenc
		try:
			startupinfo = None
			if os.name == 'nt': # Hide console on Win
				startupinfo = subprocess.STARTUPINFO()
				startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
				startupinfo.wShowWindow = subprocess.SW_HIDE

			result = subprocess.run(
				[self.ffmpeg_path, "-encoders"],
				capture_output=True, text=True, check=True,
				encoding='utf-8', errors='ignore', # Handle potential decode errors
				startupinfo=startupinfo
			)
			return "h264_nvenc" in result.stdout
		except (subprocess.CalledProcessError, FileNotFoundError, OSError):
			return False # FFmpeg error

	def _create_widgets(self):
		# Create GUI elements
		main_frame = ttk.Frame(self.root, padding="10")
		main_frame.pack(fill=tk.BOTH, expand=True)

		# Input selection
		input_frame = ttk.Frame(main_frame)
		input_frame.pack(fill=tk.X, pady=5)
		ttk.Label(input_frame, text="Input File:").pack(side=tk.LEFT, padx=(0, 5))
		ttk.Entry(input_frame, textvariable=self.input_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
		ttk.Button(input_frame, text="Browse...", command=self._select_input).pack(side=tk.LEFT, padx=(5, 0))

		# Output selection
		output_frame = ttk.Frame(main_frame)
		output_frame.pack(fill=tk.X, pady=5)
		ttk.Label(output_frame, text="Output File:").pack(side=tk.LEFT, padx=(0, 5))
		ttk.Entry(output_frame, textvariable=self.output_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
		ttk.Button(output_frame, text="Browse...", command=self._select_output).pack(side=tk.LEFT, padx=(5, 0))

		# Start button
		self.start_button = ttk.Button(main_frame, text="Start Conversion", command=self._start_conversion_thread)
		self.start_button.pack(pady=15)

		# Progress bar
		self.progress_bar = ttk.Progressbar(main_frame, mode='indeterminate')
		self.progress_bar.pack(fill=tk.X, pady=5)

		# Status bar
		status_label = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
		status_label.pack(fill=tk.X, pady=(10, 0), ipady=2)

	def _select_input(self):
		# Open input dialog
		file_path = filedialog.askopenfilename(
			title="Select Input HEVC Video",
			filetypes=[("HEVC Video Files", "*.mkv *.mp4 *.mov"), ("All Files", "*.*")]
		)
		if file_path:
			self.input_var.set(file_path)
			# Suggest output name
			if not self.output_var.get():
				base, _ = os.path.splitext(file_path)
				self.output_var.set(base + "_converted.mp4")

	def _select_output(self):
		# Open output dialog
		file_path = filedialog.asksaveasfilename(
			title="Save Converted File As",
			defaultextension=".mp4",
			filetypes=[("MP4 Video Files", "*.mp4"), ("All Files", "*.*")]
		)
		if file_path:
			self.output_var.set(file_path)

	def _update_status(self, message):
		# Update status bar
		self.root.after(0, self.status_var.set, message)

	def _show_message(self, title, message, msg_type="info"):
		# Show popup message
		if msg_type == "error":
			self.root.after(0, lambda: messagebox.showerror(title, message))
		elif msg_type == "warning":
			self.root.after(0, lambda: messagebox.showwarning(title, message))
		else:
			self.root.after(0, lambda: messagebox.showinfo(title, message))

	def _start_conversion_thread(self):
		# Disable button, start progress
		self.start_button.config(state=tk.DISABLED)
		self.progress_bar.start(10) # indeterminate speed
		self._update_status("Starting...")

		# Run ffmpeg in thread
		conversion_thread = threading.Thread(target=self._run_conversion, daemon=True)
		conversion_thread.start()

	def _run_conversion(self):
		# FFmpeg logic
		in_file = self.input_var.get()
		out_file = self.output_var.get()

		# Validate inputs
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

		# Ensure output dir exists
		out_dir = os.path.dirname(out_file)
		if out_dir and not os.path.exists(out_dir):
			try:
				os.makedirs(out_dir, exist_ok=True)
			except OSError as e:
				self._update_status(f"Error: Cannot create output directory: {e}")
				self._show_message("Error", f"Failed to create directory:\n{out_dir}\n{e}", "error")
				self._reset_gui_state()
				return

		# Run FFmpeg process
		try:
			# Base command
			# -y: overwrite output
			# -hide_banner: less verbose
			# -stats: show progress
			ffmpeg_cmd = [self.ffmpeg_path, "-y", "-hide_banner", "-stats", "-i", in_file]

			# Map streams (simple case: 1st video, 1st audio)
			ffmpeg_cmd.extend(["-map", "0:v:0", "-map", "0:a:0"])

			# Video codec options
			if self.has_cuda:
				# Use NVENC H.264
				# p6: slower preset = better quality
				# rc vbr: variable bitrate mode
				# cq 23: quality level (lower=better)
				# qmin/qmax: quality range
				ffmpeg_cmd.extend(["-c:v", "h264_nvenc", "-preset", "p6", "-rc", "vbr", "-cq", "23", "-qmin", "18", "-qmax", "28"])
				self._update_status("Encoding video with CUDA (h264_nvenc)...")
			else:
				# Use libx264 (CPU)
				# preset ultrafast: fastest speed
				# crf 23: quality level (lower=better)
				ffmpeg_cmd.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"])
				self._update_status("Encoding video with CPU (libx264)...")

			# Audio codec options
			# c:a aac: AAC codec
			# b:a 320k: High CBR
			ffmpeg_cmd.extend(["-c:a", "aac", "-b:a", "320k"]) # Set high quality CBR

			# Pixel format (compatibility)
			ffmpeg_cmd.extend(["-pix_fmt", "yuv420p"])

			# Output file
			ffmpeg_cmd.append(out_file)

			# Execute command
			self._update_status(f"Running FFmpeg...") # Final status before run


			startupinfo = None
			creationflags = 0
			if os.name == 'nt': # Hide console window on Windows
				startupinfo = subprocess.STARTUPINFO()
				startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
				startupinfo.wShowWindow = subprocess.SW_HIDE # Hide the window
				creationflags = subprocess.CREATE_NO_WINDOW # No console either

			process = subprocess.Popen(
				ffmpeg_cmd,
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT, # Redirect stderr to stdout
				text=True,
				encoding='utf-8',
				errors='replace', # Handle weird chars from ffmpeg
				startupinfo=startupinfo,
				creationflags=creationflags
			)

			# Read output line by line
			full_output = ""
			while True:
				line = process.stdout.readline()
				if not line and process.poll() is not None:
					break # Process finished
				if line:
					full_output += line
					# Update status sparsely with progress lines
					# Avoid flooding TK mainloop
					if "frame=" in line or "size=" in line:
						# Only update UI occasionally
						if len(full_output) % 1000 < 100: # Simple throttle
							self._update_status(f"Processing: {line.strip()}")
			# Wait for process completion
			retcode = process.wait()

			if retcode == 0:
				self._update_status(f"Success: Conversion complete!")
				self._show_message("Success", f"File saved as:\n{out_file}")
			else:
				self._update_status(f"Error: FFmpeg failed (code {retcode}). See logs.")
				# Show last few lines of output in message box
				error_summary = "\n".join(full_output.strip().split('\n')[-10:])
				self._show_message("Error", f"FFmpeg conversion failed (code {retcode}).\n\nOutput summary:\n{error_summary}", "error")
				print(f"FFMPEG ERROR:\n{full_output}") # Log full output

		except FileNotFoundError:
			# Handle case where ffmpeg disappears mid-run
			self._update_status("Fatal Error: FFmpeg not found during execution.")
			self._show_message("Error", "FFmpeg executable not found. Please ensure it's installed and in PATH.", "error")
		except Exception as e:
			# Catch-all for other errors
			error_details = str(e)
			self._update_status(f"Error: An unexpected error occurred: {error_details}")
			self._show_message("Error", f"An unexpected error occurred:\n{error_details}", "error")
			print(f"PYTHON ERROR: {e}") # Log Python error
		finally:
			# Always reset GUI state
			self._reset_gui_state()

	def _reset_gui_state(self):
		# Reset UI elements (thread-safe)
		self.root.after(0, self._do_reset_gui_state)

	def _do_reset_gui_state(self):
		# Actual GUI updates
		self.progress_bar.stop()
		self.progress_bar['value'] = 0
		self.start_button.config(state=tk.NORMAL if self.ffmpeg_path else tk.DISABLED)
		# Reset status if it was left at "Starting..."
		if self.status_var.get() == "Starting...":
			self.status_var.set("Ready.")


if __name__ == "__main__":
	root = tk.Tk()
	app = VideoConverterApp(root)
	root.mainloop()
