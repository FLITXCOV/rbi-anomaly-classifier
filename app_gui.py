"""
RBI Anomaly Classifier  -  Standalone Desktop Utility  v2.0
100% offline. No server. No internet. Data never leaves this machine.
"""

import os
import sys
import io
import math
import glob
import threading
from datetime import datetime

import customtkinter as ctk
from tkinter import filedialog, ttk
import tkinter as tk
from PIL import Image
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# -- Ensure project root on path so we can import main -------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# ==============================================================================
#  Design Tokens
#  Palette: deep institutional navy, restrained slate surfaces, cool signal-blue
#  for primary actions, single warm amber accent for "attention" states.
# ==============================================================================
BG          = "#090c14"
BG2         = "#0d111c"
SURFACE     = "#131826"
SURFACE2    = "#1a2033"
SURFACE3    = "#212942"
BORDER      = "#262f48"
BORDER_SOFT = "#1c2338"
ACCENT      = "#5b8dee"
ACCENT_HOVER= "#4a7bd4"
ACCENT_DIM  = "#20304f"
ACCENT_SOFT = "#8fb3f5"
TEXT        = "#eef1f7"
TEXT_SEC    = "#9aa5bd"
TEXT_MUTED  = "#5f6a85"
SUCCESS     = "#3ddc97"
SUCCESS_DIM = "#0e3328"
DANGER      = "#f76b6b"
DANGER_DIM  = "#3a1414"
WARNING     = "#f2b84b"
WARNING_DIM = "#3a2a0c"
ORANGE      = "#fb923c"
GOLD_LINE   = "#f2b84b"

CAUSE_COLORS = {
    "Current"        : "#5b8dee",
    "Savings"        : "#3ddc97",
    "Term"           : "#f2b84b",
    "Systemic"       : "#9aa5bd",
    "Data Not Found" : "#f76b6b",
}
CAUSE_DIM = {
    "Current"        : "#1c2c4a",
    "Savings"        : "#0e3328",
    "Term"           : "#3a2a0c",
    "Systemic"       : "#242c42",
    "Data Not Found" : "#3a1414",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

FONT      = "Segoe UI"
FONT_DISP = "Segoe UI Semibold"
MONO      = "Consolas"

# Easing helpers ---------------------------------------------------------------
def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - pow(1 - t, 3)

def ease_out_back(t: float) -> float:
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


# ==============================================================================
#  Helpers
# ==============================================================================
def _fig_to_ctk_image(fig, width, height):
    """Render a matplotlib figure to a CTkImage (no TkAgg overhead)."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight",
                pad_inches=0.15, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    pil = Image.open(buf)
    return ctk.CTkImage(light_image=pil, dark_image=pil, size=(width, height))


def _set_mpl_style():
    """Shared matplotlib rcParams for visual coherence."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [FONT, "Segoe UI", "Arial"],
        "axes.edgecolor": BORDER,
        "text.color": TEXT,
    })

_set_mpl_style()


def _format_quarter_label(date_val):
    """Convert a date to a short quarter label like \"Mar '25\"."""
    try:
        dt = pd.to_datetime(date_val)
        return dt.strftime("%b '%y")
    except Exception:
        return str(date_val)[:7]


# ==============================================================================
#  Animated Widgets
# ==============================================================================
class StaggeredReveal:
    """Staggered border-highlight entrance animation for a list of widgets."""

    def __init__(self, root_widget, items, delay_between=55, duration=260):
        self.root = root_widget
        self.items = items
        self.delay_between = delay_between
        self.duration = duration

    def run(self):
        for idx, widget in enumerate(self.items):
            start_delay = idx * self.delay_between
            self.root.after(start_delay, lambda w=widget: self._animate(w))

    def _animate(self, widget):
        try:
            widget.configure(border_color=ACCENT)
        except Exception:
            pass
        steps = 10
        interval = max(8, self.duration // steps)

        def step(i=0):
            if not widget.winfo_exists():
                return
            if i >= steps:
                try:
                    widget.configure(border_color=BORDER)
                except Exception:
                    pass
                return
            self.root.after(interval, lambda: step(i + 1))
        step()


class Pulse:
    """Breathing color pulse on a label's text_color."""

    def __init__(self, widget, color_a, color_b, period_ms=900):
        self.widget = widget
        self.color_a = color_a
        self.color_b = color_b
        self.period = period_ms
        self._running = False
        self._t0 = None

    def start(self):
        self._running = True
        self._t0 = datetime.now()
        self._tick()

    def stop(self):
        self._running = False

    def _tick(self):
        if not self._running or not self.widget.winfo_exists():
            return
        elapsed = (datetime.now() - self._t0).total_seconds() * 1000
        phase = (elapsed % self.period) / self.period
        blend = 1 - abs(2 * phase - 1)
        color = self._lerp(self.color_a, self.color_b, blend)
        try:
            self.widget.configure(text_color=color)
        except Exception:
            return
        self.widget.after(40, self._tick)

    @staticmethod
    def _lerp(c1, c2, t):
        c1 = c1.lstrip("#")
        c2 = c2.lstrip("#")
        r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
        r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"


class CountUpLabel(ctk.CTkLabel):
    """KPI value label that animates from 0 to target with ease-out."""

    def __init__(self, parent, target_value, formatter=None, duration=650,
                 **kwargs):
        self.formatter = formatter or (lambda v: str(int(round(v))))
        super().__init__(parent, text=self.formatter(0), **kwargs)
        self.target_value = target_value
        self.duration = duration

    def animate(self, start_delay=0):
        self.after(start_delay, self._run)

    def _run(self):
        steps = 24
        interval = max(10, self.duration // steps)

        def step(i=0):
            if not self.winfo_exists():
                return
            t = ease_out_cubic(i / steps)
            val = self.target_value * t
            try:
                self.configure(text=self.formatter(val))
            except Exception:
                return
            if i < steps:
                self.after(interval, lambda: step(i + 1))
            else:
                self.configure(text=self.formatter(self.target_value))
        step()


class HoverButton(ctk.CTkButton):
    """CTkButton with eased color transition on hover."""

    def __init__(self, parent, *, base_color, hover_target, **kwargs):
        super().__init__(parent, fg_color=base_color, hover=False, **kwargs)
        self.base_color = base_color
        self.hover_target = hover_target
        self.bind("<Enter>", lambda e: self._transition(self.base_color, self.hover_target))
        self.bind("<Leave>", lambda e: self._transition(self.hover_target, self.base_color))

    def _transition(self, c1, c2, steps=8, interval=12):
        if c1 == "transparent" or c2 == "transparent":
            try:
                self.configure(fg_color=c2)
            except Exception:
                pass
            return

        def step(i=0):
            if not self.winfo_exists():
                return
            t = i / steps
            color = Pulse._lerp(c1, c2, t)
            try:
                self.configure(fg_color=color)
            except Exception:
                return
            if i < steps:
                self.after(interval, lambda: step(i + 1))
        step()


class Tooltip:
    """Lightweight hover tooltip for any widget."""

    def __init__(self, widget, text, delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._tip_window = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._cancel)

    def _schedule(self, event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self, event=None):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        self._hide()

    def _show(self):
        if self._tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg=SURFACE3)
        label = tk.Label(tw, text=self.text, bg=SURFACE3, fg=TEXT,
                         font=(FONT, 10), padx=10, pady=6)
        label.pack()

    def _hide(self):
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None


# ==============================================================================
#  Main Application
# ==============================================================================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("RBI Anomaly Classifier")
        self.geometry("1440x900")
        self.minsize(1100, 700)
        self.configure(fg_color=BG)

        self._selected_folder = os.path.join(PROJECT_ROOT, "data", "01_raw_input")
        self._result          = None
        self._sort_asc        = True
        self._sort_col        = None
        self._status_pulse    = None
        self._elapsed_running = False
        self._step_dots       = []
        self._has_bank_col    = False
        self._has_state_col   = False

        self._build_header()
        self._build_body()

    # ------------------------------------------------------------------
    #  HEADER
    # ------------------------------------------------------------------
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=64)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        inner = ctk.CTkFrame(hdr, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32)

        # Left: monogram + wordmark
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="y")

        mark = ctk.CTkFrame(left, fg_color=ACCENT_DIM, corner_radius=8,
                             width=34, height=34)
        mark.pack(side="left", pady=15)
        mark.pack_propagate(False)
        ctk.CTkLabel(mark, text="RBI", font=ctk.CTkFont(FONT, 10, "bold"),
                     text_color=ACCENT_SOFT).pack(expand=True)

        title_block = ctk.CTkFrame(left, fg_color="transparent")
        title_block.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(
            title_block, text="Anomaly Classifier",
            font=ctk.CTkFont(FONT, 18, "bold"), text_color=TEXT
        ).pack(anchor="w", pady=(13, 0))
        ctk.CTkLabel(
            title_block, text="BSR 2 Branch Data  \u00b7  Statistical Review",
            font=ctk.CTkFont(FONT, 10), text_color=TEXT_MUTED
        ).pack(anchor="w")

        # Version badge
        badge = ctk.CTkFrame(left, fg_color=SURFACE2, corner_radius=6,
                              border_width=1, border_color=BORDER)
        badge.pack(side="left", padx=16, pady=22)
        ctk.CTkLabel(badge, text="v2.0", font=ctk.CTkFont(MONO, 10, "bold"),
                     text_color=ACCENT_SOFT).pack(padx=9, pady=2)

        # Step indicator: Data > Engine > Results
        step_frame = ctk.CTkFrame(left, fg_color="transparent")
        step_frame.pack(side="left", padx=(20, 0), pady=22)
        step_labels = ["Data", "Engine", "Results"]
        for i in range(3):
            dot_frame = ctk.CTkFrame(step_frame, fg_color="transparent")
            dot_frame.pack(side="left", padx=(0, 4))
            dot = ctk.CTkLabel(dot_frame, text="\u25cf", font=ctk.CTkFont(FONT, 8),
                               text_color=ACCENT if i == 0 else TEXT_MUTED)
            dot.pack(side="left", padx=(0, 3))
            lbl = ctk.CTkLabel(dot_frame, text=step_labels[i],
                               font=ctk.CTkFont(FONT, 9),
                               text_color=TEXT_SEC if i == 0 else TEXT_MUTED)
            lbl.pack(side="left")
            self._step_dots.append((dot, lbl))
            if i < 2:
                ctk.CTkLabel(step_frame, text="\u2014",
                             font=ctk.CTkFont(FONT, 8),
                             text_color=BORDER).pack(side="left", padx=(0, 4))

        # Right: offline chip
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right", pady=15)

        chip = ctk.CTkFrame(right, fg_color=SUCCESS_DIM, corner_radius=14)
        chip.pack(side="right")
        ctk.CTkLabel(chip, text="\u25cf", font=ctk.CTkFont(FONT, 9),
                     text_color=SUCCESS).pack(side="left", padx=(10, 4), pady=5)
        ctk.CTkLabel(chip, text="Offline \u00b7 Local Only",
                     font=ctk.CTkFont(FONT, 10, "bold"),
                     text_color=SUCCESS).pack(side="left", padx=(0, 10), pady=5)
        ctk.CTkLabel(right, text="Tier 1 + Tier 2 Engine",
                     font=ctk.CTkFont(FONT, 11),
                     text_color=TEXT_MUTED).pack(side="right", padx=(0, 16))

        # Signature dual-tone rule
        rule = ctk.CTkFrame(self, fg_color=ACCENT, height=2, corner_radius=0)
        rule.pack(fill="x")
        ember = ctk.CTkFrame(rule, fg_color=GOLD_LINE, height=2, width=110,
                              corner_radius=0)
        ember.place(relx=0, rely=0, anchor="nw")

    def _update_step(self, step_num):
        """Update the 3-dot step indicator (1-indexed)."""
        for i, (dot, lbl) in enumerate(self._step_dots):
            if i + 1 < step_num:
                dot.configure(text_color=SUCCESS, text="\u2713")
                lbl.configure(text_color=SUCCESS)
            elif i + 1 == step_num:
                dot.configure(text_color=ACCENT, text="\u25cf")
                lbl.configure(text_color=TEXT_SEC)
            else:
                dot.configure(text_color=TEXT_MUTED, text="\u25cf")
                lbl.configure(text_color=TEXT_MUTED)

    # ------------------------------------------------------------------
    #  BODY
    # ------------------------------------------------------------------
    def _build_body(self):
        self._body = ctk.CTkFrame(self, fg_color=BG)
        self._body.pack(fill="both", expand=True, padx=0, pady=0)
        self._show_upload_screen()

    def _clear_body(self):
        if self._status_pulse:
            self._status_pulse.stop()
            self._status_pulse = None
        self._elapsed_running = False
        for w in self._body.winfo_children():
            w.destroy()

    # ==================================================================
    #  SCREEN 1 \u2014 UPLOAD
    # ==================================================================
    def _show_upload_screen(self):
        self._clear_body()
        self._update_step(1)

        center = ctk.CTkFrame(self._body, fg_color=BG)
        center.pack(expand=True)

        card = ctk.CTkFrame(center, fg_color=SURFACE, corner_radius=20,
                            border_width=1, border_color=BORDER, width=620)
        card.pack(padx=80, pady=30)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=48, pady=44)

        ctk.CTkLabel(inner, text="STEP 1 OF 3",
                     font=ctk.CTkFont(MONO, 10, "bold"),
                     text_color=ACCENT_SOFT).pack(anchor="w")
        ctk.CTkLabel(inner, text="Quarter Data",
                     font=ctk.CTkFont(FONT, 27, "bold"),
                     text_color=TEXT).pack(anchor="w", pady=(6, 0))
        ctk.CTkLabel(inner,
                     text="Place quarterly BSR 2 Excel files in the input folder.",
                     font=ctk.CTkFont(FONT, 13), text_color=TEXT_SEC
                     ).pack(anchor="w", pady=(4, 16))

        # Folder path display
        folder_row = ctk.CTkFrame(inner, fg_color=BG2, corner_radius=8)
        folder_row.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(folder_row, text="\U0001f4c1",
                     font=ctk.CTkFont(FONT, 11),
                     text_color=TEXT_MUTED).pack(side="left", padx=(12, 6), pady=8)
        ctk.CTkLabel(folder_row,
                     text=os.path.relpath(self._selected_folder, PROJECT_ROOT),
                     font=ctk.CTkFont(MONO, 10), text_color=TEXT_SEC
                     ).pack(side="left", pady=8)

        # File list card
        self._file_list_frame = ctk.CTkFrame(
            inner, fg_color=BG2, corner_radius=14,
            border_width=1.5, border_color=BORDER)
        self._file_list_frame.pack(fill="x")

        self._file_list_inner = ctk.CTkFrame(
            self._file_list_frame, fg_color="transparent")
        self._file_list_inner.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(self._file_list_inner, text="Scanning folder\u2026",
                     font=ctk.CTkFont(FONT, 12),
                     text_color=TEXT_MUTED).pack(anchor="w")

        # Button row
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x", pady=(16, 0))

        HoverButton(btn_row, text="Rescan Folder",
                    font=ctk.CTkFont(FONT, 12), base_color=SURFACE3,
                    hover_target=BORDER, text_color=TEXT_SEC,
                    corner_radius=8, height=36, width=140,
                    command=self._scan_folder).pack(side="left")

        HoverButton(btn_row, text="Open Folder",
                    font=ctk.CTkFont(FONT, 12), base_color="transparent",
                    hover_target=SURFACE3, text_color=TEXT_MUTED,
                    corner_radius=8, height=36, width=120,
                    border_width=1, border_color=BORDER,
                    command=lambda: os.startfile(self._selected_folder)
                    ).pack(side="left", padx=(8, 0))

        # Engine pipeline info
        info_frame = ctk.CTkFrame(inner, fg_color=SURFACE2, corner_radius=10)
        info_frame.pack(fill="x", pady=(24, 0))
        info_inner = ctk.CTkFrame(info_frame, fg_color="transparent")
        info_inner.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(info_inner, text="ENGINE PIPELINE",
                     font=ctk.CTkFont(MONO, 9, "bold"),
                     text_color=TEXT_MUTED).pack(anchor="w")
        tier_row = ctk.CTkFrame(info_inner, fg_color="transparent")
        tier_row.pack(fill="x", pady=(8, 0))
        for i, (tag, name) in enumerate([
            ("TIER 1", "Tukey IQR + Peer Grouping"),
            ("TIER 2", "Robust Z-Score Root Cause"),
        ]):
            t = ctk.CTkFrame(tier_row, fg_color="transparent")
            t.pack(side="left", padx=(0 if i == 0 else 20, 0))
            b = ctk.CTkFrame(t, fg_color=ACCENT_DIM, corner_radius=5)
            b.pack(side="left")
            ctk.CTkLabel(b, text=tag, font=ctk.CTkFont(MONO, 9, "bold"),
                         text_color=ACCENT_SOFT).pack(padx=6, pady=2)
            ctk.CTkLabel(t, text=name, font=ctk.CTkFont(FONT, 11),
                         text_color=TEXT_SEC).pack(side="left", padx=(6, 0))

        # Run button
        self._run_btn = HoverButton(
            inner, text="Run Analysis",
            font=ctk.CTkFont(FONT, 15, "bold"),
            base_color=ACCENT, hover_target=ACCENT_HOVER,
            corner_radius=12, height=48,
            state="disabled", command=self._start_run)
        self._run_btn.pack(fill="x", pady=(24, 0))

        # Footer
        foot = ctk.CTkFrame(inner, fg_color="transparent")
        foot.pack(pady=(16, 0))
        ctk.CTkLabel(foot, text="\U0001f512", font=ctk.CTkFont(FONT, 10),
                     text_color=TEXT_MUTED).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(foot, text="Data never leaves this machine.",
                     font=ctk.CTkFont(FONT, 10),
                     text_color=TEXT_MUTED).pack(side="left")

        # Auto-scan on screen load
        self.after(300, self._scan_folder)

    def _scan_folder(self):
        """Scan input folder, validate each file, render a live file list."""
        for w in self._file_list_inner.winfo_children():
            w.destroy()

        files = glob.glob(os.path.join(self._selected_folder, "*.xls*")) + \
                glob.glob(os.path.join(self._selected_folder, "*.csv"))

        if not files:
            ctk.CTkLabel(self._file_list_inner,
                         text="No Excel or CSV files found in the input folder.",
                         font=ctk.CTkFont(FONT, 12),
                         text_color=WARNING).pack(anchor="w")
            self._file_list_frame.configure(border_color=WARNING)
            self._run_btn.configure(state="disabled")
            return

        file_info = []
        for fp in files:
            try:
                is_csv = fp.lower().endswith('.csv')
                if is_csv:
                    df_peek = pd.read_csv(fp, nrows=3)
                    if 'Period End Date' not in df_peek.columns:
                        df_peek = pd.read_csv(fp, skiprows=1, nrows=3)
                else:
                    df_peek = pd.read_excel(fp, nrows=3)
                    if 'Period End Date' not in df_peek.columns:
                        df_peek = pd.read_excel(fp, skiprows=1, nrows=3)
                        
                if ('Period End Date' in df_peek.columns
                        and not df_peek['Period End Date'].isna().all()):
                    date_val = pd.to_datetime(df_peek['Period End Date'].iloc[0])
                    
                    # Auto-Rename Logic
                    ext = '.csv' if is_csv else '.xlsx'
                    clean_name = date_val.strftime(f'%B %Y BSR2{ext}')
                    new_fp = os.path.join(os.path.dirname(fp), clean_name)
                    
                    # Safe rename if not already correctly named
                    if os.path.basename(fp).lower() != clean_name.lower():
                        counter = 1
                        while os.path.exists(new_fp) and fp.lower() != new_fp.lower():
                            clean_name = date_val.strftime(f'%B %Y BSR2 ({counter}).xlsx')
                            new_fp = os.path.join(os.path.dirname(fp), clean_name)
                            counter += 1
                        try:
                            os.rename(fp, new_fp)
                            fp = new_fp
                        except Exception:
                            pass # File locked by Excel

                    file_info.append({
                        'name': os.path.basename(fp),
                        'date': date_val,
                        'date_label': _format_quarter_label(date_val),
                        'size_mb': os.path.getsize(fp) / 1_048_576,
                        'valid': True,
                    })
                else:
                    file_info.append({
                        'name': os.path.basename(fp), 'date': None,
                        'date_label': '\u2014',
                        'size_mb': os.path.getsize(fp) / 1_048_576,
                        'valid': False,
                    })
            except Exception:
                file_info.append({
                    'name': os.path.basename(fp), 'date': None,
                    'date_label': '\u2014',
                    'size_mb': os.path.getsize(fp) / 1_048_576,
                    'valid': False,
                })

        file_info.sort(
            key=lambda x: (not x['valid'],
                           x['date'] or pd.Timestamp.min),
            reverse=True)
            
        valid_count = sum(1 for f in file_info if f['valid'])
        
        # Mark files older than the top 5 as archived
        valid_idx = 0
        for fi in file_info:
            fi['archived'] = False
            if fi['valid']:
                if valid_idx >= 5:
                    fi['archived'] = True
                valid_idx += 1

        if valid_count >= 5:
            status_color = SUCCESS
            total_archives = max(0, valid_count - 5)
            archive_str = f" ({total_archives} archived)" if total_archives > 0 else ""
            status_text = (f"{valid_count} quarter files detected{archive_str} "
                           "\u2014 ready to analyze")
            self._file_list_frame.configure(border_color=SUCCESS)
            self._run_btn.configure(state="normal")
        else:
            status_color = WARNING
            status_text = (f"{valid_count} valid files found "
                           "(minimum 5 required)")
            self._file_list_frame.configure(border_color=WARNING)
            self._run_btn.configure(state="disabled")

        ctk.CTkLabel(self._file_list_inner, text=status_text,
                     font=ctk.CTkFont(FONT, 12, "bold"),
                     text_color=status_color).pack(anchor="w", pady=(0, 10))

        for fi in file_info:
            row = ctk.CTkFrame(self._file_list_inner, fg_color="transparent",
                               height=28)
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)

            if fi['valid'] and not fi['archived']:
                icon_color, name_color = SUCCESS, TEXT
            elif fi['valid'] and fi['archived']:
                icon_color, name_color = TEXT_MUTED, TEXT_MUTED
            else:
                icon_color, name_color = DANGER, TEXT_MUTED

            ctk.CTkLabel(row, text="\u25cf", font=ctk.CTkFont(FONT, 10),
                         text_color=icon_color).pack(side="left", padx=(0, 8))
            
            display_name = fi['name']
            if fi['valid'] and fi['archived']:
                display_name += " [Archived]"
                
            ctk.CTkLabel(row, text=display_name,
                         font=ctk.CTkFont(FONT, 12, "bold" if (fi['valid'] and not fi['archived']) else "normal"),
                         text_color=name_color).pack(side="left")

            ctk.CTkLabel(row, text=f"{fi['size_mb']:.1f} MB",
                         font=ctk.CTkFont(MONO, 9),
                         text_color=TEXT_MUTED).pack(side="right")
            if fi['valid']:
                db = ctk.CTkFrame(row, fg_color=ACCENT_DIM, corner_radius=4)
                db.pack(side="right", padx=(8, 0))
                ctk.CTkLabel(db, text=fi['date_label'],
                             font=ctk.CTkFont(MONO, 9, "bold"),
                             text_color=ACCENT_SOFT).pack(padx=6, pady=1)
            ctk.CTkLabel(row, text=f"{fi['size_mb']:.1f} MB",
                         font=ctk.CTkFont(MONO, 9),
                         text_color=TEXT_MUTED).pack(side="right")

    def _start_run(self):
        self._show_processing_screen()
        threading.Thread(target=self._run_pipeline_thread, daemon=True).start()

    # ==================================================================
    #  SCREEN 2 \u2014 PROCESSING
    # ==================================================================
    def _show_processing_screen(self):
        self._clear_body()
        self._update_step(2)

        pad = ctk.CTkFrame(self._body, fg_color=BG)
        pad.pack(fill="both", expand=True, padx=32, pady=24)

        ctk.CTkLabel(pad, text="STEP 2 OF 3",
                     font=ctk.CTkFont(MONO, 10, "bold"),
                     text_color=ACCENT_SOFT).pack(anchor="w")

        top = ctk.CTkFrame(pad, fg_color="transparent")
        top.pack(fill="x", pady=(4, 0))

        status_row = ctk.CTkFrame(top, fg_color="transparent")
        status_row.pack(side="left")
        self._status_dot = ctk.CTkLabel(status_row, text="\u25cf",
                                        font=ctk.CTkFont(FONT, 13),
                                        text_color=WARNING)
        self._status_dot.pack(side="left", padx=(0, 8))
        self._status_label = ctk.CTkLabel(status_row, text="Processing",
                                          font=ctk.CTkFont(FONT, 18, "bold"),
                                          text_color=TEXT)
        self._status_label.pack(side="left")

        self._status_pulse = Pulse(self._status_dot, WARNING, TEXT_MUTED, 1000)
        self._status_pulse.start()

        # Elapsed timer
        self._elapsed_label = ctk.CTkLabel(
            top, text="00:00 elapsed",
            font=ctk.CTkFont(MONO, 11), text_color=TEXT_MUTED)
        self._elapsed_label.pack(side="right")
        self._elapsed_start = datetime.now()
        self._elapsed_running = True
        self._tick_elapsed()

        # Phase label
        self._phase_label = ctk.CTkLabel(
            pad, text="Loading files\u2026",
            font=ctk.CTkFont(FONT, 11), text_color=TEXT_MUTED)
        self._phase_label.pack(anchor="w", pady=(4, 0))

        # Progress bar
        track = ctk.CTkFrame(pad, fg_color=SURFACE2, corner_radius=3, height=6)
        track.pack(fill="x", pady=(12, 0))
        track.pack_propagate(False)
        self._progress = ctk.CTkProgressBar(
            track, height=6, fg_color=SURFACE2, progress_color=ACCENT,
            corner_radius=3)
        self._progress.pack(fill="both", expand=True)
        self._progress.set(0)
        self._progress.start()

        # Log card
        log_card = ctk.CTkFrame(pad, fg_color=SURFACE, corner_radius=14,
                                border_width=1, border_color=BORDER)
        log_card.pack(fill="both", expand=True, pady=(16, 0))
        log_header = ctk.CTkFrame(log_card, fg_color=SURFACE2,
                                  corner_radius=0, height=38)
        log_header.pack(fill="x", side="top")
        log_header.pack_propagate(False)
        lh_inner = ctk.CTkFrame(log_header, fg_color="transparent")
        lh_inner.pack(side="left", padx=14, pady=7)
        ctk.CTkLabel(lh_inner, text="ENGINE LOG",
                     font=ctk.CTkFont(MONO, 10, "bold"),
                     text_color=TEXT_SEC).pack(side="left")

        self._log_box = ctk.CTkTextbox(
            log_card, fg_color=SURFACE, text_color=TEXT_SEC,
            font=ctk.CTkFont(MONO, 11), activate_scrollbars=True,
            corner_radius=0, border_spacing=10)
        self._log_box.pack(fill="both", expand=True, padx=2, pady=(0, 2))
        self._log_box.configure(state="disabled")
        self._log_box.tag_config("ts", foreground=TEXT_MUTED)
        self._log_box.tag_config("log_warn", foreground=WARNING)
        self._log_box.tag_config("log_err", foreground=DANGER)
        self._log_box.tag_config("log_ok", foreground=SUCCESS)

        self._view_btn = HoverButton(
            pad, text="View Results",
            font=ctk.CTkFont(FONT, 14, "bold"),
            base_color=SURFACE3, hover_target=SURFACE3,
            corner_radius=12, height=46,
            command=self._show_results_screen, state="disabled")
        self._view_btn.pack(fill="x", pady=(16, 0))

    def _tick_elapsed(self):
        if not self._elapsed_running:
            return
        lbl = getattr(self, "_elapsed_label", None)
        if lbl is None or not lbl.winfo_exists():
            return
        elapsed = (datetime.now() - self._elapsed_start).total_seconds()
        mins, secs = int(elapsed // 60), int(elapsed % 60)
        try:
            lbl.configure(text=f"{mins:02d}:{secs:02d} elapsed")
        except Exception:
            return
        self.after(1000, self._tick_elapsed)

    def _append_log(self, msg: str):
        def _do():
            log_box = getattr(self, "_log_box", None)
            if log_box is None or not log_box.winfo_exists():
                return
            log_box.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            log_box.insert("end", f"  [{ts}]  ", "ts")
            ml = msg.lower()
            if "error" in ml:
                log_box.insert("end", f"{msg}\n", "log_err")
            elif "warning" in ml:
                log_box.insert("end", f"{msg}\n", "log_warn")
            elif "\u2713" in msg or "complete" in ml or "success" in ml:
                log_box.insert("end", f"{msg}\n", "log_ok")
            else:
                log_box.insert("end", f"{msg}\n")
            log_box.see("end")
            log_box.configure(state="disabled")
            # Update phase label
            pl = getattr(self, "_phase_label", None)
            if pl and pl.winfo_exists():
                if "scanning" in ml or "loading" in ml or "found" in ml:
                    pl.configure(text="Loading quarter files\u2026")
                elif "clean" in ml:
                    pl.configure(text="Cleaning & pivoting data\u2026")
                elif "tier 1" in ml:
                    pl.configure(text="Running Tier 1 \u2014 Tukey IQR Engine\u2026")
                elif "tier 2" in ml:
                    pl.configure(text="Running Tier 2 \u2014 Root Cause Diagnostics\u2026")
                elif "export" in ml or "sav" in ml:
                    pl.configure(text="Exporting results\u2026")
                elif "complete" in ml:
                    pl.configure(text="Analysis complete.")
        self.after(0, _do)

    def _run_pipeline_thread(self):
        from main import run_pipeline
        result = run_pipeline(self._selected_folder,
                              log_callback=self._append_log)

        def _finish():
            self._elapsed_running = False
            progress = getattr(self, "_progress", None)
            if progress is None or not progress.winfo_exists():
                self._result = result
                return
            self._progress.stop()
            if self._status_pulse:
                self._status_pulse.stop()
            if result:
                self._result = result
                self._progress.set(1)
                self._status_dot.configure(text_color=SUCCESS)
                self._status_label.configure(text="Analysis Complete",
                                             text_color=SUCCESS)
                self._view_btn.configure(
                    state="normal", fg_color=SUCCESS,
                    hover_color="#2ab383", text_color=BG)
                self._view_btn.base_color = SUCCESS
                self._view_btn.hover_target = "#2ab383"
            else:
                self._progress.set(0)
                self._status_dot.configure(text_color=DANGER)
                self._status_label.configure(
                    text="Analysis Failed \u2014 check log above",
                    text_color=DANGER)
        self.after(0, _finish)

    # ==================================================================
    #  SCREEN 3 \u2014 RESULTS
    # ==================================================================
    def _show_results_screen(self):
        self._clear_body()
        self._update_step(3)
        r  = self._result
        df = r['flagged_df']

        cause_clean = df['Root_Cause'].apply(
            lambda x: x.split(' (')[0] if '(' in x else x)
        self._df_display = df.copy()
        self._df_display['_cause_short'] = cause_clean

        scroll = ctk.CTkScrollableFrame(
            self._body, fg_color=BG,
            scrollbar_button_color=SURFACE3,
            scrollbar_button_hover_color=BORDER)
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        pad = ctk.CTkFrame(scroll, fg_color="transparent")
        pad.pack(fill="x", padx=32, pady=(20, 32))

        ctk.CTkLabel(pad, text="STEP 3 OF 3",
                     font=ctk.CTkFont(MONO, 10, "bold"),
                     text_color=ACCENT_SOFT).pack(anchor="w", pady=(0, 4))

        # ---- Quarter Timeline ------------------------------------------------
        quarter_cols = r.get('quarter_cols', [])
        if quarter_cols:
            tl_card = ctk.CTkFrame(pad, fg_color=SURFACE, corner_radius=12,
                                   border_width=1, border_color=BORDER)
            tl_card.pack(fill="x", pady=(0, 16))
            tl_inner = ctk.CTkFrame(tl_card, fg_color="transparent")
            tl_inner.pack(padx=20, pady=14)
            ctk.CTkLabel(tl_inner, text="ANALYSIS WINDOW",
                         font=ctk.CTkFont(MONO, 9, "bold"),
                         text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 8))
            tl_row = ctk.CTkFrame(tl_inner, fg_color="transparent")
            tl_row.pack(anchor="w")
            for i, qc in enumerate(quarter_cols):
                is_target = (i == len(quarter_cols) - 1)
                q_label = _format_quarter_label(qc)
                if is_target:
                    qb = ctk.CTkFrame(tl_row, fg_color=ACCENT_DIM,
                                      corner_radius=6, border_width=1,
                                      border_color=ACCENT)
                    qb.pack(side="left")
                    ctk.CTkLabel(qb, text=f"\u25b6 {q_label}",
                                 font=ctk.CTkFont(MONO, 11, "bold"),
                                 text_color=ACCENT_SOFT).pack(padx=10, pady=4)
                    Tooltip(qb, "Target Quarter (Q5)")
                else:
                    ctk.CTkLabel(tl_row, text=q_label,
                                 font=ctk.CTkFont(MONO, 11),
                                 text_color=TEXT_SEC).pack(side="left")
                if i < len(quarter_cols) - 1:
                    ctk.CTkLabel(tl_row, text="  \u2192  ",
                                 font=ctk.CTkFont(FONT, 11),
                                 text_color=TEXT_MUTED).pack(side="left")

        # ---- KPI Cards -------------------------------------------------------
        self._section_header(pad, "Overview")
        kpi_row = ctk.CTkFrame(pad, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(0, 8))
        for i in range(5):
            kpi_row.columnconfigure(i, weight=1, uniform="kpi")

        top_cause   = cause_clean.value_counts().idxmax()
        top_cause_n = cause_clean.value_counts().max()
        flag_rate   = (r['flagged_count'] / r['total_branches']) * 100

        kpi_icons = ["\U0001f4ca", "\u26a0", "\U0001f4c8", "\U0001f53a"]
        numeric_kpis = [
            ("Branches Analysed", r['total_branches'],
             lambda v: f"{int(round(v)):,}", ACCENT, ACCENT_DIM),
            ("Anomalies Flagged", r['flagged_count'],
             lambda v: f"{int(round(v))}", DANGER, DANGER_DIM),
            ("Flagged Rate", flag_rate,
             lambda v: f"{v:.2f}%", WARNING, WARNING_DIM),
            ("Peak Severity", r['severity_max'],
             lambda v: f"{v:.2f}", ACCENT, ACCENT_DIM),
        ]

        self._kpi_cards = []
        count_labels = []
        for i, (label, target, fmt, color, dim) in enumerate(numeric_kpis):
            shadow = ctk.CTkFrame(kpi_row, fg_color=BG2, corner_radius=16)
            shadow.grid(row=0, column=i, padx=5, pady=4, sticky="nsew")
            card = ctk.CTkFrame(shadow, fg_color=SURFACE, corner_radius=14,
                                border_width=1, border_color=BORDER)
            card.pack(fill="both", expand=True, padx=1, pady=(0, 2))
            self._kpi_cards.append(card)
            ctk.CTkFrame(card, fg_color=dim, height=4,
                         corner_radius=0).pack(fill="x", side="top")
            ctk.CTkLabel(card, text=kpi_icons[i],
                         font=ctk.CTkFont(FONT, 14),
                         text_color=TEXT_MUTED).pack(padx=16, pady=(12, 0))
            vl = CountUpLabel(card, target_value=target, formatter=fmt,
                              font=ctk.CTkFont(FONT, 22, "bold"),
                              text_color=color)
            vl.pack(padx=16, pady=(4, 2))
            count_labels.append(vl)
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(FONT, 11),
                         text_color=TEXT_MUTED).pack(padx=16, pady=(0, 14))

        # Fifth card: Top Root Cause
        tc_color = CAUSE_COLORS.get(top_cause, TEXT)
        tc_dim   = CAUSE_DIM.get(top_cause, SURFACE2)
        shadow5 = ctk.CTkFrame(kpi_row, fg_color=BG2, corner_radius=16)
        shadow5.grid(row=0, column=4, padx=5, pady=4, sticky="nsew")
        tc_card = ctk.CTkFrame(shadow5, fg_color=SURFACE, corner_radius=14,
                               border_width=1, border_color=BORDER)
        tc_card.pack(fill="both", expand=True, padx=1, pady=(0, 2))
        self._kpi_cards.append(tc_card)
        ctk.CTkFrame(tc_card, fg_color=tc_dim, height=4,
                     corner_radius=0).pack(fill="x", side="top")
        ctk.CTkLabel(tc_card, text="\U0001f3f7",
                     font=ctk.CTkFont(FONT, 14),
                     text_color=TEXT_MUTED).pack(padx=12, pady=(12, 0))
        ctk.CTkLabel(tc_card, text=top_cause,
                     font=ctk.CTkFont(FONT, 17, "bold"), text_color=tc_color,
                     wraplength=150, justify="center"
                     ).pack(padx=12, pady=(4, 0))
        ctk.CTkLabel(tc_card,
                     text=f"{top_cause_n} of {r['flagged_count']} flagged",
                     font=ctk.CTkFont(FONT, 10),
                     text_color=TEXT_MUTED).pack(padx=12, pady=(2, 2))
        ctk.CTkLabel(tc_card, text="Top Root Cause",
                     font=ctk.CTkFont(FONT, 11),
                     text_color=TEXT_MUTED).pack(padx=16, pady=(0, 14))

        StaggeredReveal(self, self._kpi_cards,
                        delay_between=70, duration=300).run()
        for i, lbl in enumerate(count_labels):
            lbl.animate(start_delay=i * 70)

        # ---- Charts ----------------------------------------------------------
        self._section_header(pad, "Distribution")
        chart_row = ctk.CTkFrame(pad, fg_color="transparent")
        chart_row.pack(fill="x", pady=(0, 8))
        chart_row.columnconfigure(0, weight=4)
        chart_row.columnconfigure(1, weight=6)

        ds = ctk.CTkFrame(chart_row, fg_color=BG2, corner_radius=16)
        ds.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        dc = ctk.CTkFrame(ds, fg_color=SURFACE, corner_radius=14,
                          border_width=1, border_color=BORDER)
        dc.pack(fill="both", expand=True, padx=1, pady=(0, 2))
        donut_img = self._render_donut(cause_clean)
        ctk.CTkLabel(dc, image=donut_img, text="").pack(padx=12, pady=12)

        bs = ctk.CTkFrame(chart_row, fg_color=BG2, corner_radius=16)
        bs.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
        bc = ctk.CTkFrame(bs, fg_color=SURFACE, corner_radius=14,
                          border_width=1, border_color=BORDER)
        bc.pack(fill="both", expand=True, padx=1, pady=(0, 2))
        bar_img = self._render_bar(df)
        ctk.CTkLabel(bc, image=bar_img, text="").pack(padx=12, pady=12)

        self._chart_refs = [donut_img, bar_img]

        # ---- Table -----------------------------------------------------------
        self._section_header(
            pad, f"All Flagged Branches ({r['flagged_count']})")
        ctrl_row = ctk.CTkFrame(pad, fg_color="transparent")
        ctrl_row.pack(fill="x", pady=(0, 8))

        self._search_var = tk.StringVar()
        sw = ctk.CTkFrame(ctrl_row, fg_color=SURFACE, corner_radius=10,
                          border_width=1, border_color=BORDER)
        sw.pack(side="left")
        ctk.CTkLabel(sw, text="\U0001f50d", font=ctk.CTkFont(FONT, 11),
                     text_color=TEXT_MUTED).pack(side="left", padx=(12, 4))
        ctk.CTkEntry(sw, textvariable=self._search_var,
                     placeholder_text="Search branches, root cause\u2026",
                     font=ctk.CTkFont(FONT, 12), fg_color="transparent",
                     border_width=0, text_color=TEXT,
                     corner_radius=0, height=36, width=260
                     ).pack(side="left", padx=(0, 10))
        self._search_var.trace_add("write", self._filter_table)

        self._peer_var = tk.StringVar(value="All Peers")
        peer_opts = (["All Peers"]
                     + [f"Group {i}" for i in range(10)]
                     + ["MERGED_SMALL_GROUPS"])
        ctk.CTkOptionMenu(
            ctrl_row, variable=self._peer_var, values=peer_opts,
            font=ctk.CTkFont(FONT, 11), fg_color=SURFACE,
            button_color=SURFACE2, button_hover_color=SURFACE3,
            text_color=TEXT, dropdown_fg_color=SURFACE, width=130,
            command=self._filter_table).pack(side="left", padx=(10, 0))

        self._dir_var = tk.StringVar(value="All Directions")
        ctk.CTkOptionMenu(
            ctrl_row, variable=self._dir_var,
            values=["All Directions", "Surge Only", "Collapse Only"],
            font=ctk.CTkFont(FONT, 11), fg_color=SURFACE,
            button_color=SURFACE2, button_hover_color=SURFACE3,
            text_color=TEXT, dropdown_fg_color=SURFACE, width=140,
            command=self._filter_table).pack(side="left", padx=(8, 0))

        self._result_count_label = ctk.CTkLabel(
            ctrl_row, text=f"{len(self._df_display)} results",
            font=ctk.CTkFont(FONT, 11), text_color=TEXT_MUTED)
        self._result_count_label.pack(side="left", padx=(12, 0))

        # Treeview
        tc = ctk.CTkFrame(pad, fg_color=SURFACE, corner_radius=14,
                          border_width=1, border_color=BORDER)
        tc.pack(fill="x")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("App.Treeview", background=SURFACE,
                        fieldbackground=SURFACE, foreground=TEXT,
                        rowheight=36, font=(FONT, 11), borderwidth=0)
        style.configure("App.Treeview.Heading", background=SURFACE2,
                        foreground=TEXT_SEC, font=(FONT, 10, "bold"),
                        borderwidth=0, relief="flat")
        style.map("App.Treeview",
                  background=[("selected", ACCENT_DIM)],
                  foreground=[("selected", TEXT)])
        style.map("App.Treeview.Heading",
                  background=[("active", SURFACE3)])
        style.layout("App.Treeview",
                     [('Treeview.treearea', {'sticky': 'nswe'})])

        self._has_bank_col = 'Bank Name' in df.columns
        self._has_state_col = 'State' in df.columns
        if self._has_bank_col and self._has_state_col:
            cols = ("Branch Code", "Bank Name", "State", "Peer Group",
                    "Severity Score", "Share Shift %", "Root Cause",
                    "Direction")
            col_w = [110, 150, 110, 85, 105, 105, 155, 95]
        elif self._has_bank_col:
            cols = ("Branch Code", "Bank Name", "Peer Group",
                    "Severity Score", "Share Shift %", "Root Cause",
                    "Direction")
            col_w = [120, 170, 100, 115, 115, 165, 100]
        else:
            cols = ("Branch Code", "Peer Group", "Severity Score",
                    "Share Shift %", "Root Cause", "Direction")
            col_w = [140, 110, 140, 130, 180, 110]

        self._tree = ttk.Treeview(tc, columns=cols, show="headings",
                                  style="App.Treeview", height=16)
        self._sort_col = None
        for col, w in zip(cols, col_w):
            self._tree.heading(col, text=col,
                               command=lambda c=col: self._sort_tree(c))
            self._tree.column(col, width=w, anchor="center", minwidth=60)

        vsb = ctk.CTkScrollbar(tc, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True,
                        padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", padx=(0, 4), pady=8)

        self._tree.tag_configure("surge",    foreground=SUCCESS)
        self._tree.tag_configure("collapse", foreground=DANGER)
        self._tree.tag_configure("na",       foreground=TEXT_MUTED)
        self._tree.tag_configure("odd",      background=SURFACE)
        self._tree.tag_configure("even",     background=SURFACE2)

        self._populate_tree(self._df_display)
        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)

        # Detail panel
        self._detail_frame = ctk.CTkFrame(
            pad, fg_color=SURFACE, corner_radius=14,
            border_width=1, border_color=BORDER)
        self._detail_frame.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(
            self._detail_frame,
            text="Select a branch above to view the full account breakdown",
            text_color=TEXT_MUTED, font=ctk.CTkFont(FONT, 12)).pack(pady=24)

        # ---- Export ----------------------------------------------------------
        self._section_header(pad, "Export")
        dl_row = ctk.CTkFrame(pad, fg_color="transparent")
        dl_row.pack(fill="x")

        HoverButton(
            dl_row, text="Open Full Report  (All Branches)",
            font=ctk.CTkFont(FONT, 13, "bold"),
            base_color=SURFACE2, hover_target=SURFACE3,
            border_width=1, border_color=BORDER,
            text_color=TEXT, corner_radius=10, height=44, width=320,
            command=lambda: os.startfile(r['output_full'])
        ).pack(side="left", padx=(0, 10))

        HoverButton(
            dl_row, text="Open Top 10 Report",
            font=ctk.CTkFont(FONT, 13, "bold"),
            base_color=ACCENT, hover_target=ACCENT_HOVER,
            text_color="white", corner_radius=10, height=44, width=240,
            command=lambda: os.startfile(r['output_top10'])
        ).pack(side="left", padx=4)

        HoverButton(
            dl_row, text="New Analysis",
            font=ctk.CTkFont(FONT, 12),
            base_color="transparent", hover_target=SURFACE2,
            border_width=1, border_color=BORDER,
            text_color=TEXT_SEC, corner_radius=10, height=44, width=160,
            command=self._show_upload_screen
        ).pack(side="right")

    # ------------------------------------------------------------------
    #  Chart renderers
    # ------------------------------------------------------------------
    def _render_donut(self, cause_series):
        rc = cause_series.value_counts()
        fig, ax = plt.subplots(figsize=(4.5, 3.6), facecolor=SURFACE)
        ax.set_facecolor(SURFACE)
        colors = [CAUSE_COLORS.get(k, TEXT_MUTED) for k in rc.index]
        wedges, _, autotexts = ax.pie(
            rc.values, labels=None, colors=colors,
            autopct="%1.0f%%", startangle=90, pctdistance=0.80,
            radius=1.0,
            wedgeprops=dict(width=0.38, edgecolor=SURFACE, linewidth=3))
        for at in autotexts:
            at.set_color("#ffffff"); at.set_fontsize(8.5)
            at.set_fontweight("bold")
        ax.text(0, 0.10, f"{rc.sum()}", ha="center", va="center",
                fontsize=19, fontweight="bold", color=TEXT, zorder=5)
        ax.text(0, -0.14, "TOTAL FLAGGED", ha="center", va="center",
                fontsize=7, color=TEXT_MUTED, fontweight="bold", zorder=5)
        patches = [mpatches.Patch(color=CAUSE_COLORS.get(k, TEXT_MUTED),
                                  label=f"{k}  ({v})")
                   for k, v in rc.items()]
        ax.legend(handles=patches, loc="lower center",
                  bbox_to_anchor=(0.5, -0.16), ncol=2, frameon=False,
                  labelcolor=TEXT_SEC, fontsize=8.5,
                  handletextpad=0.5, columnspacing=1.2)
        ax.set_title("Root Cause Breakdown", color=TEXT, fontsize=12,
                     fontweight="bold", pad=14, loc="left")
        return _fig_to_ctk_image(fig, 420, 340)

    def _render_bar(self, df):
        pg = df['Peer_Group'].value_counts().sort_index()
        fig, ax = plt.subplots(figsize=(6, 3.6), facecolor=SURFACE)
        ax.set_facecolor(SURFACE)
        x_pos = range(len(pg))
        max_v = pg.values.max() if len(pg.values) else 1
        bar_colors = [WARNING if v >= max_v * 0.75 else ACCENT
                      for v in pg.values]
        bars = ax.bar(x_pos, pg.values, color=bar_colors,
                      edgecolor=SURFACE, linewidth=1.5, width=0.55, zorder=3)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(pg.index.astype(str))
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.4,
                    str(int(h)), ha='center', va='bottom',
                    color=TEXT, fontsize=9, fontweight='bold')
        ax.set_xlabel("Peer Group  (0 = Smallest,  9 = Largest)",
                      color=TEXT_MUTED, fontsize=9, labelpad=8)
        ax.set_ylabel("Flagged", color=TEXT_MUTED, fontsize=9)
        ax.set_title("Anomalies by Peer Group", color=TEXT, fontsize=12,
                     fontweight="bold", pad=14, loc="left")
        ax.tick_params(colors=TEXT_MUTED, length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.yaxis.grid(True, color=BORDER, linewidth=0.5, alpha=0.5)
        ax.set_axisbelow(True)
        return _fig_to_ctk_image(fig, 560, 340)

    # ------------------------------------------------------------------
    #  Table helpers
    # ------------------------------------------------------------------
    def _populate_tree(self, df):
        self._tree.delete(*self._tree.get_children())
        for idx, (_, row) in enumerate(df.iterrows()):
            cause = str(row.get('_cause_short', row.get('Root_Cause', '')))
            dirn  = str(row.get('Direction', 'N/A'))
            dir_tag = ("surge" if dirn == "Surge"
                       else ("collapse" if dirn == "Collapse" else "na"))
            zebra = "even" if idx % 2 == 0 else "odd"
            sev   = row.get('Severity_Score', 0)
            share = row.get('Share_Shift', 0)
            vals = [str(row.get('Branch_Code', ''))]
            if self._has_bank_col:
                vals.append(str(row.get('Bank Name', '')))
            if self._has_state_col:
                vals.append(str(row.get('State', '')))
            vals.extend([
                str(row.get('Peer_Group', '')),
                f"{sev:.2f}" if isinstance(sev, float) else str(sev),
                f"{share:.4f}%" if isinstance(share, float) else str(share),
                cause, dirn,
            ])
            self._tree.insert("", "end", values=tuple(vals),
                              tags=(dir_tag, zebra))
        if hasattr(self, "_result_count_label"):
            self._result_count_label.configure(text=f"{len(df)} results")

    def _filter_table(self, *_):
        q    = self._search_var.get().lower()
        peer = self._peer_var.get()
        dirn = self._dir_var.get()
        dff  = self._df_display

        if peer != "All Peers":
            if peer.startswith("Group "):
                grp = peer.split(" ")[1]
                dff = dff[dff['Peer_Group'].astype(str) == grp]
            else:
                dff = dff[dff['Peer_Group'].astype(str) == peer]
        if dirn == "Surge Only":
            dff = dff[dff['Direction'] == "Surge"]
        elif dirn == "Collapse Only":
            dff = dff[dff['Direction'] == "Collapse"]
        if q:
            mask = dff.apply(
                lambda row: any(q in str(v).lower() for v in row.values),
                axis=1)
            dff = dff[mask]
        self._populate_tree(dff)

    def _sort_tree(self, col):
        col_map = {
            "Branch Code"   : "Branch_Code",
            "Bank Name"     : "Bank Name",
            "State"         : "State",
            "Peer Group"    : "Peer_Group",
            "Severity Score": "Severity_Score",
            "Share Shift %" : "Share_Shift",
            "Root Cause"    : "_cause_short",
            "Direction"     : "Direction",
        }
        key = col_map.get(col)
        if key and key in self._df_display.columns:
            if self._sort_col == col:
                self._sort_asc = not self._sort_asc
            else:
                self._sort_asc = True
                self._sort_col = col
            self._df_display = self._df_display.sort_values(
                key, ascending=self._sort_asc)
            self._populate_tree(self._df_display)
            self._refresh_sort_indicators(col_map)

    def _refresh_sort_indicators(self, cols_map):
        arrow = " \u25b2" if self._sort_asc else " \u25bc"
        for label in cols_map:
            try:
                text = label + (arrow if label == self._sort_col else "")
                self._tree.heading(label, text=text)
            except Exception:
                pass

    # ------------------------------------------------------------------
    #  Row detail (account breakdown)
    # ------------------------------------------------------------------
    def _on_row_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        branch_code = self._tree.item(sel[0], "values")[0]
        matches = self._df_display[
            self._df_display['Branch_Code'].astype(str) == branch_code]
        if matches.empty:
            return
        row = matches.iloc[0]

        for w in self._detail_frame.winfo_children():
            w.destroy()

        direction = str(row.get('Direction', 'N/A'))
        dir_color = (SUCCESS if direction == "Surge"
                     else (DANGER if direction == "Collapse" else TEXT_MUTED))
        dir_icon  = ("\u25b2" if direction == "Surge"
                     else ("\u25bc" if direction == "Collapse" else "\u2022"))

        # Header
        hdr = ctk.CTkFrame(self._detail_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(hdr, text=f"Branch {branch_code}",
                     font=ctk.CTkFont(FONT, 14, "bold"),
                     text_color=TEXT).pack(side="left")
        sev_val = row.get('Severity_Score', None)
        if sev_val is not None:
            sev_text = (f"  \u00b7  Severity {sev_val:.2f}"
                        if isinstance(sev_val, float)
                        else f"  \u00b7  Severity {sev_val}")
            ctk.CTkLabel(hdr, text=sev_text,
                         font=ctk.CTkFont(FONT, 12),
                         text_color=TEXT_MUTED).pack(side="left")
        dir_badge = ctk.CTkFrame(hdr, fg_color=(
            SUCCESS_DIM if direction == "Surge"
            else (DANGER_DIM if direction == "Collapse" else SURFACE2)),
            corner_radius=8)
        dir_badge.pack(side="right")
        ctk.CTkLabel(dir_badge, text=f" {dir_icon} {direction} ",
                     font=ctk.CTkFont(FONT, 11, "bold"),
                     text_color=dir_color).pack(padx=10, pady=4)

        # Metadata row (Bank Name, State, District, Population Group)
        meta_fields = [
            ('Bank Name', 'Bank Name'), ('Bank Group Name', 'Bank Group'),
            ('State', 'State'), ('District', 'District'),
            ('Population Group Name', 'Population'),
        ]
        meta_items = [(lbl, str(row.get(col, '')))
                      for col, lbl in meta_fields
                      if col in row.index
                      and str(row.get(col, '')) not in ('', 'nan', 'None')]
        if meta_items:
            mr = ctk.CTkFrame(self._detail_frame, fg_color=SURFACE2,
                              corner_radius=8)
            mr.pack(fill="x", padx=20, pady=(4, 4))
            mi = ctk.CTkFrame(mr, fg_color="transparent")
            mi.pack(padx=12, pady=8)
            for j, (lbl, val) in enumerate(meta_items):
                if j > 0:
                    ctk.CTkLabel(mi, text="\u00b7",
                                 font=ctk.CTkFont(FONT, 10),
                                 text_color=TEXT_MUTED
                                 ).pack(side="left", padx=8)
                ctk.CTkLabel(mi, text=f"{lbl}: ",
                             font=ctk.CTkFont(FONT, 10),
                             text_color=TEXT_MUTED).pack(side="left")
                ctk.CTkLabel(mi, text=val,
                             font=ctk.CTkFont(FONT, 10, "bold"),
                             text_color=TEXT_SEC).pack(side="left")

        # Account table
        acc_cols_map = {}
        for acc in ['Current', 'Savings', 'Term']:
            acc_cols_map[acc] = [c for c in self._df_display.columns
                                 if c.startswith(f"{acc}_")
                                 and "(Crores)" in c]
        root_cause = str(row.get('_cause_short', ''))

        grid = ctk.CTkFrame(self._detail_frame, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=(8, 20))
        for r_idx, (acc, cols) in enumerate(acc_cols_map.items()):
            is_root = (acc == root_cause)
            bg = CAUSE_DIM.get(acc, SURFACE2) if is_root else "transparent"
            fg = CAUSE_COLORS.get(acc, TEXT) if is_root else TEXT_MUTED
            rf = ctk.CTkFrame(grid, fg_color=bg, corner_radius=10,
                              border_width=1 if is_root else 0,
                              border_color=CAUSE_COLORS.get(acc, BORDER))
            rf.grid(row=r_idx, column=0, columnspan=20,
                    sticky="ew", pady=3, padx=0)
            grid.grid_columnconfigure(0, weight=1)
            name_txt = f"{'\u2605  ' if is_root else '    '}{acc}"
            ctk.CTkLabel(rf, text=name_txt, width=100,
                         font=ctk.CTkFont(FONT, 12,
                                          "bold" if is_root else "normal"),
                         text_color=fg
                         ).grid(row=0, column=0, padx=(14, 20), pady=10)
            for c_idx, col in enumerate(cols):
                val = row.get(col, 0)
                q_label = col.replace(f"{acc}_", "").replace(" (Crores)", "")
                is_last = (c_idx == len(cols) - 1)
                cell_fg = (ACCENT if is_last and is_root
                           else (TEXT if is_last else TEXT_SEC))
                ctk.CTkLabel(
                    rf, text=f"{q_label}\n{val:,}",
                    font=ctk.CTkFont(MONO, 10,
                                     "bold" if is_last else "normal"),
                    text_color=cell_fg, justify="center"
                ).grid(row=0, column=c_idx + 1, padx=14, pady=10)

        if root_cause not in acc_cols_map:
            ctk.CTkLabel(
                self._detail_frame,
                text=(f'Root cause flagged as "{root_cause}" '
                      '\u2014 see report for detail.'),
                font=ctk.CTkFont(FONT, 11), text_color=TEXT_MUTED
            ).pack(anchor="w", padx=20, pady=(0, 16))

    # ------------------------------------------------------------------
    #  UI Utilities
    # ------------------------------------------------------------------
    def _section_header(self, parent, title):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(28, 10))
        ctk.CTkLabel(row, text="\u25cf", font=ctk.CTkFont(FONT, 7),
                     text_color=ACCENT).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row, text=title,
                     font=ctk.CTkFont(FONT, 14, "bold"),
                     text_color=TEXT_SEC).pack(side="left")
        ctk.CTkFrame(row, fg_color=BORDER, height=1).pack(
            side="left", fill="x", expand=True, padx=(12, 0), pady=1)


# ==============================================================================
#  Entry Point
# ==============================================================================
if __name__ == "__main__":
    app = App()
    app.mainloop()