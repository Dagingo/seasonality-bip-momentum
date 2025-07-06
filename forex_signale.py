"""
HINWEIS: Dieses Skript stellt eine ältere, eigenständige Version der Signalanalyse dar.
Die primäre, interaktive und konfigurierbare Analysefunktionalität mit GUI
befindet sich in `forex_gui_app.py` (GUI-Anwendung) und `signal_analyzer.py` (Kernlogik).
Dieses Skript verwendet teils hartcodierte Schwellenwerte und beinhaltet nicht alle
aktuellen Konfigurationsmöglichkeiten des BIP-Momentum-Indikators.

---

Forex Signal Generator

Dieses Programm generiert Kauf- und Verkaufssignale für Forex-Währungspaare
basierend auf zwei Indikatoren: Saisonalität und BIP-Momentum-Vergleich.

Das Programm lädt historische Forex-Kursdaten und BIP-Daten, berechnet
die Indikatoren, kombiniert deren Signale und visualisiert die Ergebnisse.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- Konfiguration und Konstanten ---
FOREX_DATA_CSV = 'forex_data.csv'
BIP_DATA_CSV = 'bip_data.csv'
DATE_COLUMN = 'Datum'
PRICE_COLUMN = 'Schlusskurs'
COUNTRY_A = 'Land_A' # Basiswährung des Paares, z.B. EUR in EUR/USD
COUNTRY_B = 'Land_B' # Kurswährung des Paares, z.B. USD in EUR/USD
BIP_COLUMN_A = f'BIP_{COUNTRY_A}'
BIP_COLUMN_B = f'BIP_{COUNTRY_B}'

# Schwellenwerte für Saisonalitäts-Signalisierung (durchschnittliche monatliche prozentuale Veränderung)
SCHWELLE_SAISONALITAET_KAUF = 0.0005 # Entspricht 0.05% positivem Monatsdurchschnitt
SCHWELLE_SAISONALITAET_VERKAUF = -0.0005 # Entspricht 0.05% negativem Monatsdurchschnitt (korrigierter Name)


# --- Debugging-Funktion ---
def debug_print(message, data=None):
    """Gibt eine Debug-Nachricht und optional Daten aus."""
    print(f"[DEBUG] {message}")
    if data is not None:
        print(data.head() if isinstance(data, pd.DataFrame) else data)
        print("-" * 20)

# --- Datenladefunktionen ---
def lade_forex_daten(csv_pfad):
    """
    Lädt Forex-Kursdaten aus einer CSV-Datei.
    Die CSV-Datei sollte mindestens eine Datumsspalte und eine Preisspalte enthalten.
    """
    debug_print(f"Lade Forex-Daten von: {csv_pfad}")
    try:
        daten = pd.read_csv(csv_pfad, parse_dates=[DATE_COLUMN])
        daten.set_index(DATE_COLUMN, inplace=True)
        debug_print("Forex-Daten erfolgreich geladen.", daten)
        if PRICE_COLUMN not in daten.columns:
            raise ValueError(f"Die Spalte '{PRICE_COLUMN}' wurde in den Forex-Daten nicht gefunden.")
        return daten
    except FileNotFoundError:
        debug_print(f"FEHLER: Forex-Datendatei nicht gefunden: {csv_pfad}")
        print(f"Bitte erstellen Sie die Datei '{csv_pfad}' mit Spalten '{DATE_COLUMN}' und '{PRICE_COLUMN}'.")
        return pd.DataFrame()
    except Exception as e:
        debug_print(f"FEHLER beim Laden der Forex-Daten: {e}")
        return pd.DataFrame()

def lade_bip_daten(csv_pfad):
    """
    Lädt BIP-Daten aus einer CSV-Datei.
    Die CSV-Datei sollte eine Datumsspalte und BIP-Spalten für zwei Länder enthalten.
    """
    debug_print(f"Lade BIP-Daten von: {csv_pfad}")
    try:
        daten = pd.read_csv(csv_pfad, parse_dates=[DATE_COLUMN])
        daten.set_index(DATE_COLUMN, inplace=True)
        debug_print("BIP-Daten erfolgreich geladen.", daten)
        if BIP_COLUMN_A not in daten.columns or BIP_COLUMN_B not in daten.columns:
            raise ValueError(f"Erforderliche BIP-Spalten ('{BIP_COLUMN_A}', '{BIP_COLUMN_B}') nicht in den BIP-Daten gefunden.")
        return daten
    except FileNotFoundError:
        debug_print(f"FEHLER: BIP-Datendatei nicht gefunden: {csv_pfad}")
        print(f"Bitte erstellen Sie die Datei '{csv_pfad}' mit Spalten '{DATE_COLUMN}', '{BIP_COLUMN_A}', und '{BIP_COLUMN_B}'.")
        return pd.DataFrame()
    except Exception as e:
        debug_print(f"FEHLER beim Laden der BIP-Daten: {e}")
        return pd.DataFrame()

# --- Indikatorfunktionen ---
def berechne_saisonalitaet(forex_daten):
    """
    Berechnet saisonale Trends aus den Forex-Kursdaten.
    Die Saisonalität wird als durchschnittliche monatliche prozentuale Veränderung des Schlusskurses ermittelt.
    Gibt eine Pandas Series mit den Saisonalitätswerten zurück, ausgerichtet am Index der Forex-Daten.
    """
    debug_print("Beginne Berechnung der Saisonalität für Forex-Daten:", forex_daten.head())

    if forex_daten.empty or PRICE_COLUMN not in forex_daten.columns:
        debug_print("Forex-Daten sind leer oder Preissplate fehlt. Kann Saisonalität nicht berechnen.")
        return pd.Series(dtype=float, name="Saisonalitaet")

    forex_returns = forex_daten[PRICE_COLUMN].pct_change()
    debug_print("Prozentuale Veränderungen (Returns) der Forex-Kurse:", forex_returns.head())

    if not isinstance(forex_daten.index, pd.DatetimeIndex):
        debug_print("FEHLER: Forex-Datenindex ist kein DatetimeIndex. Konvertierung wird versucht.")
        try:
            forex_daten.index = pd.to_datetime(forex_daten.index)
        except Exception as e:
            debug_print(f"Fehler bei der Konvertierung des Index zu DatetimeIndex: {e}")
            return pd.Series(dtype=float, name="Saisonalitaet")

    monthly_returns = forex_returns.groupby(forex_daten.index.month)
    debug_print(f"Returns gruppiert nach Monat (Typ: {type(monthly_returns)}). Anzahl Gruppen: {len(monthly_returns)}", None)
    # Korrektur: Sicherstellen, dass die Debug-Ausgabe für Gruppen nicht fehlschlägt, wenn eine Gruppe leer ist oder nur NaNs enthält
    for name, group in monthly_returns:
        if not group.dropna().empty:
             debug_print(f"  Monat {name}: {len(group)} Einträge, Durchschnittlicher Return: {group.mean():.4f}", group.head(2))
        else:
            debug_print(f"  Monat {name}: {len(group)} Einträge, keine validen Returns für Durchschnittsberechnung vorhanden.", group.head(2))


    durchschnittliche_monatliche_saisonalitaet = monthly_returns.mean()
    debug_print("Durchschnittliche monatliche Saisonalität (Durchschnitt der prozentualen Veränderungen pro Monat):", durchschnittliche_monatliche_saisonalitaet)

    saisonalitaet_signal = pd.Series(index=forex_daten.index, dtype=float, name="Saisonalitaet")
    for monat, avg_saison_wert in durchschnittliche_monatliche_saisonalitaet.items():
        saisonalitaet_signal[forex_daten.index.month == monat] = avg_saison_wert

    saisonalitaet_signal.fillna(0, inplace=True)

    debug_print("Finale Saisonalitäts-Signal-Serie (zeigt den erwarteten durchschnittlichen Return für den jeweiligen Monat):", saisonalitaet_signal.head())
    debug_print(f"Statistik der Saisonalitäts-Signal-Serie: Min={saisonalitaet_signal.min():.4f}, Max={saisonalitaet_signal.max():.4f}, Mean={saisonalitaet_signal.mean():.4f}", None)

    return saisonalitaet_signal

def berechne_bip_momentum(bip_daten):
    """
    Berechnet das BIP-Momentum für zwei Länder und vergleicht es.
    Das Momentum wird aus der Veränderung der BIP-Wachstumsraten abgeleitet.
    Gibt eine Pandas Series mit den BIP-Momentum-Signalen (+1, -1, 0) zurück,
    die auf der Frequenz der BIP-Daten basieren.
    """
    debug_print("Beginne Berechnung des BIP-Momentums:", bip_daten.head())

    if bip_daten.empty or BIP_COLUMN_A not in bip_daten.columns or BIP_COLUMN_B not in bip_daten.columns:
        debug_print("BIP-Daten sind leer oder erforderliche Spalten fehlen. Kann BIP-Momentum nicht berechnen.")
        return pd.Series(dtype=float, name="BIP_Momentum_Signal")

    if not isinstance(bip_daten.index, pd.DatetimeIndex):
        debug_print("FEHLER: BIP-Datenindex ist kein DatetimeIndex. Konvertierung wird versucht.")
        try:
            bip_daten.index = pd.to_datetime(bip_daten.index)
        except Exception as e:
            debug_print(f"Fehler bei der Konvertierung des BIP-Index zu DatetimeIndex: {e}")
            return pd.Series(dtype=float, name="BIP_Momentum_Signal")

    bip_daten = bip_daten.sort_index()
    debug_print("BIP-Daten sortiert nach Datum:", bip_daten.head())

    bip_wachstum_A = bip_daten[BIP_COLUMN_A].pct_change() * 100
    bip_wachstum_B = bip_daten[BIP_COLUMN_B].pct_change() * 100
    debug_print(f"BIP-Wachstumsrate {COUNTRY_A} (%):", bip_wachstum_A.head())
    debug_print(f"BIP-Wachstumsrate {COUNTRY_B} (%):", bip_wachstum_B.head())

    momentum_A = bip_wachstum_A.diff()
    momentum_B = bip_wachstum_B.diff()
    debug_print(f"Momentum des BIP-Wachstums {COUNTRY_A}:", momentum_A.head())
    debug_print(f"Momentum des BIP-Wachstums {COUNTRY_B}:", momentum_B.head())

    momentum_df = pd.DataFrame({
        f'Momentum_{COUNTRY_A}': momentum_A,
        f'Momentum_{COUNTRY_B}': momentum_B
    })
    momentum_df.dropna(inplace=True)
    debug_print("Kombiniertes Momentum DataFrame (nach DropNA):", momentum_df.head())

    if momentum_df.empty:
        debug_print("Momentum DataFrame ist leer nach DropNA. Nicht genügend Daten für Momentum-Berechnung.")
        return pd.Series(dtype=float, name="BIP_Momentum_Signal")

    kauf_bedingung = momentum_df[f'Momentum_{COUNTRY_A}'] > momentum_df[f'Momentum_{COUNTRY_B}']
    verkauf_bedingung = momentum_df[f'Momentum_{COUNTRY_A}'] < momentum_df[f'Momentum_{COUNTRY_B}']

    bip_momentum_signal_raw = pd.Series(index=momentum_df.index, data=0, name="BIP_Momentum_Signal_Raw", dtype=int)
    bip_momentum_signal_raw[kauf_bedingung] = 1
    bip_momentum_signal_raw[verkauf_bedingung] = -1

    debug_print("Rohes BIP-Momentum-Signal (auf BIP-Datenfrequenz):", bip_momentum_signal_raw.head())
    debug_print(f"Verteilung der rohen BIP-Signale:\n{bip_momentum_signal_raw.value_counts(dropna=False)}", None)

    debug_print("BIP-Momentum-Signalberechnung (auf BIP-Frequenz) abgeschlossen.", bip_momentum_signal_raw.head())
    return bip_momentum_signal_raw

# --- Signalerzeugungsfunktion ---
def generiere_signale(forex_daten, saisonalitaet_raw, bip_momentum_signal_aligned):
    """
    Kombiniert Signale aus Saisonalität und BIP-Momentum zu einem finalen Handelssignal.
    Signalwerte: 1 für Kauf, -1 für Verkauf, 0 für Halten.
    """
    debug_print("Beginne Generierung finaler Signale...")
    debug_print("Eingang Saisonalität (roh):", saisonalitaet_raw.head())
    debug_print("Eingang BIP-Momentum (ausgerichtet):", bip_momentum_signal_aligned.head())

    common_index = forex_daten.index.intersection(saisonalitaet_raw.index).intersection(bip_momentum_signal_aligned.index)

    if len(common_index) == 0:
        debug_print("Kein gemeinsamer Index zwischen Forex-Daten, Saisonalität und BIP-Signal. Kann keine Signale generieren.")
        return pd.Series(index=forex_daten.index, data=0, name="Signal")

    saisonalitaet = saisonalitaet_raw.reindex(common_index).fillna(0)
    bip_signal = bip_momentum_signal_aligned.reindex(common_index).fillna(0) # Sollte bereits ausgerichtet sein, aber zur Sicherheit

    debug_print(f"Anzahl Datenpunkte nach Index-Angleichung: {len(common_index)}", None)

    saison_signal = pd.Series(index=common_index, data=0, name="Saison_Signal_Interpretiert")
    saison_signal[saisonalitaet > SCHWELLE_SAISONALITAET_KAUF] = 1
    saison_signal[saisonalitaet < SCHWELLE_SAISONALITAET_VERKAUF] = -1 # Korrigierter Konstantenname
    debug_print("Interpretiertes Saisonalitätssignal (+1 Kauf, -1 Verkauf, 0 Halten):", saison_signal.head())
    debug_print(f"Verteilung interpretiertes Saisonalitätssignal:\n{saison_signal.value_counts(dropna=False)}", None)

    debug_print("BIP-Momentum-Signal (wird direkt verwendet):", bip_signal.head())
    debug_print(f"Verteilung BIP-Momentum-Signal:\n{bip_signal.value_counts(dropna=False)}", None)

    final_signal = pd.Series(index=common_index, data=0, name="Signal")

    cond_kauf_stark = (saison_signal == 1) & (bip_signal == 1)
    cond_kauf_saison_primär = (saison_signal == 1) & (bip_signal == 0)
    cond_kauf_bip_primär = (saison_signal == 0) & (bip_signal == 1)
    final_signal[cond_kauf_stark | cond_kauf_saison_primär | cond_kauf_bip_primär] = 1

    cond_verkauf_stark = (saison_signal == -1) & (bip_signal == -1)
    cond_verkauf_saison_primär = (saison_signal == -1) & (bip_signal == 0)
    cond_verkauf_bip_primär = (saison_signal == 0) & (bip_signal == -1)
    final_signal[cond_verkauf_stark | cond_verkauf_saison_primär | cond_verkauf_bip_primär] = -1

    debug_print("Finale kombinierte Signale (+1 Kauf, -1 Verkauf, 0 Halten):", final_signal.head())
    debug_print(f"Verteilung finale Signale:\n{final_signal.value_counts(dropna=False)}", None)

    final_signal = final_signal.reindex(forex_daten.index).fillna(0)
    debug_print("Finale Signale (auf Forex-Datenindex ausgerichtet und gefüllt):", final_signal.head())
    debug_print(f"Verteilung finale Signale (ausgerichtet):\n{final_signal.value_counts(dropna=False)}", None)

    return final_signal

# --- Visualisierungsfunktion ---
def visualisiere_daten(forex_daten, saisonalitaet, bip_momentum_daten, bip_momentum_signal, signale):
    """
    Visualisiert die Forex-Kurse, Saisonalitätstrends, BIP-Momentum-Daten und Handelssignale.
    """
    debug_print("Starte Visualisierung...")
    fig, अक्ष = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    ax1 = अक्ष[0]
    if PRICE_COLUMN in forex_daten.columns:
        ax1.plot(forex_daten.index, forex_daten[PRICE_COLUMN], label=f'Forex Kurs ({PRICE_COLUMN})', color='blue')

        if not signale.empty:
            kauf_zeitpunkte = signale[signale == 1].index
            verkauf_zeitpunkte = signale[signale == -1].index

            kauf_zeitpunkte_valid = kauf_zeitpunkte.intersection(forex_daten.index)
            verkauf_zeitpunkte_valid = verkauf_zeitpunkte.intersection(forex_daten.index)

            if not kauf_zeitpunkte_valid.empty:
                ax1.plot(kauf_zeitpunkte_valid, forex_daten.loc[kauf_zeitpunkte_valid, PRICE_COLUMN],
                         '^', markersize=8, color='green', label='Kaufsignal', alpha=0.9, linestyle='None')
            if not verkauf_zeitpunkte_valid.empty:
                ax1.plot(verkauf_zeitpunkte_valid, forex_daten.loc[verkauf_zeitpunkte_valid, PRICE_COLUMN],
                         'v', markersize=8, color='red', label='Verkaufssignal', alpha=0.9, linestyle='None')
        ax1.set_title('Forex Kurs und Handelssignale')
        ax1.set_ylabel('Preis')
    else:
        ax1.text(0.5, 0.5, "Keine Forex-Preisdaten zum Anzeigen", horizontalalignment='center', verticalalignment='center', transform=ax1.transAxes)
    ax1.legend(loc='upper left')
    ax1.grid(True)

    ax2 = अक्ष[1]
    if not saisonalitaet.empty:
        ax2.plot(saisonalitaet.index, saisonalitaet, label='Saisonaler Trend (Durchschn. mtl. Return)', color='orange')
        ax2.axhline(0, color='grey', linestyle='--', linewidth=0.8)
        ax2.axhline(SCHWELLE_SAISONALITAET_KAUF, color='lightgreen', linestyle=':', linewidth=0.8, label=f'Kauf-Schwelle ({SCHWELLE_SAISONALITAET_KAUF:.4f})')
        ax2.axhline(SCHWELLE_SAISONALITAET_VERKAUF, color='lightcoral', linestyle=':', linewidth=0.8, label=f'Verkauf-Schwelle ({SCHWELLE_SAISONALITAET_VERKAUF:.4f})') # Korrigierter Konstantenname
        ax2.set_title('Saisonalitätstrend')
        ax2.set_ylabel('Durchschn. mtl. Return')
    else:
        ax2.text(0.5, 0.5, "Keine Saisonalitätsdaten zum Anzeigen", horizontalalignment='center', verticalalignment='center', transform=ax2.transAxes)
    ax2.legend(loc='upper left')
    ax2.grid(True)

    ax3 = अक्ष[2]
    if bip_momentum_signal is not None and not bip_momentum_signal.empty:
        ax3.plot(bip_momentum_signal.index, bip_momentum_signal, label='BIP Momentum Signal (ausgerichtet)', color='purple', linestyle='-')

        if bip_momentum_daten is not None and not bip_momentum_daten.empty:
            ax3_twin = ax3.twinx()
            if BIP_COLUMN_A in bip_momentum_daten.columns:
                 ax3_twin.plot(bip_momentum_daten.index, bip_momentum_daten[BIP_COLUMN_A], label=f'BIP {COUNTRY_A} (roh)', color='mediumturquoise', alpha=0.5, linestyle='--')
            if BIP_COLUMN_B in bip_momentum_daten.columns:
                 ax3_twin.plot(bip_momentum_daten.index, bip_momentum_daten[BIP_COLUMN_B], label=f'BIP {COUNTRY_B} (roh)', color='lightcoral', alpha=0.5, linestyle='--')
            ax3_twin.set_ylabel('BIP Rohwerte')
            lines, labels = ax3.get_legend_handles_labels()
            lines2, labels2 = ax3_twin.get_legend_handles_labels()
            ax3.legend(lines + lines2, labels + labels2, loc='upper left')
        else:
            ax3.legend(loc='upper left')
    else:
        ax3.text(0.5, 0.5, "Keine BIP-Momentum-Signaldaten zum Anzeigen", horizontalalignment='center', verticalalignment='center', transform=ax3.transAxes)

    ax3.set_title('BIP Momentum Signal und Rohdaten')
    ax3.set_xlabel('Datum')
    ax3.set_ylabel('BIP Momentum Signal (+1, 0, -1)')
    ax3.grid(True)

    plt.tight_layout()
    plt.show()
    debug_print("Visualisierung abgeschlossen.")

# --- Hauptfunktion ---
def main():
    """Hauptfunktion des Programms."""
    debug_print("Programmstart.")

    forex_daten = lade_forex_daten(FOREX_DATA_CSV)
    bip_daten = lade_bip_daten(BIP_DATA_CSV)

    if forex_daten.empty:
        print("Konnte Forex-Daten nicht laden. Programm wird beendet.")
        return

    saisonalitaet = berechne_saisonalitaet(forex_daten.copy())

    # Initialisiere das ausgerichtete BIP-Signal mit Nullen
    bip_momentum_signal_aligned = pd.Series(index=forex_daten.index, data=0.0, name="BIP_Momentum_Signal") # Explizit float für Konsistenz

    if not bip_daten.empty:
        bip_momentum_signal_raw = berechne_bip_momentum(bip_daten.copy())
        if not bip_momentum_signal_raw.empty:
            debug_print("BIP-Momentum-Signal (roh, auf BIP-Frequenz) erhalten:", bip_momentum_signal_raw.head())

            # Richte das rohe BIP-Signal auf den Forex-Datenindex aus und fülle vorwärts
            temp_signal = bip_momentum_signal_raw.reindex(forex_daten.index, method='ffill')
            # Fülle verbleibende NaNs (typischerweise am Anfang, wenn Forex-Daten früher beginnen als BIP-Signale) mit 0
            temp_signal.fillna(0.0, inplace=True) # Explizit float
            bip_momentum_signal_aligned = temp_signal
            bip_momentum_signal_aligned.name = "BIP_Momentum_Signal" # Stelle sicher, dass der Name korrekt ist

            debug_print("BIP-Momentum-Signal (ausgerichtet auf Forex-Frequenz):", bip_momentum_signal_aligned.head())
            debug_print(f"Verteilung der ausgerichteten BIP-Signale:\n{bip_momentum_signal_aligned.value_counts(dropna=False)}", None)
        else:
            debug_print("BIP-Momentum-Berechnung ergab ein leeres Signal. Verwende Nullen für BIP-Signal.")
    else:
        debug_print("Keine BIP-Daten vorhanden, überspringe BIP-Momentum-Berechnung. Verwende Nullen für BIP-Signal.")

    signale = generiere_signale(forex_daten, saisonalitaet, bip_momentum_signal_aligned)

    visualisiere_daten(forex_daten, saisonalitaet, bip_daten, bip_momentum_signal_aligned, signale)

    debug_print("Programmende.")

if __name__ == "__main__":
    main()
