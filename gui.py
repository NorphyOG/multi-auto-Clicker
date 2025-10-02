"""
Graphical user interface for the Multi Auto Clicker application.

Key capabilities
----------------
- Manage static position lists and a follow-cursor mode
- Capture click targets by selecting the next mouse click on screen
- Persist user preferences (rate, total clicks, mode, hotkeys, etc.)
- Visualise click targets with an overlay debug mode (multi-monitor safe)
- Provide a dedicated automation tab for background execution
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
from typing import Optional, List, Dict, Any, Tuple
import sys
import os
import shutil

import pyautogui

from models import (
    ApplicationSettings,
    ClickConfiguration,
    ClickMode,
    ClickPosition,
    ClickType,
    ClickerState,
)
from clicker_engine import AutoClickerEngine
from automation import AutomationEngine, AutomationScript
from click_capture import ClickCaptureService
from debug_overlay import DebugOverlayManager
from hotkey_manager import HotkeyManager
from logger import StatusLogger
from settings_manager import SettingsManager


class AutoClickerGUI:
    """Tkinter based GUI that orchestrates all application services."""

    MONITOR_POLL_MS = 400
    CLICK_COUNTER_POLL_MS = 120
    DEFAULT_WINDOW_SIZE = (1150, 1000)
    MIN_WINDOW_SIZE = (960, 760)
    WINDOW_MARGIN = (48, 80)

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Multi Auto Clicker")
        self._configure_window_geometry()

        self.settings_manager = SettingsManager()
        self.settings: ApplicationSettings = self.settings_manager.load()

        self.style = ttk.Style()
        self.dark_mode_var = tk.BooleanVar(value=getattr(self.settings, "dark_mode_enabled", False))
        self._configure_styles()
        self._apply_theme()

        # Runtime state --------------------------------------------------
        self.click_positions: List[ClickPosition] = list(self.settings.click_positions)
        self.engine: Optional[AutoClickerEngine] = None
        self.automation_engine: Optional[AutoClickerEngine] = None
        self.script_engine: Optional[AutomationEngine] = None
        self.logger = StatusLogger()
        self.hotkey_manager = HotkeyManager(
            start_hotkey=self.settings.start_hotkey, stop_hotkey=self.settings.stop_hotkey
        )
        self.debug_overlay = DebugOverlayManager(root)
        self.capture_service = ClickCaptureService(root)

        self._persist_suspended = True
        self.manual_update_job: Optional[str] = None
        self.automation_update_job: Optional[str] = None
        self.monitor_job: Optional[str] = None
        self.capture_in_progress = False
        self._cps_tracker: Dict[str, Dict[str, float]] = {}

        # Tk variables ---------------------------------------------------
        self.click_mode_var = tk.StringVar(value=self.settings.click_mode.value)
        self.click_rate_var = tk.DoubleVar(value=self.settings.click_rate_per_second)
        self.total_clicks_var = tk.IntVar(value=self.settings.total_clicks)
        self.click_type_var = tk.StringVar(value=self.settings.click_type.value)
        self.background_var = tk.BooleanVar(value=self.settings.run_in_background)
        self.debug_overlay_var = tk.BooleanVar(value=self.settings.debug_overlay_enabled)
        self.start_hotkey_var = tk.StringVar(value=self.settings.start_hotkey)
        self.stop_hotkey_var = tk.StringVar(value=self.settings.stop_hotkey)
        self.capture_status_var = tk.StringVar(value="Bereit für Positionsaufnahme.")
        self.status_var = tk.StringVar(value="Status: Bereit")
        self.automation_status_var = tk.StringVar(value="Automatisierung: Bereit")
        self.click_count_var = tk.StringVar(value="Ausgeführte Klicks: 0")
        self.automation_clicks_var = tk.StringVar(value="Klicks (Automatisierung): 0")
        self.manual_cps_var = tk.StringVar(value="Aktuelle CPS: 0.00")
        self.automation_cps_var = tk.StringVar(value="CPS (Automatisierung): 0.00")
        self.script_status_var = tk.StringVar(value="Script: Bereit")
        # Script-Builder (no-code) state
        self.script_actions: List[Dict[str, Any]] = []
        self.builder_action_type = tk.StringVar(value="type_text")
        self.builder_text_var = tk.StringVar(value="Hello from Script!")
        self.builder_sequence_var = tk.StringVar(value="<ENTER>")
        self.builder_wait_ms_var = tk.IntVar(value=300)
        self.builder_command_var = tk.StringVar(value="notepad.exe")
        self.builder_args_var = tk.StringVar(value="")
        self.builder_title_var = tk.StringVar(value="")
        self.builder_template_var = tk.StringVar(value="Vorlage wählen…")
        # Mouse/Scroll builder vars
        self.builder_click_x_var = tk.StringVar(value="")  # allow blank for current cursor
        self.builder_click_y_var = tk.StringVar(value="")
        self.builder_click_button_var = tk.StringVar(value="left")
        self.builder_click_count_var = tk.IntVar(value=1)
        self.builder_scroll_amount_var = tk.IntVar(value=300)
        self.builder_scroll_horizontal_var = tk.BooleanVar(value=False)
        self.builder_autosync_var = tk.BooleanVar(value=True)
        # Loop builder vars
        self.builder_repeat_count_var = tk.IntVar(value=1)
        self.builder_until_stopped_var = tk.BooleanVar(value=False)
        # Builder window/widget placeholders (created on demand)
        self._builder_win = None
        self._fld_text = None
        self._fld_seq = None
        self._fld_wait = None
        self._fld_cmd = None
        self._fld_args = None
        self._fld_title = None
        self.script_actions_listbox = None
        self._builder_context_menu = None
        self.monitor_info_var = tk.StringVar(value="Cursor: (0, 0) | Bildschirm 1")
        self.automation_minimize_var = tk.BooleanVar(value=True)
        self.automation_infinite_var = tk.BooleanVar(value=True)
        self.position_count_var = tk.StringVar(value="")
        self.click_interval_hint_var = tk.StringVar(value="")
        self.estimated_duration_var = tk.StringVar(value="")
        # Builder capture state
        self._builder_capture_in_progress = False

        # Autosync traces for loop fields
        try:
            self.builder_repeat_count_var.trace_add("write", lambda *_: self._builder_maybe_autosync())
            self.builder_until_stopped_var.trace_add("write", lambda *_: self._builder_maybe_autosync())
        except Exception:
            pass

        self.click_rate_var.trace_add("write", lambda *_: self._update_click_metrics())
        self.total_clicks_var.trace_add("write", lambda *_: self._update_click_metrics())
        self._update_click_metrics()

        # UI --------------------------------------------------------------
        self._build_ui()
        self._apply_theme()
        self._refresh_position_list()
        self._on_click_mode_changed()
        self.debug_overlay.set_positions(self.click_positions)
        self.debug_overlay.toggle(self.debug_overlay_var.get())

        # Platform-specific hints (Linux/Wayland, missing tools)
        self._check_platform_hints()

        # Services -------------------------------------------------------
        self._setup_hotkeys()
        self._start_monitor_updates()

        self._persist_suspended = False
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _configure_window_geometry(self) -> None:
        """Adapt the main window to the active monitor resolution."""
        # Try to use virtual screen across all monitors if available
        screen_bounds = self._get_virtual_screen_bounds()
        screen_width = max(int(screen_bounds[2]), 1)
        screen_height = max(int(screen_bounds[3]), 1)
        margin_x, margin_y = self.WINDOW_MARGIN

        usable_width = max(screen_width - margin_x, 720)
        usable_height = max(screen_height - margin_y, 640)

        default_width, default_height = self.DEFAULT_WINDOW_SIZE
        min_width, min_height = self.MIN_WINDOW_SIZE

        width = min(default_width, usable_width)
        height = min(default_height, usable_height)

        width = max(width, min(min_width, usable_width))
        height = max(height, min(min_height, usable_height))

        x = max((screen_width - width) // 2 + int(screen_bounds[0]), int(screen_bounds[0]))
        y = max((screen_height - height) // 2 + int(screen_bounds[1]), int(screen_bounds[1]))

        self.root.geometry(f"{int(width)}x{int(height)}+{int(x)}+{int(y)}")

        self.root.minsize(int(width), int(height))

        allow_resize = width < default_width or height < default_height
        self.root.resizable(allow_resize, allow_resize)

    def _get_virtual_screen_bounds(self) -> Tuple[int, int, int, int]:
        """Return (x, y, width, height) spanning all monitors if possible."""
        try:
            from screeninfo import get_monitors  # type: ignore
            mons = get_monitors()
            if not mons:
                raise RuntimeError()
            min_x = min(m.x for m in mons)
            min_y = min(m.y for m in mons)
            max_r = max(m.x + m.width for m in mons)
            max_b = max(m.y + m.height for m in mons)
            return int(min_x), int(min_y), int(max_r - min_x), int(max_b - min_y)
        except Exception:
            # Fallback to Tk single screen
            try:
                w = int(self.root.winfo_screenwidth())
                h = int(self.root.winfo_screenheight())
                return 0, 0, w, h
            except Exception:
                return 0, 0, 1280, 800

    def _configure_styles(self) -> None:
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        base_font = ("Segoe UI", 10)
        heading_font = ("Segoe UI", 15, "bold")
        subheading_font = ("Segoe UI", 10)

        self.style.configure(".", font=base_font)
        self.style.configure("Header.TLabel", font=heading_font)
        self.style.configure("HeaderSubtitle.TLabel", font=subheading_font)
        self.style.configure("Card.TLabelframe", borderwidth=1, relief="solid")
        self.style.configure("Card.TLabelframe.Label", font=("Segoe UI", 11, "bold"))
        self.style.configure("CardBody.TFrame")
        self.style.configure("AccentCard.TLabelframe", borderwidth=1, relief="solid")
        self.style.configure("AccentCard.TLabelframe.Label", font=("Segoe UI", 11, "bold"))
        self.style.configure("AccentCardLabel.TLabel")
        self.style.configure("AccentCardHint.TLabel", font=("Segoe UI", 9))
        self.style.configure("App.TNotebook", borderwidth=0, padding=0)
        self.style.configure("App.TNotebook.Tab", padding=(16, 8), font=("Segoe UI", 10, "bold"))
        self.style.configure("Toolbar.TButton", padding=(8, 6))
        self.style.configure("Accent.TButton", padding=(10, 7), borderwidth=0)
        self.style.configure("Danger.TButton", padding=(10, 7), borderwidth=0)
        self.style.configure("Ghost.TButton", padding=(8, 6), borderwidth=0)
        self.style.configure("AccentCard.TSpinbox", arrowsize=14, padding=4)
        self.style.configure("AccentCard.TCombobox", padding=4)
        self.style.configure("Secondary.TLabel")
        self.style.configure("Hint.TLabel")

        self._apply_theme(initial=True)

    def _get_palette(self, dark: bool) -> Dict[str, str]:
        if dark:
            return {
                "app_bg": "#0f172a",
                "card_bg": "#1f2937",
                "header_bg": "#0b1628",
                "accent_card_bg": "#1e293b",
                "accent_outline": "#3b82f6",
                "text_primary": "#f9fafb",
                "text_secondary": "#d1d5db",
                "text_muted": "#9ca3af",
                "border_color": "#374151",
                "accent_color": "#60a5fa",
                "accent_hover": "#7dd3fc",
                "accent_active": "#2563eb",
                "accent_disabled": "#1d4ed8",
                "text_on_accent": "#0b1628",
                "text_on_disabled": "#bac8ff",
                "danger_color": "#f87171",
                "danger_hover": "#fb7185",
                "danger_active": "#dc2626",
                "danger_disabled": "#7f1d1d",
                "ghost_bg": "#1f2937",
                "ghost_hover": "#273548",
                "ghost_active": "#324158",
                "list_bg": "#111827",
                "list_fg": "#f9fafb",
                "text_area_bg": "#111827",
                "entry_bg": "#111827",
                "entry_fg": "#f9fafb",
                "tab_unselected_fg": "#9ca3af",
                "tab_selected_fg": "#f9fafb",
                "separator": "#1f2937",
                "highlight": "#3b82f6",
            }
        return {
            "app_bg": "#eef2f9",
            "card_bg": "#ffffff",
            "header_bg": "#f3f5f9",
            "accent_card_bg": "#edf3ff",
            "accent_outline": "#4e8cff",
            "text_primary": "#1f2933",
            "text_secondary": "#4b5563",
            "text_muted": "#6b7280",
            "border_color": "#d8dee9",
            "accent_color": "#4e8cff",
            "accent_hover": "#5f9dff",
            "accent_active": "#2f6ed6",
            "accent_disabled": "#99b9ff",
            "text_on_accent": "#ffffff",
            "text_on_disabled": "#cbd5f5",
            "danger_color": "#d83b3b",
            "danger_hover": "#e15656",
            "danger_active": "#a72c2c",
            "danger_disabled": "#f5b4b4",
            "ghost_bg": "#eef2f9",
            "ghost_hover": "#e2e8f5",
            "ghost_active": "#cfd8ec",
            "list_bg": "#ffffff",
            "list_fg": "#1f2933",
            "text_area_bg": "#ffffff",
            "entry_bg": "#ffffff",
            "entry_fg": "#1f2933",
            "tab_unselected_fg": "#4b5563",
            "tab_selected_fg": "#1f2933",
            "separator": "#d8dee9",
            "highlight": "#4e8cff",
        }

    def _apply_theme(self, *, initial: bool = False) -> None:
        palette = self._get_palette(self.dark_mode_var.get())
        self._current_palette = palette

        self.root.configure(background=palette["app_bg"])

        self.style.configure("TFrame", background=palette["card_bg"])
        self.style.configure("TLabel", background=palette["card_bg"], foreground=palette["text_primary"])
        self.style.configure("TLabelFrame", background=palette["card_bg"], foreground=palette["text_primary"])
        self.style.configure("TEntry", fieldbackground=palette["entry_bg"], foreground=palette["entry_fg"], background=palette["card_bg"])
        self.style.configure("TCombobox", fieldbackground=palette["entry_bg"], foreground=palette["entry_fg"], background=palette["card_bg"])
        self.style.configure("TCheckbutton", background=palette["card_bg"], foreground=palette["text_primary"])
        self.style.configure("TButton", background=palette["card_bg"], foreground=palette["text_primary"])

        self.style.configure("Background.TFrame", background=palette["app_bg"])
        self.style.configure("Card.TFrame", background=palette["card_bg"])
        self.style.configure("Header.TFrame", background=palette["header_bg"])
        self.style.configure("Header.TLabel", background=palette["header_bg"], foreground=palette["text_primary"])
        self.style.configure("HeaderSubtitle.TLabel", background=palette["header_bg"], foreground=palette["text_secondary"])

        self.style.configure(
            "Card.TLabelframe",
            background=palette["card_bg"],
            lightcolor=palette["border_color"],
            darkcolor=palette["border_color"],
            bordercolor=palette["border_color"],
        )
        self.style.configure("Card.TLabelframe.Label", background=palette["card_bg"], foreground=palette["text_primary"])
        self.style.configure("CardBody.TFrame", background=palette["card_bg"])

        self.style.configure(
            "AccentCard.TLabelframe",
            background=palette["accent_card_bg"],
            lightcolor=palette["accent_outline"],
            darkcolor=palette["accent_outline"],
            bordercolor=palette["accent_outline"],
        )
        self.style.configure("AccentCard.TLabelframe.Label", background=palette["accent_card_bg"], foreground=palette["text_secondary"])
        self.style.configure("AccentCard.TFrame", background=palette["accent_card_bg"])
        self.style.configure("AccentCardLabel.TLabel", background=palette["accent_card_bg"], foreground=palette["text_primary"])
        self.style.configure("AccentCardHint.TLabel", background=palette["accent_card_bg"], foreground=palette["text_muted"])

        self.style.configure("Secondary.TLabel", background=palette["card_bg"], foreground=palette["text_secondary"])
        self.style.configure("Hint.TLabel", background=palette["card_bg"], foreground=palette["text_muted"])

        self.style.configure("App.TNotebook", background=palette["app_bg"])
        self.style.configure("App.TNotebook.Tab", background=palette["app_bg"], foreground=palette["tab_unselected_fg"])
        self.style.map(
            "App.TNotebook.Tab",
            background=[("selected", palette["card_bg"]), ("!selected", palette["app_bg"])],
            foreground=[("selected", palette["tab_selected_fg"]), ("!selected", palette["tab_unselected_fg"])],
        )

        self.style.configure("Accent.TButton", background=palette["accent_color"], foreground=palette["text_on_accent"])
        self.style.map(
            "Accent.TButton",
            background=[
                ("disabled", palette["accent_disabled"]),
                ("pressed", palette["accent_active"]),
                ("active", palette["accent_hover"]),
            ],
            foreground=[("disabled", palette["text_on_disabled"])],
        )

        self.style.configure("Danger.TButton", background=palette["danger_color"], foreground=palette["text_on_accent"])
        self.style.map(
            "Danger.TButton",
            background=[
                ("disabled", palette["danger_disabled"]),
                ("pressed", palette["danger_active"]),
                ("active", palette["danger_hover"]),
            ],
            foreground=[("disabled", palette["text_on_disabled"])],
        )

        self.style.configure("Ghost.TButton", background=palette["ghost_bg"], foreground=palette["text_primary"])
        self.style.map(
            "Ghost.TButton",
            background=[
                ("pressed", palette["ghost_active"]),
                ("active", palette["ghost_hover"]),
            ],
        )

        self.style.configure(
            "AccentCard.TSpinbox",
            fieldbackground=palette["entry_bg"],
            background=palette["entry_bg"],
            foreground=palette["entry_fg"],
        )
        self.style.map(
            "AccentCard.TSpinbox",
            fieldbackground=[("disabled", palette["entry_bg"]), ("readonly", palette["entry_bg"])],
            foreground=[("disabled", palette["text_muted"])],
            arrowcolor=[("active", palette["accent_hover"]), ("!active", palette["accent_color"])],
        )

        self.style.configure(
            "AccentCard.TCombobox",
            fieldbackground=palette["entry_bg"],
            background=palette["entry_bg"],
            foreground=palette["entry_fg"],
        )
        self.style.map(
            "AccentCard.TCombobox",
            fieldbackground=[("readonly", palette["entry_bg"]), ("disabled", palette["entry_bg"])],
            foreground=[("disabled", palette["text_muted"])],
        )

        if not initial:
            self._apply_widget_theme()

    def _apply_widget_theme(self) -> None:
        if not hasattr(self, "_current_palette"):
            return
        palette = self._current_palette

        if hasattr(self, "position_listbox"):
            self.position_listbox.configure(
                bg=palette["list_bg"],
                fg=palette["list_fg"],
                selectbackground=palette["accent_color"],
                selectforeground=palette["text_on_accent"],
                highlightbackground=palette["border_color"],
                highlightcolor=palette["highlight"],
                relief=tk.FLAT,
            )

        if hasattr(self, "log_text"):
            self.log_text.configure(
                background=palette["text_area_bg"],
                foreground=palette["text_primary"],
                insertbackground=palette["text_primary"],
            )

    def _on_dark_mode_toggle(self) -> None:
        self._apply_theme()
        self._persist_settings()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        container = ttk.Frame(self.root, padding=18, style="Background.TFrame")
        container.grid(row=0, column=0, sticky="nsew")

        notebook = ttk.Notebook(container, style="App.TNotebook")
        notebook.pack(fill=tk.BOTH, expand=True)

        manual_tab = ttk.Frame(notebook, style="Background.TFrame")
        automation_tab = ttk.Frame(notebook, style="Background.TFrame")
        options_tab = ttk.Frame(notebook, style="Background.TFrame")
        notebook.add(manual_tab, text="Manuelle Steuerung")
        notebook.add(automation_tab, text="Automatisierung")
        notebook.add(options_tab, text="Optionen & Hotkeys")

        manual_tab.configure(padding=12)
        automation_tab.configure(padding=12)
        options_tab.configure(padding=12)

        manual_tab.columnconfigure(0, weight=3, minsize=300)
        manual_tab.columnconfigure(1, weight=5, minsize=500)
        manual_tab.rowconfigure(0, weight=0)
        manual_tab.rowconfigure(1, weight=1)
        manual_tab.rowconfigure(2, weight=0)

        hero = ttk.Frame(manual_tab, style="Header.TFrame", padding=(18, 20))
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        ttk.Label(hero, text="Manuelle Steuerung", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            hero,
            text="Erstellen Sie präzise Klick-Sequenzen oder folgen Sie dem Cursor – inklusive Live-Statistiken.",
            style="HeaderSubtitle.TLabel",
        ).pack(anchor="w", pady=(6, 0))

        top_row = ttk.Frame(manual_tab, style="CardBody.TFrame")
        top_row.grid(row=1, column=0, columnspan=2, sticky="nsew")
        top_row.columnconfigure(0, weight=3, minsize=340)
        top_row.columnconfigure(1, weight=5, minsize=420)
        top_row.rowconfigure(0, weight=1)

        positions_container = ttk.Frame(top_row, style="CardBody.TFrame")
        positions_container.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        positions_container.columnconfigure(0, weight=1)
        positions_container.rowconfigure(0, weight=1)

        right_column = ttk.Frame(top_row, style="CardBody.TFrame")
        right_column.grid(row=0, column=1, sticky="nsew")
        right_column.columnconfigure(0, weight=1)
        right_column.rowconfigure(0, weight=1)
        right_column.rowconfigure(1, weight=0)

        self._build_position_section(positions_container)
        self._build_configuration_section(right_column, row=0)
        self._build_manual_controls_section(right_column, row=1)

        status_container = ttk.Frame(manual_tab, style="Background.TFrame")
        status_container.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(18, 0))
        status_container.columnconfigure(0, weight=1)
        status_container.rowconfigure(0, weight=1)

        self._build_status_section(status_container)

        self._build_automation_tab(automation_tab)
        self._build_options_tab(options_tab)

    def _build_position_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Klick-Positionen", padding=14, style="Card.TLabelframe")
        frame.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        header = ttk.Frame(frame, style="Card.TFrame")
        header.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Gespeicherte Ziele", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(header, textvariable=self.position_count_var, style="Secondary.TLabel").grid(
            row=0, column=1, sticky="e"
        )

        self.position_listbox = tk.Listbox(
            frame,
            height=9,
            font=("Segoe UI", 10),
            bd=0,
            highlightthickness=0,
            selectmode=tk.SINGLE,
            selectbackground="#4e8cff",
            selectforeground="#ffffff",
        )
        self.position_listbox.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(0, 6))

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.position_listbox.yview)
        scrollbar.grid(row=1, column=3, sticky="ns")
        self.position_listbox.configure(yscrollcommand=scrollbar.set)

        btn_frame = ttk.Frame(frame, style="Card.TFrame")
        btn_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(0, 6))
        btn_frame.columnconfigure((0, 1, 2), weight=1)

        self.add_current_button = ttk.Button(
            btn_frame,
            text="Aktuelle Position",
            command=self._add_current_position,
            style="Ghost.TButton",
        )
        self.add_current_button.grid(row=0, column=0, padx=4, pady=4, sticky="ew")

        self.add_custom_button = ttk.Button(
            btn_frame,
            text="Benutzerdefiniert",
            command=self._add_custom_position,
            style="Ghost.TButton",
        )
        self.add_custom_button.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        self.capture_button = ttk.Button(
            btn_frame,
            text="Nächsten Klick aufnehmen",
            command=self._capture_next_position,
            style="Accent.TButton",
        )
        self.capture_button.grid(row=0, column=2, padx=4, pady=4, sticky="ew")

        self.capture_cancel_button = ttk.Button(
            btn_frame,
            text="Aufnahme stoppen",
            command=self._cancel_capture,
            style="Danger.TButton",
        )
        self.capture_cancel_button.grid(row=1, column=0, padx=4, pady=4, sticky="ew")

        self.remove_selected_button = ttk.Button(
            btn_frame,
            text="Entfernen",
            command=self._remove_selected_position,
            style="Ghost.TButton",
        )
        self.remove_selected_button.grid(row=1, column=1, padx=4, pady=4, sticky="ew")

        self.clear_all_button = ttk.Button(
            btn_frame,
            text="Alle löschen",
            command=self._clear_all_positions,
            style="Ghost.TButton",
        )
        self.clear_all_button.grid(row=1, column=2, padx=4, pady=4, sticky="ew")

        ttk.Button(
            btn_frame,
            text="Duplizieren",
            command=self._duplicate_selected_position,
            style="Ghost.TButton",
        ).grid(row=2, column=0, padx=4, pady=4, sticky="ew")

        ttk.Button(
            btn_frame,
            text="Kopieren",
            command=self._copy_position_to_clipboard,
            style="Ghost.TButton",
        ).grid(row=2, column=1, columnspan=2, padx=4, pady=4, sticky="ew")

        ttk.Label(frame, textvariable=self.capture_status_var).grid(
            row=3,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(10, 0),
        )

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=4, column=0, columnspan=4, sticky="ew", pady=(12, 0))

        ttk.Label(
            frame,
            text="Tipp: Nutzen Sie den Debug-Modus, um Zielpunkte live auf dem Bildschirm zu sehen.",
            style="Hint.TLabel",
            wraplength=320,
        ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(10, 0))

    def _build_configuration_section(self, parent: ttk.Frame, row: int) -> None:
        parent.rowconfigure(row, weight=1)
        frame = ttk.LabelFrame(parent, text="Konfiguration", padding=(18, 20), style="AccentCard.TLabelframe")
        frame.grid(row=row, column=0, sticky="nsew", pady=(0, 14))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1, minsize=320)

        inputs = [
            (
                "Klicks pro Sekunde:",
                ttk.Spinbox(
                    frame,
                    from_=0.1,
                    to=1000.0,
                    increment=0.1,
                    textvariable=self.click_rate_var,
                    justify="right",
                    width=8,
                    style="AccentCard.TSpinbox",
                ),
                (0, 6),
            ),
            (
                "Gesamtanzahl (0 = unendlich):",
                ttk.Spinbox(
                    frame,
                    from_=0,
                    to=1_000_000,
                    increment=10,
                    textvariable=self.total_clicks_var,
                    justify="right",
                    width=8,
                    style="AccentCard.TSpinbox",
                ),
                (0, 6),
            ),
            (
                "Klicktyp:",
                ttk.Combobox(
                    frame,
                    textvariable=self.click_type_var,
                    values=[choice.value for choice in ClickType],
                    state="readonly",
                    style="AccentCard.TCombobox",
                    width=18,
                ),
                (4, 6),
            ),
        ]

        for row_index, (label_text, widget, pady) in enumerate(inputs):
            ttk.Label(frame, text=label_text, style="AccentCardLabel.TLabel").grid(
                row=row_index, column=0, sticky="w", pady=pady
            )
            widget.grid(row=row_index, column=1, sticky="ew", padx=(16, 0), pady=pady)
            widget.configure(font=("Segoe UI", 10))

        ttk.Label(frame, text="Modus:", style="AccentCardLabel.TLabel").grid(
            row=len(inputs), column=0, sticky="w", pady=(6, 6)
        )
        mode_frame = ttk.Frame(frame, style="AccentCard.TFrame")
        mode_frame.grid(row=len(inputs), column=1, sticky="ew", pady=(6, 0), padx=(16, 0))
        mode_frame.columnconfigure((0, 1), weight=1)

        ttk.Radiobutton(
            mode_frame,
            text="Feste Positionen",
            value=ClickMode.STATIC_SEQUENCE.value,
            variable=self.click_mode_var,
            command=self._on_click_mode_changed,
        ).grid(row=0, column=0, padx=(0, 12), sticky="w")

        ttk.Radiobutton(
            mode_frame,
            text="Cursor folgen",
            value=ClickMode.FOLLOW_CURSOR.value,
            variable=self.click_mode_var,
            command=self._on_click_mode_changed,
        ).grid(row=0, column=1, sticky="w")

        metrics_row = len(inputs) + 1
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(
            row=metrics_row, column=0, columnspan=2, sticky="ew", pady=(16, 10)
        )
        ttk.Label(
            frame,
            text="Hinweis: 0 Gesamtanzahl bedeutet unbegrenztes Klicken.",
            style="AccentCardHint.TLabel",
        ).grid(row=metrics_row + 1, column=0, columnspan=2, sticky="w")

        metrics_frame = ttk.Frame(frame, style="AccentCard.TFrame")
        metrics_frame.grid(row=metrics_row + 2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        metrics_frame.columnconfigure(0, weight=1)

        ttk.Label(
            metrics_frame,
            textvariable=self.click_interval_hint_var,
            style="AccentCardHint.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            metrics_frame,
            textvariable=self.estimated_duration_var,
            style="AccentCardHint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

    def _build_manual_controls_section(self, parent: ttk.Frame, row: int) -> None:
        parent.rowconfigure(row, weight=0)
        frame = ttk.LabelFrame(parent, text="Steuerung & Statistik", padding=(18, 20), style="Card.TLabelframe")
        frame.grid(row=row, column=0, sticky="nsew", pady=(0, 14))
        frame.columnconfigure(0, weight=1)

        button_frame = ttk.Frame(frame, style="CardBody.TFrame")
        button_frame.grid(row=0, column=0, sticky="ew")
        button_frame.columnconfigure((0, 1, 2), weight=1)

        self.start_button = ttk.Button(
            button_frame,
            text="Start",
            command=self._start_manual_clicking,
            style="Accent.TButton",
        )
        self.start_button.grid(row=0, column=0, padx=(0, 8), pady=(0, 4), sticky="ew")

        ttk.Button(
            button_frame,
            text="Stopp",
            command=self._stop_manual_clicking,
            style="Danger.TButton",
        ).grid(row=0, column=1, padx=(8, 8), pady=(0, 4), sticky="ew")

        ttk.Button(
            button_frame,
            text="Statistiken zurücksetzen",
            command=self._reset_manual_statistics,
            style="Ghost.TButton",
        ).grid(row=0, column=2, padx=(0, 0), pady=(0, 4), sticky="ew")

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=1, column=0, sticky="ew", pady=(12, 10))

        stats_frame = ttk.Frame(frame, style="CardBody.TFrame")
        stats_frame.grid(row=2, column=0, sticky="ew")
        stats_frame.columnconfigure((0, 1), weight=1)

        ttk.Label(stats_frame, textvariable=self.click_count_var, anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(stats_frame, textvariable=self.manual_cps_var, anchor="e").grid(
            row=0, column=1, sticky="e"
        )

        ttk.Label(frame, textvariable=self.status_var).grid(row=3, column=0, sticky="w", pady=(12, 0))

    def _build_options_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        container = ttk.Frame(parent, style="Background.TFrame", padding=12)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)

        frame = ttk.LabelFrame(container, text="Optionen & Hotkeys", padding=(18, 20), style="Card.TLabelframe")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)

        options_frame = ttk.Frame(frame, style="CardBody.TFrame")
        options_frame.grid(row=0, column=0, sticky="ew")
        options_frame.columnconfigure(0, weight=1)

        ttk.Checkbutton(
            options_frame,
            text="Dunkles Design aktivieren",
            variable=self.dark_mode_var,
            command=self._on_dark_mode_toggle,
        ).grid(row=0, column=0, sticky="w")

        ttk.Checkbutton(
            options_frame,
            text="Im Hintergrund ausführen (Fenster darf im Vordergrund bleiben)",
            variable=self.background_var,
            command=self._persist_settings,
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        ttk.Checkbutton(
            options_frame,
            text="Debug-Modus: Positionen mit ✕ markieren",
            variable=self.debug_overlay_var,
            command=lambda: self._toggle_debug_overlay(self.debug_overlay_var.get()),
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=1, column=0, sticky="ew", pady=(12, 10))

        hotkey_frame = ttk.Frame(frame, style="CardBody.TFrame")
        hotkey_frame.grid(row=2, column=0, sticky="ew")
        hotkey_frame.columnconfigure(1, weight=1)

        ttk.Label(hotkey_frame, text="Start-Hotkey:").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(hotkey_frame, textvariable=self.start_hotkey_var, width=14).grid(
            row=0, column=1, sticky="ew", padx=(8, 16)
        )

        ttk.Label(hotkey_frame, text="Stopp-Hotkey:").grid(row=1, column=0, sticky="w")
        ttk.Entry(hotkey_frame, textvariable=self.stop_hotkey_var, width=14).grid(
            row=1, column=1, sticky="ew", padx=(8, 16)
        )

        ttk.Button(
            hotkey_frame,
            text="Hotkeys anwenden",
            command=self._apply_hotkeys,
            style="Accent.TButton",
        ).grid(row=0, column=2, rowspan=2, sticky="nswe")

        ttk.Label(frame, textvariable=self.monitor_info_var, style="Hint.TLabel").grid(
            row=3, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Label(
            frame,
            text="Tipp: Hinterlegte Hotkeys sind global aktiv. Nutzen Sie einzigartige Kombinationen.",
            style="Hint.TLabel",
            wraplength=360,
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))
    def _build_status_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Status & Log", padding=14, style="Card.TLabelframe")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(frame, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

        self.log_text = scrolledtext.ScrolledText(frame, height=10, state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

        button_bar = ttk.Frame(frame, style="Card.TFrame")
        button_bar.grid(row=2, column=0, sticky="e", pady=(12, 0))
        button_bar.columnconfigure((0, 1, 2), weight=0)

        ttk.Button(
            button_bar,
            text="Log kopieren",
            command=self._copy_logs_to_clipboard,
            style="Ghost.TButton",
        ).grid(row=0, column=0, padx=(0, 6))

        ttk.Button(
            button_bar,
            text="Log leeren",
            command=self._clear_log_output,
            style="Ghost.TButton",
        ).grid(row=0, column=1, padx=(0, 6))

        ttk.Button(
            button_bar,
            text="Log exportieren",
            command=self._export_logs,
            style="Ghost.TButton",
        ).grid(row=0, column=2)

    def _clear_log_output(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self.status_var.set("Status: Loganzeige gelöscht.")
        self.logger.log_info("Loganzeige gelöscht.")

    def _copy_logs_to_clipboard(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        content = self.log_text.get("1.0", tk.END).strip()
        self.log_text.configure(state=tk.DISABLED)
        if not content:
            self.status_var.set("Status: Log ist leer.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.status_var.set("Status: Log in Zwischenablage.")
        self.logger.log_info("Log in Zwischenablage kopiert.")

    def _update_click_metrics(self) -> None:
        try:
            rate = float(self.click_rate_var.get())
        except (tk.TclError, ValueError):
            rate = 0.0

        if rate > 0:
            interval_ms = 1000.0 / rate
            self.click_interval_hint_var.set(f"Intervall zwischen Klicks: {interval_ms:.1f} ms")
        else:
            self.click_interval_hint_var.set("Intervall zwischen Klicks: –")

        try:
            total = int(self.total_clicks_var.get())
        except (tk.TclError, ValueError):
            total = 0

        if total == 0:
            self.estimated_duration_var.set("Geschätzte Dauer: unbegrenzt (0 = unbegrenzt)")
            return

        if rate <= 0:
            self.estimated_duration_var.set("Geschätzte Dauer: –")
            return

        seconds = total / rate
        if seconds >= 3600:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            self.estimated_duration_var.set(f"Geschätzte Dauer: {hours}h {minutes}m {secs}s")
        elif seconds >= 60:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            self.estimated_duration_var.set(f"Geschätzte Dauer: {minutes}m {secs}s")
        else:
            self.estimated_duration_var.set(f"Geschätzte Dauer: {seconds:.1f}s")

    def _build_automation_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        hero = ttk.Frame(parent, style="Header.TFrame", padding=(18, 18))
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        ttk.Label(hero, text="Automatisierung", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            hero,
            text=(
                "Kombinieren Sie Ihre gespeicherten Positionen mit einem Hintergrundlauf – inklusive Minimierungs-"
                " und Endlosmodus. Die Konfiguration aus der manuellen Ansicht wird automatisch übernommen."
            ),
            style="HeaderSubtitle.TLabel",
            wraplength=700,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(6, 0))

        layout = ttk.Frame(parent, style="CardBody.TFrame")
        layout.grid(row=1, column=0, sticky="nsew")
        layout.columnconfigure(0, weight=1)
        layout.columnconfigure(1, weight=1)
        layout.rowconfigure(0, weight=1)

        settings_card = ttk.LabelFrame(layout, text="Ausführungseinstellungen", padding=(18, 20), style="Card.TLabelframe")
        settings_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        settings_card.columnconfigure(0, weight=1)

        ttk.Label(
            settings_card,
            text="Verhalten",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        ttk.Checkbutton(
            settings_card,
            text="Fenster beim Start minimieren",
            variable=self.automation_minimize_var,
        ).grid(row=1, column=0, sticky="w")

        ttk.Checkbutton(
            settings_card,
            text="Unendlich klicken (ignoriert Gesamtanzahl)",
            variable=self.automation_infinite_var,
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))

        ttk.Separator(settings_card, orient=tk.HORIZONTAL).grid(row=3, column=0, sticky="ew", pady=(16, 12))

        ttk.Label(
            settings_card,
            text="Die Automatisierung nutzt die gleichen Klickparameter wie der manuelle Tab.",
            style="Hint.TLabel",
            wraplength=320,
        ).grid(row=4, column=0, sticky="w")

        controls_card = ttk.LabelFrame(layout, text="Steuerung & Status", padding=(18, 20), style="Card.TLabelframe")
        controls_card.grid(row=0, column=1, sticky="nsew")
        controls_card.columnconfigure(0, weight=1)

        button_frame = ttk.Frame(controls_card, style="CardBody.TFrame")
        button_frame.grid(row=0, column=0, sticky="ew")
        button_frame.columnconfigure((0, 1, 2), weight=1)

        ttk.Button(
            button_frame,
            text="Start (Hintergrund)",
            command=self._start_automation,
            style="Accent.TButton",
        ).grid(row=0, column=0, padx=(0, 8), pady=(0, 4), sticky="ew")
        ttk.Button(
            button_frame,
            text="Stopp",
            command=self._stop_automation,
            style="Danger.TButton",
        ).grid(row=0, column=1, padx=(8, 8), pady=(0, 4), sticky="ew")
        ttk.Button(
            button_frame,
            text="Statistiken zurücksetzen",
            command=self._reset_automation_statistics,
            style="Ghost.TButton",
        ).grid(row=0, column=2, padx=(0, 0), pady=(0, 4), sticky="ew")

        ttk.Separator(controls_card, orient=tk.HORIZONTAL).grid(row=1, column=0, sticky="ew", pady=(12, 10))

        status_box = ttk.Frame(controls_card, style="CardBody.TFrame")
        status_box.grid(row=2, column=0, sticky="ew")
        status_box.columnconfigure((0, 1), weight=1)

        ttk.Label(status_box, textvariable=self.automation_status_var, anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(status_box, textvariable=self.automation_clicks_var, anchor="w").grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Label(status_box, textvariable=self.automation_cps_var, anchor="e").grid(
            row=1, column=1, sticky="e", pady=(6, 0)
        )

        info_card = ttk.LabelFrame(parent, text="Workflow-Tipp", padding=(18, 18), style="Card.TLabelframe")
        info_card.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        info_card.columnconfigure(0, weight=1)

        ttk.Label(
            info_card,
            text=(
                "Nutzen Sie die Hotkeys aus der manuellen Ansicht, um Automatisierung und manuelles Klicken ohne "
                "Fensterwechsel zu starten oder zu stoppen. Aktivieren Sie bei Bedarf zuerst den Debug-Modus, um "
                "die Zielpunkte zu prüfen."
            ),
            style="Hint.TLabel",
            wraplength=720,
        ).grid(row=0, column=0, sticky="w")

        # Script Automation (Background without cursor)
        script_card = ttk.LabelFrame(parent, text="Script-Automatisierung (Hintergrund)", padding=(18, 18), style="Card.TLabelframe")
        script_card.grid(row=3, column=0, sticky="nsew", pady=(18, 0))
        script_card.columnconfigure(0, weight=1)
        # row 1 = builder, row 2 = editor
        script_card.rowconfigure(2, weight=1)

        toolbar = ttk.Frame(script_card, style="CardBody.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for i in range(8):
            toolbar.columnconfigure(i, weight=1)

        ttk.Button(toolbar, text="Beispiel laden", command=self._load_example_script, style="Ghost.TButton").grid(row=0, column=0, padx=4, sticky="ew")
        ttk.Button(toolbar, text="Öffnen…", command=self._open_script_file, style="Ghost.TButton").grid(row=0, column=1, padx=4, sticky="ew")
        ttk.Button(toolbar, text="Speichern unter…", command=self._save_script_as, style="Ghost.TButton").grid(row=0, column=2, padx=4, sticky="ew")
        ttk.Button(toolbar, text="Start (Script)", command=self._start_script_automation, style="Accent.TButton").grid(row=0, column=3, padx=4, sticky="ew")
        ttk.Button(toolbar, text="Stopp (Script)", command=self._stop_script_automation, style="Danger.TButton").grid(row=0, column=4, padx=4, sticky="ew")
        ttk.Button(toolbar, text="Validieren", command=self._validate_script_editor, style="Ghost.TButton").grid(row=0, column=5, padx=4, sticky="ew")
        ttk.Button(toolbar, text="Editor → Builder", command=self._editor_to_builder, style="Ghost.TButton").grid(row=0, column=6, padx=4, sticky="ew")
        ttk.Button(toolbar, text="Script‑Builder öffnen…", command=self._open_builder_window, style="Ghost.TButton").grid(row=0, column=7, padx=4, sticky="ew")

        # Editor --------------------------------------------------------
        self.script_text = scrolledtext.ScrolledText(script_card, height=10, wrap=tk.WORD)
        self.script_text.grid(row=2, column=0, sticky="nsew")
        self._populate_script_editor_with_default()

        ttk.Label(script_card, textvariable=self.script_status_var).grid(row=3, column=0, sticky="w", pady=(8, 0))

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------
    def _add_current_position(self) -> None:
        x, y = pyautogui.position()
        position = ClickPosition(x=int(x), y=int(y))
        self.click_positions.append(position)
        self._after_positions_updated(f"Position hinzugefügt: {position}")

    def _add_custom_position(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Position hinzufügen")
        dialog.geometry("280x200")
        dialog.transient(self.root)
        dialog.grab_set()

        x_var = tk.StringVar(value="0")
        y_var = tk.StringVar(value="0")
        label_var = tk.StringVar(value="")

        ttk.Label(dialog, text="X-Koordinate:").pack(pady=(10, 0))
        ttk.Entry(dialog, textvariable=x_var).pack()

        ttk.Label(dialog, text="Y-Koordinate:").pack(pady=(10, 0))
        ttk.Entry(dialog, textvariable=y_var).pack()

        ttk.Label(dialog, text="Label (optional):").pack(pady=(10, 0))
        ttk.Entry(dialog, textvariable=label_var).pack()

        status_var = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=status_var, foreground="red").pack(pady=4)

        def submit() -> None:
            try:
                x_value = int(x_var.get())
                y_value = int(y_var.get())
                label_value = label_var.get().strip() or None
                self.click_positions.append(ClickPosition(x=x_value, y=y_value, label=label_value))
                dialog.destroy()
                self._after_positions_updated(
                    f"Position hinzugefügt: {label_value or ''} ({x_value}, {y_value})"
                )
            except ValueError:
                status_var.set("Bitte gültige Ganzzahlen eingeben.")

        ttk.Button(dialog, text="Hinzufügen", command=submit).pack(pady=(12, 0))
        ttk.Button(dialog, text="Abbrechen", command=dialog.destroy).pack(pady=(4, 0))

    def _capture_next_position(self) -> None:
        if self.capture_in_progress:
            return
        self.capture_in_progress = True
        started = self.capture_service.capture_next_click(
            on_captured=self._on_click_captured, on_error=self._on_capture_error
        )
        if started:
            self.capture_status_var.set(
                "Aufnahme läuft … klicken Sie auf die gewünschte Stelle oder drücken Sie \"Aufnahme stoppen\"."
            )
        else:
            self.capture_in_progress = False
            self.capture_status_var.set("Aufnahme bereits aktiv – bitte zuerst stoppen.")

    def _cancel_capture(self) -> None:
        if self.capture_in_progress:
            self.capture_service.cancel()
            self.capture_in_progress = False
            self.capture_status_var.set("Aufnahme abgebrochen.")

    def _on_click_captured(self, x: int, y: int) -> None:
        self.capture_in_progress = False
        self.capture_status_var.set("Position aufgenommen.")
        self.click_positions.append(ClickPosition(x=x, y=y))
        self._after_positions_updated(f"Position aufgenommen: ({x}, {y})")

    def _on_capture_error(self, exc: Exception) -> None:  # pragma: no cover - platform specific
        self.capture_in_progress = False
        self.capture_status_var.set("Fehler bei der Aufnahme. Details im Log.")
        self._log_message(f"Fehler bei der Aufnahme: {exc}", level="ERROR")

    def _remove_selected_position(self) -> None:
        selection = self.position_listbox.curselection()
        if not selection:
            return
        index = int(selection[0])
        removed = self.click_positions.pop(index)
        self._after_positions_updated(f"Position entfernt: {removed}")

    def _duplicate_selected_position(self) -> None:
        selection = self.position_listbox.curselection()
        if not selection:
            return
        index = int(selection[0])
        original = self.click_positions[index]
        duplicate_label = f"{original.label} (Kopie)" if original.label else None
        duplicate = ClickPosition(x=original.x, y=original.y, label=duplicate_label)
        self.click_positions.insert(index + 1, duplicate)
        self._after_positions_updated(
            f"Position dupliziert: {duplicate.label or f'({duplicate.x}, {duplicate.y})'}"
        )
        self.position_listbox.selection_clear(0, tk.END)
        self.position_listbox.selection_set(index + 1)

    def _copy_position_to_clipboard(self) -> None:
        selection = self.position_listbox.curselection()
        if not selection:
            return
        position = self.click_positions[int(selection[0])]
        text = f"{position.x}, {position.y}"
        if position.label:
            text = f"{position.label}: {text}"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._log_message(f"Position in Zwischenablage: {text}")

    def _clear_all_positions(self) -> None:
        if not self.click_positions:
            return
        self.click_positions.clear()
        self._after_positions_updated("Alle Positionen gelöscht")

    def _refresh_position_list(self) -> None:
        self.position_listbox.delete(0, tk.END)
        for idx, position in enumerate(self.click_positions, start=1):
            label = position.label or f"#{idx}"
            self.position_listbox.insert(tk.END, f"{idx}. {label} @ ({position.x}, {position.y})")
        count = len(self.click_positions)
        if count == 1:
            self.position_count_var.set("1 Position gespeichert")
        else:
            self.position_count_var.set(f"{count} Positionen gespeichert")

    def _reset_manual_statistics(self) -> None:
        self.click_count_var.set("Ausgeführte Klicks: 0")
        self.manual_cps_var.set("Aktuelle CPS: 0.00")
        if "engine" in self._cps_tracker:
            self._reset_cps_tracker("engine", 0)
        self._log_message("Manuelle Statistiken zurückgesetzt.")

    def _reset_automation_statistics(self) -> None:
        self.automation_clicks_var.set("Klicks (Automatisierung): 0")
        self.automation_cps_var.set("CPS (Automatisierung): 0.00")
        if "automation_engine" in self._cps_tracker:
            self._reset_cps_tracker("automation_engine", 0)
        self._log_message("Automatisierungsstatistiken zurückgesetzt.")
        # Script status is independent
        self.script_status_var.set("Script: Bereit")

    def _after_positions_updated(self, message: str) -> None:
        self._refresh_position_list()
        self.debug_overlay.set_positions(self.click_positions)
        self._log_message(message)
        self._persist_settings()

    # ------------------------------------------------------------------
    # Engine management
    # ------------------------------------------------------------------
    def _start_manual_clicking(self) -> None:
        try:
            config = self._build_configuration(run_in_background=self.background_var.get())
        except ValueError as exc:
            messagebox.showerror("Konfiguration ungültig", str(exc))
            return

        self._start_engine(
            engine_attr="engine",
            config=config,
            status_var=self.status_var,
            click_var=self.click_count_var,
            click_reset_text="Ausgeführte Klicks: 0",
            cps_var=self.manual_cps_var,
            cps_reset_text="Aktuelle CPS: 0.00",
            update_job_attr="manual_update_job",
            minimize=False,
            on_success="Manueller Start ausgeführt.",
            click_prefix="Ausgeführte Klicks",
            status_running_text="Status: Läuft",
            status_ready_text="Status: Bereit",
            cps_prefix="Aktuelle CPS",
        )

    def _stop_manual_clicking(self) -> None:
        self._stop_engine(
            engine_attr="engine",
            status_var=self.status_var,
            click_var=self.click_count_var,
            click_reset_text="Ausgeführte Klicks: 0",
            cps_var=self.manual_cps_var,
            cps_reset_text="Aktuelle CPS: 0.00",
            update_job_attr="manual_update_job",
            status_ready_text="Status: Bereit",
        )

    def _start_automation(self) -> None:
        try:
            total_override = 0 if self.automation_infinite_var.get() else self.total_clicks_var.get()
            config = self._build_configuration(
                run_in_background=True,
                total_override=total_override,
            )
        except ValueError as exc:
            messagebox.showerror("Konfiguration ungültig", str(exc))
            return

        minimize = self.automation_minimize_var.get()
        self._start_engine(
            engine_attr="automation_engine",
            config=config,
            status_var=self.automation_status_var,
            click_var=self.automation_clicks_var,
            click_reset_text="Klicks (Automatisierung): 0",
            cps_var=self.automation_cps_var,
            cps_reset_text="CPS (Automatisierung): 0.00",
            update_job_attr="automation_update_job",
            minimize=minimize,
            on_success="Automatisierung gestartet.",
            click_prefix="Klicks (Automatisierung)",
            status_running_text="Automatisierung: Läuft",
            status_ready_text="Automatisierung: Bereit",
            cps_prefix="CPS (Automatisierung)",
        )

    def _stop_automation(self) -> None:
        self._stop_engine(
            engine_attr="automation_engine",
            status_var=self.automation_status_var,
            click_var=self.automation_clicks_var,
            click_reset_text="Klicks (Automatisierung): 0",
            cps_var=self.automation_cps_var,
            cps_reset_text="CPS (Automatisierung): 0.00",
            update_job_attr="automation_update_job",
            status_ready_text="Automatisierung: Bereit",
        )

    def _build_configuration(
        self,
        *,
        run_in_background: bool,
        total_override: Optional[int] = None,
    ) -> ClickConfiguration:
        mode = ClickMode(self.click_mode_var.get())
        positions = list(self.click_positions)

        if mode == ClickMode.STATIC_SEQUENCE and not positions:
            raise ValueError("Für den Positionsmodus müssen Zielpunkte vorhanden sein.")

        total_clicks = self.total_clicks_var.get() if total_override is None else total_override

        return ClickConfiguration(
            click_positions=positions,
            click_rate_per_second=max(float(self.click_rate_var.get()), 0.01),
            total_clicks=max(int(total_clicks), 0),
            click_type=ClickType(self.click_type_var.get()),
            click_mode=mode,
            run_in_background=run_in_background,
        )

    def _start_engine(
        self,
        *,
        engine_attr: str,
        config: ClickConfiguration,
        status_var: tk.StringVar,
        click_var: tk.StringVar,
        click_reset_text: str,
        cps_var: tk.StringVar,
        cps_reset_text: str,
        update_job_attr: str,
        minimize: bool,
        on_success: str,
        click_prefix: str,
        status_running_text: str,
        status_ready_text: str,
        cps_prefix: str,
    ) -> None:
        engine: Optional[AutoClickerEngine] = getattr(self, engine_attr)
        if engine and engine.is_running():
            self._log_message("Klicker läuft bereits.")
            return

        existing_job = getattr(self, update_job_attr, None)
        if existing_job:
            self.root.after_cancel(existing_job)
            setattr(self, update_job_attr, None)

        engine = AutoClickerEngine(config)
        engine.register_status_callback(lambda msg: self._log_message(msg))
        setattr(self, engine_attr, engine)

        if engine.start():
            status_var.set(status_running_text)
            click_var.set(click_reset_text)
            cps_var.set(cps_reset_text)
            self._reset_cps_tracker(engine_attr, 0)
            self._log_message(on_success)
            if minimize:
                self.root.iconify()
            self._schedule_click_update(
                engine_attr=engine_attr,
                click_var=click_var,
                cps_var=cps_var,
                update_job_attr=update_job_attr,
                click_prefix=click_prefix,
                cps_prefix=cps_prefix,
            )
        else:
            self._log_message("Klicker konnte nicht gestartet werden", level="WARNING")
            status_var.set(status_ready_text)
            cps_var.set(cps_reset_text)

    def _stop_engine(
        self,
        *,
        engine_attr: str,
        status_var: tk.StringVar,
        click_var: tk.StringVar,
        click_reset_text: str,
        cps_var: tk.StringVar,
        cps_reset_text: str,
        update_job_attr: str,
        status_ready_text: str,
    ) -> None:
        engine: Optional[AutoClickerEngine] = getattr(self, engine_attr)
        if engine and engine.is_running():
            engine.stop()
            self._log_message("Klicker gestoppt.")
        setattr(self, engine_attr, None)
        job = getattr(self, update_job_attr, None)
        if job:
            self.root.after_cancel(job)
            setattr(self, update_job_attr, None)
        status_var.set(status_ready_text)
        click_var.set(click_reset_text)
        cps_var.set(cps_reset_text)
        self._cps_tracker.pop(engine_attr, None)

    def _schedule_click_update(
        self,
        *,
        engine_attr: str,
        click_var: tk.StringVar,
        cps_var: tk.StringVar,
        update_job_attr: str,
        click_prefix: str,
        cps_prefix: str,
    ) -> None:
        engine: Optional[AutoClickerEngine] = getattr(self, engine_attr)
        if not engine:
            return

        def poll() -> None:
            engine_poll: Optional[AutoClickerEngine] = getattr(self, engine_attr)
            if engine_poll and engine_poll.is_running():
                executed = engine_poll.get_clicks_executed()
                click_var.set(f"{click_prefix}: {executed}")
                self._update_cps(
                    engine_attr=engine_attr,
                    current_clicks=executed,
                    cps_var=cps_var,
                    cps_prefix=cps_prefix,
                )
                job_id = self.root.after(self.CLICK_COUNTER_POLL_MS, poll)
                setattr(self, update_job_attr, job_id)
            else:
                setattr(self, update_job_attr, None)
                cps_var.set(f"{cps_prefix}: 0.00")
                self._cps_tracker.pop(engine_attr, None)

        poll()

    def _reset_cps_tracker(self, engine_attr: str, clicks: int) -> None:
        self._cps_tracker[engine_attr] = {
            "count": clicks,
            "time": time.perf_counter(),
        }

    def _update_cps(
        self,
        *,
        engine_attr: str,
        current_clicks: int,
        cps_var: tk.StringVar,
        cps_prefix: str,
    ) -> None:
        now = time.perf_counter()
        tracker = self._cps_tracker.get(engine_attr)
        if tracker is None:
            self._cps_tracker[engine_attr] = {"count": current_clicks, "time": now}
            cps_var.set(f"{cps_prefix}: 0.00")
            return

        delta_clicks = current_clicks - tracker["count"]
        if delta_clicks < 0:
            self._reset_cps_tracker(engine_attr, current_clicks)
            cps_var.set(f"{cps_prefix}: 0.00")
            return

        delta_time = now - tracker["time"]
        if delta_time <= 0 or delta_time < 0.05:
            return

        cps_value = delta_clicks / delta_time if delta_time > 0 else 0.0
        cps_var.set(f"{cps_prefix}: {cps_value:.2f}")
        tracker["count"] = current_clicks
        tracker["time"] = now

    # ------------------------------------------------------------------
    # Hotkeys & logging
    # ------------------------------------------------------------------
    def _setup_hotkeys(self) -> None:
        self.hotkey_manager.register_start_callback(self._handle_hotkey_start)
        self.hotkey_manager.register_stop_callback(self._handle_hotkey_stop)
        ok = self.hotkey_manager.enable_hotkeys()
        if not ok:
            self._log_message("Hotkeys konnten nicht global registriert werden. Prüfen Sie Systemberechtigungen.", level="WARNING")

    def _apply_hotkeys(self) -> None:
        start = self.start_hotkey_var.get().strip() or "F6"
        stop = self.stop_hotkey_var.get().strip() or "F7"
        if self.hotkey_manager.update_hotkeys(start, stop):
            self._log_message(f"Hotkeys aktualisiert: Start={start}, Stop={stop}")
            self._persist_settings()
        else:
            messagebox.showwarning("Hotkeys", "Hotkeys konnten nicht aktualisiert werden.")

    def _handle_hotkey_start(self) -> None:
        if self.engine and self.engine.is_running():
            return
        self.root.after(0, self._start_manual_clicking)

    def _handle_hotkey_stop(self) -> None:
        if self.engine and self.engine.is_running():
            self.root.after(0, self._stop_manual_clicking)
        if self.automation_engine and self.automation_engine.is_running():
            self.root.after(0, self._stop_automation)
        # Also stop any running script automation loop
        if self.script_engine and self.script_engine.is_running():
            try:
                self.script_engine.cancel()
                self.script_status_var.set("Script: Gestoppt")
            except Exception:
                pass

    def _log_message(self, message: str, level: str = "INFO") -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

        if level == "INFO":
            self.logger.log_info(message)
        elif level == "WARNING":
            self.logger.log_warning(message)
        else:
            self.logger.log_error(message)

        self.status_var.set(f"Status: {message}")

    # ------------------------------------------------------------------
    # Script automation helpers
    # ------------------------------------------------------------------
    def _builder_refresh_field_states(self) -> None:
        t = self.builder_action_type.get()
        # Enable/disable inputs according to type
        def set_state(widget, enabled: bool) -> None:
            try:
                widget.configure(state=(tk.NORMAL if enabled else tk.DISABLED))
            except Exception:
                pass
        if self._fld_text is not None:
            set_state(self._fld_text, t == "type_text")
        if self._fld_seq is not None:
            set_state(self._fld_seq, t == "send_keys")
        if self._fld_wait is not None:
            set_state(self._fld_wait, t == "wait")
        if self._fld_cmd is not None:
            set_state(self._fld_cmd, t == "launch_process")
        if self._fld_args is not None:
            set_state(self._fld_args, t == "launch_process")
        if self._fld_title is not None:
            set_state(self._fld_title, t == "window_activate")
        # Mouse/scroll
        for w, condition in [
            (getattr(self, "_fld_click_x", None), t == "mouse_click"),
            (getattr(self, "_fld_click_y", None), t == "mouse_click"),
            (getattr(self, "_fld_click_button", None), t == "mouse_click"),
            (getattr(self, "_fld_click_count", None), t == "mouse_click"),
            (getattr(self, "_fld_scroll_amount", None), t == "scroll"),
            (getattr(self, "_fld_scroll_horizontal", None), t == "scroll"),
        ]:
            if w is not None:
                set_state(w, condition)
        # Optional mouse helpers
        for w, condition in [
            (getattr(self, "_btn_builder_capture", None), t == "mouse_click"),
            (getattr(self, "_btn_builder_cursor", None), t == "mouse_click"),
        ]:
            if w is not None:
                set_state(w, condition)

    def _builder_add_action(self) -> None:
        t = self.builder_action_type.get()
        try:
            if t == "type_text":
                action = {"type": t, "text": self.builder_text_var.get()}
            elif t == "send_keys":
                action = {"type": t, "sequence": self.builder_sequence_var.get()}
            elif t == "wait":
                ms = max(0, int(self.builder_wait_ms_var.get()))
                action = {"type": t, "milliseconds": ms}
            elif t == "launch_process":
                args = [a for a in self.builder_args_var.get().split() if a]
                action = {"type": t, "command": self.builder_command_var.get(), "args": args}
            elif t == "window_activate":
                action = {"type": t, "title": self.builder_title_var.get()}
            elif t == "mouse_click":
                x = self.builder_click_x_var.get().strip()
                y = self.builder_click_y_var.get().strip()
                action = {
                    "type": t,
                    "button": (self.builder_click_button_var.get() or "left"),
                    "clicks": max(1, int(self.builder_click_count_var.get() or 1)),
                }
                if x:
                    action["x"] = int(x)
                if y:
                    action["y"] = int(y)
            elif t == "scroll":
                action = {
                    "type": t,
                    "amount": int(self.builder_scroll_amount_var.get() or 0),
                    "horizontal": bool(self.builder_scroll_horizontal_var.get()),
                }
            else:
                return
            self.script_actions.append(action)
            self._builder_refresh_list()
        except Exception as exc:
            messagebox.showerror("Builder", f"Aktion konnte nicht hinzugefügt werden: {exc}")

    def _builder_remove_action(self) -> None:
        if not self.script_actions_listbox:
            return
        sel = self.script_actions_listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self.script_actions):
            del self.script_actions[idx]
            self._builder_refresh_list()
            self._builder_maybe_autosync()

    def _builder_duplicate_action(self) -> None:
        if not self.script_actions_listbox:
            return
        sel = self.script_actions_listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self.script_actions):
            import copy
            self.script_actions.insert(idx + 1, copy.deepcopy(self.script_actions[idx]))
            self._builder_refresh_list()
            if self.script_actions_listbox:
                self.script_actions_listbox.selection_clear(0, tk.END)
                self.script_actions_listbox.selection_set(idx + 1)
                self.script_actions_listbox.see(idx + 1)
            self._builder_maybe_autosync()

    def _builder_move_action(self, delta: int) -> None:
        if not self.script_actions_listbox:
            return
        sel = self.script_actions_listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= len(self.script_actions):
            return
        # Swap actions
        self.script_actions[idx], self.script_actions[new_idx] = (
            self.script_actions[new_idx],
            self.script_actions[idx],
        )
        self._builder_refresh_list()
        # Reselect moved item
        if self.script_actions_listbox:
            self.script_actions_listbox.selection_clear(0, tk.END)
            self.script_actions_listbox.selection_set(new_idx)
            self.script_actions_listbox.see(new_idx)
        self._builder_maybe_autosync()

    def _builder_move_action_to(self, where: str) -> None:
        if not self.script_actions_listbox:
            return
        sel = self.script_actions_listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if not (0 <= idx < len(self.script_actions)):
            return
        action = self.script_actions.pop(idx)
        if where == "top":
            self.script_actions.insert(0, action)
            new_idx = 0
        else:
            self.script_actions.append(action)
            new_idx = len(self.script_actions) - 1
        self._builder_refresh_list()
        if self.script_actions_listbox:
            self.script_actions_listbox.selection_clear(0, tk.END)
            self.script_actions_listbox.selection_set(new_idx)
            self.script_actions_listbox.see(new_idx)
        self._builder_maybe_autosync()

    def _builder_clear_actions(self) -> None:
        if not self.script_actions:
            return
        self.script_actions.clear()
        self._builder_refresh_list()
        self._builder_maybe_autosync()

    def _builder_replace_action(self) -> None:
        if not self.script_actions_listbox:
            return
        sel = self.script_actions_listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if not (0 <= idx < len(self.script_actions)):
            return
        # Build action from current form fields
        t = self.builder_action_type.get()
        try:
            if t == "type_text":
                action = {"type": t, "text": self.builder_text_var.get()}
            elif t == "send_keys":
                action = {"type": t, "sequence": self.builder_sequence_var.get()}
            elif t == "wait":
                action = {"type": t, "milliseconds": max(0, int(self.builder_wait_ms_var.get()))}
            elif t == "launch_process":
                args = [a for a in self.builder_args_var.get().split() if a]
                action = {"type": t, "command": self.builder_command_var.get(), "args": args}
            elif t == "window_activate":
                action = {"type": t, "title": self.builder_title_var.get()}
            elif t == "mouse_click":
                x = self.builder_click_x_var.get().strip()
                y = self.builder_click_y_var.get().strip()
                action = {
                    "type": t,
                    "button": (self.builder_click_button_var.get() or "left"),
                    "clicks": max(1, int(self.builder_click_count_var.get() or 1)),
                }
                if x:
                    action["x"] = int(x)
                if y:
                    action["y"] = int(y)
            elif t == "scroll":
                action = {
                    "type": t,
                    "amount": int(self.builder_scroll_amount_var.get() or 0),
                    "horizontal": bool(self.builder_scroll_horizontal_var.get()),
                }
            else:
                return
            self.script_actions[idx] = action
            self._builder_refresh_list()
            if self.script_actions_listbox:
                self.script_actions_listbox.selection_clear(0, tk.END)
                self.script_actions_listbox.selection_set(idx)
                self.script_actions_listbox.see(idx)
            self._builder_maybe_autosync()
        except Exception as exc:
            messagebox.showerror("Builder", f"Aktion konnte nicht ersetzt werden: {exc}")

    def _builder_insert_template(self) -> None:
        name = (self.builder_template_var.get() or "").strip()
        if not name or name == "Vorlage wählen…":
            return
        try:
            if name == "Notepad: Start + Tippen + Enter":
                tpl = [
                    {"type": "launch_process", "command": "notepad.exe", "args": []},
                    {"type": "wait", "milliseconds": 400},
                    {"type": "type_text", "text": "Hello from Script!"},
                    {"type": "send_keys", "sequence": "<ENTER>"},
                ]
            elif name == "Nur Tippen + Enter":
                tpl = [
                    {"type": "type_text", "text": self.builder_text_var.get() or "Hello"},
                    {"type": "send_keys", "sequence": "<ENTER>"},
                ]
            elif name == "Warte + Fenster aktivieren":
                tpl = [
                    {"type": "wait", "milliseconds": max(0, int(self.builder_wait_ms_var.get()))},
                    {"type": "window_activate", "title": self.builder_title_var.get() or ""},
                ]
            elif name == "Chrome: URL öffnen + Enter":
                url = self.builder_text_var.get().strip() or "https://example.com"
                tpl = [
                    {"type": "launch_process", "command": "chrome.exe", "args": []},
                    {"type": "wait", "milliseconds": 700},
                    {"type": "type_text", "text": url},
                    {"type": "send_keys", "sequence": "<ENTER>"},
                ]
            elif name == "Scroll: 3x runter":
                tpl = [
                    {"type": "scroll", "amount": -600, "horizontal": False},
                    {"type": "wait", "milliseconds": 200},
                    {"type": "scroll", "amount": -600, "horizontal": False},
                    {"type": "wait", "milliseconds": 200},
                    {"type": "scroll", "amount": -600, "horizontal": False},
                ]
            elif name == "Mausklick an Koordinaten":
                x = self.builder_click_x_var.get().strip()
                y = self.builder_click_y_var.get().strip()
                action = {"type": "mouse_click", "button": "left", "clicks": 1}
                if x:
                    action["x"] = int(x)
                if y:
                    action["y"] = int(y)
                tpl = [action]
            else:
                tpl = []
            self.script_actions.extend(tpl)
            self._builder_refresh_list()
            self._builder_maybe_autosync()
        except Exception as exc:
            messagebox.showerror("Vorlage", f"Vorlage konnte nicht eingefügt werden: {exc}")

    def _builder_insert_key_token(self) -> None:
        try:
            token = (self.builder_key_token_var.get() or "").strip()
            if not token:
                return
            current = self.builder_sequence_var.get() or ""
            if current and not current.endswith(" "):
                current += " "
            self.builder_sequence_var.set(current + token)
        except Exception:
            pass

    def _builder_refresh_list(self) -> None:
        if not self.script_actions_listbox:
            return
        self.script_actions_listbox.delete(0, tk.END)
        for i, a in enumerate(self.script_actions, start=1):
            summary = a.get("type", "?")
            if summary == "type_text":
                summary += f" — {a.get('text','')}"
            elif summary == "send_keys":
                summary += f" — {a.get('sequence','')}"
            elif summary == "wait":
                summary += f" — {a.get('milliseconds',0)} ms"
            elif summary == "launch_process":
                summary += f" — {a.get('command','')}"
            elif summary == "window_activate":
                summary += f" — {a.get('title','')}"
            elif summary == "mouse_click":
                pos = []
                if "x" in a and "y" in a:
                    pos = [str(a.get("x")), str(a.get("y"))]
                summary += " — " + ", ".join(pos or ["Cursor"]) + f" | {a.get('button','left')} x{a.get('clicks',1)}"
            elif summary == "scroll":
                amt = a.get("amount", 0)
                direction = "horizontal" if a.get("horizontal", False) else "vertical"
                summary += f" — {amt} ({direction})"
            self.script_actions_listbox.insert(tk.END, f"{i}. {summary}")

    def _builder_maybe_autosync(self) -> None:
        if bool(self.builder_autosync_var.get()):
            self._builder_to_editor()

    # ------------------------------------------------------------------
    # Builder Window
    # ------------------------------------------------------------------
    def _open_builder_window(self) -> None:
        if self._builder_win and tk.Toplevel.winfo_exists(self._builder_win):
            try:
                self._builder_win.deiconify()
                self._builder_win.lift()
                self._builder_win.focus_force()
                return
            except Exception:
                pass

        win = tk.Toplevel(self.root)
        win.title("Script‑Builder")
        win.geometry("1000x950")
        win.transient(self.root)
        self._builder_win = win

        container = ttk.Frame(win, padding=12, style="Background.TFrame")
        container.pack(fill=tk.BOTH, expand=True)
        # Layout: left = vertical buttons, right = main area (fields top + list bottom)
        container.columnconfigure(0, weight=0)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        # Left: sidebar (buttons only)
        sidebar = ttk.Frame(container, style="CardBody.TFrame")
        sidebar.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        sidebar.columnconfigure(0, weight=1)
        for r in range(12):
            sidebar.rowconfigure(r, weight=0)

        # Right: main area (fields + list)
        main = ttk.Frame(container, style="CardBody.TFrame")
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=0)
        main.rowconfigure(1, weight=1)

        # Fields (top of main)
        fields = ttk.Frame(main, style="CardBody.TFrame")
        fields.grid(row=0, column=0, sticky="new", padx=0)
        for i in range(2):
            fields.columnconfigure(i, weight=1)

        ttk.Label(fields, text="Schnell-Bau: Aktion").grid(row=0, column=0, sticky="w")
        type_cb = ttk.Combobox(
            fields,
            textvariable=self.builder_action_type,
            state="readonly",
            values=[
                "type_text",
                "send_keys",
                "wait",
                "launch_process",
                "window_activate",
                "mouse_click",
                "scroll",
            ],
        )
        type_cb.grid(row=0, column=1, sticky="ew")
        type_cb.bind("<<ComboboxSelected>>", lambda e: self._builder_refresh_field_states())

        # Row inputs
        self._fld_text = ttk.Entry(fields, textvariable=self.builder_text_var)
        self._fld_seq = ttk.Entry(fields, textvariable=self.builder_sequence_var)
        self._fld_wait = ttk.Spinbox(fields, from_=0, to=600000, increment=50, textvariable=self.builder_wait_ms_var, width=10)
        self._fld_cmd = ttk.Entry(fields, textvariable=self.builder_command_var)
        self._fld_args = ttk.Entry(fields, textvariable=self.builder_args_var)
        self._fld_title = ttk.Entry(fields, textvariable=self.builder_title_var)
        # Mouse click fields
        self._fld_click_x = ttk.Entry(fields, textvariable=self.builder_click_x_var, width=10)
        self._fld_click_y = ttk.Entry(fields, textvariable=self.builder_click_y_var, width=10)
        self._fld_click_button = ttk.Combobox(fields, textvariable=self.builder_click_button_var, state="readonly", values=["left", "right", "middle"], width=10)
        self._fld_click_count = ttk.Spinbox(fields, from_=1, to=10, increment=1, textvariable=self.builder_click_count_var, width=8)
        # Scroll fields
        self._fld_scroll_amount = ttk.Spinbox(fields, from_=-5000, to=5000, increment=50, textvariable=self.builder_scroll_amount_var, width=10)
        self._fld_scroll_horizontal = ttk.Checkbutton(fields, text="Horizontal", variable=self.builder_scroll_horizontal_var)

        ttk.Label(fields, text="Text:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self._fld_text.grid(row=1, column=1, sticky="ew", pady=(6, 0))
        ttk.Label(fields, text="Keys/Sequenz:").grid(row=2, column=0, sticky="w")
        seq_row = ttk.Frame(fields)
        seq_row.grid(row=2, column=1, sticky="ew")
        seq_row.columnconfigure(0, weight=1)
        self._fld_seq.grid(in_=seq_row, row=0, column=0, sticky="ew")
        self.builder_key_token_var = tk.StringVar(value="<ENTER>")
        ttk.Combobox(seq_row, textvariable=self.builder_key_token_var, state="readonly", values=[
            "<ENTER>", "<TAB>", "<ESC>", "<SPACE>", "<BACKSPACE>", "<DELETE>",
            "<HOME>", "<END>", "<PAGE_UP>", "<PAGE_DOWN>", "<UP>", "<DOWN>", "<LEFT>", "<RIGHT>",
        ], width=14).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(seq_row, text="Einfügen", style="Ghost.TButton", command=self._builder_insert_key_token).grid(row=0, column=2, padx=(6, 0))
        ttk.Label(fields, text="Warte (ms):").grid(row=3, column=0, sticky="w")
        self._fld_wait.grid(row=3, column=1, sticky="w")
        ttk.Label(fields, text="Programm:").grid(row=4, column=0, sticky="w")
        self._fld_cmd.grid(row=4, column=1, sticky="ew")
        ttk.Label(fields, text="Argumente (Leerzeichen-getrennt):").grid(row=5, column=0, sticky="w")
        self._fld_args.grid(row=5, column=1, sticky="ew")
        ttk.Label(fields, text="Fenstertitel enthält:").grid(row=6, column=0, sticky="w")
        self._fld_title.grid(row=6, column=1, sticky="ew")

        # Mouse click row
        mouse_row = 7
        ttk.Label(fields, text="Mausklick (x,y leer = Cursor):").grid(row=mouse_row, column=0, sticky="w", pady=(6, 0))
        mouse_frame = ttk.Frame(fields)
        mouse_frame.grid(row=mouse_row, column=1, sticky="ew", pady=(6, 0))
        for i in range(6):
            mouse_frame.columnconfigure(i, weight=0)
        ttk.Label(mouse_frame, text="X:").grid(row=0, column=0, padx=(0, 4))
        self._fld_click_x.grid(in_=mouse_frame, row=0, column=1)
        ttk.Label(mouse_frame, text="Y:").grid(row=0, column=2, padx=(8, 4))
        self._fld_click_y.grid(in_=mouse_frame, row=0, column=3)
        self._fld_click_button.grid(in_=mouse_frame, row=0, column=4, padx=(8, 4))
        self._fld_click_count.grid(in_=mouse_frame, row=0, column=5)
        # Mouse helpers row
        mouse_help = ttk.Frame(fields)
        mouse_help.grid(row=mouse_row+1, column=1, sticky="w", pady=(2, 0))
        self._btn_builder_capture = ttk.Button(mouse_help, text="Wählen…", style="Ghost.TButton", command=self._builder_capture_click)
        self._btn_builder_capture.grid(row=0, column=0, padx=(0, 6))
        self._btn_builder_cursor = ttk.Button(mouse_help, text="Cursor übernehmen", style="Ghost.TButton", command=self._builder_set_xy_from_cursor)
        self._btn_builder_cursor.grid(row=0, column=1)

        # Scroll row
        scroll_row = 9
        ttk.Label(fields, text="Scroll:").grid(row=scroll_row, column=0, sticky="w")
        scroll_frame = ttk.Frame(fields)
        scroll_frame.grid(row=scroll_row, column=1, sticky="ew")
        ttk.Label(scroll_frame, text="Amount:").grid(row=0, column=0)
        self._fld_scroll_amount.grid(in_=scroll_frame, row=0, column=1, padx=(6, 6))
        self._fld_scroll_horizontal.grid(in_=scroll_frame, row=0, column=2)

    # Sidebar controls (no extra separator; keep fields visible)
        ttk.Button(sidebar, text="Hinzufügen", style="Accent.TButton", command=self._builder_add_action).grid(row=0, column=0, sticky="ew", pady=(0,4))
        ttk.Button(sidebar, text="Ersetzen", style="Ghost.TButton", command=self._builder_replace_action).grid(row=1, column=0, sticky="ew", pady=2)
        ttk.Button(sidebar, text="Duplizieren", style="Ghost.TButton", command=self._builder_duplicate_action).grid(row=2, column=0, sticky="ew", pady=2)
        ttk.Button(sidebar, text="Entfernen", style="Ghost.TButton", command=self._builder_remove_action).grid(row=3, column=0, sticky="ew", pady=2)
        ttk.Button(sidebar, text="Leeren", style="Ghost.TButton", command=self._builder_clear_actions).grid(row=4, column=0, sticky="ew", pady=2)
        ttk.Separator(sidebar, orient="horizontal").grid(row=5, column=0, sticky="ew", pady=6)
        ttk.Button(sidebar, text="Auswahl laden", style="Ghost.TButton", command=self._builder_load_selected_to_fields).grid(row=6, column=0, sticky="ew", pady=2)
        ttk.Button(sidebar, text="→ Editor übertragen", style="Ghost.TButton", command=self._builder_to_editor).grid(row=7, column=0, sticky="ew", pady=2)
        ttk.Checkbutton(sidebar, text="Auto‑Sync", variable=self.builder_autosync_var).grid(row=8, column=0, sticky="w", pady=(6,2))
        ttk.Label(sidebar, text="Vorlagen:").grid(row=9, column=0, sticky="w", pady=(8,2))
        ttk.Combobox(
            sidebar,
            textvariable=self.builder_template_var,
            state="readonly",
            values=[
                "Vorlage wählen…",
                "Notepad: Start + Tippen + Enter",
                "Nur Tippen + Enter",
                "Warte + Fenster aktivieren",
                "Chrome: URL öffnen + Enter",
                "Scroll: 3x runter",
                "Mausklick an Koordinaten",
            ],
            width=20,
        ).grid(row=10, column=0, sticky="ew")
        ttk.Button(sidebar, text="Vorlage einfügen", style="Ghost.TButton", command=self._builder_insert_template).grid(row=11, column=0, sticky="ew", pady=(4,0))
        # Loop controls
        ttk.Separator(sidebar, orient="horizontal").grid(row=12, column=0, sticky="ew", pady=6)
        loop_frame = ttk.Frame(sidebar)
        loop_frame.grid(row=13, column=0, sticky="ew")
        loop_frame.columnconfigure(1, weight=1)
        ttk.Label(loop_frame, text="Wiederholungen:").grid(row=0, column=0, sticky="w")
        repeat_spin = ttk.Spinbox(loop_frame, from_=1, to=1000000, increment=1, textvariable=self.builder_repeat_count_var, width=8)
        repeat_spin.grid(row=0, column=1, sticky="ew", padx=(6,0))
        until_chk = ttk.Checkbutton(loop_frame, text="Bis Stop", variable=self.builder_until_stopped_var)
        until_chk.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6,0))
        # Disable repeat when until_stopped is enabled
        def _toggle_repeat_state(*_args):
            try:
                repeat_spin.configure(state=(tk.DISABLED if self.builder_until_stopped_var.get() else tk.NORMAL))
            except Exception:
                pass
        _toggle_repeat_state()
        try:
            self.builder_until_stopped_var.trace_add("write", lambda *_: _toggle_repeat_state())
        except Exception:
            pass

        # Right: actions list (bottom area of main)
        right = ttk.Frame(main, style="CardBody.TFrame")
        right.grid(row=1, column=0, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        ttk.Label(right, text="Aktionen").grid(row=0, column=0, sticky="w")
        self.script_actions_listbox = tk.Listbox(right, height=16, bd=0, highlightthickness=0)
        self.script_actions_listbox.grid(row=1, column=0, sticky="nsew")
        self.script_actions_listbox.bind("<Double-1>", lambda e: self._builder_edit_selected_action())
        self.script_actions_listbox.bind("<Button-3>", self._builder_show_context_menu)

        # Context menu
        self._builder_context_menu = tk.Menu(win, tearoff=0)
        self._builder_context_menu.add_command(label="Bearbeiten", command=self._builder_edit_selected_action)
        self._builder_context_menu.add_command(label="Duplizieren", command=self._builder_duplicate_action)
        self._builder_context_menu.add_command(label="Entfernen", command=self._builder_remove_action)
        self._builder_context_menu.add_separator()
        self._builder_context_menu.add_command(label="▲ Hoch", command=lambda: self._builder_move_action(-1))
        self._builder_context_menu.add_command(label="▼ Runter", command=lambda: self._builder_move_action(1))
        self._builder_context_menu.add_command(label="⤒ Anfang", command=lambda: self._builder_move_action_to("top"))
        self._builder_context_menu.add_command(label="⤓ Ende", command=lambda: self._builder_move_action_to("bottom"))

        reorder = ttk.Frame(right, style="CardBody.TFrame")
        reorder.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        reorder.columnconfigure((0, 1, 2, 3), weight=1)
        ttk.Button(reorder, text="▲ Hoch", style="Ghost.TButton", command=lambda: self._builder_move_action(-1)).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(reorder, text="▼ Runter", style="Ghost.TButton", command=lambda: self._builder_move_action(1)).grid(row=0, column=1, sticky="ew", padx=(3, 3))
        ttk.Button(reorder, text="⤒ Anfang", style="Ghost.TButton", command=lambda: self._builder_move_action_to("top")).grid(row=0, column=2, sticky="ew", padx=(3, 3))
        ttk.Button(reorder, text="⤓ Ende", style="Ghost.TButton", command=lambda: self._builder_move_action_to("bottom")).grid(row=0, column=3, sticky="ew", padx=(3, 0))

        # Setup states and list
        self._builder_refresh_field_states()
        self._builder_refresh_list()

        def on_close() -> None:
            try:
                self._close_builder_window()
            finally:
                win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)

    def _close_builder_window(self) -> None:
        # Clear widget references
        self._builder_win = None
        self.script_actions_listbox = None
        self._fld_text = None
        self._fld_seq = None
        self._fld_wait = None
        self._fld_cmd = None
        self._fld_args = None
        self._fld_title = None
        self._btn_builder_capture = None
        self._btn_builder_cursor = None
        self._builder_capture_in_progress = False

    def _builder_to_editor(self) -> None:
        try:
            data = {"name": "Script", "actions": self.script_actions or []}
            # Loop settings
            if bool(self.builder_until_stopped_var.get()):
                data["until_stopped"] = True
            else:
                rc = int(self.builder_repeat_count_var.get() or 1)
                if rc > 1:
                    data["repeat"] = rc
            self.script_text.delete("1.0", tk.END)
            self.script_text.insert(tk.END, json.dumps(data, ensure_ascii=False, indent=2))
            self.script_status_var.set("Script: In Editor übertragen")
        except Exception as exc:
            self._log_message(f"Builder→Editor Fehler: {exc}", level="ERROR")

    def _editor_to_builder(self) -> None:
        try:
            raw = self.script_text.get("1.0", tk.END).strip()
            data = json.loads(raw)
            actions = data.get("actions", [])
            if not isinstance(actions, list):
                raise ValueError("'actions' muss eine Liste sein")
            # Minimal sanitize: keep only known keys
            sanitized = []
            for a in actions:
                if not isinstance(a, dict) or "type" not in a:
                    continue
                t = a.get("type")
                if t == "type_text":
                    sanitized.append({"type": t, "text": a.get("text", "")})
                elif t == "send_keys":
                    sanitized.append({"type": t, "sequence": a.get("sequence", "")})
                elif t == "wait":
                    ms = int(a.get("milliseconds", 0) or 0)
                    sanitized.append({"type": t, "milliseconds": max(0, ms)})
                elif t == "launch_process":
                    args = a.get("args", [])
                    if not isinstance(args, list):
                        args = []
                    sanitized.append({"type": t, "command": a.get("command", ""), "args": args})
                elif t == "window_activate":
                    sanitized.append({"type": t, "title": a.get("title", "")})
                elif t == "mouse_click":
                    out = {"type": t, "button": a.get("button", "left"), "clicks": int(a.get("clicks", 1) or 1)}
                    x_val = a.get("x", None)
                    y_val = a.get("y", None)
                    if isinstance(x_val, (int, float, str)) and str(x_val).strip() != "":
                        out["x"] = int(x_val)
                    if isinstance(y_val, (int, float, str)) and str(y_val).strip() != "":
                        out["y"] = int(y_val)
                    sanitized.append(out)
                elif t == "scroll":
                    sanitized.append({"type": t, "amount": int(a.get("amount", 0) or 0), "horizontal": bool(a.get("horizontal", False))})
            self.script_actions = sanitized
            # Loop settings
            try:
                if bool(data.get("until_stopped", False)):
                    self.builder_until_stopped_var.set(True)
                else:
                    rc = int(data.get("repeat", 1) or 1)
                    self.builder_repeat_count_var.set(max(1, rc))
                    self.builder_until_stopped_var.set(False)
            except Exception:
                self.builder_repeat_count_var.set(1)
                self.builder_until_stopped_var.set(False)
            self._builder_refresh_list()
            self.script_status_var.set("Script: In Builder übertragen")
        except Exception as exc:
            messagebox.showerror("Editor", f"Konnte Aktionen nicht laden: {exc}")

    def _builder_edit_selected_action(self) -> None:
        if not self.script_actions_listbox:
            return
        sel = self.script_actions_listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if not (0 <= idx < len(self.script_actions)):
            return
        a = self.script_actions[idx]
        t = a.get("type", "")
        dlg = tk.Toplevel(self._builder_win or self.root)
        dlg.title("Aktion bearbeiten")
        dlg.geometry("420x260")
        dlg.transient(self._builder_win or self.root)
        container = ttk.Frame(dlg, padding=12)
        container.pack(fill=tk.BOTH, expand=True)
        row = 0
        ttk.Label(container, text=f"Typ: {t}", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        # create fields per type
        entries: Dict[str, Any] = {}
        def add_entry(label: str, init_val: str = ""):
            nonlocal row
            ttk.Label(container, text=label).grid(row=row, column=0, sticky="w", pady=(6,0))
            var = tk.StringVar(value=init_val)
            ent = ttk.Entry(container, textvariable=var)
            ent.grid(row=row, column=1, sticky="ew", pady=(6,0))
            container.columnconfigure(1, weight=1)
            entries[label] = var
            row += 1
        if t == "type_text":
            add_entry("Text", a.get("text", ""))
        elif t == "send_keys":
            add_entry("Sequenz", a.get("sequence", ""))
        elif t == "wait":
            add_entry("Millisekunden", str(a.get("milliseconds", 0)))
        elif t == "launch_process":
            add_entry("Programm", a.get("command", ""))
            add_entry("Argumente", " ".join(a.get("args", []) if isinstance(a.get("args", []), list) else []))
        elif t == "window_activate":
            add_entry("Fenstertitel", a.get("title", ""))
        elif t == "mouse_click":
            add_entry("X", str(a.get("x", "")))
            add_entry("Y", str(a.get("y", "")))
            add_entry("Button", a.get("button", "left"))
            add_entry("Klicks", str(a.get("clicks", 1)))
        elif t == "scroll":
            add_entry("Amount", str(a.get("amount", 0)))
            add_entry("Horizontal", "1" if a.get("horizontal", False) else "0")

        btns = ttk.Frame(container)
        btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12,0))
        def save_and_close() -> None:
            try:
                if t == "type_text":
                    a.update({"type":"type_text","text": entries["Text"].get()})
                elif t == "send_keys":
                    a.update({"type":"send_keys","sequence": entries["Sequenz"].get()})
                elif t == "wait":
                    a.update({"type":"wait","milliseconds": max(0,int(entries["Millisekunden"].get() or 0))})
                elif t == "launch_process":
                    args = [p for p in (entries["Argumente"].get() or "").split() if p]
                    a.update({"type":"launch_process","command": entries["Programm"].get(), "args": args})
                elif t == "window_activate":
                    a.update({"type":"window_activate","title": entries["Fenstertitel"].get()})
                elif t == "mouse_click":
                    x = entries["X"].get().strip(); y = entries["Y"].get().strip()
                    upd = {"type":"mouse_click","button": entries["Button"].get() or "left","clicks": max(1,int(entries["Klicks"].get() or 1))}
                    if x: upd["x"] = int(x)
                    if y: upd["y"] = int(y)
                    a.clear(); a.update(upd)
                elif t == "scroll":
                    a.update({"type":"scroll","amount": int(entries["Amount"].get() or 0), "horizontal": entries["Horizontal"].get().strip() in ("1","true","True")})
                self._builder_refresh_list(); self._builder_maybe_autosync(); dlg.destroy()
            except Exception as exc:
                messagebox.showerror("Bearbeiten", f"Konnte Aktion nicht speichern: {exc}")
        ttk.Button(btns, text="Speichern", command=save_and_close, style="Accent.TButton").grid(row=0, column=0, padx=6)
        ttk.Button(btns, text="Abbrechen", command=dlg.destroy, style="Ghost.TButton").grid(row=0, column=1)

    def _builder_show_context_menu(self, event) -> None:
        if not self.script_actions_listbox or not self._builder_context_menu:
            return
        try:
            # Select item under cursor
            idx = self.script_actions_listbox.nearest(event.y)
            self.script_actions_listbox.selection_clear(0, tk.END)
            self.script_actions_listbox.selection_set(idx)
            self._builder_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self._builder_context_menu.grab_release()
            except Exception:
                pass

    def _builder_load_selected_to_fields(self) -> None:
        if not self.script_actions_listbox:
            return
        sel = self.script_actions_listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if not (0 <= idx < len(self.script_actions)):
            return
        a = self.script_actions[idx]
        t = a.get("type")
        try:
            self.builder_action_type.set(str(t or "type_text"))
            if t == "type_text":
                self.builder_text_var.set(a.get("text", ""))
            elif t == "send_keys":
                self.builder_sequence_var.set(a.get("sequence", ""))
            elif t == "wait":
                self.builder_wait_ms_var.set(int(a.get("milliseconds", 0) or 0))
            elif t == "launch_process":
                self.builder_command_var.set(a.get("command", ""))
                args = a.get("args", [])
                if isinstance(args, list):
                    self.builder_args_var.set(" ".join(str(x) for x in args))
                else:
                    self.builder_args_var.set("")
            elif t == "window_activate":
                self.builder_title_var.set(a.get("title", ""))
            elif t == "mouse_click":
                x = a.get("x")
                y = a.get("y")
                self.builder_click_x_var.set("" if x is None else str(int(x)))
                self.builder_click_y_var.set("" if y is None else str(int(y)))
                self.builder_click_button_var.set(a.get("button", "left"))
                self.builder_click_count_var.set(int(a.get("clicks", 1) or 1))
            elif t == "scroll":
                self.builder_scroll_amount_var.set(int(a.get("amount", 0) or 0))
                self.builder_scroll_horizontal_var.set(bool(a.get("horizontal", False)))
        finally:
            self._builder_refresh_field_states()

    def _validate_script_editor(self) -> None:
        # Clear previous error highlight
        try:
            self.script_text.tag_delete("json_error")
        except Exception:
            pass
        self.script_text.tag_configure("json_error", background="#ffdddd")
        raw = self.script_text.get("1.0", tk.END).strip()
        if not raw:
            self.script_status_var.set("Script: Leer")
            return
        try:
            json.loads(raw)
            self.script_status_var.set("Script: JSON gültig")
        except Exception as exc:
            # Try to extract position
            line = 1
            col = 0
            msg = str(exc)
            try:
                # JSONDecodeError has lineno & colno
                line = getattr(exc, 'lineno', 1) or 1
                col = getattr(exc, 'colno', 0) or 0
            except Exception:
                pass
            # Highlight the error line
            try:
                start = f"{line}.0"
                end = f"{line}.end"
                self.script_text.tag_add("json_error", start, end)
                self.script_text.see(start)
            except Exception:
                pass
            self.script_status_var.set(f"Script: JSON Fehler (Zeile {line}, Spalte {col})")
            self._log_message(f"JSON-Validierung: {msg}", level="WARNING")
    def _populate_script_editor_with_default(self) -> None:
        template = {
            "name": "Demo",
            "actions": [
                {"type": "wait", "milliseconds": 300},
                {"type": "type_text", "text": "Hello from Script!"},
                {"type": "send_keys", "sequence": "<ENTER>"},
            ],
        }
        try:
            self.script_text.delete("1.0", tk.END)
            self.script_text.insert(tk.END, json.dumps(template, ensure_ascii=False, indent=2))
        except Exception:
            pass

    def _load_example_script(self) -> None:
        try:
            import pathlib
            path = pathlib.Path(__file__).with_name("automation").joinpath("examples", "example_notepad.json")
            if path.exists():
                content = path.read_text(encoding="utf-8")
            else:
                content = self.script_text.get("1.0", tk.END)
            self.script_text.delete("1.0", tk.END)
            self.script_text.insert(tk.END, content)
            self.script_status_var.set("Script: Beispiel geladen")
        except Exception as exc:
            self.script_status_var.set("Script: Konnte Beispiel nicht laden")
            self._log_message(f"Script-Beispiel konnte nicht geladen werden: {exc}", level="ERROR")

    def _open_script_file(self) -> None:
        try:
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                filetypes=[("JSON", "*.json"), ("Alle Dateien", "*.*")]
            )
            if not path:
                return
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.script_text.delete("1.0", tk.END)
            self.script_text.insert(tk.END, content)
            self.script_status_var.set(f"Script: Datei geladen")
        except Exception as exc:
            self.script_status_var.set("Script: Fehler beim Öffnen")
            self._log_message(f"Script konnte nicht geöffnet werden: {exc}", level="ERROR")

    def _save_script_as(self) -> None:
        try:
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
            if not path:
                return
            content = self.script_text.get("1.0", tk.END).strip()
            # Validate JSON before saving
            json.loads(content)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.script_status_var.set("Script: Gespeichert")
        except Exception as exc:
            self.script_status_var.set("Script: Fehler beim Speichern")
            self._log_message(f"Script konnte nicht gespeichert werden: {exc}", level="ERROR")

    def _start_script_automation(self) -> None:
        # Don't run multiple
        if self.script_engine and self.script_engine.is_running():
            self._log_message("Script läuft bereits.")
            return
        raw = self.script_text.get("1.0", tk.END).strip()
        try:
            data = json.loads(raw)
            script = AutomationScript.from_dict(data)
            engine = AutomationEngine(script)
            engine.on_log(lambda m: self._log_message(f"[Script] {m}"))
            engine.on_done(lambda ok, msg: self._on_script_done(ok, msg))
            self.script_engine = engine
            self.script_status_var.set("Script: Läuft")
            engine.start()
        except Exception as exc:
            messagebox.showerror("Script", f"Ungültiges Script: {exc}")
            self.script_status_var.set("Script: Fehler")
            self._log_message(f"Script konnte nicht gestartet werden: {exc}", level="ERROR")

    def _stop_script_automation(self) -> None:
        if self.script_engine and self.script_engine.is_running():
            self.script_engine.cancel()
            self.script_status_var.set("Script: Bereit")
            self._log_message("Script gestoppt.")

    def _on_script_done(self, ok: bool, msg: str) -> None:
        self.script_status_var.set(f"Script: {'Fertig' if ok else 'Beendet'} ({msg})")
        self._log_message(f"Script beendet: {msg}")

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------
    def _on_click_mode_changed(self) -> None:
        static_mode = ClickMode(self.click_mode_var.get()) == ClickMode.STATIC_SEQUENCE
        state = tk.NORMAL if static_mode else tk.DISABLED
        for widget in (
            self.position_listbox,
            self.add_current_button,
            self.add_custom_button,
            self.capture_button,
            self.capture_cancel_button,
            self.remove_selected_button,
            self.clear_all_button,
        ):
            widget.configure(state=state)
        if not static_mode:
            self.position_listbox.selection_clear(0, tk.END)
        self._persist_settings()

    def _toggle_debug_overlay(self, enabled: bool) -> None:
        self.debug_overlay.toggle(enabled)
        self._persist_settings()

    def _start_monitor_updates(self) -> None:
        def poll() -> None:
            try:
                x, y = pyautogui.position()
                # Compute monitor list (lazy)
                mons = self._get_monitors()
                idx = self._find_monitor_index(int(x), int(y), mons)
                if idx is None:
                    info = f"Cursor: ({int(x)}, {int(y)}) | Monitore: {len(mons)}"
                else:
                    m = mons[idx]
                    info = (
                        f"Cursor: ({int(x)}, {int(y)}) | Monitor {idx+1}: {m['width']}x{m['height']} @ ({m['x']},{m['y']}) | Monitore: {len(mons)}"
                    )
                self.monitor_info_var.set(info)
            except Exception:
                self.monitor_info_var.set("Cursorinformationen nicht verfügbar.")
            self.monitor_job = self.root.after(self.MONITOR_POLL_MS, poll)

        poll()

    def _get_monitors(self) -> List[Dict[str, int]]:
        """List monitor rectangles as dicts with x,y,width,height."""
        try:
            from screeninfo import get_monitors  # type: ignore
            mons = get_monitors() or []
            out: List[Dict[str, int]] = []
            for m in mons:
                out.append({"x": int(m.x), "y": int(m.y), "width": int(m.width), "height": int(m.height)})
            if out:
                return out
        except Exception:
            pass
        # Fallback: single screen via pyautogui
        try:
            s = pyautogui.size()
            return [{"x": 0, "y": 0, "width": int(s.width), "height": int(s.height)}]
        except Exception:
            return [{"x": 0, "y": 0, "width": 1280, "height": 800}]

    # --- Builder mouse helpers --------------------------------------
    def _builder_capture_click(self) -> None:
        if self._builder_capture_in_progress or self.capture_in_progress:
            return
        self._builder_capture_in_progress = True
        started = self.capture_service.capture_next_click(
            on_captured=self._on_builder_click_captured,
            on_error=self._on_builder_capture_error,
        )
        if not started:
            self._builder_capture_in_progress = False

    def _on_builder_click_captured(self, x: int, y: int) -> None:
        self._builder_capture_in_progress = False
        try:
            # Clamp to monitor bounds to avoid invalid positions on multi‑monitor
            mons = self._get_monitors()
            if mons:
                # Find monitor for (x,y); if none, clamp to overall extents
                min_x = min(m["x"] for m in mons)
                min_y = min(m["y"] for m in mons)
                max_x = max(m["x"] + m["width"] - 1 for m in mons)
                max_y = max(m["y"] + m["height"] - 1 for m in mons)
                xx = max(min_x, min(int(x), max_x))
                yy = max(min_y, min(int(y), max_y))
            else:
                xx, yy = int(x), int(y)
            self.builder_click_x_var.set(str(xx))
            self.builder_click_y_var.set(str(yy))
        except Exception:
            pass

    def _on_builder_capture_error(self, exc: Exception) -> None:  # pragma: no cover - platform specific
        self._builder_capture_in_progress = False
        try:
            self._log_message(f"Builder-Aufnahmefehler: {exc}", level="WARNING")
        except Exception:
            pass

    def _builder_set_xy_from_cursor(self) -> None:
        try:
            x, y = pyautogui.position()
            # Same clamping as capture to be consistent across monitors
            mons = self._get_monitors()
            if mons:
                min_x = min(m["x"] for m in mons)
                min_y = min(m["y"] for m in mons)
                max_x = max(m["x"] + m["width"] - 1 for m in mons)
                max_y = max(m["y"] + m["height"] - 1 for m in mons)
                xx = max(min_x, min(int(x), max_x))
                yy = max(min_y, min(int(y), max_y))
            else:
                xx, yy = int(x), int(y)
            self.builder_click_x_var.set(str(xx))
            self.builder_click_y_var.set(str(yy))
        except Exception:
            pass

    @staticmethod
    def _find_monitor_index(x: int, y: int, monitors: List[Dict[str, int]]) -> Optional[int]:
        for i, m in enumerate(monitors):
            if (x >= m["x"]) and (y >= m["y"]) and (x < m["x"] + m["width"]) and (y < m["y"] + m["height"]):
                return i
        return None

    def _export_logs(self) -> None:
        from tkinter import filedialog

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Textdateien", "*.txt"), ("Alle Dateien", "*.*")],
        )
        if not path:
            return
        if self.logger.export_logs_to_file(path):
            messagebox.showinfo("Export", "Log erfolgreich exportiert.")
        else:
            messagebox.showerror("Export", "Log konnte nicht exportiert werden.")

    def _persist_settings(self) -> None:
        if self._persist_suspended:
            return
        self.settings.click_positions = list(self.click_positions)
        self.settings.click_rate_per_second = float(self.click_rate_var.get())
        self.settings.total_clicks = int(self.total_clicks_var.get())
        self.settings.click_type = ClickType(self.click_type_var.get())
        self.settings.click_mode = ClickMode(self.click_mode_var.get())
        self.settings.run_in_background = bool(self.background_var.get())
        self.settings.debug_overlay_enabled = bool(self.debug_overlay_var.get())
        self.settings.dark_mode_enabled = bool(self.dark_mode_var.get())
        self.settings.start_hotkey = self.start_hotkey_var.get().strip() or "F6"
        self.settings.stop_hotkey = self.stop_hotkey_var.get().strip() or "F7"
        self.settings_manager.save(self.settings)

    def _on_closing(self) -> None:
        self._cancel_capture()
        self._stop_manual_clicking()
        self._stop_automation()
        self.hotkey_manager.disable_hotkeys()
        self.debug_overlay.disable()
        if self.monitor_job:
            self.root.after_cancel(self.monitor_job)
        self._persist_settings()
        self.root.destroy()

    # ------------------------------------------------------------------
    # Platform checks (Linux)
    # ------------------------------------------------------------------
    def _check_platform_hints(self) -> None:
        try:
            if not sys.platform.startswith("linux"):
                return
            msgs: List[str] = []
            session = (os.environ.get("XDG_SESSION_TYPE", "").strip().lower())
            if session == "wayland":
                msgs.append("Linux/Wayland erkannt – globale Hotkeys und Mausaufzeichnung sind ggf. eingeschränkt. Xorg-Sitzung empfohlen.")
            # python-xlib for pynput
            try:
                import Xlib  # type: ignore
                _ = Xlib  # silence unused
            except Exception:
                msgs.append("Python-Xlib fehlt – installieren Sie 'python-xlib' (sollte via requirements automatisch mitkommen).")
            # scrot for screenshots (pyautogui dependency on many distros)
            if shutil.which("scrot") is None:
                msgs.append("'scrot' nicht gefunden – pyautogui Screenshots sind ggf. eingeschränkt. Installieren Sie das Paket Ihrer Distribution.")
            for m in msgs:
                self._log_message(m, level="WARNING")
        except Exception:
            # Never break startup because of environment checks
            pass
