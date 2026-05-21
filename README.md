# Leadmachine

Call-Management-Dashboard für Google-Places-CSV-Exporte. macOS-Desktop-App.

Importiert beliebig viele CSV-Dateien in eine zentrale Lead-Liste, dedupliziert
automatisch über die Telefonnummer und zeigt pro Anruf alle Infos zum nächsten
Lead — inklusive Status-Tracking und Notizen.

---

## Installation

```bash
git clone https://github.com/finnkoetting/Leadmachine.git
cd Leadmachine
chmod +x install.sh
./install.sh
```

Das Skript:
1. Prüft ob Python 3.12+ mit Tk 8.6 vorhanden ist — installiert es automatisch falls nicht
2. Installiert `customtkinter` + `PyInstaller`
3. Baut `Leadmachine.app` (~60 Sek.)
4. Fragt ob die App nach `/Applications` oder in den Repo-Ordner installiert werden soll
5. Bietet an, die App direkt zu öffnen

**Beim ersten Start** fragt macOS nach Ordner-Zugriff (für `leads.json`) → **Erlauben** klicken.

> **Hinweis:** Das macOS-System-Python (3.9, Tk 8.5) funktioniert nicht.
> Das Installationsskript lädt automatisch python.org Python 3.12 herunter
> falls kein geeignetes Python gefunden wird. Einmalig Admin-Passwort nötig.

---

## Funktionen

| Bereich | Was es kann |
|---|---|
| **CSV-Import** | Mehrere Dateien auf einmal, Duplikate (gleiche Telefonnummer) werden übersprungen |
| **Anruf-Ansicht** | Nächster Lead: Firma, Bewertung, Telefon (kopierbar), Adresse, Website, Branche |
| **Status setzen** | Nicht erreicht · Interessiert · Rückruf · Kein Interesse · Kunde |
| **Pipeline** | Status-Balken + Gesamtfortschritt |
| **Alle Leads** | Tabelle mit Status-Filter und Freitext-Suche |
| **Notizen** | Pro Lead, werden beim Status-Setzen gespeichert |

Daten werden in `leads.json` neben der App gespeichert (erstellt beim ersten Start).

---

## Manuell bauen

```bash
./build.sh
```

Erzeugt `Leadmachine.app` im Repo-Ordner.

---

## Aus dem Quellcode starten (ohne App-Bundle)

```bash
pip3 install customtkinter
python3 leadmachine.py
```

Benötigt Python 3.12+ mit Tk 8.6 (python.org-Installer).

---

## CSV-Format

Kompatibel mit Google-Places-Crawler-Exporten. Erwartete Spalten:

```
title, totalScore, reviewsCount, street, city, countryCode,
website, phone, categories/0 … categories/9, url, categoryName
```
