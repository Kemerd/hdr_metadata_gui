import os
import sys
import platform
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import subprocess
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    messagebox.showerror("Error", "Please install tkinterdnd2 using: pip install tkinterdnd2")
    sys.exit(1)

class HDRVideoProcessor:
    def __init__(self):
        self.root = TkinterDnD.Tk()
        self.root.title("HDR Video Processor")
        self.root.geometry("1280x720")  # Set default window size
        
        # Try to load SF Pro Display font - use tuple format for font
        self.default_font = ("SF Pro Display", 10)
        self.header_font = ("SF Pro Display", 12)
        self.button_font = ("SF Pro Display", 12, "bold")
        
        try:
            # Test if font works
            test_label = tk.Label(self.root, text="", font=self.default_font)
            test_label.destroy()
        except:
            print("[__init__] Could not load SF Pro Display font, falling back to default")
            self.default_font = ("Arial", 10)
            self.header_font = ("Arial", 12)
            self.button_font = ("Arial", 12, "bold")
        
        # Initialize variables
        self.video_path = tk.StringVar()
        self.lut_path = tk.StringVar()
        self.delete_original = tk.BooleanVar()
        self.mkvmerge_path = self._get_mkvmerge_path()
        self.mkvinfo_path = self._get_mkvinfo_path()
        self.delete_original.set(True)  # Set delete original to True by default
        self.show_info = tk.BooleanVar(value=True)  # Add show info option
        self.output_prefix = tk.StringVar()
        self.output_prefix.set("_with_sdr_lut")  # Default prefix
        
        self._setup_ui()
        
    def _get_mkvmerge_path(self):
        """Determine mkvmerge path based on platform"""
        system = platform.system()
        if system == "Windows":
            if platform.machine().endswith('64'):
                return "./windows/64bits/mkvmerge.exe"
            else:
                return "./windows/32bits/mkvmerge.exe"
        else:  # MacOS or Linux
            return "./macos/mkvmerge.app/Contents/MacOS/mkvmerge"
            
    def _get_mkvinfo_path(self):
        """Determine mkvinfo path based on platform"""
        system = platform.system()
        if system == "Windows":
            if platform.machine().endswith('64'):
                return "./windows/64bits/mkvinfo.exe"
            else:
                return "./windows/32bits/mkvinfo.exe"
        else:  # MacOS or Linux
            return "./macos/mkvinfo.app/Contents/MacOS/mkvinfo"

    def _setup_ui(self):
        """Setup the GUI elements"""
        # Enable drag and drop for the main window
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self._handle_drop)
        
        # Video drop zone
        self.video_drop_frame = tk.LabelFrame(self.root, text="Video File", 
                                            width=1200, height=100,
                                            font=self.default_font)
        self.video_drop_frame.pack(pady=10, padx=20, fill='x')
        self.video_drop_frame.pack_propagate(False)  # Maintain fixed size
        self.video_drop_frame.drop_target_register(DND_FILES)
        self.video_drop_frame.dnd_bind('<<Drop>>', self._handle_video_drop)
        
        drop_label = tk.Label(self.video_drop_frame, 
                             text="Drag and drop video file here\nor click to select",
                             font=self.header_font)
        drop_label.pack(expand=True)
        
        # Video path label
        self.video_label = tk.Label(self.root, textvariable=self.video_path, 
                                   wraplength=1100, font=self.default_font)
        self.video_label.pack(pady=5)
        
        # LUT drop zone
        self.lut_drop_frame = tk.LabelFrame(self.root, text="LUT File", 
                                          width=1200, height=100,
                                          font=self.default_font)
        self.lut_drop_frame.pack(pady=10, padx=20, fill='x')
        self.lut_drop_frame.pack_propagate(False)  # Maintain fixed size
        
        lut_drop_label = tk.Label(self.lut_drop_frame, 
                                 text="Drag and drop LUT file here\nor click to select",
                                 font=self.header_font)
        lut_drop_label.pack(expand=True)
        
        # Make the frame clickable
        self.lut_drop_frame.bind("<Button-1>", lambda e: self.browse_lut())
        lut_drop_label.bind("<Button-1>", lambda e: self.browse_lut())
        
        # LUT path label
        self.lut_label = tk.Label(self.root, textvariable=self.lut_path, 
                                 wraplength=1100, font=self.default_font)
        self.lut_label.pack(pady=5)
        
        # Output prefix frame
        prefix_frame = tk.Frame(self.root)
        prefix_frame.pack(pady=5)
        
        tk.Label(prefix_frame, text="Output File Prefix:", 
                 font=self.default_font).pack(side=tk.LEFT, padx=5)
        
        prefix_entry = tk.Entry(prefix_frame, textvariable=self.output_prefix,
                               font=self.default_font, width=30)
        prefix_entry.pack(side=tk.LEFT, padx=5)
        
        # Checkboxes frame for better alignment
        checkbox_frame = tk.Frame(self.root)
        checkbox_frame.pack(pady=5)
        
        # Checkboxes
        tk.Checkbutton(checkbox_frame, text="Show MKVInfo after processing", 
                       variable=self.show_info,
                       font=self.default_font).pack()
        
        tk.Checkbutton(checkbox_frame, text="Prompt to delete original after conversion", 
                       variable=self.delete_original,
                       font=self.default_font).pack()
        
        # Process button
        tk.Button(self.root, text="Process Video",
                  command=self.process_video,
                  font=self.button_font).pack(pady=10)
        
        # Status/Output area
        self.status_frame = tk.LabelFrame(self.root, text="Status & Output", 
                                        font=self.default_font)
        self.status_frame.pack(pady=10, padx=20, fill='both', expand=True)
        
        # Text widget for command output
        self.output_text = tk.Text(self.status_frame, wrap=tk.WORD, 
                                  font=("Consolas", 10), height=10)
        self.output_text.pack(padx=5, pady=5, fill='both', expand=True)
        
        # Add scrollbar
        scrollbar = tk.Scrollbar(self.output_text, command=self.output_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.config(yscrollcommand=scrollbar.set)

    def browse_video(self):
        """Open file dialog for video selection"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Video files", "*.mov;*.mp4"), ("All files", "*.*")]
        )
        if file_path:
            self.video_path.set(file_path)

    def browse_lut(self):
        """Open file dialog for LUT selection"""
        file_path = filedialog.askopenfilename(
            filetypes=[("LUT files", "*.cube"), ("All files", "*.*")]
        )
        if file_path:
            self.lut_path.set(file_path)

    def _log_output(self, message):
        """Add message to output text widget"""
        self.output_text.insert(tk.END, f"{message}\n")
        self.output_text.see(tk.END)  # Auto-scroll to bottom
        self.root.update()  # Force GUI update

    def process_video(self):
        """Process the video with the selected LUT"""
        if not self.video_path.get() or not self.lut_path.get():
            messagebox.showerror("Error", "Please provide both video and LUT files")
            return
            
        input_path = self.video_path.get()
        input_name = Path(input_path).stem
        output_path = str(Path(input_path).parent / f"{input_name}{self.output_prefix.get()}.mkv")
        
        # Build command
        cmd = [
            self.mkvmerge_path,
            '-o', output_path,
            '--attachment-mime-type', 'application/x-cube',
            '--attach-file', self.lut_path.get(),
            input_path
        ]
        
        try:
            # Clear previous output
            self.output_text.delete('1.0', tk.END)
            self._log_output("Starting video processing...")
            self._log_output(f"Command: {' '.join(cmd)}\n")
            
            # Run mkvmerge
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT, text=True)
            
            # Read output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self._log_output(output.strip())
            
            if process.returncode != 0:
                raise Exception("mkvmerge failed")
                
            # Verify output file
            if not self._verify_output(input_path, output_path):
                raise Exception("Output file verification failed")
                
            self._log_output("\nVerification successful!")
            
            # Show MKVInfo if requested
            if self.show_info.get():
                self._show_mkvinfo(output_path)
                
            # Prompt for deletion if enabled
            if self.delete_original.get():
                if messagebox.askyesno("Delete Original", 
                                     "Do you want to delete the original file?"):
                    os.remove(input_path)
                    self._log_output("Original file deleted")
                    
            self._log_output("\nProcessing completed successfully!")
            messagebox.showinfo("Success", "Video processed successfully!")
            
        except Exception as e:
            error_msg = str(e)
            self._log_output(f"\nError: {error_msg}")
            messagebox.showerror("Error", error_msg)

    def _verify_output(self, input_path, output_path):
        """Verify the output file is valid and at least as large as input"""
        if not os.path.exists(output_path):
            return False
            
        input_size = os.path.getsize(input_path)
        output_size = os.path.getsize(output_path)
        
        # Check file size
        if output_size < input_size:
            return False
            
        # Verify with mkvinfo
        try:
            result = subprocess.run([self.mkvinfo_path, output_path], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False

    def _show_mkvinfo(self, file_path):
        """Show MKVInfo output for the processed file"""
        try:
            result = subprocess.run([self.mkvinfo_path, file_path], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                # Create a new window to show the info
                info_window = tk.Toplevel(self.root)
                info_window.title("MKVInfo Output")
                
                text_widget = tk.Text(info_window, wrap=tk.WORD, width=80, height=30)
                text_widget.pack(padx=10, pady=10)
                
                # Insert the mkvinfo output
                text_widget.insert('1.0', result.stdout)
                text_widget.config(state='disabled')
                
                # Add scrollbar
                scrollbar = tk.Scrollbar(info_window, command=text_widget.yview)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                text_widget.config(yscrollcommand=scrollbar.set)
            else:
                raise Exception(f"MKVInfo failed: {result.stderr}")
        except Exception as e:
            messagebox.showerror("MKVInfo Error", str(e))

    def _handle_drop(self, event):
        """Handle files dropped on the main window"""
        files = self.root.tk.splitlist(event.data)
        if not files:
            return
            
        file_path = files[0]
        if file_path.lower().endswith(('.mov', '.mp4')):
            self.video_path.set(file_path)
        elif file_path.lower().endswith('.cube'):
            self.lut_path.set(file_path)

    def _handle_video_drop(self, event):
        """Handle files dropped on video drop zone"""
        files = self.root.tk.splitlist(event.data)
        if files and files[0].lower().endswith(('.mov', '.mp4')):
            self.video_path.set(files[0])

    def _handle_lut_drop(self, event):
        """Handle files dropped on LUT drop zone"""
        files = self.root.tk.splitlist(event.data)
        if files and files[0].lower().endswith('.cube'):
            self.lut_path.set(files[0])

    def run(self):
        """Start the GUI"""
        self.root.mainloop()

if __name__ == "__main__":
    app = HDRVideoProcessor()
    app.run()