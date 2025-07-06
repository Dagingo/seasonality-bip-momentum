import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from data_manager import DataManager # Importieren
from signal_analyzer import SignalAnalyzer, set_debug_output_callback as analyzer_set_debug_callback, compare_gdp_momentum
import threading
from matplotlib.figure import Figure # Importieren
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg # Importieren
import pandas as pd # Für leere BIP-Series im Fehlerfall in _run_analyse_prozess

# --- Globale Konfiguration für Forex-Paare ---
FOREX_PAIRS_CONFIG = [
    {"display": "EUR/USD", "pair_code": "EURUSD", "country1": "Eurozone", "country2": "USA", "base_curr": "EUR", "quote_curr": "USD"},
    {"display": "GBP/JPY", "pair_code": "GBPJPY", "country1": "UK", "country2": "Japan", "base_curr": "GBP", "quote_curr": "JPY"},
    {"display": "USD/CHF", "pair_code": "USDCHF", "country1": "USA", "country2": "Switzerland", "base_curr": "USD", "quote_curr": "CHF"},
    {"display": "AUD/CAD", "pair_code": "AUDCAD", "country1": "Australia", "country2": "Canada", "base_curr": "AUD", "quote_curr": "CAD"}
]
FOREX_PAIR_DISPLAY_NAMES = [p["display"] for p in FOREX_PAIRS_CONFIG]


class ForexApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Forex Signal Generator GUI")
        self.root.minsize(800, 600)
        self.root.geometry("1200x800")

        # DataManager und SignalAnalyzer Instanzen (werden bei Bedarf erstellt)
        self.data_manager = DataManager()
        self.signal_analyzer = None # Wird mit aktuellen Schwellenwerten bei Analyse neu erstellt

        # Analyseergebnisse speichern
        self.forex_data_df = None
        self.bip_data_df = None
        self.saisonalitaet_series = None
        self.bip_aligned_signal_series = None
        self.final_signals_series = None
        self.bip_plot_col_country1 = None # Für die Legende im Plot
        self.bip_plot_col_country2 = None
        self.current_gdp_long_thresh = 30.0 # Standardwert, wird von Analyse überschrieben
        self.current_gdp_short_thresh = -30.0 # Standardwert, wird von Analyse überschrieben


        # Zugriff auf globale Konfiguration
        self.forex_pairs_config = FOREX_PAIRS_CONFIG
        self.forex_pair_display_names = FOREX_PAIR_DISPLAY_NAMES


        # --- Hauptframe erstellen ---
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Eingabeframe ---
        input_frame = ttk.LabelFrame(main_frame, text="Einstellungen", padding="10")
        input_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # Forex-Paar Auswahl
        ttk.Label(input_frame, text="Forex-Paar:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.forex_pair_var = tk.StringVar()
        self.forex_pair_combo = ttk.Combobox(input_frame, textvariable=self.forex_pair_var,
                                             values=self.forex_pair_display_names, state="readonly", width=15)
        self.forex_pair_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        if self.forex_pair_display_names:
            self.forex_pair_combo.current(0) # Standardauswahl

        # Zeitraum Auswahl
        ttk.Label(input_frame, text="Startdatum (JJJJ-MM-TT):").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.start_date_var = tk.StringVar()
        self.start_date_entry = ttk.Entry(input_frame, textvariable=self.start_date_var, width=18)
        self.start_date_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)

        ttk.Label(input_frame, text="Enddatum (JJJJ-MM-TT):").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.end_date_var = tk.StringVar()
        self.end_date_entry = ttk.Entry(input_frame, textvariable=self.end_date_var, width=18)
        self.end_date_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.EW)

        # Standardwerte für Datum (letztes Jahr bis heute)
        end_date_default = datetime.today()
        start_date_default = end_date_default - timedelta(days=365)
        self.start_date_var.set(start_date_default.strftime("%Y-%m-%d"))
        self.end_date_var.set(end_date_default.strftime("%Y-%m-%d"))

        # Indikator-Grenzwerte
        ttk.Label(input_frame, text="Saisonalität Kauf-Schwelle (% mtl. Return):").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        self.saison_kauf_var = tk.StringVar(value="0.05") # Standardwert als String
        self.saison_kauf_entry = ttk.Entry(input_frame, textvariable=self.saison_kauf_var, width=18)
        self.saison_kauf_entry.grid(row=3, column=1, padx=5, pady=5, sticky=tk.EW)

        ttk.Label(input_frame, text="Saisonalität Verkauf-Schwelle (% mtl. Return):").grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
        self.saison_verkauf_var = tk.StringVar(value="-0.05") # Standardwert als String
        self.saison_verkauf_entry = ttk.Entry(input_frame, textvariable=self.saison_verkauf_var, width=18)
        self.saison_verkauf_entry.grid(row=4, column=1, padx=5, pady=5, sticky=tk.EW)

        # Neue GDP Momentum Differenz Schwellenwerte
        ttk.Label(input_frame, text="Long-Schwelle (GDP Diff):").grid(row=5, column=0, padx=5, pady=5, sticky=tk.W)
        self.gdp_long_schwelle_var = tk.StringVar(value="30.0") # Standardwert
        self.gdp_long_schwelle_entry = ttk.Entry(input_frame, textvariable=self.gdp_long_schwelle_var, width=18)
        self.gdp_long_schwelle_entry.grid(row=5, column=1, padx=5, pady=5, sticky=tk.EW)

        ttk.Label(input_frame, text="Short-Schwelle (GDP Diff):").grid(row=6, column=0, padx=5, pady=5, sticky=tk.W)
        self.gdp_short_schwelle_var = tk.StringVar(value="-30.0") # Standardwert
        self.gdp_short_schwelle_entry = ttk.Entry(input_frame, textvariable=self.gdp_short_schwelle_var, width=18)
        self.gdp_short_schwelle_entry.grid(row=6, column=1, padx=5, pady=5, sticky=tk.EW)

        # Analyse-Button
        self.analyse_button = ttk.Button(input_frame, text="Analyse starten", command=self.start_analyse_thread)
        self.analyse_button.grid(row=7, column=0, columnspan=2, padx=5, pady=10, sticky=tk.EW) # Row index bleibt gleich da alte Felder ersetzt wurden

        # Fortschrittsanzeige (ProgressBar)
        self.progress_bar = ttk.Progressbar(input_frame, mode='indeterminate')
        self.progress_bar.grid(row=8, column=0, columnspan=2, padx=5, pady=5, sticky=tk.EW) # Row index bleibt gleich

        # Status Label
        self.status_var = tk.StringVar(value="Bereit.")
        self.status_label = ttk.Label(input_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=9, column=0, columnspan=2, padx=5, pady=5, sticky=tk.EW) # Row index bleibt gleich

        # --- Frame für Plot und Debug-Konsole (rechts neben Eingabe) ---
        output_frame = ttk.Frame(main_frame)
        output_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Platzhalter für Plot-Bereich
        plot_frame = ttk.LabelFrame(output_frame, text="Analyse-Chart", padding="5")
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Matplotlib Figure und Canvas erstellen
        self.plot_figure = Figure(figsize=(8, 6), dpi=150) # Erhöhte DPI für höhere Auflösung
        self.plot_canvas = FigureCanvasTkAgg(self.plot_figure, master=plot_frame)
        self.canvas_widget = self.plot_canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)
        # Initial leeren Plot zeichnen oder eine Nachricht anzeigen
        self._clear_plot()


        # Platzhalter für Debug-Konsole
        debug_frame = ttk.LabelFrame(output_frame, text="Debug-Konsole", padding="5")
        debug_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5) # Erlaubt Expansion
        self.debug_text = tk.Text(debug_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        debug_scrollbar = ttk.Scrollbar(debug_frame, orient=tk.VERTICAL, command=self.debug_text.yview)
        self.debug_text.configure(yscrollcommand=debug_scrollbar.set)
        debug_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.debug_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.log_message("ForexApp GUI initialisiert und Layout erstellt.")

    def log_message(self, message):
        """Schreibt eine Nachricht in das Debug-Textfeld."""
        if self.debug_text:
            self.debug_text.config(state=tk.NORMAL)
            self.debug_text.insert(tk.END, message + "\n")
            self.debug_text.see(tk.END) # Auto-Scroll
            self.debug_text.config(state=tk.DISABLED)

        # Setze den Debug-Callback für den SignalAnalyzer
        analyzer_set_debug_callback(self.log_message)


    def get_selected_forex_pair_config(self):
        """Gibt die Konfiguration des ausgewählten Forex-Paares zurück."""
        selected_display_name = self.forex_pair_var.get()
        for config in self.forex_pairs_config:
            if config["display"] == selected_display_name:
                return config
        return None

    def start_analyse_thread(self):
        """Startet den Analyseprozess in einem separaten Thread."""
        self.log_message("Starte Analyse-Thread...")
        self.status_var.set("Analysiere...")
        self._set_input_widgets_state(tk.DISABLED) # Alle Eingabefelder deaktivieren
        self.progress_bar.start()

        # Eingaben validieren und sammeln
        try:
            selected_pair_config = self.get_selected_forex_pair_config()
            if not selected_pair_config:
                messagebox.showerror("Fehler", "Bitte ein gültiges Forex-Paar auswählen.")
                self._analysis_done() # GUI zurücksetzen
                return

            forex_pair_code = selected_pair_config["pair_code"]
            country1 = selected_pair_config["country1"]
            country2 = selected_pair_config["country2"]
            base_curr = selected_pair_config["base_curr"]
            quote_curr = selected_pair_config["quote_curr"]

            start_date_str = self.start_date_var.get()
            end_date_str = self.end_date_var.get()
            # Einfache Datumsvalidierung (Format)
            datetime.strptime(start_date_str, "%Y-%m-%d")
            datetime.strptime(end_date_str, "%Y-%m-%d")

            saison_kauf_schwelle = float(self.saison_kauf_var.get()) / 100.0 # Umrechnung von % in Dezimal
            saison_verkauf_schwelle = float(self.saison_verkauf_var.get()) / 100.0 # Umrechnung von % in Dezimal
            # Lese neue GDP Differenz Schwellenwerte
            gdp_long_schwelle = float(self.gdp_long_schwelle_var.get())
            gdp_short_schwelle = float(self.gdp_short_schwelle_var.get())


            analyzer_config = { # Nur noch Saisonalitätsschwellen für den Analyzer-Konstruktor
                'SCHWELLE_SAISONALITAET_KAUF': saison_kauf_schwelle,
                'SCHWELLE_SAISONALITAET_VERKAUF': saison_verkauf_schwelle
                # Die GDP-Schwellenwerte werden direkt an compare_gdp_momentum übergeben
            }

        except ValueError as ve:
            messagebox.showerror("Eingabefehler", f"Ungültige Eingabe: {ve}\nBitte Datum im Format JJJJ-MM-TT und Zahlen für Schwellenwerte verwenden.")
            self._analysis_done()
            return

        # Starte den Analyse-Prozess in einem neuen Thread
        # Das Target `_run_analyse_prozess` muss die gesammelten Parameter erhalten
        # Füge gdp_long_schwelle und gdp_short_schwelle zu den args hinzu
        analyse_thread = threading.Thread(target=self._run_analyse_prozess,
                                          args=(forex_pair_code, country1, country2, base_curr, quote_curr,
                                                start_date_str, end_date_str, analyzer_config,
                                                gdp_long_schwelle, gdp_short_schwelle), # Neue Argumente
                                          daemon=True) # Daemon, damit Thread mit Hauptprogramm schließt
        analyse_thread.start()

    def _run_analyse_prozess(self, forex_pair_code, country1, country2, base_curr, quote_curr,
                             start_date, end_date, analyzer_config_dict,
                             gdp_long_threshold, gdp_short_threshold): # Neue Parameter hier
        """Führt den eigentlichen Datenabruf und die Analyse durch (läuft im Thread)."""
        try:
            # Speichere die aktuellen GDP-Schwellenwerte für den Plot-Aufruf
            self.current_gdp_long_thresh = gdp_long_threshold
            self.current_gdp_short_thresh = gdp_short_threshold

            self.log_message(f"Datenabruf für {forex_pair_code} ({start_date} bis {end_date}).")
            self.forex_data_df = self.data_manager.get_forex_data(forex_pair_code, start_date, end_date)

            if self.forex_data_df is None or self.forex_data_df.empty:
                self.log_message(f"Keine Forex-Daten für {forex_pair_code} erhalten. Analyse abgebrochen.")
                self.root.after(0, self._analysis_done, "Fehler: Keine Forex-Daten.")
                return

            self.log_message(f"Datenabruf für BIP-Daten ({country1}, {country2}).")
            # Beachte: get_bip_data erwartet Ländernamen, nicht Währungscodes
            bip_data_tuple = self.data_manager.get_bip_data(country1, country2)
            self.bip_data_df = bip_data_tuple[0]
            self.bip_plot_col_country1 = bip_data_tuple[1] # Speichere die tatsächlichen Spaltennamen für den Plot
            self.bip_plot_col_country2 = bip_data_tuple[2]

            # Store all GDP momentum outputs for plotting
            self.gdp_momentum_outputs = None # (mom_a, mom_b, diff, signal_series_raw)
            self.gdp_momentum_signal_aligned_to_forex = pd.Series(index=self.forex_data_df.index, data=0, name="GDP_Momentum_Signal_Aligned")


            if self.bip_data_df is None or self.bip_data_df.empty or not self.bip_plot_col_country1 or not self.bip_plot_col_country2:
                self.log_message(f"Keine validen BIP-Daten oder Spaltennamen für {country1}/{country2} erhalten. GDP-Momentum-Analyse wird übersprungen.")
            else:
                self.log_message(f"Berechne GDP Momentum Vergleich für {self.bip_plot_col_country1} und {self.bip_plot_col_country2}...")
                gdp_series_a = self.bip_data_df[self.bip_plot_col_country1]
                gdp_series_b = self.bip_data_df[self.bip_plot_col_country2]

                # N_PERIODS_GROWTH: Annahme ist 4 für YoY bei Quartalsdaten. Dies könnte man auch konfigurierbar machen.
                # Fürs Erste hardcoded als 4.
                n_periods_for_gdp_growth = 4

                # Wichtig: signal_analyzer Modul importieren, falls noch nicht geschehen (ist es aber global) -> compare_gdp_momentum wurde direkt importiert
                # Die Funktion compare_gdp_momentum ist jetzt im signal_analyzer Modul
                gdp_mom_a, gdp_mom_b, gdp_mom_diff, gdp_signal_raw = compare_gdp_momentum( # Aufruf ohne Modul-Präfix
                    gdp_series_a=gdp_series_a,
                    gdp_series_b=gdp_series_b,
                    n_periods_growth=n_periods_for_gdp_growth, # z.B. 4 für YoY bei Quartalsdaten
                    long_threshold=gdp_long_threshold,
                    short_threshold=gdp_short_threshold
                    # debug_callback=self.log_message # Entfernt
                )
                self.gdp_momentum_outputs = (gdp_mom_a, gdp_mom_b, gdp_mom_diff, gdp_signal_raw)

                if gdp_signal_raw is not None and not gdp_signal_raw.empty:
                    self.log_message("GDP Momentum Rohsignale erhalten.")
                    # self.log_message(f"Momentum A (skaliert):\n{gdp_mom_a.tail().to_string()}")
                    # self.log_message(f"Momentum B (skaliert):\n{gdp_mom_b.tail().to_string()}")
                    # self.log_message(f"Momentum Differenz:\n{gdp_mom_diff.tail().to_string()}")
                    # self.log_message(f"GDP Signale (roh):\n{gdp_signal_raw[gdp_signal_raw.notna()].to_string()}")

                    # Reindex GDP signal to Forex data frequency
                    self.gdp_momentum_signal_aligned_to_forex = gdp_signal_raw.reindex(self.forex_data_df.index, method='ffill')
                    self.gdp_momentum_signal_aligned_to_forex.fillna(method='bfill', inplace=True) # Fülle auch am Anfang, falls GDP-Daten später starten
                    self.gdp_momentum_signal_aligned_to_forex.fillna(0, inplace=True) # Falls immer noch NaNs, mit 0 füllen (neutral)
                                                                                        # Wichtig: Konvertiere 'long'/'short' zu 0, falls sie nicht durch ffill/bfill ersetzt wurden.
                                                                                        # Die Umwandlung in numerisch (1, -1, 0) passiert in generiere_signale.
                    self.gdp_momentum_signal_aligned_to_forex.name = "GDP_Momentum_Signal_Aligned"
                    self.log_message("GDP Momentum Signale an Forex-Daten Frequenz angeglichen.")
                else:
                    self.log_message("Keine GDP Momentum Rohsignale von compare_gdp_momentum erhalten oder Signale sind leer. Verwende neutrales Signal (0).")

            # Initialisiere SignalAnalyzer (hat jetzt keine BIP-spezifischen Schwellen mehr in config)
            self.signal_analyzer = SignalAnalyzer(config=analyzer_config_dict) # analyzer_config_dict enthält nur Saisonalität
            self.saisonalitaet_series = self.signal_analyzer.berechne_saisonalitaet(self.forex_data_df)

            # Generiere finale Signale mit dem neuen gdp_momentum_signal_aligned_to_forex
            self.final_signals_series = self.signal_analyzer.generiere_signale(
                forex_daten_idx=self.forex_data_df.index,
                saisonalitaet_raw=self.saisonalitaet_series,
                gdp_momentum_signal_aligned=self.gdp_momentum_signal_aligned_to_forex # Hier das neue Signal übergeben
            )

            self.log_message("Analyse abgeschlossen.")
            # GUI-Update im Hauptthread planen (für Plot etc.)
            self.root.after(0, self._analysis_done, "Analyse erfolgreich abgeschlossen.")
            self.root.after(0, self.update_plot) # update_plot muss angepasst werden, um gdp_momentum_outputs zu verwenden


        except Exception as e:
            self.log_message(f"Fehler während der Analyse: {e}")
            import traceback
            self.log_message(traceback.format_exc()) # Detaillierter Traceback in die GUI-Konsole
            self.root.after(0, self._analysis_done, f"Analyse fehlgeschlagen: {e}")


    def _analysis_done(self, status_message="Bereit."):
        """Setzt die GUI nach Abschluss der Analyse zurück."""
        self.progress_bar.stop()
        self._set_input_widgets_state(tk.NORMAL) # Alle Eingabefelder wieder aktivieren
        self.status_var.set(status_message)

    def _set_input_widgets_state(self, state):
        """Aktiviert oder deaktiviert alle Eingabe-Widgets."""
        widgets_to_toggle = [
            self.forex_pair_combo,
            self.start_date_entry,
            self.end_date_entry,
            self.saison_kauf_entry,
            self.saison_verkauf_entry,
            self.gdp_long_schwelle_entry, # Neu
            self.gdp_short_schwelle_entry, # Neu
            self.analyse_button
        ]
        for widget in widgets_to_toggle:
            if widget: # Sicherstellen, dass das Widget existiert
                widget.config(state=state)

    def update_plot(self):
        """Aktualisiert den Matplotlib-Chart in der GUI mit den Analyseergebnissen."""
        self.log_message("Aktualisiere Plot mit Analyseergebnissen...")

        if self.signal_analyzer and self.forex_data_df is not None and \
           self.saisonalitaet_series is not None and \
           self.bip_aligned_signal_series is not None and \
           self.final_signals_series is not None:

            try:
                # Stelle sicher, dass die Figur vor dem Neuzeichnen geleert wird durch plot_analyse_results
                self.signal_analyzer.plot_analyse_results(
                    fig=self.plot_figure,
                    forex_daten=self.forex_data_df,
                    saisonalitaet_values=self.saisonalitaet_series,
                    bip_roh_daten=self.bip_data_df,
                    gdp_momentum_outputs=self.gdp_momentum_outputs, # Übergebe das Tupel
                    final_signale=self.final_signals_series,
                    bip_col_country1=self.bip_plot_col_country1,
                    bip_col_country2=self.bip_plot_col_country2,
                    gdp_diff_long_thresh=self.current_gdp_long_thresh, # Verwende gespeicherte Werte
                    gdp_diff_short_thresh=self.current_gdp_short_thresh # Verwende gespeicherte Werte
                )
                self.plot_canvas.draw()
                self.log_message("Plot erfolgreich aktualisiert.")
            except Exception as e:
                self.log_message(f"Fehler beim Aktualisieren des Plots: {e}")
                import traceback
                self.log_message(traceback.format_exc())
                # Zeige Fehlermeldung im Plotbereich
                self.plot_figure.clear()
                ax = self.plot_figure.add_subplot(111)
                ax.text(0.5, 0.5, f"Fehler beim Plotten:\n{e}",
                        horizontalalignment='center', verticalalignment='center',
                        transform=ax.transAxes, color='red', wrap=True)
                self.plot_canvas.draw()
        else:
            self.log_message("Keine ausreichenden Daten für Plot-Aktualisierung vorhanden.")
            self._clear_plot() # Zeige die Standardnachricht, wenn keine Daten da sind

    def _clear_plot(self):
        """Löscht die aktuelle Figur und zeigt eine Startnachricht."""
        self.plot_figure.clear()
        ax = self.plot_figure.add_subplot(111)
        ax.text(0.5, 0.5, "Bitte Analyse starten, um den Chart anzuzeigen.",
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=12, color='grey')
        self.plot_canvas.draw()


if __name__ == "__main__":
    root = tk.Tk()
    app = ForexApp(root)
    root.mainloop()
