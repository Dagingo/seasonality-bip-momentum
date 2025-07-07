import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from data_manager import DataManager # Importieren
from signal_analyzer import SignalAnalyzer, set_debug_output_callback as analyzer_set_debug_callback, compare_gdp_momentum
import threading
from matplotlib.figure import Figure # Importieren
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk # Importieren
import pandas as pd # Für leere BIP-Series im Fehlerfall in _run_analyse_prozess
from backtester import Backtester # <--- NEUER IMPORT
import json # For saving/loading presets
import os # For checking file existence

# --- Konfigurationsdateinamen ---
PRESETS_FILE = 'forex_presets.json'
APP_CONFIG_FILE = 'forex_app_config.json'

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

        # Presets Initialisierung
        self.presets = {} # Wird aus Datei geladen
        self.app_config = {} # Für "last_used_preset"


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
        ttk.Label(input_frame, text="Saison. Long-Schwelle (% wöch. Return):").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W) # Geändert zu Long
        self.saison_kauf_var = tk.StringVar(value="0.01") # Standardwert angepasst für wöchentliche Basis
        self.saison_kauf_entry = ttk.Entry(input_frame, textvariable=self.saison_kauf_var, width=18)
        self.saison_kauf_entry.grid(row=3, column=1, padx=5, pady=5, sticky=tk.EW)

        ttk.Label(input_frame, text="Saison. Short-Schwelle (% wöch. Return):").grid(row=4, column=0, padx=5, pady=5, sticky=tk.W) # Geändert zu Short
        self.saison_verkauf_var = tk.StringVar(value="-0.01") # Standardwert angepasst für wöchentliche Basis
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

        # --- Presets Frame ---
        preset_frame = ttk.LabelFrame(input_frame, text="Presets", padding="10")
        preset_frame.grid(row=7, column=0, columnspan=2, padx=5, pady=10, sticky=tk.NSEW)

        ttk.Label(preset_frame, text="Preset wählen:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(preset_frame, textvariable=self.preset_var, state="readonly", width=20)
        self.preset_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        # self.preset_combo.bind("<<ComboboxSelected>>", self._load_selected_preset) # Optional: Aktion bei Auswahl

        self.load_preset_button = ttk.Button(preset_frame, text="Ausgewähltes Preset laden", command=self._load_selected_preset)
        self.load_preset_button.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky=tk.EW)

        ttk.Label(preset_frame, text="Neuer Preset Name:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.new_preset_name_var = tk.StringVar()
        self.new_preset_name_entry = ttk.Entry(preset_frame, textvariable=self.new_preset_name_var, width=23) # Adjusted width
        self.new_preset_name_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.EW)

        self.save_preset_button = ttk.Button(preset_frame, text="Aktuelle Einstellungen als Preset speichern", command=self._save_current_settings_as_preset)
        self.save_preset_button.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky=tk.EW)

        # TODO: Delete Preset Button (optional)
        # self.delete_preset_button = ttk.Button(preset_frame, text="Ausgewähltes Preset löschen", command=self._delete_selected_preset_action)
        # self.delete_preset_button.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky=tk.EW)


        # Analyse-Button (eine Zeile nach unten verschoben wegen Presets)
        self.analyse_button = ttk.Button(input_frame, text="Analyse starten", command=self.start_analyse_thread)
        self.analyse_button.grid(row=8, column=0, columnspan=2, padx=5, pady=5, sticky=tk.EW)

        # Backtest-Button
        self.backtest_button = ttk.Button(input_frame, text="Backtest starten", command=self.start_backtest_thread)
        self.backtest_button.grid(row=9, column=0, columnspan=2, padx=5, pady=5, sticky=tk.EW)

        # Fortschrittsanzeige (ProgressBar)
        self.progress_bar = ttk.Progressbar(input_frame, mode='indeterminate')
        self.progress_bar.grid(row=10, column=0, columnspan=2, padx=5, pady=5, sticky=tk.EW)

        # Status Label
        self.status_var = tk.StringVar(value="Bereit.")
        self.status_label = ttk.Label(input_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=11, column=0, columnspan=2, padx=5, pady=5, sticky=tk.EW)

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

        # Matplotlib Navigation Toolbar hinzufügen
        toolbar_frame = ttk.Frame(plot_frame) # Eigener Frame für Toolbar, um Layout zu steuern
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)
        toolbar = NavigationToolbar2Tk(self.plot_canvas, toolbar_frame)
        toolbar.update() # Wichtig für die Initialanzeige

        self.canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True) # Canvas unter der Toolbar packen
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

        # Setze den Debug-Callback für den SignalAnalyzer einmalig nach Initialisierung der GUI-Komponenten
        analyzer_set_debug_callback(self.log_message)

        # Lade Presets und App-Konfiguration beim Start
        self._load_app_config_file() # Muss vor _load_presets_from_file sein, falls presets leer ist und wir defaults brauchen
        self._load_presets_from_file()
        # self._load_last_used_preset_on_startup() # Wird später implementiert, nachdem GUI-Elemente für Presets da sind
        self._populate_preset_combobox() # Initialisiere Combobox mit geladenen Presets
        self._load_last_used_preset_on_startup() # Versuche, das letzte Preset zu laden

        self.log_message("ForexApp GUI initialisiert und Layout erstellt.")

        # Backtester Instanz
        self.backtester = Backtester(gui_log_callback=self.log_message)


    # --- Preset Kernlogik ---
    def _get_current_settings_as_dict(self):
        """Sammelt aktuelle GUI-Einstellungen in einem Dictionary."""
        return {
            "forex_pair": self.forex_pair_var.get(),
            "start_date": self.start_date_var.get(),
            "end_date": self.end_date_var.get(),
            "saison_kauf": self.saison_kauf_var.get(),
            "saison_verkauf": self.saison_verkauf_var.get(),
            "gdp_long": self.gdp_long_schwelle_var.get(),
            "gdp_short": self.gdp_short_schwelle_var.get()
        }

    def _apply_settings_from_dict(self, settings_dict):
        """Wendet Einstellungen aus einem Dictionary auf die GUI an."""
        self.forex_pair_var.set(settings_dict.get("forex_pair", self.forex_pair_display_names[0] if self.forex_pair_display_names else ""))
        self.start_date_var.set(settings_dict.get("start_date", datetime.today().strftime("%Y-%m-%d")))
        self.end_date_var.set(settings_dict.get("end_date", (datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d")))
        self.saison_kauf_var.set(settings_dict.get("saison_kauf", "0.01"))
        self.saison_verkauf_var.set(settings_dict.get("saison_verkauf", "-0.01"))
        self.gdp_long_schwelle_var.set(settings_dict.get("gdp_long", "30.0"))
        self.gdp_short_schwelle_var.set(settings_dict.get("gdp_short", "-30.0"))
        self.log_message(f"Einstellungen aus Preset '{settings_dict.get('_preset_name_', 'Unbekannt')}' geladen.")


    def _populate_preset_combobox(self):
        """Aktualisiert die Preset-Combobox mit den Namen der geladenen Presets."""
        preset_names = list(self.presets.keys())
        self.preset_combo['values'] = preset_names
        if preset_names:
            current_selection = self.preset_var.get()
            if current_selection in preset_names:
                self.preset_combo.set(current_selection) # Behalte aktuelle Auswahl wenn möglich
            else:
                self.preset_combo.set(preset_names[0]) # Sonst wähle erstes Element
        else:
            self.preset_combo.set('') # Leere Combobox, wenn keine Presets

    def _save_current_settings_as_preset(self):
        """Speichert die aktuellen GUI-Einstellungen als neues Preset."""
        preset_name = self.new_preset_name_var.get()
        if not preset_name:
            messagebox.showerror("Preset Fehler", "Bitte einen Namen für das Preset eingeben.")
            return

        current_settings = self._get_current_settings_as_dict()
        self.presets[preset_name] = current_settings
        self._save_presets_to_file()
        self._populate_preset_combobox() # Combobox aktualisieren
        self.preset_var.set(preset_name) # Das neue Preset auswählen

        # Speichere als "last_used_preset"
        self.app_config['last_used_preset_name'] = preset_name
        self._save_app_config_to_file()

        self.log_message(f"Preset '{preset_name}' erfolgreich gespeichert.")
        self.new_preset_name_var.set("") # Eingabefeld leeren

    def _load_selected_preset(self):
        """Lädt die Einstellungen des in der Combobox ausgewählten Presets."""
        preset_name = self.preset_var.get()
        if not preset_name:
            messagebox.showwarning("Preset Info", "Kein Preset zum Laden ausgewählt.")
            return

        if preset_name in self.presets:
            settings_to_load = self.presets[preset_name].copy() # Kopie machen
            settings_to_load['_preset_name_'] = preset_name # Für Logging in _apply_settings
            self._apply_settings_from_dict(settings_to_load)

            # Speichere als "last_used_preset"
            self.app_config['last_used_preset_name'] = preset_name
            self._save_app_config_to_file()
        else:
            messagebox.showerror("Preset Fehler", f"Preset '{preset_name}' nicht gefunden.")
            self.log_message(f"FEHLER: Preset '{preset_name}' beim Laden nicht gefunden.")

    def _load_last_used_preset_on_startup(self):
        """Lädt das zuletzt verwendete Preset beim Start der Anwendung."""
        last_used_name = self.app_config.get('last_used_preset_name')
        if last_used_name and last_used_name in self.presets:
            self.log_message(f"Lade zuletzt verwendetes Preset: '{last_used_name}'")
            self.preset_var.set(last_used_name) # Setzt Combobox-Auswahl
            self._load_selected_preset() # Lädt die Einstellungen in die GUI
        elif self.presets: # Wenn es Presets gibt, aber kein "last_used" oder ungültig
            first_preset_name = list(self.presets.keys())[0]
            self.preset_var.set(first_preset_name)
            # Optional: auch das erste Preset direkt laden
            # self._load_selected_preset()
            self.log_message(f"Kein 'last_used_preset' gefunden oder ungültig. Erstes verfügbares Preset '{first_preset_name}' ausgewählt.")
        else:
            self.log_message("Keine Presets und kein 'last_used_preset' gefunden.")


    # --- Preset und App Config Datei-Hilfsfunktionen ---
    def _load_presets_from_file(self):
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE, 'r') as f:
                    self.presets = json.load(f)
                self.log_message(f"Presets erfolgreich aus {PRESETS_FILE} geladen.")
            except json.JSONDecodeError:
                self.log_message(f"FEHLER: {PRESETS_FILE} enthält ungültiges JSON. Initialisiere mit leeren Presets.")
                self.presets = {}
            except Exception as e:
                self.log_message(f"FEHLER beim Laden von Presets aus {PRESETS_FILE}: {e}. Initialisiere mit leeren Presets.")
                self.presets = {}
        else:
            self.log_message(f"{PRESETS_FILE} nicht gefunden. Initialisiere mit leeren Presets.")
            self.presets = {}

    def _save_presets_to_file(self):
        try:
            with open(PRESETS_FILE, 'w') as f:
                json.dump(self.presets, f, indent=4)
            self.log_message(f"Presets erfolgreich in {PRESETS_FILE} gespeichert.")
        except Exception as e:
            self.log_message(f"FEHLER beim Speichern von Presets in {PRESETS_FILE}: {e}")

    def _load_app_config_file(self): # Renamed to avoid conflict with future method
        if os.path.exists(APP_CONFIG_FILE):
            try:
                with open(APP_CONFIG_FILE, 'r') as f:
                    self.app_config = json.load(f)
                self.log_message(f"App-Konfiguration erfolgreich aus {APP_CONFIG_FILE} geladen.")
            except json.JSONDecodeError:
                self.log_message(f"FEHLER: {APP_CONFIG_FILE} enthält ungültiges JSON. Initialisiere mit leerer Konfig.")
                self.app_config = {}
            except Exception as e:
                self.log_message(f"FEHLER beim Laden der App-Konfiguration aus {APP_CONFIG_FILE}: {e}. Initialisiere mit leerer Konfig.")
                self.app_config = {}
        else:
            self.log_message(f"{APP_CONFIG_FILE} nicht gefunden. Initialisiere mit leerer Konfig.")
            self.app_config = {}

    def _save_app_config_to_file(self): # Renamed
        try:
            with open(APP_CONFIG_FILE, 'w') as f:
                json.dump(self.app_config, f, indent=4)
            self.log_message(f"App-Konfiguration erfolgreich in {APP_CONFIG_FILE} gespeichert.")
        except Exception as e:
            self.log_message(f"FEHLER beim Speichern der App-Konfiguration in {APP_CONFIG_FILE}: {e}")

    # --- Ende Preset und App Config Datei-Hilfsfunktionen ---

    def log_message(self, message):
        """Schreibt eine Nachricht in das Debug-Textfeld und die Konsole."""
        # Print to console as well for reliable full log
        print(f"[GUI DEBUG] {message}")

        if self.debug_text:
            self.debug_text.config(state=tk.NORMAL)
            self.debug_text.insert(tk.END, message + "\n")
            self.debug_text.see(tk.END) # Auto-Scroll
            self.debug_text.config(state=tk.DISABLED)

        # Setze den Debug-Callback für den SignalAnalyzer
        # This should only be done once, perhaps in __init__ after debug_text is created.
        # analyzer_set_debug_callback(self.log_message) # Moved to __init__


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
                    self.gdp_momentum_signal_aligned_to_forex.bfill(inplace=True) # Fülle auch am Anfang, falls GDP-Daten später starten (Modern pandas)
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
            # Wende Cooldown-Periode auf die finalen Signale an
            self.final_signals_series = self.signal_analyzer.apply_signal_cooldown(self.final_signals_series, cooldown_days=5)
            self.log_message("Signal-Cooldown von 5 Tagen angewendet.")


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

        # Detailed check for data availability
        plot_data_valid = True
        conditions_to_check = {
            "self.signal_analyzer object": self.signal_analyzer is not None, # Check instance exists
            "self.forex_data_df": self.forex_data_df is not None and not self.forex_data_df.empty,
            "self.saisonalitaet_series": self.saisonalitaet_series is not None and not self.saisonalitaet_series.empty,
            "self.gdp_momentum_outputs": self.gdp_momentum_outputs is not None,
            "self.final_signals_series": self.final_signals_series is not None and not self.final_signals_series.empty
        }

        for name, condition_met in conditions_to_check.items():
            if not condition_met:
                self.log_message(f"Plot Update Check: Condition '{name}' is FALSE.")
                plot_data_valid = False

        if self.gdp_momentum_outputs is not None: # Further check components if gdp_momentum_outputs itself is fine
            gdp_mom_a, gdp_mom_b, gdp_mom_diff, gdp_signal_raw = self.gdp_momentum_outputs
            if gdp_mom_diff is None:
                 self.log_message("Plot Update Check: gdp_momentum_outputs[2] (gdp_mom_diff) is None.")
                 # This could be a reason plot_analyse_results does not plot GDP section,
                 # but it shouldn't make plot_data_valid False for the whole plot if other series are fine.
            elif hasattr(gdp_mom_diff, 'empty') and gdp_mom_diff.empty: # Check if it's a Series and empty
                 self.log_message("Plot Update Check: gdp_momentum_outputs[2] (gdp_mom_diff) is an empty Series.")
        else: # This case is already covered by the conditions_to_check if self.gdp_momentum_outputs is None
            pass


        if plot_data_valid:
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
        ax.text(0.5, 0.5, "Bitte Analyse oder Backtest starten, um den Chart anzuzeigen.", # Angepasster Text
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=12, color='grey')
        self.plot_canvas.draw()

    # --- Backtesting Methoden ---
    def start_backtest_thread(self):
        """Startet den Backtest-Prozess in einem separaten Thread."""
        self.log_message("Starte Backtest-Thread...")
        self.status_var.set("Backtesting...")
        self._set_input_widgets_state(tk.DISABLED)
        self.progress_bar.start()

        try:
            selected_pair_config = self.get_selected_forex_pair_config()
            if not selected_pair_config:
                messagebox.showerror("Fehler", "Bitte ein gültiges Forex-Paar auswählen.")
                self._analysis_done("Fehler: Kein Forex-Paar.") # Nutzt _analysis_done zum Zurücksetzen
                return

            start_date_str = self.start_date_var.get()
            end_date_str = self.end_date_var.get()
            datetime.strptime(start_date_str, "%Y-%m-%d") # Validierung
            datetime.strptime(end_date_str, "%Y-%m-%d") # Validierung

            saison_kauf_schwelle = float(self.saison_kauf_var.get()) / 100.0
            saison_verkauf_schwelle = float(self.saison_verkauf_var.get()) / 100.0
            gdp_long_schwelle = float(self.gdp_long_schwelle_var.get())
            gdp_short_schwelle = float(self.gdp_short_schwelle_var.get())

            analyzer_config = {
                'SCHWELLE_SAISONALITAET_KAUF': saison_kauf_schwelle,
                'SCHWELLE_SAISONALITAET_VERKAUF': saison_verkauf_schwelle
            }

            # Parameter für Backtester.run_backtest
            backtest_params = {
                "forex_pair_config": selected_pair_config,
                "start_date_str": start_date_str,
                "end_date_str": end_date_str,
                "analyzer_config_dict": analyzer_config,
                "gdp_long_threshold": gdp_long_schwelle,
                "gdp_short_threshold": gdp_short_schwelle,
                "initial_cash": 10000, # Standardwert, könnte konfigurierbar gemacht werden
                "benchmark_ticker": "^SPX", # Standardwert, könnte konfigurierbar gemacht werden
                "trade_amount_percent": 0.10 # Standardwert, könnte konfigurierbar gemacht werden
            }

        except ValueError as ve:
            messagebox.showerror("Eingabefehler", f"Ungültige Eingabe für Backtest: {ve}")
            self._analysis_done("Fehler: Ungültige Eingabe.")
            return

        backtest_thread = threading.Thread(target=self._run_backtest_prozess,
                                           args=(backtest_params,),
                                           daemon=True)
        backtest_thread.start()

    def _run_backtest_prozess(self, backtest_params):
        """Führt den eigentlichen Backtest im Thread durch."""
        try:
            self.log_message("Backtest-Prozess gestartet im Thread.")
            strategy_history, benchmark_history = self.backtester.run_backtest(**backtest_params)

            if strategy_history is not None and benchmark_history is not None:
                self.log_message("Backtest erfolgreich abgeschlossen.")
                # GUI-Update im Hauptthread planen
                self.root.after(0, self.display_backtest_results, strategy_history, benchmark_history)
                self.root.after(0, self._analysis_done, "Backtest erfolgreich.")
            else:
                self.log_message("Backtest fehlgeschlagen oder keine Daten zurückgegeben.")
                self.root.after(0, self._analysis_done, "Backtest fehlgeschlagen.")

        except Exception as e:
            self.log_message(f"Fehler während des Backtests: {e}")
            import traceback
            self.log_message(traceback.format_exc())
            self.root.after(0, self._analysis_done, f"Backtest fehlgeschlagen: {e}")

    def display_backtest_results(self, strategy_df, benchmark_df):
        """Zeigt die Backtest-Ergebnisse (Portfolio-Wertentwicklung) im Plot an."""
        self.log_message("Anzeige der Backtest-Ergebnisse...")
        self.plot_figure.clear()
        ax = self.plot_figure.add_subplot(111)

        if strategy_df.empty:
            self.log_message("Keine Daten für Strategie-Portfolio vorhanden.")
            ax.text(0.5, 0.6, "Keine Daten für Strategie-Portfolio.", ha='center', va='center', transform=ax.transAxes)
        else:
            ax.plot(strategy_df['date'], strategy_df['value'], label="Strategie Portfolio", color="blue")

        if benchmark_df.empty:
            self.log_message("Keine Daten für Benchmark-Portfolio vorhanden.")
            # Optional: Nachricht im Plot, falls nur Benchmark fehlt
            if strategy_df.empty: # Nur wenn beide leer sind, größere Nachricht
                 ax.text(0.5, 0.4, "Keine Daten für Benchmark-Portfolio.", ha='center', va='center', transform=ax.transAxes)
        else:
            ax.plot(benchmark_df['date'], benchmark_df['value'], label="Benchmark Portfolio (SPX)", color="orange")

        ax.set_title("Portfolio Wertentwicklung (Backtest)")
        ax.set_xlabel("Datum")
        ax.set_ylabel("Portfolio Wert")
        ax.legend(loc="best")
        ax.grid(True)

        # Formatierung der Datumsachse für bessere Lesbarkeit
        import matplotlib.dates as mdates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        self.plot_figure.autofmt_xdate() # Verbessert das Layout der Datumslabels

        self.plot_canvas.draw()
        self.log_message("Backtest-Ergebnisse im Chart angezeigt.")


if __name__ == "__main__":
    root = tk.Tk()
    app = ForexApp(root)
    root.mainloop()
