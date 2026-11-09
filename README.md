# Zündfunke

Stammbuch für Youngtimer (VW T4 und Audi TT): Journal, Fälligkeiten, Kosten, Chronik, Lager, Bestellungen und Wissen in einer einzigen statischen Web-App. Kein Server, kein Konto, kein KI-Dienst nötig.

## Datenschutz
- Dieses Repository enthält **nur Programmcode**, keine persönlichen Daten.
- Alle Daten liegen ausschließlich im Browser des Geräts (IndexedDB). Es gibt keine Netzwerkanfragen mit Daten.
- Die Dateien `*.csv`, `*.xlsx`, `wissen.json` und `zuendfunke-backup*.json` sind per `.gitignore` ausgeschlossen. Nie in dieses Repo einchecken.

## Benutzen
1. Seite öffnen (GitHub Pages) oder `index.html` lokal im Browser öffnen.
2. Menü **Daten**: `eintraege.csv`, `service.csv`, `wartungsplan.csv` (optional `wissen.json`) importieren.
3. Erfassen, Bestellen, Abhaken und Bearbeiten wirkt sofort auf das Journal und wird im Browser gespeichert.
4. Regelmäßig im Menü **Daten** exportieren (Journal als CSV, Komplett-Backup als JSON). Die App erinnert nach 14 Tagen an ungesicherte Änderungen.

iPhone: In Safari „Teilen“ > „Zum Home-Bildschirm“. Die App läuft dann im Vollbild und offline.

## Datenformat
Das Journal hat 27 Spalten: `id, fahrzeug, datum, datum_abgeleitet, km, typ, status, prio, bereich, titel, betrag, kostenart, zweck, zweck_status, betrag_geplant, auf_lager, lagerort, box, fach, bestellt_am, notiz, eltern_id, quelle, kategorie, unterkategorie, kat_status, platz` (UTF-8, Komma, Dezimalpunkt). Der CSV-Export ist byte-gleich zum Import, solange nichts geändert wurde.

- Neue Einträge aus der App tragen eine ID `A1`, `A2` … und die Quelle `app:…`.
- Wartungen mit km-Stand (z. B. Ölwechsel) schreibt die App zusätzlich in den Service-Nachweis.
- Fälligkeiten berechnet die App aus Service-Nachweis, Wartungsplan und km-Verlauf. Sie zeigt nur an, was in den Daten steht.

## Grenzen
- Kein Abgleich zwischen Geräten: Jedes Gerät hat seine eigene Datenbank. Zum Umziehen Backup exportieren und importieren.
- Safari kann Browserdaten von Seiten löschen, die lange nicht geöffnet wurden. Gegenmaßnahmen: Home-Bildschirm-App, dauerhafter Speicher (Menü Daten), regelmäßiges Backup.

## Entwicklung
Alles steckt in `index.html` (HTML, CSS, JS). Dazu `sw.js` (Offline), `manifest.webmanifest` und `icons/`. Lokal testen: `python3 -m http.server` im Repo-Ordner.
