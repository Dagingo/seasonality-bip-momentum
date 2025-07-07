# Forex Signal Generator & Backtester mit GUI

Dieses Projekt implementiert einen Forex-Signal-Generator und ein Backtesting-Framework mit einer grafischen Benutzeroberfläche (GUI). Es generiert Kauf- und Verkaufssignale für eine erweiterte Auswahl von Währungspaaren (inklusive G20-Kombinationen) basierend auf Saisonalität und BIP-Wachstumsmomentum. Die generierten Signale können anschließend in einem integrierten Backtester auf ihre historische Performance überprüft werden, verglichen mit einer Buy-and-Hold-Strategie des SPX-Index.

## Hauptfunktionen

*   **Grafische Benutzeroberfläche (GUI):**
    *   Gebaut mit Tkinter.
    *   Auswahl des Forex-Paares aus einer erweiterten Liste (inkl. G20-Währungen).
    *   Auswahl des Analyse- und Backtesting-Zeitraums.
    *   Eingabe von benutzerdefinierten Schwellenwerten für Saisonalitäts- und BIP-Momentum-Indikatoren.
    *   Speichern und Laden von Analyse-/Backtest-Konfigurationen als Presets.
    *   Buttons zum Starten der Signalanalyse und des Backtests.
    *   Fortschrittsanzeige und Statusmeldungen.
    *   Integrierte Debug-Konsole.
*   **Datenmanagement:**
    *   Abruf von historischen Forex-Kursdaten über `yfinance`.
    *   Abruf von BIP-Daten (Bruttoinlandsprodukt) über die FRED-API (via `pandas_datareader`) für viele G20-Länder.
    *   Fallback auf provisorische, länderspezifische CSV-Dateien für BIP-Daten, falls keine API-Daten verfügbar sind (z.B. für Saudi-Arabien).
    *   Caching von Preisdaten im Portfolio-Manager zur Effizienzsteigerung bei wiederholten Zugriffen.
*   **Signalanalyse:**
    *   **Saisonalität:** Analysiert historische Kursdaten auf wöchentlicher Basis.
    *   **BIP-Momentum-Vergleich:** Vergleicht normalisierte BIP-Wachstumsraten zweier Länder/Regionen.
    *   Kombinierte Signalerzeugung basierend auf der Übereinstimmung beider Indikatoren.
    *   Visualisierung der Forex-Kurse, Indikatoren und Signale in einem Chart.
*   **Backtesting-Framework:**
    *   Simulation einer Handelsstrategie: Kauft bei Kaufsignal, verkauft bei Verkaufssignal oder am Ende jeder Woche (Freitag).
    *   Positionsgröße: Standardmäßig 10% des Portfolio-Gesamtwerts pro Trade.
    *   Startkapital: Standardmäßig 10.000 Einheiten der Basiswährung.
    *   Vergleich mit einem Benchmark-Portfolio (Buy-and-Hold des SPX-Index mit gleichem Startkapital).
    *   Visualisierung der Wertentwicklung des Strategie-Portfolios und des Benchmark-Portfolios in einem gemeinsamen Chart.
*   **Modularer Aufbau:** Trennung von GUI (`forex_gui_app.py`), Datenmanagement (`data_manager.py`), Signalanalyse (`signal_analyzer.py`), Portfolio-Management (`portfolio_manager.py`) und Backtesting-Logik (`backtester.py`).

## Technische Details & Abhängigkeiten

*   Python 3.8+
*   Tkinter (meist Teil der Standard-Python-Distribution)
*   Pandas
*   NumPy
*   Matplotlib
*   yfinance
*   pandas_datareader

Installation der Abhängigkeiten:
```bash
pip install pandas numpy matplotlib yfinance pandas_datareader
```

## Datenquellen

*   **Forex-Kursdaten:** Yahoo Finance (via `yfinance`).
*   **BIP-Daten (API):** Federal Reserve Economic Data (FRED) über `pandas_datareader` für unterstützte Länder.
*   **BIP-Daten (Provisorisch):** Manuell erstellte CSV-Dateien im Verzeichnis `data/gdp_provisional/` für Länder ohne direkte API-Anbindung (z.B. Saudi-Arabien). Diese dienen als Fallback und enthalten Beispieldaten.
*   **BIP-Daten (Legacy Fallback):** `bip_data_live.csv` und `bip_data.csv` als generischer Fallback, falls weder API noch provisorische Daten gefunden werden.

## Einrichtung & Ausführung

1.  Stelle sicher, dass alle oben genannten Abhängigkeiten installiert sind.
2.  Klone das Repository oder lade die Projektdateien herunter.
3.  Führe das Hauptskript aus dem Root-Verzeichnis des Projekts aus:
    ```bash
    python forex_gui_app.py
    ```

## Kurzanleitung

1.  **Einstellungen vornehmen:**
    *   Wähle ein **Forex-Paar** aus der Dropdown-Liste.
    *   Definiere **Start- und Enddatum** für die Analyse/den Backtest.
    *   Passe die **Schwellenwerte** für die Saisonalität (wöchentlicher Return in %) und die BIP-Momentum-Differenz an.
    *   Optional: Speichere deine aktuellen Einstellungen als **Preset** oder lade ein bestehendes Preset.
2.  **Signalanalyse durchführen:**
    *   Klicke auf **"Analyse starten"**.
    *   Der Chart zeigt den Kursverlauf, die Indikatoren (Saisonalität, BIP-Momentum-Differenz) und die generierten Handelssignale (Long/Short).
3.  **Backtest durchführen:**
    *   Klicke auf **"Backtest starten"**.
    *   Der Backtest simuliert die Handelsstrategie basierend auf den aktuellen Einstellungen und den generierten Signalen.
    *   Der Chart zeigt die Wertentwicklung des Strategie-Portfolios im Vergleich zum SPX-Benchmark-Portfolio.
4.  **Logs verfolgen:** Die Debug-Konsole unten rechts zeigt detaillierte Log-Meldungen des Analyse- und Backtesting-Prozesses.

## Wichtige Hinweise

*   Die bereitgestellten BIP-Daten (insbesondere die provisorischen) dienen primär Demonstrations- und Testzwecken. Für reale Anwendungen müssten verlässliche und aktuelle BIP-Datenquellen verwendet werden.
*   Die generierten Signale und Backtesting-Ergebnisse stellen keine Anlageberatung dar und sollten kritisch hinterfragt werden. Historische Performance ist keine Garantie für zukünftige Ergebnisse.
*   Die Qualität der Forex-Daten hängt von Yahoo Finance ab.

## Dateistruktur (Wichtige Komponenten)

*   `forex_gui_app.py`: Hauptanwendung, GUI-Logik.
*   `data_manager.py`: Datenbeschaffung (Forex, BIP).
*   `signal_analyzer.py`: Berechnung der Indikatoren und Signalerzeugung.
*   `portfolio_manager.py`: Verwaltung von Portfoliozustand, Trades, Wertentwicklung.
*   `backtester.py`: Durchführung des Backtests, Handelslogik.
*   `data/gdp_provisional/`: Enthält provisorische BIP-Daten als CSV.
*   `*.csv` (im Root): Legacy BIP-Daten und ggf. voreingestellte Forex-Daten.
*   `forex_presets.json`, `forex_app_config.json`: Speichern von Benutzereinstellungen und Presets.

## Mögliche zukünftige Erweiterungen

*   Implementierung von Transaktionskosten und Slippage im Backtester.
*   Fortgeschrittenes Risikomanagement (Stop-Loss, Take-Profit).
*   Dynamisches Positionsgrößenmanagement.
*   Berechnung und Anzeige detaillierter statistischer Performance-Metriken für den Backtest.
*   Weitere Indikatoren und Strategieoptionen.
```
