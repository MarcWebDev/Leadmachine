# Leadmachine

Call-Management-Dashboard für Google-Places-CSV-Exporte. macOS-Desktop-App.

Importiert beliebig viele CSV-Dateien in eine zentrale Lead-Liste, dedupliziert
automatisch über die Telefonnummer und zeigt pro Anruf alle Infos zum nächsten
Lead — inklusive Status-Tracking und Notizen.

## Funktionen

- **CSV-Import** — mehrere Dateien gleichzeitig, Duplikate (gleiche Telefonnummer) werden übersprungen
- **Anruf-Ansicht** — nächster Lead mit Firma, Bewertung, Telefon, Adresse, Website, Branche
- **Status** — Nicht erreicht · Interessiert · Rückruf · Kein Interesse · Kunde
- **Pipeline** — Status-Übersicht und Gesamtfortschritt
- **Alle Leads** — Tabelle mit Filter und Suche
- **Notizen** pro Lead
- Daten persistent in `leads.json` neben der App

## Voraussetzungen

- macOS
- Python 3.12+ mit **Tk 8.6+** (python.org-Installer, nicht das macOS-System-Python)
  - Download: https://www.python.org/downloads/macos/

## Aus dem Quellcode starten

```bash
pip install customtkinter
python3 leadmachine.py
```

## App-Bundle bauen

```bash
./build.sh
```

Erzeugt `Leadmachine.app` — eigenständig (Python + Tk gebündelt), per Doppelklick startbar.

Beim ersten Start fragt macOS nach Zugriff auf den Ordner, in dem die App liegt
(für `leads.json`) — **Erlauben** klicken.

## CSV-Format

Erwartet Google-Places-Crawler-Export mit den Spalten:
`title, totalScore, reviewsCount, street, city, website, phone, categories/0…9, url, categoryName`
