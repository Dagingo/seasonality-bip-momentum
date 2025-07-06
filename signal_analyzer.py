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

        # Spaltennamen, die für die Analyse erwartet werden
        self.PRICE_COLUMN = 'Schlusskurs' # Standardname für die Preissplate in Forex-Daten
        # BIP-Spaltennamen werden dynamisch übergeben
        debug_print("SignalAnalyzer initialisiert.")
        debug_print(f"Saisonalität Kauf-Schwelle: {self.schwelle_saisonalitaet_kauf}, Verkauf-Schwelle: {self.schwelle_saisonalitaet_verkauf}")


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

        monthly_returns = forex_returns.groupby(forex_daten.index.month)

        # Debug-Ausgabe für monatliche Returns
        for name, group in monthly_returns:
           mean_val = group.mean()
           # Sicherstellen, dass mean_val ein Skalar ist für die Formatierung
           if isinstance(mean_val, pd.Series):
               mean_val = mean_val.iloc[0] if not mean_val.empty else np.nan

           if pd.notna(mean_val): # Nur drucken, wenn mean_val nicht NaN ist
               debug_print(f"  Monat {name}: {len(group)} Einträge, Durchschnittlicher Return: {float(mean_val):.4f}", group.head(2))
           elif not group.dropna().empty:
               debug_print(f"  Monat {name}: {len(group)} Einträge, Durchschnittlicher Return: NaN (nach Verarbeitung)", group.head(2))
           else:
               debug_print(f"  Monat {name}: {len(group)} Einträge, keine validen Returns.", group.head(2))

        durchschnittliche_monatliche_saisonalitaet = monthly_returns.mean()
        # Sicherstellen, dass durchschnittliche_monatliche_saisonalitaet eine Series von Skalaren ist
        if isinstance(durchschnittliche_monatliche_saisonalitaet, pd.DataFrame):
            if durchschnittliche_monatliche_saisonalitaet.shape[1] == 1:
                durchschnittliche_monatliche_saisonalitaet = durchschnittliche_monatliche_saisonalitaet.iloc[:, 0]
            else:
                debug_print("FEHLER: `durchschnittliche_monatliche_saisonalitaet` ist ein mehrspaltiges DataFrame, unerwartet.")
                # Fallback oder Fehlerbehandlung
                return pd.Series(dtype=float, name="Saisonalitaet")
        elif isinstance(durchschnittliche_monatliche_saisonalitaet, pd.Series) and isinstance(durchschnittliche_monatliche_saisonalitaet.iloc[0], pd.Series):
             # Falls die Einträge der Series selbst Series sind (z.B. durch MultiIndex)
            debug_print("Warnung: Einträge von `durchschnittliche_monatliche_saisonalitaet` sind Series, versuche zu entpacken.")
            try:
                durchschnittliche_monatliche_saisonalitaet = durchschnittliche_monatliche_saisonalitaet.apply(lambda s: s.iloc[0] if isinstance(s, pd.Series) and not s.empty else s)
            except Exception as e:
                debug_print(f"Fehler beim Entpacken von `durchschnittliche_monatliche_saisonalitaet`: {e}")
                return pd.Series(dtype=float, name="Saisonalitaet")


        debug_print("Durchschnittliche monatliche Saisonalität (verarbeitet):", durchschnittliche_monatliche_saisonalitaet)

        saisonalitaet_signal = pd.Series(index=forex_daten.index, dtype=float, name="Saisonalitaet")
        debug_print("Durchschnittliche monatliche Saisonalität:", durchschnittliche_monatliche_saisonalitaet)

        saisonalitaet_signal = pd.Series(index=forex_daten.index, dtype=float, name="Saisonalitaet")
        for monat, avg_saison_wert in durchschnittliche_monatliche_saisonalitaet.items():
            saisonalitaet_signal[forex_daten.index.month == monat] = avg_saison_wert

        saisonalitaet_signal.fillna(0, inplace=True)

        debug_print("Finale Saisonalitäts-Signal-Serie:", saisonalitaet_signal)
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
        kauf_bedingung = momentum_df['Momentum_A'] > momentum_df['Momentum_B']
        verkauf_bedingung = momentum_df['Momentum_A'] < momentum_df['Momentum_B']

        bip_momentum_signal_raw = pd.Series(index=momentum_df.index, data=0, name="BIP_Momentum_Signal_Raw", dtype=int)
        bip_momentum_signal_raw[kauf_bedingung] = 1
        bip_momentum_signal_raw[verkauf_bedingung] = -1

        debug_print("Rohes BIP-Momentum-Signal (auf BIP-Datenfrequenz):", bip_momentum_signal_raw)
        if not bip_momentum_signal_raw.empty:
            debug_print(f"Verteilung rohes BIP-Signal:\n{bip_momentum_signal_raw.value_counts(dropna=False)}")

        return bip_momentum_signal_raw

    def generiere_signale(self, forex_daten_idx, saisonalitaet_raw, bip_momentum_signal_aligned):
        """
        Kombiniert Signale. forex_daten_idx wird nur für den finalen Index benötigt.
        """
        debug_print("Beginne Generierung finaler Signale...")
        debug_print("Eingang Saisonalität (roh):", saisonalitaet_raw)
        debug_print("Eingang BIP-Momentum (ausgerichtet):", bip_momentum_signal_aligned)

        # Stelle sicher, dass alle Zeitreihen denselben Index haben oder angleichen
        common_index = saisonalitaet_raw.index.intersection(bip_momentum_signal_aligned.index)

        if common_index.empty:
            debug_print("Kein gemeinsamer Index zwischen Saisonalität und BIP-Signal.")
            return pd.Series(index=forex_daten_idx, data=0, name="Signal")

        saisonalitaet = saisonalitaet_raw.reindex(common_index).fillna(0)
        bip_signal = bip_momentum_signal_aligned.reindex(common_index).fillna(0)

        saison_signal = pd.Series(index=common_index, data=0, name="Saison_Signal_Interpretiert")
        saison_signal[saisonalitaet > self.schwelle_saisonalitaet_kauf] = 1
        saison_signal[saisonalitaet < self.schwelle_saisonalitaet_verkauf] = -1
        debug_print("Interpretiertes Saisonalitätssignal:", saison_signal)
        if not saison_signal.empty:
            debug_print(f"Verteilung Saisonalitätssignal (interpretiert):\n{saison_signal.value_counts(dropna=False)}")


        final_signal = pd.Series(index=common_index, data=0, name="Signal")
        cond_kauf_stark = (saison_signal == 1) & (bip_signal == 1)
        cond_kauf_saison_primär = (saison_signal == 1) & (bip_signal == 0)
        cond_kauf_bip_primär = (saison_signal == 0) & (bip_signal == 1)
        final_signal[cond_kauf_stark | cond_kauf_saison_primär | cond_kauf_bip_primär] = 1

        cond_verkauf_stark = (saison_signal == -1) & (bip_signal == -1)
        cond_verkauf_saison_primär = (saison_signal == -1) & (bip_signal == 0)
        cond_verkauf_bip_primär = (saison_signal == 0) & (bip_signal == -1)
        final_signal[cond_verkauf_stark | cond_verkauf_saison_primär | cond_verkauf_bip_primär] = -1

        # Reindex auf den ursprünglichen Forex-Daten-Index, um sicherzustellen, dass alle Datenpunkte abgedeckt sind
        final_signal = final_signal.reindex(forex_daten_idx).fillna(0)
        debug_print("Finale kombinierte Signale:", final_signal)
        if not final_signal.empty:
            debug_print(f"Verteilung finale Signale:\n{final_signal.value_counts(dropna=False)}")

        return final_signal

    def plot_analyse_results(self, fig, forex_daten, saisonalitaet_values, bip_roh_daten, bip_aligned_signal, final_signale, bip_col_country1, bip_col_country2):
        """
        Zeichnet die Analyseergebnisse auf die übergebene Matplotlib-Figur.
        fig: Eine Matplotlib-Figur, auf der gezeichnet wird.
        """
        debug_print("Starte Visualisierung der Analyseergebnisse...")
        fig.clear() # Alte Zeichnungen entfernen

        ax = fig.subplots(3, 1, sharex=True) # Erstellt Subplots auf der Figur

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

        # Plot 3: BIP Momentum Signal und Rohdaten
        ax3 = ax[2]
        if bip_aligned_signal is not None and not bip_aligned_signal.empty:
            ax3.plot(bip_aligned_signal.index, bip_aligned_signal, label='BIP Momentum Signal (ausgerichtet)', color='purple', linestyle='-')

            if bip_roh_daten is not None and not bip_roh_daten.empty:
                ax3_twin = ax3.twinx()
                if bip_col_country1 in bip_roh_daten.columns:
                     ax3_twin.plot(bip_roh_daten.index, bip_roh_daten[bip_col_country1], label=f'BIP {bip_col_country1} (roh)', color='mediumturquoise', alpha=0.5, linestyle='--')
                if bip_col_country2 in bip_roh_daten.columns:
                     ax3_twin.plot(bip_roh_daten.index, bip_roh_daten[bip_col_country2], label=f'BIP {bip_col_country2} (roh)', color='lightcoral', alpha=0.5, linestyle='--')
                ax3_twin.set_ylabel('BIP Rohwerte')
                lines, labels = ax3.get_legend_handles_labels()
                lines2, labels2 = ax3_twin.get_legend_handles_labels()
                ax3.legend(lines + lines2, labels + labels2, loc='upper left') # Kombinierte Legende
            else:
                 ax3.legend(loc='upper left')
        else:
            ax3.text(0.5, 0.5, "Keine BIP-Momentum-Daten", ha='center', va='center', transform=ax3.transAxes)

        ax3.set_title('BIP Momentum Signal und Rohdaten')
        ax3.set_xlabel('Datum')
        ax3.set_ylabel('BIP Momentum Signal (+1, 0, -1)')
        ax3.grid(True)

        fig.tight_layout()
        debug_print("Visualisierung auf Figur abgeschlossen.")
        # plt.show() wird hier nicht aufgerufen, das macht die GUI-Anwendung mit dem Canvas


# Temporäre Konstanten, die aus der alten Datei stammen könnten (werden durch Analyzer-Config ersetzt)
# PRICE_COLUMN = 'Schlusskurs' # Wird jetzt in der Klasse als self.PRICE_COLUMN definiert
# SCHWELLE_SAISONALITAET_KAUF = 0.0005 # Wird jetzt in der Klasse als self.schwelle_saisonalitaet_kauf definiert
# SCHWELLE_SAISONALITAET_VERKAUF = -0.0005 # Wird jetzt in der Klasse als self.schwelle_saisonalitaet_verkauf definiert

print("SignalAnalyzer Modul geladen.") # Temporärer Debug-Print
