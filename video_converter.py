import os
import sys
import time
import subprocess
import threading
import shutil
import tkinter as tk  # For the DnD frame
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

# Support running from PyInstaller bundle
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Adjust paths to ffmpeg and ffprobe relative to bundle
ffmpeg_exe_path = os.path.join(BASE_DIR, "ffmpeg.exe")
ffprobe_exe_path = os.path.join(BASE_DIR, "ffprobe.exe")

FORMATS = ["mp4", "avi", "mkv", "mov", "flv", "webm", "mp3", "wav", "aac", "gif"]
RESOLUTIONS = ["Same as input", "1920x1080", "1280x720", "640x360"]
AUDIO_BITRATES = ["128k", "192k", "256k", "320k"]
VIDEO_BITRATES = ["500k", "1000k", "2000k"]

#---------------------------------------------------------------------
# Build the converter UI as a CTkFrame so that we can attach it
# to a single main TkinterDnD.Tk window.
#---------------------------------------------------------------------
class VideoConverterApp(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master  # reference to the main window
        self.dark_mode = False

        if not self._check_ffmpeg():
            messagebox.showerror("FFmpeg Error", "ffmpeg.exe or ffprobe.exe not found!")
            sys.exit(1)

        self.input_files = []
        self.output_dir = ""
        self.cancel_flag = False
        self.process = None

        # Top Frame
        self.top_frame = ctk.CTkFrame(self, corner_radius=10)
        self.top_frame.pack(pady=10, fill="x")
        self.title_label = ctk.CTkLabel(
            self.top_frame,
            text="Drag & Drop or Browse Files to Convert",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.title_label.pack(side="left", padx=10)
        self.dark_mode_btn = ctk.CTkButton(
            self.top_frame,
            text="Toggle Dark Mode",
            command=self.toggle_theme,
            width=150
        )
        self.dark_mode_btn.pack(side="right", padx=10)

        # DnD Frame (a raw tk.Frame to attach tkdnd)
        self.dnd_parent = tk.Frame(self, bg="#333333")
        self.dnd_parent.pack(pady=5, fill="x", padx=10)
        self.drop_label = ctk.CTkLabel(
            self.dnd_parent,
            text="Drop files here",
            font=ctk.CTkFont(size=14)
        )
        self.drop_label.pack(pady=10)

        # File Info
        self.info_frame = ctk.CTkFrame(self, corner_radius=10)
        self.info_frame.pack(pady=5, fill="x")
        self.file_label = ctk.CTkLabel(
            self.info_frame,
            text="No files selected",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.file_label.pack(pady=5)
        self.browse_button = ctk.CTkButton(
            self.info_frame,
            text="Browse Files",
            command=self.browse_files
        )
        self.browse_button.pack(pady=5)
        self.outdir_button = ctk.CTkButton(
            self.info_frame,
            text="Choose Output Directory",
            command=self.choose_output_directory
        )
        self.outdir_button.pack(pady=5)
        self.outdir_label = ctk.CTkLabel(
            self.info_frame,
            text="(Same as input by default)",
            text_color="gray"
        )
        self.outdir_label.pack(pady=5)

        # Options
        self.options_frame = ctk.CTkFrame(self, corner_radius=10)
        self.options_frame.pack(pady=5, fill="x")
        # Format
        self.format_label = ctk.CTkLabel(self.options_frame, text="Output Format:")
        self.format_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.format_var = ctk.StringVar(value=FORMATS[0])
        self.format_combo = ctk.CTkComboBox(
            self.options_frame,
            values=FORMATS,
            variable=self.format_var,
            width=140
        )
        self.format_combo.grid(row=0, column=1, padx=5, pady=5)
        # Resolution
        self.res_label = ctk.CTkLabel(self.options_frame, text="Resolution:")
        self.res_label.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.res_var = ctk.StringVar(value=RESOLUTIONS[0])
        self.res_combo = ctk.CTkComboBox(
            self.options_frame,
            values=RESOLUTIONS,
            variable=self.res_var,
            width=140
        )
        self.res_combo.grid(row=0, column=3, padx=5, pady=5)
        # Audio Bitrate
        self.aud_label = ctk.CTkLabel(self.options_frame, text="Audio Bitrate:")
        self.aud_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.aud_bitrate_var = ctk.StringVar(value=AUDIO_BITRATES[0])
        self.aud_bitrate_combo = ctk.CTkComboBox(
            self.options_frame,
            values=AUDIO_BITRATES,
            variable=self.aud_bitrate_var,
            width=140
        )
        self.aud_bitrate_combo.grid(row=1, column=1, padx=5, pady=5)
        # Video Bitrate
        self.vid_label = ctk.CTkLabel(self.options_frame, text="Video Bitrate:")
        self.vid_label.grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.vid_bitrate_var = ctk.StringVar(value=VIDEO_BITRATES[1])
        self.vid_bitrate_combo = ctk.CTkComboBox(
            self.options_frame,
            values=VIDEO_BITRATES,
            variable=self.vid_bitrate_var,
            width=140
        )
        self.vid_bitrate_combo.grid(row=1, column=3, padx=5, pady=5)

        # Buttons
        self.button_frame = ctk.CTkFrame(self, corner_radius=10)
        self.button_frame.pack(pady=5, fill="x")
        self.convert_button = ctk.CTkButton(
            self.button_frame,
            text="Convert",
            command=self.start_conversion_thread,
            fg_color="#2196F3",
            width=140
        )
        self.convert_button.grid(row=0, column=0, padx=10, pady=10)
        self.cancel_button = ctk.CTkButton(
            self.button_frame,
            text="Cancel",
            command=self.cancel_conversion,
            fg_color="#f44336",
            width=140
        )
        self.cancel_button.grid(row=0, column=1, padx=10, pady=10)
        self.thumb_button = ctk.CTkButton(
            self.button_frame,
            text="Generate Thumbnail (2s)",
            command=self.generate_thumbnail,
            fg_color="#9C27B0",
            width=200
        )
        self.thumb_button.grid(row=0, column=2, padx=10, pady=10)

        # Progress
        self.progress_bar = ctk.CTkProgressBar(self, orientation="horizontal", width=600)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10)
        self.time_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=14))
        self.time_label.pack()
        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=14))
        self.status_label.pack()

        # Console
        self.console_frame = ctk.CTkFrame(self, corner_radius=10)
        self.console_frame.pack(pady=5, fill="both", expand=True)
        self.console_textbox = ctk.CTkTextbox(self.console_frame, width=800, height=200)
        self.console_textbox.pack(fill="both", expand=True)

        # Finally, enable drag and drop on the dnd frame
        self._enable_dnd()

    def set_theme(self):
        if self.dark_mode:
            ctk.set_appearance_mode("dark")
        else:
            ctk.set_appearance_mode("light")

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.set_theme()
        # ✅ Update the button text based on new mode
        if self.dark_mode:
            self.dark_mode_btn.configure(text="Toggle Light Mode")
        else:
            self.dark_mode_btn.configure(text="Toggle Dark Mode")

    def _enable_dnd(self):
        from tkinterdnd2 import DND_FILES
        self.dnd_parent.drop_target_register(DND_FILES)
        self.dnd_parent.dnd_bind('<<Drop>>', self._drop_event)

    def _drop_event(self, event):
        data = self.dnd_parent.tk.splitlist(event.data)
        if data:
            self.input_files = list(data)
            self.file_label.configure(text=f"{len(self.input_files)} file(s) selected", text_color="white")

    def browse_files(self):
        filetypes = [
            ("Video files", "*.mp4 *.avi *.mkv *.mov *.flv *.webm"),
            ("All files", "*.*")
        ]
        files = filedialog.askopenfilenames(title="Select video files", filetypes=filetypes)
        if files:
            self.input_files = list(files)
            self.file_label.configure(text=f"{len(self.input_files)} file(s) selected", text_color="white")

    def choose_output_directory(self):
        folder = filedialog.askdirectory(title="Choose Output Directory")
        if folder:
            self.output_dir = folder
            self.outdir_label.configure(text=f"Output Directory: {folder}", text_color="white")
        else:
            self.output_dir = ""

    def generate_thumbnail(self):
        if not self.input_files:
            messagebox.showerror("Error", "No file selected.")
            return
        input_file = self.input_files[0]
        base = os.path.splitext(input_file)[0]
        thumb_file = base + "_thumb.jpg"
        cmd = [
            ffmpeg_exe_path,
            "-i", input_file,
            "-ss", "00:00:02.000",
            "-frames:v", "1",
            "-update", "1",
            "-y", thumb_file
        ]
        try:
            subprocess.run(cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self._log(f"Thumbnail generated: {thumb_file}")
            messagebox.showinfo("Success", f"Thumbnail saved:\n{thumb_file}")
            try:
                os.startfile(thumb_file)
            except Exception as e:
                self._log(f"Failed to open thumbnail: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate thumbnail:\n{str(e)}")

    def start_conversion_thread(self):
        if not self.input_files:
            messagebox.showerror("Error", "No files selected.")
            return
        t = threading.Thread(target=self.convert_videos)
        t.start()

    def convert_videos(self):
        if not self.output_dir:
            self.output_dir = os.path.dirname(self.input_files[0])
        for f in self.input_files:
            self.convert_single_video(f)
        # After all conversions, open the destination folder
        if self.output_dir:
            try:
                os.startfile(self.output_dir)
            except Exception as e:
                self._log(f"Could not open destination folder: {e}")

    def convert_single_video(self, input_file):
        output_format = self.format_var.get()
        resolution = self.res_var.get()
        aud_br = self.aud_bitrate_var.get()
        vid_br = self.vid_bitrate_var.get()
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(self.output_dir, f"{base_name}_converted.{output_format}")
        # Handle audio extraction or GIF conversion separately
        if output_format.lower() in ["mp3", "wav", "aac"]:
            self._extract_audio(input_file, output_file, output_format.lower())
            return
        if output_format.lower() == "gif":
            self._convert_gif(input_file, output_file)
            return
        total_duration = self._get_duration(input_file)
        if total_duration <= 0:
            self._log(f"Cannot get duration for {input_file}. Skipping.")
            return
        self._log(f"Converting {input_file} to {output_format} ...")
        self.progress_bar.set(0)
        self.cancel_flag = False
        cmd = [
            ffmpeg_exe_path,
            "-progress", "pipe:1",
            "-nostats",
            "-i", input_file
        ]
        if resolution != "Same as input":
            try:
                w, h = resolution.split("x")
                cmd.extend(["-vf", f"scale={w}:{h}"])
            except Exception:
                pass
        cmd.extend(["-c:v", "libx264", "-c:a", "aac", "-b:v", vid_br, "-b:a", aud_br, "-y", output_file])
        start_time = time.time()
        self._run_ffmpeg_command(cmd, total_duration, start_time, output_file)

    def cancel_conversion(self):
        if self.process:
            self.cancel_flag = True
            self.process.terminate()
            self._log("Conversion cancelled by user.")

    def _extract_audio(self, infile, outfile, fmt):
        total_duration = self._get_duration(infile)
        if fmt == "mp3":
            acodec = "libmp3lame"
        elif fmt == "wav":
            acodec = "pcm_s16le"
        else:
            acodec = "aac"
        cmd = [
            ffmpeg_exe_path,
            "-progress", "pipe:1",
            "-nostats",
            "-i", infile,
            "-vn",
            "-acodec", acodec,
            "-q:a", "2",
            "-y", outfile
        ]
        self._log(f"Extracting audio from {infile} ...")
        start_time = time.time()
        self._run_ffmpeg_command(cmd, total_duration, start_time, outfile)

    def _convert_gif(self, infile, outfile):
        total_duration = self._get_duration(infile)
        cmd = [
            ffmpeg_exe_path,
            "-progress", "pipe:1",
            "-nostats",
            "-i", infile,
            "-vf", "fps=10,scale=320:-1:flags=lanczos",
            "-y", outfile
        ]
        self._log(f"Converting {infile} -> GIF ...")
        start_time = time.time()
        self._run_ffmpeg_command(cmd, total_duration, start_time, outfile)

    def _run_ffmpeg_command(self, cmd, total_duration, start_time, output_file):
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        last_elapsed = 0
        while True:
            line = self.process.stdout.readline()
            if not line:
                break
            line = line.strip()
            self._log(line)
            if self.cancel_flag:
                self.process.terminate()
                self._log("Conversion cancelled by user.")
                return
            if "=" in line:
                key, value = line.split("=", 1)
                if key == "out_time_ms":
                    try:
                        last_elapsed = float(value) / 1_000_000.0
                    except Exception:
                        last_elapsed = 0
                elif key == "out_time":
                    last_elapsed = self._parse_time_str(value)
                elif key == "progress" and value == "end":
                    break
            if total_duration > 0:
                pct = min(last_elapsed / total_duration, 1)
                self.progress_bar.set(pct)
                remain = max(total_duration - last_elapsed, 0)
                self.time_label.configure(text=f"Remaining: {int(remain)}s")
            self.update_idletasks()
        self.process.wait()
        elapsed_time = int(time.time() - start_time)
        if self.process.returncode == 0:
            self.progress_bar.set(1)
            size_mb = 0
            if os.path.exists(output_file):
                size_mb = os.path.getsize(output_file) / (1024 * 1024)
            self._log(f"Done: {output_file} | {size_mb:.2f}MB in {elapsed_time}s")
        else:
            self._log("Conversion failed!")
            self.time_label.configure(text="")

    def _get_duration(self, path):
        cmd = [
            ffprobe_exe_path, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return float(res.stdout.strip())
        except Exception:
            return 0

    def _parse_time_str(self, time_str):
        try:
            h, m, s = time_str.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
        except Exception:
            return 0

    def _log(self, msg):
        self.console_textbox.insert("end", msg + "\n")
        self.console_textbox.see("end")

    def _check_ffmpeg(self):
        if not shutil.which(ffmpeg_exe_path) and not os.path.exists(ffmpeg_exe_path):
            return False
        if not shutil.which(ffprobe_exe_path) and not os.path.exists(ffprobe_exe_path):
            return False
        return True

#---------------------------------------------------------------------
# Main Application using TkinterDnD.Tk as the root window.
#---------------------------------------------------------------------
if __name__ == "__main__":
    from tkinterdnd2 import TkinterDnD

    class DnDApp(TkinterDnD.Tk):
        def __init__(self):
            TkinterDnD.Tk.__init__(self)
            self.title("VidCraft")
            self.geometry("900x720")
            self.icon_path = os.path.join(BASE_DIR, "icon.ico")
            self.iconbitmap(self.icon_path)

            # Get proper base directory
            if getattr(sys, 'frozen', False):
                base_dir = sys._MEIPASS
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            # Path to tkdnd2.8 directory
            tkdnd_dir = os.path.join(base_dir, "tkdnd2.8")
            try:
                # Add DLL folder to system PATH (for Windows DLL loader)
                os.environ["PATH"] += os.pathsep + tkdnd_dir
                # Tell Tcl where to find the tkdnd package
                self.tk.eval(f'lappend auto_path {{{tkdnd_dir}}}')
                self.tk.eval('package require tkdnd 2.9')
            except Exception as e:
                messagebox.showerror("TkDND Load Error",
                                     f"Failed to load tkdnd:\n{e}\nChecked in: {tkdnd_dir}")
                sys.exit(1)
            # Create the converter frame and pack it into the root window.
            self.app_frame = VideoConverterApp(self)
            self.app_frame.pack(fill="both", expand=True)

    app = DnDApp()
    app.mainloop()
