import os
import sys
import platform
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import subprocess
import threading
from send2trash import send2trash
import configparser
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    messagebox.showerror("Error", "Please install tkinterdnd2 using: pip install tkinterdnd2")
    sys.exit(1)

class ConfigHandler:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config_file = 'settings.ini'
        self.load_config()

    def load_config(self):
        # Default values
        self.last_video_path = ''
        self.last_lut_path = ''
        self.show_info = True
        self.delete_original = True
        self.save_video_path = True
        self.save_lut_path = True
        self.output_prefix = '_with_sdr_lut'  # Default prefix

        # ------------------------------------------------------------------
        # HDR tagging defaults (tuned for DJI Osmo Pocket 3 HDR @ Rec.2100 HLG)
        # ------------------------------------------------------------------
        # The Pocket 3 records HDR in HLG (Hybrid Log-Gamma, ARIB STD-B67),
        # NOT PQ. So transfer=18 is the correct default. HLG is scene-referred
        # and does not require mastering-display metadata — leaving MaxCLL,
        # MaxFALL, chromaticity, white point, and luminance fields blank is
        # what YouTube expects for clean HLG detection. They're still exposed
        # in the UI so the user can switch the panel to PQ (transfer=16) and
        # fill them in for PQ workflows like Sony A7S III, iPhone Dolby Vision
        # rewraps, etc.
        # ------------------------------------------------------------------
        self.tag_hdr = True                              # master enable/disable
        self.hdr_colour_matrix = '9'                     # 9 = BT.2020 non-constant luma
        self.hdr_colour_range = '1'                      # 1 = broadcast/limited range
        self.hdr_transfer = '18'                         # 18 = HLG (Pocket 3); 16 = PQ/ST2084
        self.hdr_primaries = '9'                         # 9 = BT.2020 primaries
        # Mastering-display fields: blank by default for HLG — fill in only
        # when switching to a PQ workflow.
        self.hdr_max_cll = ''                            # MaxCLL in cd/m^2 (PQ only)
        self.hdr_max_fall = ''                           # MaxFALL in cd/m^2 (PQ only)
        self.hdr_chromaticity = ''                       # red/green/blue x,y (PQ only)
        self.hdr_white_point = ''                        # D65 white point (PQ only)
        self.hdr_max_luminance = ''                      # mastering peak nits (PQ only)
        self.hdr_min_luminance = ''                      # mastering black floor (PQ only)

        # Create config file if it doesn't exist
        if not os.path.exists(self.config_file):
            self.save_config()
            return

        try:
            self.config.read(self.config_file)
            if 'Paths' in self.config:
                self.last_video_path = self.config['Paths'].get('last_video_path', '')
                self.last_lut_path = self.config['Paths'].get('last_lut_path', '')
            if 'Preferences' in self.config:
                self.show_info = self.config['Preferences'].getboolean('show_info', True)
                self.delete_original = self.config['Preferences'].getboolean('delete_original', True)
                self.save_video_path = self.config['Preferences'].getboolean('save_video_path', True)
                self.save_lut_path = self.config['Preferences'].getboolean('save_lut_path', True)
                self.output_prefix = self.config['Preferences'].get('output_prefix', '_with_sdr_lut')
            # Pull HDR section — fall back to Pocket 3 defaults if missing so
            # existing settings.ini files from earlier versions still load.
            if 'HDR' in self.config:
                self.tag_hdr = self.config['HDR'].getboolean('tag_hdr', True)
                self.hdr_colour_matrix = self.config['HDR'].get('colour_matrix', self.hdr_colour_matrix)
                self.hdr_colour_range = self.config['HDR'].get('colour_range', self.hdr_colour_range)
                self.hdr_transfer = self.config['HDR'].get('transfer', self.hdr_transfer)
                self.hdr_primaries = self.config['HDR'].get('primaries', self.hdr_primaries)
                self.hdr_max_cll = self.config['HDR'].get('max_cll', self.hdr_max_cll)
                self.hdr_max_fall = self.config['HDR'].get('max_fall', self.hdr_max_fall)
                self.hdr_chromaticity = self.config['HDR'].get('chromaticity', self.hdr_chromaticity)
                self.hdr_white_point = self.config['HDR'].get('white_point', self.hdr_white_point)
                self.hdr_max_luminance = self.config['HDR'].get('max_luminance', self.hdr_max_luminance)
                self.hdr_min_luminance = self.config['HDR'].get('min_luminance', self.hdr_min_luminance)
        except Exception as e:
            print(f'[ConfigHandler.load_config] Error loading config: {str(e)}')

    def save_config(self):
        if not 'Paths' in self.config:
            self.config['Paths'] = {}
        if not 'Preferences' in self.config:
            self.config['Preferences'] = {}
        if not 'HDR' in self.config:
            self.config['HDR'] = {}

        # Save paths
        self.config['Paths']['last_video_path'] = self.last_video_path
        self.config['Paths']['last_lut_path'] = self.last_lut_path

        # Save preferences
        self.config['Preferences']['show_info'] = str(self.show_info)
        self.config['Preferences']['delete_original'] = str(self.delete_original)
        self.config['Preferences']['save_video_path'] = str(self.save_video_path)
        self.config['Preferences']['save_lut_path'] = str(self.save_lut_path)
        self.config['Preferences']['output_prefix'] = self.output_prefix

        # Save HDR section — every flag the user can tweak so a relaunch
        # restores their exact Pocket 3 / custom HDR profile.
        self.config['HDR']['tag_hdr'] = str(self.tag_hdr)
        self.config['HDR']['colour_matrix'] = self.hdr_colour_matrix
        self.config['HDR']['colour_range'] = self.hdr_colour_range
        self.config['HDR']['transfer'] = self.hdr_transfer
        self.config['HDR']['primaries'] = self.hdr_primaries
        self.config['HDR']['max_cll'] = self.hdr_max_cll
        self.config['HDR']['max_fall'] = self.hdr_max_fall
        self.config['HDR']['chromaticity'] = self.hdr_chromaticity
        self.config['HDR']['white_point'] = self.hdr_white_point
        self.config['HDR']['max_luminance'] = self.hdr_max_luminance
        self.config['HDR']['min_luminance'] = self.hdr_min_luminance

        try:
            with open(self.config_file, 'w') as configfile:
                self.config.write(configfile)
        except Exception as e:
            print(f'[ConfigHandler.save_config] Error saving config: {str(e)}')

    def update_preferences(self, show_info, delete_original, save_video_path, save_lut_path, output_prefix):
        self.show_info = show_info
        self.delete_original = delete_original
        self.save_video_path = save_video_path
        self.save_lut_path = save_lut_path
        self.output_prefix = output_prefix
        self.save_config()

    def update_hdr(self, tag_hdr, colour_matrix, colour_range, transfer, primaries,
                   max_cll, max_fall, chromaticity, white_point,
                   max_luminance, min_luminance):
        """Persist the HDR tagging block to disk."""
        # Stored as raw strings to keep parity with mkvmerge's CLI expectations.
        self.tag_hdr = tag_hdr
        self.hdr_colour_matrix = colour_matrix
        self.hdr_colour_range = colour_range
        self.hdr_transfer = transfer
        self.hdr_primaries = primaries
        self.hdr_max_cll = max_cll
        self.hdr_max_fall = max_fall
        self.hdr_chromaticity = chromaticity
        self.hdr_white_point = white_point
        self.hdr_max_luminance = max_luminance
        self.hdr_min_luminance = min_luminance
        self.save_config()

    def update_video_path(self, path):
        """Update the last video path"""
        self.last_video_path = path
        self.save_config()

    def update_lut_path(self, path):
        """Update the last LUT path"""
        self.last_lut_path = path
        self.save_config()

# ----------------------------------------------------------------------------
# HDR preset table.
# ----------------------------------------------------------------------------
# Each preset maps a friendly camera/format label to a dict of the mkvmerge
# colour/light/mastering values we feed into the command. Empty strings mean
# "do not emit this flag", which matters for HLG presets that don't carry
# mastering-display metadata.
#
# Display:Transfer codes (per CTA / ITU specs that mkvmerge mirrors):
#   1  = BT.709          (SDR)
#   16 = SMPTE ST 2084   (PQ / HDR10)
#   18 = ARIB STD-B67    (HLG)
# Primaries / Matrix codes:
#   1  = BT.709
#   9  = BT.2020
# Range:
#   1  = limited / broadcast (TV)
#   2  = full / PC
# ----------------------------------------------------------------------------
HDR_PRESETS = {
    # ---- HLG family (no mastering-display metadata needed) ----------------
    'DJI Osmo Pocket 3 (HLG)': {
        'colour_matrix': '9', 'colour_range': '1', 'transfer': '18', 'primaries': '9',
        'max_cll': '', 'max_fall': '', 'chromaticity': '', 'white_point': '',
        'max_luminance': '', 'min_luminance': '',
    },
    'DJI Mavic / Air / Mini (HLG)': {
        'colour_matrix': '9', 'colour_range': '1', 'transfer': '18', 'primaries': '9',
        'max_cll': '', 'max_fall': '', 'chromaticity': '', 'white_point': '',
        'max_luminance': '', 'min_luminance': '',
    },
    'Sony HLG (a7S III / FX3 / FX6)': {
        'colour_matrix': '9', 'colour_range': '1', 'transfer': '18', 'primaries': '9',
        'max_cll': '', 'max_fall': '', 'chromaticity': '', 'white_point': '',
        'max_luminance': '', 'min_luminance': '',
    },
    'Panasonic HLG (GH5/GH6/S5)': {
        'colour_matrix': '9', 'colour_range': '1', 'transfer': '18', 'primaries': '9',
        'max_cll': '', 'max_fall': '', 'chromaticity': '', 'white_point': '',
        'max_luminance': '', 'min_luminance': '',
    },
    'Generic Rec.2100 HLG': {
        'colour_matrix': '9', 'colour_range': '1', 'transfer': '18', 'primaries': '9',
        'max_cll': '', 'max_fall': '', 'chromaticity': '', 'white_point': '',
        'max_luminance': '', 'min_luminance': '',
    },
    # ---- PQ / HDR10 family (mastering metadata required) ------------------
    # Standard Rec.2020 primaries are encoded as the six chromaticity coords
    # below in R,G,B x,y order. D65 white point is 0.3127,0.329.
    'iPhone Dolby Vision / HDR10 (PQ)': {
        'colour_matrix': '9', 'colour_range': '1', 'transfer': '16', 'primaries': '9',
        'max_cll': '1000', 'max_fall': '400',
        'chromaticity': '0.708,0.292,0.170,0.797,0.131,0.046',
        'white_point': '0.3127,0.329',
        'max_luminance': '1000', 'min_luminance': '0.0001',
    },
    'Sony HDR10 (PQ)': {
        'colour_matrix': '9', 'colour_range': '1', 'transfer': '16', 'primaries': '9',
        'max_cll': '1000', 'max_fall': '400',
        'chromaticity': '0.708,0.292,0.170,0.797,0.131,0.046',
        'white_point': '0.3127,0.329',
        'max_luminance': '1000', 'min_luminance': '0.0001',
    },
    'Generic Rec.2100 PQ / HDR10 (1000 nits)': {
        'colour_matrix': '9', 'colour_range': '1', 'transfer': '16', 'primaries': '9',
        'max_cll': '1000', 'max_fall': '400',
        'chromaticity': '0.708,0.292,0.170,0.797,0.131,0.046',
        'white_point': '0.3127,0.329',
        'max_luminance': '1000', 'min_luminance': '0.0001',
    },
    'Generic Rec.2100 PQ / HDR10 (4000 nits)': {
        'colour_matrix': '9', 'colour_range': '1', 'transfer': '16', 'primaries': '9',
        'max_cll': '4000', 'max_fall': '1000',
        'chromaticity': '0.708,0.292,0.170,0.797,0.131,0.046',
        'white_point': '0.3127,0.329',
        'max_luminance': '4000', 'min_luminance': '0.0001',
    },
    # ---- SDR ---------------------------------------------------------------
    'SDR Rec.709 (no HDR)': {
        'colour_matrix': '1', 'colour_range': '1', 'transfer': '1', 'primaries': '1',
        'max_cll': '', 'max_fall': '', 'chromaticity': '', 'white_point': '',
        'max_luminance': '', 'min_luminance': '',
    },
    # ---- Custom (left as a sentinel; selecting it does nothing) -----------
    'Custom (manual)': None,
}

# Dropdown options for the individual enum fields. Pairs of (display_label,
# raw_value) — the raw value is what gets written into the StringVar / passed
# to mkvmerge. Using a Combobox in 'readonly' mode prevents typos.
HDR_MATRIX_OPTIONS = [
    ('1 - BT.709',  '1'),
    ('9 - BT.2020 non-constant', '9'),
    ('10 - BT.2020 constant',    '10'),
    ('0 - Identity / RGB',       '0'),
]
HDR_RANGE_OPTIONS = [
    ('1 - Limited / Broadcast', '1'),
    ('2 - Full / PC',           '2'),
    ('0 - Unspecified',         '0'),
]
HDR_TRANSFER_OPTIONS = [
    ('1 - BT.709 (SDR)',                '1'),
    ('16 - SMPTE ST 2084 (PQ / HDR10)', '16'),
    ('18 - ARIB STD-B67 (HLG)',         '18'),
    ('6 - SMPTE 170M (NTSC)',           '6'),
    ('14 - BT.2020 10-bit',             '14'),
    ('15 - BT.2020 12-bit',             '15'),
]
HDR_PRIMARIES_OPTIONS = [
    ('1 - BT.709',           '1'),
    ('9 - BT.2020',          '9'),
    ('11 - DCI P3',          '11'),
    ('12 - Display P3 / D65','12'),
]


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
        self.save_video_path = tk.BooleanVar(value=True)  # Default to True
        self.save_lut_path = tk.BooleanVar(value=True)    # Default to True
        self.config = ConfigHandler()  # Load configuration
        self.output_prefix = tk.StringVar(value=self.config.output_prefix)

        # Initialize variables with saved preferences
        self.delete_original = tk.BooleanVar(value=self.config.delete_original)
        self.show_info = tk.BooleanVar(value=self.config.show_info)
        self.save_video_path = tk.BooleanVar(value=self.config.save_video_path)
        self.save_lut_path = tk.BooleanVar(value=self.config.save_lut_path)

        # ------------------------------------------------------------------
        # HDR tagging Tk variables — bound to the HDR settings panel.
        # All defaults come from ConfigHandler (which preloads Osmo Pocket 3
        # values), so a first-run user gets a working HDR tag out of the box.
        # ------------------------------------------------------------------
        self.tag_hdr = tk.BooleanVar(value=self.config.tag_hdr)
        self.hdr_colour_matrix = tk.StringVar(value=self.config.hdr_colour_matrix)
        self.hdr_colour_range = tk.StringVar(value=self.config.hdr_colour_range)
        self.hdr_transfer = tk.StringVar(value=self.config.hdr_transfer)
        self.hdr_primaries = tk.StringVar(value=self.config.hdr_primaries)
        self.hdr_max_cll = tk.StringVar(value=self.config.hdr_max_cll)
        self.hdr_max_fall = tk.StringVar(value=self.config.hdr_max_fall)
        self.hdr_chromaticity = tk.StringVar(value=self.config.hdr_chromaticity)
        self.hdr_white_point = tk.StringVar(value=self.config.hdr_white_point)
        self.hdr_max_luminance = tk.StringVar(value=self.config.hdr_max_luminance)
        self.hdr_min_luminance = tk.StringVar(value=self.config.hdr_min_luminance)

        if self.config.last_video_path and os.path.exists(self.config.last_video_path):
            self.video_path.set(self.config.last_video_path)
        if self.config.last_lut_path and os.path.exists(self.config.last_lut_path):
            self.lut_path.set(self.config.last_lut_path)
        self._setup_ui()

        # If the restored video path actually points at a file (not just a
        # directory), prime the instant-info panel on startup so the user
        # immediately sees metadata for whatever they were last working on.
        restored = self.video_path.get()
        if restored and os.path.isfile(restored):
            # Defer the probe until after the event loop starts spinning so
            # the UI has a chance to fully render first.
            self.root.after(100, lambda: self._probe_file_instantly(restored))
        
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
        
        # Path saving preferences
        tk.Checkbutton(checkbox_frame, text="Remember last video folder", 
                      variable=self.save_video_path,
                      font=self.default_font).pack()
        
        tk.Checkbutton(checkbox_frame, text="Remember last LUT file", 
                      variable=self.save_lut_path,
                      font=self.default_font).pack()
        
        # Existing checkboxes
        tk.Checkbutton(checkbox_frame, text="Show MKVInfo after processing?", 
                      variable=self.show_info,
                      font=self.default_font).pack()
        
        tk.Checkbutton(checkbox_frame, text="Prompt to move original to trash folder after conversion?",
                      variable=self.delete_original,
                      font=self.default_font).pack()

        # ------------------------------------------------------------------
        # HDR Metadata Tagging panel
        # ------------------------------------------------------------------
        # When enabled, the appropriate mkvmerge --colour-* / --max-* /
        # --chromaticity-coordinates flags are appended to the mux command so
        # the output MKV's Video track contains a proper Colour block. Without
        # this, YouTube / players treat HDR footage as Rec.709 SDR.
        #
        # Defaults are tuned for DJI Osmo Pocket 3 (Rec.2100 HLG). All fields
        # remain editable so the same UI works for Sony / iPhone PQ workflows.
        # ------------------------------------------------------------------
        hdr_frame = tk.LabelFrame(self.root, text="HDR Metadata Tagging",
                                  font=self.default_font)
        hdr_frame.pack(pady=10, padx=20, fill='x')

        # ------------------------------------------------------------------
        # Layout strategy: use grid() throughout this LabelFrame. Configure
        # column weights so the "wide" coordinate columns (1 and 3) can grow
        # and absorb extra horizontal space — that's what prevents the
        # Primaries field on the right edge from being clipped at narrower
        # window widths.
        # ------------------------------------------------------------------
        for _c in (1, 3):
            hdr_frame.grid_columnconfigure(_c, weight=1, minsize=180)
        for _c in (0, 2):
            hdr_frame.grid_columnconfigure(_c, weight=0, minsize=110)

        # Row 0 — master enable toggle. Spans all columns.
        tk.Checkbutton(hdr_frame,
                       text="Tag output as HDR (default: Osmo Pocket 3 HLG)",
                       variable=self.tag_hdr,
                       font=self.default_font).grid(row=0, column=0, columnspan=4,
                                                    sticky='w', padx=8, pady=(6, 2))

        # ------------------------------------------------------------------
        # Row 1 — preset selector + Apply button.
        # ------------------------------------------------------------------
        # The preset combobox is the headline feature here: pick "DJI Osmo
        # Pocket 3 (HLG)" or any other common camera/format and the entire
        # field set below auto-fills with sane values. "Custom (manual)" is
        # a no-op sentinel for users who want to hand-edit everything.
        # ------------------------------------------------------------------
        tk.Label(hdr_frame, text='Preset:', font=self.default_font)\
            .grid(row=1, column=0, sticky='e', padx=(8, 2), pady=4)

        self.hdr_preset_var = tk.StringVar(value='DJI Osmo Pocket 3 (HLG)')
        preset_combo = ttk.Combobox(hdr_frame, textvariable=self.hdr_preset_var,
                                    values=list(HDR_PRESETS.keys()),
                                    state='readonly', font=self.default_font)
        # Span columns 1..3 so the dropdown gets a generous width on every
        # window size.
        preset_combo.grid(row=1, column=1, columnspan=3, sticky='ew',
                          padx=(0, 8), pady=4)
        # Applying immediately on selection is the expected UX — no extra
        # button press to commit. We still leave the fields editable below
        # so a preset is a starting point, not a lock.
        preset_combo.bind('<<ComboboxSelected>>',
                          lambda e: self._apply_hdr_preset(self.hdr_preset_var.get()))

        # ------------------------------------------------------------------
        # Helper builders for the per-field rows. Comboboxes are used for the
        # four enum fields so the user picks from a labeled list rather than
        # remembering numeric codes.
        # ------------------------------------------------------------------
        def add_enum_combo(row, col, label_text, var, options):
            """Place a label + readonly Combobox on the grid.

            options: list of (display_label, raw_value) tuples. The combobox
            shows the display labels; we wire a binding that pushes the raw
            value back into the StringVar so the mkvmerge command stays
            numeric.
            """
            tk.Label(hdr_frame, text=label_text, font=self.default_font)\
                .grid(row=row, column=col*2, sticky='e', padx=(8, 2), pady=2)

            display_values = [opt[0] for opt in options]
            # Initial display label = whichever option's raw value matches
            # the current StringVar contents. Fall back to first option if
            # the saved value doesn't appear in the list (custom code).
            current_raw = var.get()
            initial_display = next(
                (opt[0] for opt in options if opt[1] == current_raw),
                display_values[0]
            )
            display_var = tk.StringVar(value=initial_display)

            combo = ttk.Combobox(hdr_frame, textvariable=display_var,
                                 values=display_values, state='readonly',
                                 font=self.default_font)
            combo.grid(row=row, column=col*2 + 1, sticky='ew',
                       padx=(0, 8), pady=2)

            # When the user picks an option, translate the display label
            # back to the raw enum code and store it on the real StringVar.
            def on_pick(_event, opts=options, dv=display_var, target=var):
                picked = dv.get()
                for label, raw in opts:
                    if label == picked:
                        target.set(raw)
                        return
            combo.bind('<<ComboboxSelected>>', on_pick)

            # If something else (e.g. a preset apply) changes the raw var,
            # reflect that in the display widget too. This keeps the combo
            # in sync without an extra event loop.
            def on_raw_change(*_a, opts=options, dv=display_var, target=var):
                raw_now = target.get()
                for label, raw in opts:
                    if raw == raw_now:
                        dv.set(label)
                        return
            target_trace = var.trace_add('write', on_raw_change)
            return combo

        def add_text_field(row, col, label_text, var, tip=''):
            """Place a label + free-text Entry on the grid (sticky='ew')."""
            tk.Label(hdr_frame, text=label_text, font=self.default_font)\
                .grid(row=row, column=col*2, sticky='e', padx=(8, 2), pady=2)
            entry = tk.Entry(hdr_frame, textvariable=var, font=self.default_font)
            entry.grid(row=row, column=col*2 + 1, sticky='ew',
                       padx=(0, 8), pady=2)
            if tip:
                # Render hint as small grey label beneath the entry so it
                # never overlaps the input (the previous version overlaid
                # the tip on top of the entry and clipped on narrow widths).
                tk.Label(hdr_frame, text=tip,
                         font=(self.default_font[0], 8), fg='#777')\
                    .grid(row=row + 1, column=col*2 + 1,
                          sticky='w', padx=(0, 8))
            return entry

        # Row 2 — the four enum dropdowns. These are the YouTube-critical
        # signaling values.
        add_enum_combo(2, 0, 'Matrix:',    self.hdr_colour_matrix, HDR_MATRIX_OPTIONS)
        add_enum_combo(2, 1, 'Range:',     self.hdr_colour_range,  HDR_RANGE_OPTIONS)
        add_enum_combo(3, 0, 'Transfer:',  self.hdr_transfer,      HDR_TRANSFER_OPTIONS)
        add_enum_combo(3, 1, 'Primaries:', self.hdr_primaries,     HDR_PRIMARIES_OPTIONS)

        # Row 4-5 — PQ light-level metadata (blank for HLG presets).
        add_text_field(4, 0, 'MaxCLL:',  self.hdr_max_cll,  tip='PQ only, e.g. 1000')
        add_text_field(4, 1, 'MaxFALL:', self.hdr_max_fall, tip='PQ only, e.g. 400')
        add_text_field(6, 0, 'Max Lum:', self.hdr_max_luminance, tip='PQ only, peak nits')
        add_text_field(6, 1, 'Min Lum:', self.hdr_min_luminance, tip='PQ only, e.g. 0.0001')

        # Row 8-9 — mastering display chromaticity + white point. These are
        # full-width coord lists; give them the whole row so they breathe.
        add_text_field(8, 0, 'Chromaticity (R,G,B x,y):', self.hdr_chromaticity,
                       tip='Rec.2020: 0.708,0.292,0.170,0.797,0.131,0.046')
        add_text_field(8, 1, 'White point (x,y):', self.hdr_white_point,
                       tip='D65 = 0.3127,0.329')

        # Persist HDR fields automatically as the user edits them.
        def on_hdr_change(*args):
            self.config.update_hdr(
                self.tag_hdr.get(),
                self.hdr_colour_matrix.get(),
                self.hdr_colour_range.get(),
                self.hdr_transfer.get(),
                self.hdr_primaries.get(),
                self.hdr_max_cll.get(),
                self.hdr_max_fall.get(),
                self.hdr_chromaticity.get(),
                self.hdr_white_point.get(),
                self.hdr_max_luminance.get(),
                self.hdr_min_luminance.get(),
            )
        for _hdr_var in (self.tag_hdr, self.hdr_colour_matrix, self.hdr_colour_range,
                         self.hdr_transfer, self.hdr_primaries, self.hdr_max_cll,
                         self.hdr_max_fall, self.hdr_chromaticity, self.hdr_white_point,
                         self.hdr_max_luminance, self.hdr_min_luminance):
            _hdr_var.trace_add('write', on_hdr_change)

        # Process button
        tk.Button(self.root, text="Process Video",
                  command=self.process_video,
                  font=self.button_font).pack(pady=10)
        
        # ------------------------------------------------------------------
        # Instant Info panel
        # ------------------------------------------------------------------
        # Fires the moment a video is dropped (before any processing), so the
        # user can immediately inspect container/track metadata. Uses mkvinfo
        # for Matroska files and falls back to ffprobe for mov/mp4/others.
        # ------------------------------------------------------------------
        self.instant_info_frame = tk.LabelFrame(self.root, text="Instant Info (on drop)",
                                                font=self.default_font)
        self.instant_info_frame.pack(pady=10, padx=20, fill='both', expand=True)

        # Read-only text widget showing the probe output. Kept disabled by
        # default so the user does not accidentally type into it; we re-enable
        # it programmatically whenever we refresh the contents.
        self.instant_info_text = tk.Text(self.instant_info_frame, wrap=tk.WORD,
                                         font=("Consolas", 10), height=10,
                                         state='disabled')
        self.instant_info_text.pack(padx=5, pady=5, fill='both', expand=True, side=tk.LEFT)

        # Dedicated scrollbar so long mkvinfo dumps remain navigable.
        instant_scrollbar = tk.Scrollbar(self.instant_info_frame,
                                         command=self.instant_info_text.yview)
        instant_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.instant_info_text.config(yscrollcommand=instant_scrollbar.set)

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

        # Initialize variables with saved preferences
        self.delete_original.set(self.config.delete_original)
        self.show_info.set(self.config.show_info)
        self.save_video_path.set(self.config.save_video_path)
        self.save_lut_path.set(self.config.save_lut_path)
        
        # Update config when checkboxes change
        def on_preference_change(*args):
            self.config.update_preferences(
                self.show_info.get(),
                self.delete_original.get(),
                self.save_video_path.get(),
                self.save_lut_path.get(),
                self.output_prefix.get()
            )

        # Bind checkbox changes to save preferences
        self.show_info.trace_add('write', on_preference_change)
        self.delete_original.trace_add('write', on_preference_change)
        self.save_video_path.trace_add('write', on_preference_change)
        self.save_lut_path.trace_add('write', on_preference_change)
        self.output_prefix.trace_add('write', on_preference_change)

        # Make the frame clickable
        self.video_drop_frame.bind("<Button-1>", lambda e: self.browse_video())
        drop_label.bind("<Button-1>", lambda e: self.browse_video())

    def browse_video(self):
        """Open file dialog for video selection"""
        # Use the last video path if it exists, otherwise use the current working directory
        initial_dir = self.config.last_video_path if os.path.exists(self.config.last_video_path) else os.getcwd()
        file_path = filedialog.askopenfilename(
            initialdir=initial_dir,
            filetypes=[("Video files", "*.mov;*.mp4"), ("All files", "*.*")]
        )
        if file_path:
            self.video_path.set(file_path)
            # Update the last video path to the directory of the selected file
            if self.save_video_path.get():
                self.config.update_video_path(os.path.dirname(file_path))
            # Fire the instant info probe so the user sees metadata right away,
            # even though they picked the file via dialog rather than drag&drop.
            self._probe_file_instantly(file_path)

    def browse_lut(self):
        """Open file dialog for LUT selection"""
        initial_dir = os.path.dirname(self.config.last_lut_path) if os.path.exists(self.config.last_lut_path) else os.getcwd()
        file_path = filedialog.askopenfilename(
            initialdir=initial_dir,
            filetypes=[("LUT files", "*.cube"), ("All files", "*.*")]
        )
        if file_path:
            self.lut_path.set(file_path)
            if self.save_lut_path.get():
                self.config.update_lut_path(file_path)

    # ----------------------------------------------------------------------
    # Instant Info helpers
    # ----------------------------------------------------------------------
    # The goal here is "drop file -> see metadata immediately." We must avoid
    # blocking the Tk main loop, so the actual subprocess call runs in a
    # worker thread and the result is marshalled back via root.after().
    # ----------------------------------------------------------------------

    def _set_instant_info(self, text):
        """Replace the contents of the Instant Info panel (thread-safe via after)."""
        # The widget is created as 'disabled' to prevent stray edits; flip it
        # to 'normal' just long enough to swap the contents, then lock it back.
        self.instant_info_text.config(state='normal')
        self.instant_info_text.delete('1.0', tk.END)
        self.instant_info_text.insert('1.0', text)
        self.instant_info_text.config(state='disabled')

    def _probe_file_instantly(self, file_path):
        """Kick off an async metadata probe for the given file.

        Picks the right tool based on extension:
          * .mkv / .mka / .mks / .webm  -> bundled mkvinfo
          * everything else             -> system ffprobe (if installed)
        """
        # Bail out early on missing/bogus paths so we don't show stale info.
        if not file_path or not os.path.exists(file_path):
            self._set_instant_info("(no file)")
            return

        # Show an immediate placeholder so the user knows we heard the drop,
        # even if the actual probe takes a moment to spin up.
        self._set_instant_info(f"Probing: {file_path}\nPlease wait...")

        # Dispatch to a worker so the GUI stays responsive on large files.
        thread = threading.Thread(
            target=self._run_probe_worker,
            args=(file_path,),
            daemon=True
        )
        thread.start()

    def _run_probe_worker(self, file_path):
        """Worker-thread body: run mkvinfo or ffprobe and post the result back."""
        ext = os.path.splitext(file_path)[1].lower()
        # Matroska-family extensions that mkvinfo can read natively.
        mkv_exts = {'.mkv', '.mka', '.mks', '.webm'}

        try:
            if ext in mkv_exts:
                # Use the bundled mkvinfo binary for true Matroska containers.
                output = self._run_mkvinfo(file_path)
            else:
                # Fall back to ffprobe for mov/mp4/etc. We try -show_format and
                # -show_streams so the user gets both container- and track-
                # level metadata in one shot.
                output = self._run_ffprobe(file_path)
        except Exception as e:
            # Surface the error inline rather than popping a dialog — the user
            # is dragging files, not running an operation, so noise is bad.
            output = f"[Instant Info error] {e}"

        # Marshal the UI update back onto the Tk main thread.
        self.root.after(0, lambda: self._set_instant_info(output))

    def _run_mkvinfo(self, file_path):
        """Run the bundled mkvinfo and return its stdout (or stderr on failure)."""
        result = subprocess.run(
            [self.mkvinfo_path, file_path],
            capture_output=True, text=True,
            # On Windows, suppress the flashing console window that would
            # otherwise pop up for each subprocess call.
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        )
        if result.returncode == 0:
            return result.stdout
        # Non-zero exit: still show whatever output we got, it's usually
        # diagnostic ("not a Matroska file" etc.).
        return (result.stdout or '') + (result.stderr or '')

    def _run_ffprobe(self, file_path):
        """Run ffprobe (if available) and return a human-readable dump."""
        # Resolve ffprobe lazily so the rest of the app still works on systems
        # where it isn't installed.
        ffprobe = shutil.which('ffprobe')
        if not ffprobe:
            return ("ffprobe not found on PATH.\n"
                    "Install FFmpeg and add it to PATH to see instant info "
                    "for non-Matroska files (.mov, .mp4, etc).")

        # -hide_banner trims the noisy build-config preamble.
        # -show_format dumps container-level metadata (duration, bitrate, tags).
        # -show_streams dumps per-track metadata (codec, resolution, HDR fields).
        cmd = [
            ffprobe,
            '-hide_banner',
            '-show_format',
            '-show_streams',
            file_path
        ]
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        )
        if result.returncode == 0:
            # ffprobe prints to stderr by default for non-JSON output, but with
            # -show_format/-show_streams it goes to stdout. Concatenate just in
            # case so we never silently drop info.
            return (result.stdout or '') + (result.stderr or '')
        return f"[ffprobe failed: exit {result.returncode}]\n{result.stderr}"

    def _log_output(self, message):
        """Add message to output text widget"""
        self.output_text.insert(tk.END, f"{message}\n")
        self.output_text.see(tk.END)  # Auto-scroll to bottom
        self.root.update()  # Force GUI update

    def _apply_hdr_preset(self, preset_name):
        """Populate every HDR field from a named preset.

        Called when the user picks an entry from the preset Combobox. The
        'Custom (manual)' sentinel is a no-op so users can flip back to
        editing without their values being clobbered.
        """
        preset = HDR_PRESETS.get(preset_name)
        # Custom or unknown name -> leave everything alone. The user is in
        # control of the fields directly.
        if preset is None:
            return

        # Map preset keys to the Tk StringVars they drive. Updating the var
        # also fires the trace_add('write') hook that persists to settings.ini
        # AND the secondary trace inside add_enum_combo that updates the
        # display label on each Combobox.
        self.hdr_colour_matrix.set(preset['colour_matrix'])
        self.hdr_colour_range.set(preset['colour_range'])
        self.hdr_transfer.set(preset['transfer'])
        self.hdr_primaries.set(preset['primaries'])
        self.hdr_max_cll.set(preset['max_cll'])
        self.hdr_max_fall.set(preset['max_fall'])
        self.hdr_chromaticity.set(preset['chromaticity'])
        self.hdr_white_point.set(preset['white_point'])
        self.hdr_max_luminance.set(preset['max_luminance'])
        self.hdr_min_luminance.set(preset['min_luminance'])

    def _build_hdr_flags(self):
        """Assemble the mkvmerge HDR/colour flag list from the UI vars.

        Returns a flat list of CLI args. Each flag is only included when the
        corresponding field is non-empty, so HLG users (who leave the
        mastering-display fields blank) don't end up with bogus zero-valued
        metadata in their output.

        All flags target track ID 0 because the source mov/mp4 has the video
        as its first track (confirmed via the user's mkvinfo dumps).
        """
        flags = []

        # Helper: append "flag 0:value" only if the value is meaningfully set.
        # Strip whitespace so a field full of spaces is treated as empty.
        def add(flag_name, raw_value):
            if raw_value is None:
                return
            value = raw_value.strip()
            if not value:
                return
            flags.extend([flag_name, f'0:{value}'])

        # Core colour-space identifiers. These four are the bare minimum for
        # YouTube to flip the HDR badge on, so they should almost always be
        # populated. We still go through add() so an intentionally blank
        # field is honored rather than silently overridden.
        add('--colour-matrix', self.hdr_colour_matrix.get())
        add('--colour-range', self.hdr_colour_range.get())
        add('--colour-transfer-characteristics', self.hdr_transfer.get())
        add('--colour-primaries', self.hdr_primaries.get())

        # Light-level metadata — relevant for PQ, omitted for HLG.
        add('--max-content-light', self.hdr_max_cll.get())
        add('--max-frame-light', self.hdr_max_fall.get())

        # Mastering-display chromaticity + white point. mkvmerge expects six
        # comma-separated coords for chromaticity (Rx,Ry,Gx,Gy,Bx,By) and two
        # for the white point (Wx,Wy). We pass them through verbatim — the
        # user's responsibility to format them correctly.
        add('--chromaticity-coordinates', self.hdr_chromaticity.get())
        add('--white-colour-coordinates', self.hdr_white_point.get())

        # Mastering-display luminance bounds, in cd/m^2.
        add('--max-luminance', self.hdr_max_luminance.get())
        add('--min-luminance', self.hdr_min_luminance.get())

        return flags

    def process_video(self):
        """Process the video with the selected LUT"""
        if not self.video_path.get() or not self.lut_path.get():
            messagebox.showerror("Error", "Please provide both video and LUT files")
            return
            
        input_path = self.video_path.get()
        input_name = Path(input_path).stem
        output_path = str(Path(input_path).parent / f"{input_name}{self.output_prefix.get()}.mkv")

        # ------------------------------------------------------------------
        # Build the HDR flag block.
        # ------------------------------------------------------------------
        # mkvmerge applies --colour-* / --max-* / --chromaticity-coordinates /
        # --white-colour-coordinates / --max-luminance / --min-luminance to
        # the NEXT input file's track 0 (our video track). They must appear
        # BEFORE the input filename on the command line.
        #
        # Each flag takes the form "TID:VALUE" where TID is the track ID. The
        # source video sits at track ID 0 in the mov/mp4 we're muxing in, so
        # every flag is prefixed with "0:".
        # ------------------------------------------------------------------
        hdr_flags = self._build_hdr_flags() if self.tag_hdr.get() else []

        # Build command. HDR flags are inserted immediately before the input
        # path so mkvmerge associates them with that input's video track.
        cmd = [
            self.mkvmerge_path,
            '-o', output_path,
            '--attachment-mime-type', 'application/x-cube',
            '--attach-file', self.lut_path.get(),
        ] + hdr_flags + [
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
                if messagebox.askyesno("Move to Trash", 
                                     "Do you want to move the original file to trash? It will not be permanently deleted, just moved to the trash folder."):
                    try:
                        # Convert path to absolute path and normalize it
                        abs_path = os.path.abspath(os.path.normpath(input_path))
                        if os.path.exists(abs_path):
                            send2trash(abs_path)
                            self._log_output("Original file moved to trash")
                        else:
                            raise FileNotFoundError(f"Could not find file: {abs_path}")
                    except Exception as e:
                        error_msg = f"Could not move file to trash: {str(e)}"
                        self._log_output(error_msg)
                        messagebox.showerror("Error", error_msg)
            
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
        # Accept any extension mkvinfo or ffprobe might understand for the
        # instant-info path, but still gate the actual mkvmerge pipeline on
        # the supported source extensions (mov/mp4) like before.
        if file_path.lower().endswith(('.mov', '.mp4', '.mkv', '.mka', '.mks', '.webm', '.m4v')):
            self.video_path.set(file_path)
            if self.save_video_path.get():
                self.config.update_video_path(os.path.dirname(file_path))
            # Instant probe: user wants metadata immediately on drop.
            self._probe_file_instantly(file_path)
        elif file_path.lower().endswith('.cube'):
            self.lut_path.set(file_path)
            if self.save_lut_path.get():
                self.config.update_lut_path(file_path)

    def _handle_video_drop(self, event):
        """Handle files dropped on video drop zone"""
        files = self.root.tk.splitlist(event.data)
        # Same widened extension set as _handle_drop — see comment there.
        if files and files[0].lower().endswith(('.mov', '.mp4', '.mkv', '.mka', '.mks', '.webm', '.m4v')):
            self.video_path.set(files[0])
            if self.save_video_path.get():
                self.config.update_video_path(os.path.dirname(files[0]))
            # Fire the instant info probe the moment the file lands.
            self._probe_file_instantly(files[0])

    def _handle_lut_drop(self, event):
        """Handle files dropped on LUT drop zone"""
        files = self.root.tk.splitlist(event.data)
        if files and files[0].lower().endswith('.cube'):
            self.lut_path.set(files[0])
            if self.save_lut_path.get():
                self.config.update_lut_path(files[0])

    def run(self):
        """Start the GUI"""
        self.root.mainloop()

if __name__ == "__main__":
    app = HDRVideoProcessor()
    app.run()