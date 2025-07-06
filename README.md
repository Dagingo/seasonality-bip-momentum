# Forex Signal Generator mit GUI

Dieses Projekt implementiert einen Forex-Signal-Generator mit einer grafischen Benutzeroberfläche (GUI), der Kauf- und Verkaufssignale für ausgewählte Währungspaare auf Basis von zwei Indikatoren generiert: Saisonalität und BIP-Momentum-Vergleich.

## Funktionen

*   **Grafische Benutzeroberfläche (GUI):**
    *   Gebaut mit Tkinter für eine leichtgewichtige Desktop-Anwendung.
    *   Auswahl des Forex-Paares (z.B. EUR/USD, GBP/JPY).
    *   Auswahl des Analysezeitraums (Start- und Enddatum).
    *   Eingabe von benutzerdefinierten Schwellenwerten für den Saisonalitätsindikator.
    *   Button zum Starten der Analyse.
    *   Fortschrittsanzeige während der Datenverarbeitung.
    *   Integrierte Debug-Konsole zur Anzeige von Log-Meldungen.
    *   Visualisierung der Ergebnisse (Forex-Kurse, Indikatoren, Signale) direkt in der GUI mittels Matplotlib.
*   **Datenanbindung:**
    *   Abruf von historischen Forex-Kursdaten über `yfinance` (Yahoo Finance API).
    *   Laden von BIP-Daten (Bruttoinlandsprodukt) aus einer mitgelieferten CSV-Datei (`bip_data_live.csv`).
    *   Fallback auf eine ältere BIP-Datendatei (`bip_data.csv`), falls die primäre CSV nicht verfügbar ist.
*   **Analyse-Indikatoren:**
    *   **Saisonalität:** Analysiert historische Kursdaten auf monatlicher Basis, um typische saisonale Trends zu identifizieren.
    *   **GDP-Momentum-Vergleich (NEU):**
        *   Berechnet die Wachstumsraten (z.B. über 4 Quartale für YoY) für die BIP-Zeitreihen zweier Länder/Regionen.
        *   Normalisiert diese Wachstumsraten für jedes Land separat auf einen skalierten Wert von -100 bis 100 (Min-Max-Skalierung über die Historie der Wachstumsraten).
        *   Berechnet die Differenz dieser skalierten Momentum-Werte (`momentum_A - momentum_B`).
        *   Ein Long-Signal wird generiert, wenn diese Differenz einen benutzerdefinierten positiven Schwellenwert (z.B. 30) übersteigt.
        *   Ein Short-Signal wird generiert, wenn die Differenz einen benutzerdefinierten negativen Schwellenwert (z.B. -30) unterschreitet.
        *   Die Schwellenwerte für diese Differenz sind in der GUI konfigurierbar.
*   **Signalerzeugung:** Kombiniert die Signale aus Saisonalität und dem GDP-Momentum-Vergleich zu einem finalen Kauf-, Verkaufs- oder Haltensignal.
*   **Modularer Aufbau:** Trennung von GUI, Datenmanagement und Analyse-Logik.

## Struktur des Projekts

*   `forex_gui_app.py`: Enthält die Hauptanwendung und die Tkinter GUI-Logik.
*   `data_manager.py`: Zuständig für den Abruf und das Management von Forex- und BIP-Daten.
*   `signal_analyzer.py`: Beinhaltet die Logik für die Berechnung der Indikatoren, die Signalerzeugung und die Erstellung der Plots.
*   `forex_data.csv`: Sehr kleine Beispieldatei für Forex-Kurse (wird von der GUI-Version nicht primär verwendet, war Teil der ursprünglichen Konsolenversion).
*   `bip_data_live.csv`: Enthält aktuellere (Beispiel-)BIP-Daten für verschiedene Wirtschaftsräume/Länder. Dies ist die primäre Quelle für BIP-Daten.
*   `bip_data.csv`: Enthält ältere (Beispiel-)BIP-Daten und dient als Fallback.
*   `README.md`: Diese Datei.

## Installation

1.  **Python:** Stelle sicher, dass Python 3.8 oder höher installiert ist.
2.  **Abhängigkeiten:** Installiere die benötigten Python-Bibliotheken. Du kannst dies über pip tun:
    ```bash
    pip install pandas numpy matplotlib yfinance
    ```
    (Tkinter ist normalerweise Teil der Standard-Python-Distribution.)

## Benutzung

1.  Führe das Hauptskript aus:
    ```bash
    python forex_gui_app.py
    ```
2.  Die GUI öffnet sich. Wähle im Bereich "Einstellungen":
    *   Das gewünschte **Forex-Paar** aus dem Dropdown-Menü.
    *   Das **Start- und Enddatum** für die Analyse (Format: JJJJ-MM-TT). Standard ist das letzte Jahr bis heute.
    *   Die **Schwellenwerte für die Saisonalität** (als Prozentwert des monatlichen Returns, z.B. `0.05` für 0.05%).
    *   Den **Long-Schwellenwert (GDP Diff)**: Positiver Wert (z.B. `30`). Ein Long-Signal vom GDP-Momentum wird ausgelöst, wenn die skalierte Momentum-Differenz (Land A - Land B) diesen Wert übersteigt.
    *   Den **Short-Schwellenwert (GDP Diff)**: Negativer Wert (z.B. `-30`). Ein Short-Signal vom GDP-Momentum wird ausgelöst, wenn die skalierte Momentum-Differenz diesen Wert unterschreitet.
3.  Klicke auf den Button **"Analyse starten"**.
4.  Während der Analyse wird der Fortschritt angezeigt und die Eingabefelder sind gesperrt. Debug-Meldungen erscheinen in der Konsole unten rechts, inklusive der berechneten skalierten Momentum-Werte (A, B), deren Differenz und dem resultierenden GDP-Signal.
5.  Nach Abschluss der Analyse wird der Chart im Hauptbereich der GUI aktualisiert und zeigt:
    *   Den Forex-Kursverlauf mit markierten Kauf- (grüne Pfeile) und Verkaufssignalen (rote Pfeile).
    *   Den Saisonalitätstrend mit den eingestellten Schwellen.
    *   Das BIP-Momentum-Signal (und optional Roh-BIP-Daten).

## Datenquellen und Hinweise

*   **Forex-Daten:** Werden live von Yahoo Finance über die `yfinance`-Bibliothek bezogen. Die Verfügbarkeit und Genauigkeit hängt von Yahoo Finance ab.
*   **BIP-Daten:**
    *   Die primäre Quelle ist die Datei `bip_data_live.csv`, die mit dem Projekt ausgeliefert wird. Diese enthält exemplarische, quartalsweise BIP-Daten. Für eine reale Anwendung müssten diese Daten regelmäßig aktualisiert und aus verlässlichen Quellen (z.B. Weltbank, Eurostat, nationale Statistikämter) bezogen werden. Der Code ist so strukturiert, dass eine Anbindung an eine API später erfolgen könnte.
    *   `bip_data.csv` ist eine ältere Version und dient nur als Fallback, falls `bip_data_live.csv` nicht gefunden wird.
*   **Indikatoren:** Die Implementierung der Indikatoren ist eine von vielen möglichen. Die Ergebnisse und Signale sollten kritisch bewertet und nicht als direkte Handelsaufforderung verstanden werden.

## Mögliche Erweiterungen

*   Anbindung an eine Live-API für BIP-Daten (z.B. Weltbank).
*   Weitere Indikatoren hinzufügen.
*   Konfigurierbare Gewichtung der Indikatoren.
*   Erweiterte Fehlerbehandlung und Benutzereingabevalidierung.
*   Speichern/Laden von Konfigurationen.
*   Backtesting-Funktionalität.
*   Verbesserte Kalender-Widgets für die Datumsauswahl.
```
