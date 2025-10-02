# Multi Auto Clicker

Schneller Auto-Clicker mit Fokus auf saubere Architektur – plus einfache Script-Automatisierung ohne Mausbewegung.

```text
[GUI] ──▶ [Clicker Engine] ──▶ Klicks (manuell/auto)
  │
  └────▶ [Script Engine] ──▶ Aktionen (Text, Tasten, Wartezeit, Programm …)
```

## Installation

1) Python 3.10+ installieren
2) Abhängigkeiten installieren:

```powershell
pip install -r requirements.txt
```

Linux mit evdev-Fehler? Siehe `INSTALLATION.md` (Kernel-Header/Dev-Tools nachinstallieren).

## Start

```powershell
python main.py
```

## Manuelles Klicken (Kurz)

- Ziele hinzufügen: Aktuelle Position, Benutzerdefiniert oder Aufnahme
- Rate/Anzahl/Typ einstellen
- Start/Stop mit Buttons oder Hotkeys (Standard: F6/F7)

## Automatisierung – Script-Editor & Builder

Im Tab „Automatisierung“:

- Script-Builder (oben):
  - Aktionstyp wählen (type_text, send_keys, wait, launch_process, window_activate)
  - Felder ausfüllen, „Hinzufügen“ klicken (Liste rechts zeigt die Aktionen)
  - Aktionen sortieren (▲/▼), Liste leeren/entfernen
  - Vorlagen: z. B. „Notepad: Start + Tippen + Enter“
  - „→ Editor übertragen“ erzeugt JSON unten; „Editor → Builder“ liest JSON wieder ein
- Script-Editor (unten): JSON anpassen oder laden/speichern
- Toolbar: Validieren hebt JSON-Fehlerzeile hervor
- Start (Script) / Stopp (Script) führt das Script im Hintergrund aus

Beispiel (JSON):

```json
{
  "name": "Demo",
  "actions": [
    { "type": "type_text", "text": "Hello from Script!" },
    { "type": "send_keys", "sequence": "<ENTER>" }
  ]
}
```

Hinweise:

- Windows: Hintergrund-Tasten via pywinauto (wenn verfügbar), sonst Fallback pynput
- Linux/macOS: Tasten an fokussiertes Fenster (systembedingt)
- Linux: In Wayland-Sitzungen sind globale Hotkeys/Mausaufnahme eingeschränkt. Xorg empfohlen. Bei Build-Fehlern für evdev/python-xlib siehe INSTALLATION.md.

## Troubleshooting (Kurz)

- „Import could not be resolved“ → `pip install -r requirements.txt`
- Linux-Fehler bei evdev → `INSTALLATION.md` Befehle für deine Distro
- Hotkeys kollidieren? In Optionen neue konfigurieren

## Struktur (Kurz)

```text
gui.py            # Oberfläche
clicker_engine.py # Klick-Engine
automation/       # Script-Engine + Aktionen
```

MIT-Lizenz. Beiträge willkommen – bitte Clean Code & SOLID beibehalten.
