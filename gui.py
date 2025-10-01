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
from typing import Optional, List, Dict

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
from click_capture import ClickCaptureService
from debug_overlay import DebugOverlayManager
from hotkey_manager import HotkeyManager
from logger import StatusLogger
from settings_manager import SettingsManager


class AutoClickerGUI:
    """Tkinter based GUI that orchestrates all application services."""

    MONITOR_POLL_MS = 400
    CLICK_COUNTER_POLL_MS = 120

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Multi Auto Clicker")
        self.root.geometry("780x660")
        self.root.resizable(False, False)

        self.settings_manager = SettingsManager()
        self.settings: ApplicationSettings = self.settings_manager.load()

        # Runtime state --------------------------------------------------
        self.click_positions: List[ClickPosition] = list(self.settings.click_positions)
        self.engine: Optional[AutoClickerEngine] = None
        self.automation_engine: Optional[AutoClickerEngine] = None
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
        self.monitor_info_var = tk.StringVar(value="Cursor: (0, 0) | Bildschirm 1")
        self.automation_minimize_var = tk.BooleanVar(value=True)
        self.automation_infinite_var = tk.BooleanVar(value=True)

        # UI --------------------------------------------------------------
        self._build_ui()
        self._refresh_position_list()
        self._on_click_mode_changed()
        self.debug_overlay.set_positions(self.click_positions)
        self.debug_overlay.toggle(self.debug_overlay_var.get())

        # Services -------------------------------------------------------
        self._setup_hotkeys()
        self._start_monitor_updates()

        self._persist_suspended = False
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        container = ttk.Frame(self.root, padding=12)
        container.grid(row=0, column=0, sticky="nsew")

        notebook = ttk.Notebook(container)
        notebook.pack(fill=tk.BOTH, expand=True)

        manual_tab = ttk.Frame(notebook)
        automation_tab = ttk.Frame(notebook)
        notebook.add(manual_tab, text="Manuelle Steuerung")
        notebook.add(automation_tab, text="Automatisierung")

        manual_tab.columnconfigure(0, weight=3)
        manual_tab.columnconfigure(1, weight=2)
        manual_tab.rowconfigure(0, weight=1)
        manual_tab.rowconfigure(1, weight=1)

        left_column = ttk.Frame(manual_tab)
        left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_column.columnconfigure(0, weight=1)
        left_column.rowconfigure(0, weight=1)

        right_column = ttk.Frame(manual_tab)
        right_column.grid(row=0, column=1, sticky="nsew")
        right_column.columnconfigure(0, weight=1)

        self._build_position_section(left_column)
        self._build_configuration_section(right_column)
        self._build_options_section(right_column)
        self._build_control_section(right_column)
        self._build_statistics_section(right_column)

        status_container = ttk.Frame(manual_tab)
        status_container.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        status_container.columnconfigure(0, weight=1)
        status_container.rowconfigure(0, weight=1)

        self._build_status_section(status_container)

        self._build_automation_tab(automation_tab)

    def _build_position_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Klick-Positionen", padding=10)
        frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        frame.columnconfigure(0, weight=1)

        self.position_listbox = tk.Listbox(frame, height=6)
        self.position_listbox.grid(row=0, column=0, columnspan=3, sticky="nsew")

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.position_listbox.yview)
        scrollbar.grid(row=0, column=3, sticky="ns")
        self.position_listbox.configure(yscrollcommand=scrollbar.set)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        btn_frame.columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.add_current_button = ttk.Button(
            btn_frame, text="Aktuelle Position", command=self._add_current_position
        )
        self.add_current_button.grid(row=0, column=0, padx=2)

        self.add_custom_button = ttk.Button(
            btn_frame, text="Benutzerdefiniert", command=self._add_custom_position
        )
        self.add_custom_button.grid(row=0, column=1, padx=2)

        self.capture_button = ttk.Button(
            btn_frame, text="Nächsten Klick aufnehmen", command=self._capture_next_position
        )
        self.capture_button.grid(row=0, column=2, padx=2)

        self.capture_cancel_button = ttk.Button(
            btn_frame, text="Aufnahme stoppen", command=self._cancel_capture
        )
        self.capture_cancel_button.grid(row=0, column=3, padx=2)

        self.remove_selected_button = ttk.Button(
            btn_frame, text="Entfernen", command=self._remove_selected_position
        )
        self.remove_selected_button.grid(row=0, column=4, padx=2)

        self.clear_all_button = ttk.Button(
            btn_frame, text="Alle löschen", command=self._clear_all_positions
        )
        self.clear_all_button.grid(row=0, column=5, padx=2)

        ttk.Label(frame, textvariable=self.capture_status_var).grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(6, 0)
        )

    def _build_configuration_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Konfiguration", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Klicks pro Sekunde:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(
            frame,
            from_=0.1,
            to=1000.0,
            increment=0.1,
            textvariable=self.click_rate_var,
            width=8,
        ).grid(row=0, column=1, sticky="w")

        ttk.Label(frame, text="Gesamtanzahl (0 = unendlich):").grid(row=1, column=0, sticky="w")
        ttk.Spinbox(
            frame,
            from_=0,
            to=1_000_000,
            increment=10,
            textvariable=self.total_clicks_var,
            width=8,
        ).grid(row=1, column=1, sticky="w")

        ttk.Label(frame, text="Klicktyp:").grid(row=2, column=0, sticky="w")
        click_type_combo = ttk.Combobox(
            frame,
            textvariable=self.click_type_var,
            values=[choice.value for choice in ClickType],
            state="readonly",
            width=10,
        )
        click_type_combo.grid(row=2, column=1, sticky="w")

        ttk.Label(frame, text="Modus:").grid(row=3, column=0, sticky="w")
        mode_frame = ttk.Frame(frame)
        mode_frame.grid(row=3, column=1, sticky="w")

        ttk.Radiobutton(
            mode_frame,
            text="Feste Positionen",
            value=ClickMode.STATIC_SEQUENCE.value,
            variable=self.click_mode_var,
            command=self._on_click_mode_changed,
        ).grid(row=0, column=0, padx=(0, 12))

        ttk.Radiobutton(
            mode_frame,
            text="Cursor folgen",
            value=ClickMode.FOLLOW_CURSOR.value,
            variable=self.click_mode_var,
            command=self._on_click_mode_changed,
        ).grid(row=0, column=1)

    def _build_options_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Optionen", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            frame,
            text="Im Hintergrund ausführen (Fenster darf im Vordergrund bleiben)",
            variable=self.background_var,
            command=self._persist_settings,
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Checkbutton(
            frame,
            text="Debug-Modus: Positionen mit ✕ markieren",
            variable=self.debug_overlay_var,
            command=lambda: self._toggle_debug_overlay(self.debug_overlay_var.get()),
        ).grid(row=1, column=0, columnspan=2, sticky="w")

        ttk.Label(frame, text="Start-Hotkey:").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.start_hotkey_var, width=12).grid(
            row=2, column=1, sticky="w")

        ttk.Label(frame, text="Stopp-Hotkey:").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.stop_hotkey_var, width=12).grid(
            row=3, column=1, sticky="w")

        ttk.Button(frame, text="Hotkeys anwenden", command=self._apply_hotkeys).grid(
            row=2, column=2, rowspan=2, padx=(12, 0)
        )

        ttk.Label(frame, textvariable=self.monitor_info_var).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

    def _build_control_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Steuerung", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))
        frame.columnconfigure((0, 1), weight=1)

        self.start_button = ttk.Button(frame, text="Start", command=self._start_manual_clicking)
        self.start_button.grid(row=0, column=0, padx=5, sticky="ew")

        ttk.Button(frame, text="Stopp", command=self._stop_manual_clicking).grid(row=0, column=1, padx=5, sticky="ew")

    def _build_statistics_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Live-Statistiken", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))
        frame.columnconfigure((0, 1), weight=1)

        ttk.Label(frame, textvariable=self.click_count_var, anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(frame, textvariable=self.manual_cps_var, anchor="e").grid(
            row=0, column=1, sticky="e"
        )

    def _build_status_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Status & Log", padding=10)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(frame, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

        self.log_text = scrolledtext.ScrolledText(frame, height=10, state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

        ttk.Button(frame, text="Log exportieren", command=self._export_logs).grid(
            row=2, column=0, sticky="e", pady=(8, 0)
        )

    def _build_automation_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        info = ttk.Label(
            parent,
            text=(
                "Automatisierungsmodus: Führt Klicks im Hintergrund aus und kann das Fenster "
                "automatisch minimieren. Die Einstellungen aus dem Tab \"Manuelle Steuerung\" "
                "werden wiederverwendet."
            ),
            wraplength=720,
            justify=tk.LEFT,
        )
        info.grid(row=0, column=0, sticky="w", pady=(10, 10), padx=10)

        options = ttk.LabelFrame(parent, text="Automatisierungs-Optionen", padding=10)
        options.grid(row=1, column=0, sticky="ew", padx=10)
        options.columnconfigure(0, weight=1)

        ttk.Checkbutton(
            options,
            text="Fenster beim Start minimieren",
            variable=self.automation_minimize_var,
        ).grid(row=0, column=0, sticky="w")

        ttk.Checkbutton(
            options,
            text="Unendlich klicken (ignoriert Gesamtanzahl)",
            variable=self.automation_infinite_var,
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        controls = ttk.LabelFrame(parent, text="Automatisierung", padding=10)
        controls.grid(row=2, column=0, sticky="ew", padx=10, pady=(10, 0))
        controls.columnconfigure(0, weight=1)

        ttk.Button(controls, text="Start (Hintergrund)", command=self._start_automation).grid(
            row=0, column=0, padx=5, pady=(0, 4)
        )
        ttk.Button(controls, text="Stop", command=self._stop_automation).grid(
            row=0, column=1, padx=5, pady=(0, 4)
        )

        ttk.Label(controls, textvariable=self.automation_status_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )
        ttk.Label(controls, textvariable=self.automation_clicks_var).grid(
            row=2, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(controls, textvariable=self.automation_cps_var).grid(
            row=3, column=0, columnspan=2, sticky="w"
        )

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
        self.hotkey_manager.enable_hotkeys()

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
                screen_size = pyautogui.size()
                self.monitor_info_var.set(
                    f"Cursor: ({int(x)}, {int(y)}) | Bildschirmgröße: {screen_size.width}x{screen_size.height}"
                )
            except Exception:
                self.monitor_info_var.set("Cursorinformationen nicht verfügbar.")
            self.monitor_job = self.root.after(self.MONITOR_POLL_MS, poll)

        poll()

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
