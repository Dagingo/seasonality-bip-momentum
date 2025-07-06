import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- Debugging-Funktion ---
# Diese Funktion wird von der GUI-App bereitgestellt oder hier für Standalone-Tests definiert
DEBUG_OUTPUT_CALLBACK = print # Standard-Callback ist print

def set_debug_output_callback(callback_function):
    """Setzt die Callback-Funktion für Debug-Ausgaben."""
    global DEBUG_OUTPUT_CALLBACK
    DEBUG_OUTPUT_CALLBACK = callback_function

def debug_print(message, data=None):
    """Gibt eine Debug-Nachricht und optional Daten über den Callback aus."""
    log_message = f"[DEBUG] {message}"
    if data is not None and isinstance(data, pd.DataFrame):
        log_message += f"\n{data.head().to_string()}\n--------------------"
    elif data is not None:
        log_message += f"\n{str(data)}\n--------------------"

    if DEBUG_OUTPUT_CALLBACK:
        DEBUG_OUTPUT_CALLBACK(log_message)
    else: # Fallback, falls kein Callback gesetzt ist (z.B. bei direkten Tests)
        print(log_message)


class SignalAnalyzer:
    def __init__(self, config=None):
        """
        Initialisiert den SignalAnalyzer.
        config: Ein Dictionary, das z.B. Schwellenwerte enthalten kann.
        """
        self.config = config if config else {}
        # Standard Schwellenwerte, können über config überschrieben werden
        self.schwelle_saisonalitaet_kauf = self.config.get('SCHWELLE_SAISONALITAET_KAUF', 0.0005)
        self.schwelle_saisonalitaet_verkauf = self.config.get('SCHWELLE_SAISONALITAET_VERKAUF', -0.0005)
        # Entferne alte BIP Momentum Schwellenwerte
        # self.schwelle_bip_momentum_kauf = self.config.get('SCHWELLE_BIP_MOMENTUM_KAUF', 0.1)
        # self.schwelle_bip_momentum_verkauf = self.config.get('SCHWELLE_BIP_MOMENTUM_VERKAUF', 0.1)

        # Spaltennamen, die für die Analyse erwartet werden
        self.PRICE_COLUMN = 'Schlusskurs' # Standardname für die Preissplate in Forex-Daten
        # BIP-Spaltennamen werden dynamisch übergeben (bleibt relevant für Datenabruf)
        debug_print("SignalAnalyzer initialisiert.")
        debug_print(f"Saisonalität Kauf-Schwelle: {self.schwelle_saisonalitaet_kauf}, Verkauf-Schwelle: {self.schwelle_saisonalitaet_verkauf}")
        # debug_print(f"BIP Momentum Kauf-Schwelle: {self.schwelle_bip_momentum_kauf}, Verkauf-Schwelle: {self.schwelle_bip_momentum_verkauf}") # Entfernt


    def berechne_saisonalitaet(self, forex_daten):
        """
        Berechnet saisonale Trends aus den Forex-Kursdaten.
        """
        debug_print("Beginne Berechnung der Saisonalität für Forex-Daten:", forex_daten)

        if forex_daten.empty or self.PRICE_COLUMN not in forex_daten.columns:
            debug_print(f"Forex-Daten sind leer oder Preissplate '{self.PRICE_COLUMN}' fehlt. Kann Saisonalität nicht berechnen.")
            return pd.Series(dtype=float, name="Saisonalitaet")

        forex_returns = forex_daten[self.PRICE_COLUMN].pct_change()
        debug_print(f"Prozentuale Veränderungen (Returns) der Forex-Kurse ({self.PRICE_COLUMN}):", forex_returns)

        if not isinstance(forex_daten.index, pd.DatetimeIndex):
            debug_print("FEHLER: Forex-Datenindex ist kein DatetimeIndex.")
            # Versuch der Konvertierung (optional, besser wäre es, wenn Daten schon korrekt sind)
            try:
                forex_daten.index = pd.to_datetime(forex_daten.index)
                debug_print("Forex-Datenindex erfolgreich zu DatetimeIndex konvertiert.")
            except Exception as e:
                debug_print(f"Fehler bei Konvertierung des Forex-Index zu DatetimeIndex: {e}")
                return pd.Series(dtype=float, name="Saisonalitaet")

        # Umstellung auf wöchentliche Saisonalität
        # Group by ISO week of year
        weekly_returns_grouped = forex_returns.groupby(forex_daten.index.isocalendar().week)

        # Debug-Ausgabe für wöchentliche Returns
        for week_num, group in weekly_returns_grouped:
           mean_val = group.mean()
           if isinstance(mean_val, pd.Series): # Should not happen with .mean() on a series group but good practice
               mean_val = mean_val.iloc[0] if not mean_val.empty else np.nan

           if pd.notna(mean_val):
               debug_print(f"  Woche {week_num}: {len(group)} Einträge, Durchschnittlicher Return: {float(mean_val):.6f}", group.head(2)) # Increased precision for weekly
           elif not group.dropna().empty:
               debug_print(f"  Woche {week_num}: {len(group)} Einträge, Durchschnittlicher Return: NaN (nach Verarbeitung)", group.head(2))
           else:
               debug_print(f"  Woche {week_num}: {len(group)} Einträge, keine validen Returns.", group.head(2))

        durchschnittliche_woechentliche_saisonalitaet = weekly_returns_grouped.mean()

        # Handle potential DataFrame output if original series name was complex (though unlikely for pct_change)
        if isinstance(durchschnittliche_woechentliche_saisonalitaet, pd.DataFrame):
            if durchschnittliche_woechentliche_saisonalitaet.shape[1] == 1:
                durchschnittliche_woechentliche_saisonalitaet = durchschnittliche_woechentliche_saisonalitaet.iloc[:, 0]
            else:
                debug_print("FEHLER: `durchschnittliche_woechentliche_saisonalitaet` ist ein mehrspaltiges DataFrame, unerwartet.")
                return pd.Series(dtype=float, name="Saisonalitaet")

        debug_print("Durchschnittliche wöchentliche Saisonalität (verarbeitet):", durchschnittliche_woechentliche_saisonalitaet)

        saisonalitaet_signal = pd.Series(index=forex_daten.index, dtype=float, name="Saisonalitaet")

        # Map average weekly seasonality back to the daily forex data index
        # Ensure forex_daten.index.isocalendar().week is available
        if not hasattr(forex_daten.index, 'isocalendar'):
             debug_print("FEHLER: Forex-Datenindex scheint kein DatetimeIndex mehr zu sein oder isocalendar nicht verfügbar.")
             return pd.Series(dtype=float, name="Saisonalitaet")

        forex_week_numbers = forex_daten.index.isocalendar().week

        for week_num, avg_saison_wert in durchschnittliche_woechentliche_saisonalitaet.items():
            saisonalitaet_signal[forex_week_numbers == week_num] = avg_saison_wert

        saisonalitaet_signal.fillna(0, inplace=True) # Fill any day not covered (e.g. if a week had no returns) with 0

        debug_print("Finale Saisonalitäts-Signal-Serie (wöchentlich):", saisonalitaet_signal)
        if not saisonalitaet_signal.empty:
             debug_print(f"Statistik Saisonalität: Min={saisonalitaet_signal.min():.4f}, Max={saisonalitaet_signal.max():.4f}, Mean={saisonalitaet_signal.mean():.4f}")

        return saisonalitaet_signal

    def berechne_bip_momentum(self, bip_daten, bip_col_country1, bip_col_country2):
        """
        Berechnet das BIP-Momentum. bip_col_country1 ist für die Basiswährung, bip_col_country2 für die Kurswährung.
        """
        debug_print(f"Beginne Berechnung des BIP-Momentums mit Spalten: Land1='{bip_col_country1}', Land2='{bip_col_country2}'", bip_daten)

        if bip_daten.empty or bip_col_country1 not in bip_daten.columns or bip_col_country2 not in bip_daten.columns:
            debug_print(f"BIP-Daten sind leer oder erforderliche Spalten ('{bip_col_country1}', '{bip_col_country2}') fehlen.")
            return pd.Series(dtype=float, name="BIP_Momentum_Signal_Raw") # Leere Series mit korrektem Namen

        if not isinstance(bip_daten.index, pd.DatetimeIndex):
            debug_print("FEHLER: BIP-Datenindex ist kein DatetimeIndex.")
            try:
                bip_daten.index = pd.to_datetime(bip_daten.index)
                debug_print("BIP-Datenindex erfolgreich zu DatetimeIndex konvertiert.")
            except Exception as e:
                debug_print(f"Fehler bei Konvertierung des BIP-Index zu DatetimeIndex: {e}")
                return pd.Series(dtype=float, name="BIP_Momentum_Signal_Raw")


        bip_daten_sorted = bip_daten.sort_index() # Stelle sicher, dass Daten sortiert sind

        bip_wachstum_A = bip_daten_sorted[bip_col_country1].pct_change() * 100
        bip_wachstum_B = bip_daten_sorted[bip_col_country2].pct_change() * 100
        debug_print(f"BIP-Wachstumsrate Land 1 ({bip_col_country1}) (%):", bip_wachstum_A)
        debug_print(f"BIP-Wachstumsrate Land 2 ({bip_col_country2}) (%):", bip_wachstum_B)

        momentum_A = bip_wachstum_A.diff()
        momentum_B = bip_wachstum_B.diff()
        debug_print(f"Momentum BIP-Wachstum Land 1 ({bip_col_country1}):", momentum_A)
        debug_print(f"Momentum BIP-Wachstum Land 2 ({bip_col_country2}):", momentum_B)

        momentum_df = pd.DataFrame({
            'Momentum_A': momentum_A, # Generische Namen intern
            'Momentum_B': momentum_B
        })
        momentum_df.dropna(inplace=True) # Wichtig, da diff und pct_change NaNs erzeugen
        debug_print("Kombiniertes Momentum DataFrame (nach DropNA):", momentum_df)

        if momentum_df.empty:
            debug_print("Momentum DataFrame ist leer nach DropNA. Nicht genügend BIP-Daten für Momentum.")
            return pd.Series(dtype=float, name="BIP_Momentum_Signal_Raw")

        # Signal: +1 wenn Momentum A > Momentum B (gut für Währung A / schlecht für Währung B des Paares)
        # Forex-Paar ist typischerweise Basis/Quote. Wenn Basis (Land A) stärker wird, steigt der Kurs -> Kauf Basis/Verkauf Quote.
        # Kaufbedingung: Momentum A muss um die Kauf-Schwelle stärker sein als Momentum B
        kauf_bedingung = momentum_df['Momentum_A'] > (momentum_df['Momentum_B'] + self.schwelle_bip_momentum_kauf)
        # Verkaufsbedingung: Momentum A muss um die Verkauf-Schwelle schwächer sein als Momentum B
        # (oder Momentum B ist um die Verkauf-Schwelle stärker als Momentum A)
        verkauf_bedingung = momentum_df['Momentum_A'] < (momentum_df['Momentum_B'] - self.schwelle_bip_momentum_verkauf)


        bip_momentum_signal_raw = pd.Series(index=momentum_df.index, data=0, name="BIP_Momentum_Signal_Raw", dtype=int)
        bip_momentum_signal_raw[kauf_bedingung] = 1
        bip_momentum_signal_raw[verkauf_bedingung] = -1

        debug_print("Rohes BIP-Momentum-Signal (auf BIP-Datenfrequenz):", bip_momentum_signal_raw)
        if not bip_momentum_signal_raw.empty:
            debug_print(f"Verteilung rohes BIP-Signal:\n{bip_momentum_signal_raw.value_counts(dropna=False)}")

        return bip_momentum_signal_raw

    # Die Methode berechne_bip_momentum wird entfernt, da sie durch compare_gdp_momentum ersetzt wird.
    # def berechne_bip_momentum(self, bip_daten, bip_col_country1, bip_col_country2):
    #     ... (alter Code) ...


    def generiere_signale(self, forex_daten_idx, saisonalitaet_raw, gdp_momentum_signal_aligned):
        """
        Kombiniert Signale aus Saisonalität und dem neuen GDP-Momentum-Signal.
        forex_daten_idx wird für den finalen Index benötigt.
        gdp_momentum_signal_aligned: Die Signal-Serie ('long', 'short', None) von compare_gdp_momentum,
                                     ausgerichtet auf den Forex-Datenindex.
        """
        debug_print("Beginne Generierung finaler Signale...")
        debug_print("Eingang Saisonalität (roh):", saisonalitaet_raw)
        debug_print("Eingang GDP-Momentum-Signal (ausgerichtet):", gdp_momentum_signal_aligned)

        # Stelle sicher, dass alle Zeitreihen denselben Index haben oder angleichen
        # gdp_momentum_signal_aligned sollte bereits auf forex_daten_idx ausgerichtet sein.
        common_index = saisonalitaet_raw.index.intersection(gdp_momentum_signal_aligned.index)

        if common_index.empty:
            debug_print("Kein gemeinsamer Index zwischen Saisonalität und GDP-Momentum-Signal.")
            return pd.Series(index=forex_daten_idx, data=0, name="Signal")

        saisonalitaet = saisonalitaet_raw.reindex(common_index).fillna(0)
        # Konvertiere 'long'/'short'/None zu 1/-1/0 für die Kombination
        gdp_signal_numeric = pd.Series(index=common_index, data=0, dtype=int)
        gdp_signal_numeric[gdp_momentum_signal_aligned.reindex(common_index) == 'long'] = 1
        gdp_signal_numeric[gdp_momentum_signal_aligned.reindex(common_index) == 'short'] = -1

        debug_print("Numerisches GDP-Momentum-Signal (1=long, -1=short, 0=none):", gdp_signal_numeric)


        saison_signal_numeric = pd.Series(index=common_index, data=0, name="Saison_Signal_Interpretiert", dtype=int)
        saison_signal_numeric[saisonalitaet > self.schwelle_saisonalitaet_kauf] = 1
        saison_signal_numeric[saisonalitaet < self.schwelle_saisonalitaet_verkauf] = -1
        debug_print("Interpretiertes Saisonalitätssignal (numerisch):", saison_signal_numeric)
        if not saison_signal_numeric.empty: # Geändert von saison_signal zu saison_signal_numeric
            debug_print(f"Verteilung Saisonalitätssignal (interpretiert):\n{saison_signal_numeric.value_counts(dropna=False)}")


        final_signal = pd.Series(index=common_index, data=0, name="Signal", dtype=int)
        # Geänderte Logik: Ein Signal wird nur gegeben, wenn BEIDE Indikatoren die jeweiligen Schwellenwerte erreichen (übereinstimmen).

        # Strenge Kaufbedingung: Saisonalität signalisiert Kauf UND GDP-Momentum signalisiert Long.
        cond_kauf_stark = (saison_signal_numeric == 1) & (gdp_signal_numeric == 1)
        final_signal[cond_kauf_stark] = 1

        # Strenge Verkaufsbedingung: Saisonalität signalisiert Verkauf UND GDP-Momentum signalisiert Short.
        cond_verkauf_stark = (saison_signal_numeric == -1) & (gdp_signal_numeric == -1)
        final_signal[cond_verkauf_stark] = -1

        # Alle anderen Fälle resultieren in einem neutralen Signal (0), was die Standardinitialisierung ist.


        # Reindex auf den ursprünglichen Forex-Daten-Index, um sicherzustellen, dass alle Datenpunkte abgedeckt sind
        final_signal = final_signal.reindex(forex_daten_idx).fillna(0) # ffill() könnte hier auch Sinn machen, je nach Anforderung
        debug_print("Finale kombinierte Signale:", final_signal)
        if not final_signal.empty:
            debug_print(f"Verteilung finale Signale:\n{final_signal.value_counts(dropna=False)}")

        return final_signal

    def plot_analyse_results(self, fig, forex_daten, saisonalitaet_values,
                             bip_roh_daten, # Bleibt für Rohdaten-Plot
                             gdp_momentum_outputs, # Tupel von compare_gdp_momentum
                             final_signale, bip_col_country1, bip_col_country2,
                             gdp_diff_long_thresh, gdp_diff_short_thresh # Neue Schwellenwerte für Legende
                             ):
        """
        Zeichnet die Analyseergebnisse auf die übergebene Matplotlib-Figur.
        fig: Eine Matplotlib-Figur, auf der gezeichnet wird.
        gdp_momentum_outputs: Tupel (momentum_a_scaled, momentum_b_scaled, momentum_difference, signal_series)
        """
        debug_print("Starte Visualisierung der Analyseergebnisse...")
        fig.clear() # Alte Zeichnungen entfernen

        ax = fig.subplots(3, 1, sharex=True) # Erstellt Subplots auf der Figur

        # Unpack gdp_momentum_outputs, falls vorhanden
        gdp_mom_a, gdp_mom_b, gdp_mom_diff, gdp_signal_raw = (None, None, None, None)
        if gdp_momentum_outputs:
            gdp_mom_a, gdp_mom_b, gdp_mom_diff, gdp_signal_raw = gdp_momentum_outputs


        # Plot 1: Forex-Kurse und Signale
        ax1 = ax[0]
        if self.PRICE_COLUMN in forex_daten.columns:
            ax1.plot(forex_daten.index, forex_daten[self.PRICE_COLUMN], label=f'Forex Kurs ({self.PRICE_COLUMN})', color='blue')

            if not final_signale.empty:
                kauf_zeitpunkte = final_signale[final_signale == 1].index
                verkauf_zeitpunkte = final_signale[final_signale == -1].index

                kauf_zeitpunkte_valid = kauf_zeitpunkte.intersection(forex_daten.index)
                verkauf_zeitpunkte_valid = verkauf_zeitpunkte.intersection(forex_daten.index)

                if not kauf_zeitpunkte_valid.empty:
                    ax1.plot(kauf_zeitpunkte_valid, forex_daten.loc[kauf_zeitpunkte_valid, self.PRICE_COLUMN],
                             '^', markersize=8, color='green', label='Kaufsignal', alpha=0.9, linestyle='None')
                if not verkauf_zeitpunkte_valid.empty:
                    ax1.plot(verkauf_zeitpunkte_valid, forex_daten.loc[verkauf_zeitpunkte_valid, self.PRICE_COLUMN],
                             'v', markersize=8, color='red', label='Verkaufssignal', alpha=0.9, linestyle='None')
            ax1.set_title('Forex Kurs und Handelssignale')
            ax1.set_ylabel('Preis')
        else:
            ax1.text(0.5, 0.5, "Keine Forex-Preisdaten", ha='center', va='center', transform=ax1.transAxes)
        ax1.legend(loc='upper left')
        ax1.grid(True)

        # Plot 2: Saisonalität
        ax2 = ax[1]
        if not saisonalitaet_values.empty:
            ax2.plot(saisonalitaet_values.index, saisonalitaet_values, label='Saisonaler Trend', color='orange')
            ax2.axhline(0, color='grey', linestyle='--', linewidth=0.8)
            ax2.axhline(self.schwelle_saisonalitaet_kauf, color='lightgreen', linestyle=':', linewidth=0.8, label=f'Kauf-Schwelle ({self.schwelle_saisonalitaet_kauf:.4f})')
            ax2.axhline(self.schwelle_saisonalitaet_verkauf, color='lightcoral', linestyle=':', linewidth=0.8, label=f'Verkauf-Schwelle ({self.schwelle_saisonalitaet_verkauf:.4f})')
            ax2.set_title('Saisonalitätstrend')
            ax2.set_ylabel('Durchschn. mtl. Return')
        else:
            ax2.text(0.5, 0.5, "Keine Saisonalitätsdaten", ha='center', va='center', transform=ax2.transAxes)
        ax2.legend(loc='upper left')
        ax2.grid(True)

        # Plot 3: GDP Momentum Daten
        ax3 = ax[2]
        handles_ax3 = []
        labels_ax3 = []

        # Verwende gdp_mom_a, gdp_mom_b, gdp_mom_diff aus gdp_momentum_outputs
        if gdp_mom_diff is not None and not gdp_mom_diff.empty:
            line1, = ax3.plot(gdp_mom_diff.index, gdp_mom_diff, label='GDP Mom. Diff (A-B, skaliert)', color='purple', linestyle='-')
            handles_ax3.append(line1)
            labels_ax3.append('GDP Mom. Diff (A-B, skaliert)')

            # Plotten der Schwellenwerte für die Differenz
            line2 = ax3.axhline(gdp_diff_long_thresh, color='darkgreen', linestyle=':', linewidth=1.2, label=f'Long Schwelle ({gdp_diff_long_thresh:.1f})')
            line3 = ax3.axhline(gdp_diff_short_thresh, color='darkred', linestyle=':', linewidth=1.2, label=f'Short Schwelle ({gdp_diff_short_thresh:.1f})')
            # Manuelles Hinzufügen zur Legende, da axhline keine Handles/Labels automatisch hinzufügt, die von ax3.legend() erfasst werden
            handles_ax3.extend([line2, line3])
            labels_ax3.extend([f'Long Schwelle ({gdp_diff_long_thresh:.1f})', f'Short Schwelle ({gdp_diff_short_thresh:.1f})'])

            # Optional: Plotten der einzelnen skalierten Momentum-Werte
            if gdp_mom_a is not None and not gdp_mom_a.empty:
                line_a, = ax3.plot(gdp_mom_a.index, gdp_mom_a, label='GDP Mom. A (skaliert)', color='blue', linestyle='--', alpha=0.7)
                handles_ax3.append(line_a)
                labels_ax3.append(f'GDP Mom. {bip_col_country1 or "A"} (skaliert)') # Verwende tatsächliche Ländernamen falls verfügbar
            if gdp_mom_b is not None and not gdp_mom_b.empty:
                line_b, = ax3.plot(gdp_mom_b.index, gdp_mom_b, label='GDP Mom. B (skaliert)', color='orange', linestyle='--', alpha=0.7)
                handles_ax3.append(line_b)
                labels_ax3.append(f'GDP Mom. {bip_col_country2 or "B"} (skaliert)')

            ax3.set_ylabel('Skaliertes GDP Momentum [-100, 100]')
        else:
            # Fallback, falls keine GDP Momentum Daten vorhanden sind (z.B. wenn compare_gdp_momentum nichts zurückgibt)
            ax3.text(0.5, 0.5, "Keine GDP Momentum Daten verfügbar", ha='center', va='center', transform=ax3.transAxes)

        # Plot Raw BIP data on twin axis (bleibt bestehen)
        handles_twin_ax3 = []
        labels_twin_ax3 = []
        if bip_roh_daten is not None and not bip_roh_daten.empty:
            ax3_twin = ax3.twinx() # Erzeuge Twin-Achse nur wenn Daten da sind
            if bip_col_country1 and bip_col_country1 in bip_roh_daten.columns: # Stelle sicher, dass Spaltenname existiert
                 line_c1, = ax3_twin.plot(bip_roh_daten.index, bip_roh_daten[bip_col_country1], label=f'BIP {bip_col_country1} (roh)', color='mediumturquoise', alpha=0.4, linestyle=':')
                 handles_twin_ax3.append(line_c1)
                 labels_twin_ax3.append(f'BIP {bip_col_country1} (roh)')
            if bip_col_country2 and bip_col_country2 in bip_roh_daten.columns: # Stelle sicher, dass Spaltenname existiert
                 line_c2, = ax3_twin.plot(bip_roh_daten.index, bip_roh_daten[bip_col_country2], label=f'BIP {bip_col_country2} (roh)', color='lightcoral', alpha=0.4, linestyle=':')
                 handles_twin_ax3.append(line_c2)
                 labels_twin_ax3.append(f'BIP {bip_col_country2} (roh)')
            ax3_twin.set_ylabel('BIP Rohwerte')

        # Kombinierte Legende für ax3 und ax3_twin
        # Stelle sicher, dass handles_ax3 und labels_ax3 zuerst da sind
        combined_handles = handles_ax3 + handles_twin_ax3
        combined_labels = labels_ax3 + labels_twin_ax3
        if combined_handles: # Nur Legende anzeigen, wenn es etwas zu zeigen gibt
            ax3.legend(combined_handles, combined_labels, loc='upper left', fontsize='small')


        ax3.set_title('GDP Momentum Analyse und BIP Rohdaten')
        ax3.set_xlabel('Datum')
        ax3.grid(True)

        fig.tight_layout()
        debug_print("Visualisierung auf Figur abgeschlossen.")
        # plt.show() wird hier nicht aufgerufen, das macht die GUI-Anwendung mit dem Canvas


# Temporäre Konstanten, die aus der alten Datei stammen könnten (werden durch Analyzer-Config ersetzt)
# PRICE_COLUMN = 'Schlusskurs' # Wird jetzt in der Klasse als self.PRICE_COLUMN definiert
# SCHWELLE_SAISONALITAET_KAUF = 0.0005 # Wird jetzt in der Klasse als self.schwelle_saisonalitaet_kauf definiert
# SCHWELLE_SAISONALITAET_VERKAUF = -0.0005 # Wird jetzt in der Klasse als self.schwelle_saisonalitaet_verkauf definiert


# Neue Funktion gemäß Anforderung
def compare_gdp_momentum(gdp_series_a: pd.Series, gdp_series_b: pd.Series,
                         n_periods_growth: int = 4,
                         long_threshold: float = 30.0, short_threshold: float = -30.0):
    """
    Analysiert und bewertet das BIP-Momentum zweier Staaten oder Regionen normiert.
    Verwendet die global in signal_analyzer.py gesetzte DEBUG_OUTPUT_CALLBACK Funktion.

    Args:
        gdp_series_a (pd.Series): Zeitreihe (Datum -> BIP-Wert) für Staat A.
        gdp_series_b (pd.Series): Zeitreihe (Datum -> BIP-Wert) für Staat B.
        n_periods_growth (int): Anzahl der Perioden für die Wachstumsberechnung (z.B. 4 für YoY bei Quartalsdaten).
        long_threshold (float): Schwellenwert für Long-Signal auf Basis der skalierten Momentum-Differenz.
        short_threshold (float): Schwellenwert für Short-Signal auf Basis der skalierten Momentum-Differenz.

    Returns:
        tuple: (momentum_a_scaled, momentum_b_scaled, momentum_difference, signal_series)
               Alle als pandas Series, indexiert wie die synchronisierten Eingangsdaten.
               Signal-Series enthält 'long', 'short', oder None.
               Gibt (empty_series, empty_series, empty_series, empty_object_series) zurück bei Datenproblemen.
    """
    # current_debug_print = debug_callback if debug_callback else debug_print # Entfernt - nutze globalen debug_print

    debug_print(f"Starte compare_gdp_momentum für {gdp_series_a.name} und {gdp_series_b.name}") # Geändert zu debug_print
    debug_print(f"n_periods_growth: {n_periods_growth}, long_threshold: {long_threshold}, short_threshold: {short_threshold}") # Geändert zu debug_print

    # 1. Datenvorbereitung und Synchronisierung
    if not isinstance(gdp_series_a.index, pd.DatetimeIndex):
        gdp_series_a.index = pd.to_datetime(gdp_series_a.index)
    if not isinstance(gdp_series_b.index, pd.DatetimeIndex):
        gdp_series_b.index = pd.to_datetime(gdp_series_b.index)

    # Kombiniere die Serien, um einen gemeinsamen Zeitindex zu erhalten und NaN, wo Daten fehlen
    combined_gdp = pd.DataFrame({'A': gdp_series_a, 'B': gdp_series_b})
    original_len_a = len(gdp_series_a.dropna())
    original_len_b = len(gdp_series_b.dropna())

    # Interpolation - nur wenn es Lücken gibt, nicht an den Enden, wo es keine Referenz gibt
    # Lineare Interpolation ist ein Standardansatz für Zeitreihen
    combined_gdp_interpolated = combined_gdp.interpolate(method='linear', limit_direction='both')

    # Überprüfe, ob nach Interpolation noch NaNs vorhanden sind (wahrscheinlich an den Rändern)
    if combined_gdp_interpolated['A'].isnull().any() or combined_gdp_interpolated['B'].isnull().any():
        debug_print("WARNUNG: NaN-Werte in BIP-Daten auch nach Interpolation vorhanden (wahrscheinlich an den Rändern). Dies kann die Wachstumsberechnung beeinflussen.") # Geändert zu debug_print

    # Entferne Zeilen, wo nach Interpolation immer noch für eine der Serien NaN ist (passiert typischerweise an den Enden, wenn Serien unterschiedlich lang sind)
    # Dies ist wichtig, bevor .pct_change oder .diff angewendet wird, um Fehler zu vermeiden
    processed_gdp = combined_gdp_interpolated.dropna()

    if len(processed_gdp) < n_periods_growth + 1: # Brauchen genug Daten für mindestens eine Wachstumsberechnung
        debug_print(f"FEHLER: Nicht genügend überlappende Datenpunkte ({len(processed_gdp)}) nach Synchronisierung und Bereinigung für Wachstumsberechnung mit n_periods_growth={n_periods_growth}.") # Geändert zu debug_print
        empty_series = pd.Series(dtype=float)
        return empty_series, empty_series, empty_series, pd.Series(dtype=object)


    # 2. Wachstumsratenberechnung (z.B. Year-over-Year)
    # (Wert_aktuell / Wert_vor_n_perioden) - 1
    gdp_growth_a = (processed_gdp['A'] / processed_gdp['A'].shift(n_periods_growth)) - 1
    gdp_growth_b = (processed_gdp['B'] / processed_gdp['B'].shift(n_periods_growth)) - 1

    # Entferne NaNs, die durch .shift() am Anfang der Serie entstehen
    gdp_growth_a = gdp_growth_a.dropna()
    gdp_growth_b = gdp_growth_b.dropna()

    # Erneut ausrichten, falls eine Serie nach dropna kürzer ist
    growth_df = pd.DataFrame({'growth_A': gdp_growth_a, 'growth_B': gdp_growth_b}).dropna()

    if growth_df.empty:
        debug_print("FEHLER: Keine überlappenden Wachstumsdaten nach Berechnung und Bereinigung.") # Geändert zu debug_print
        empty_series = pd.Series(dtype=float)
        return empty_series, empty_series, empty_series, pd.Series(dtype=object)

    debug_print("BIP-Wachstumsraten berechnet (A):", growth_df['growth_A']) # Geändert zu debug_print
    debug_print("BIP-Wachstumsraten berechnet (B):", growth_df['growth_B']) # Geändert zu debug_print

    # 3. Min-Max Skalierung der Wachstumsraten auf [-100, 100]
    # Die Skalierung erfolgt über die gesamte Historie der jeweiligen Wachstumsrate.
    def min_max_scale_series(series, out_min=-100, out_max=100):
        """Skaliert eine Pandas Series linear auf den Bereich [out_min, out_max]."""
        min_val = series.min()
        max_val = series.max()
        if pd.isna(min_val) or pd.isna(max_val) or min_val == max_val:
            # Wenn keine Varianz oder nur NaNs, returniere eine Serie von Nullen (oder Mittelwert des Zielbereichs)
            debug_print(f"WARNUNG: Min-Max-Skalierung für '{series.name}' nicht möglich (min={min_val}, max={max_val}). Gebe Nullen zurück.") # Geändert zu debug_print
            return pd.Series(0, index=series.index, name=series.name + "_scaled")

        # y = (y_max - y_min) * (x - x_min) / (x_max - x_min) + y_min
        scaled_series = (out_max - out_min) * (series - min_val) / (max_val - min_val) + out_min
        return scaled_series.rename(series.name + "_scaled")

    momentum_a_scaled = min_max_scale_series(growth_df['growth_A'])
    momentum_b_scaled = min_max_scale_series(growth_df['growth_B'])

    debug_print("Skalierte Momentum-Werte (A):", momentum_a_scaled) # Geändert zu debug_print
    debug_print("Skalierte Momentum-Werte (B):", momentum_b_scaled) # Geändert zu debug_print

    # 4. Differenz der skalierten Momentum-Werte berechnen
    momentum_difference = (momentum_a_scaled - momentum_b_scaled).rename("Momentum_Difference")
    debug_print("Momentum-Differenz (A - B, skaliert):", momentum_difference) # Geändert zu debug_print

    # 5. Signallogik anwenden
    # Initialisiere die Signal-Serie mit None (oder np.nan, dann konvertieren)
    signal_series = pd.Series(index=momentum_difference.index, dtype=object, name="Signal")

    # Long-Signal Bedingung
    signal_series[momentum_difference > long_threshold] = 'long'
    # Short-Signal Bedingung
    signal_series[momentum_difference < short_threshold] = 'short'
    # Kein Signal (bleibt None oder NaN, was in Ordnung ist)

    debug_print("Generierte Signale:", signal_series[signal_series.notna()]) # Geändert zu debug_print, zeige nur tatsächliche Signale

    return momentum_a_scaled, momentum_b_scaled, momentum_difference, signal_series


print("SignalAnalyzer Modul geladen.") # Temporärer Debug-Print
