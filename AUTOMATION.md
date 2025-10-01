# Automatisierung (Hintergrund ohne Cursor)

Dieser Ordner führt eine neue, skriptbasierte Automatisierung ein, die Programme im Hintergrund steuern kann – ohne Mausbewegungen. Sie betrifft ausschließlich den Bereich „Automatisierung“ und ändert nichts an der manuellen Klick-Funktion.

## Ziel

- Programme im Hintergrund starten und steuern
- Tastatureingaben und Text senden, ohne den Cursor zu bewegen
- Abläufe als JSON-Skripte speichern, bearbeiten und ausführen

## Schnellstart

1. Abhängigkeiten installieren (Windows): pywinauto wird automatisch per Marker installiert.
2. Beispiel ausführen:

```powershell
python .\run_script.py .\automation\examples\example_notepad.json
```

> Hinweis: Unter Linux/macOS werden Tasten über `pynput` an das fokussierte Fenster geschickt. Echte Hintergrund-Steuerung ist systembedingt limitiert.

## Skriptformat

```json
{
  "name": "Mein Script",
  "actions": [
    { "type": "launch_process", "command": "notepad.exe", "args": [], "cwd": null, "wait": 0.8 },
    { "type": "wait", "milliseconds": 600 },
    { "type": "window_activate", "title": "Notepad" },
    { "type": "type_text", "text": "Hallo Welt" },
    { "type": "send_keys", "sequence": "<ENTER>" }
  ]
}
```

### Unterstützte Aktionen

- `launch_process`: Startet ein Programm. Felder: `command`, optional `args`, `cwd`, `wait` (Sekunden)
- `wait`: Pausiert für `milliseconds` (ms)
- `send_keys`: Sendet Tastenkombinationen. Beispiel-Sequenzen: `"<ENTER>"`, `"hello"`. Unter Windows nutzt das System `pywinauto` (falls vorhanden), sonst Fallback `pynput`.
- `type_text`: Tippt reinen Text.
- `window_activate`: Aktiviert ein Fenster anhand eines Titel-Fragments (nur Windows, Best-Effort auf anderen OS)

## Einbindung in die GUI

Die Engine ist bewusst unabhängig gehalten. Die GUI kann später einen Skript-Editor (JSON/No-Code) bekommen und die `AutomationEngine` starten/stoppen. Dafür stehen Callbacks `on_log` und `on_done` bereit.

## Hinweise

- Für echte Hintergrund-Automation unter Windows ist `pywinauto` empfohlen. Es wird nur auf Windows installiert.
- Sicherheit: Skripte können Programme starten. Verwenden Sie nur vertrauenswürdige Dateien.
