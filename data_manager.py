import pandas as pd
import yfinance as yf
from datetime import datetime, date # Added date for DataReader
import pandas_datareader.data as pdr_web # For fetching live GDP data

# Pfade zu den BIP-Daten CSV-Dateien
BIP_DATA_LIVE_CSV = 'bip_data_live.csv'
BIP_DATA_FALLBACK_CSV = 'bip_data.csv' # Die bereits existierende Datei für den Fallback
PROVISIONAL_GDP_DATA_PATH = 'data/gdp_provisional/' # <--- NEUE Konstante

# Importiere debug_print (oder verwende einen lokalen Stub)
# Dies setzt voraus, dass die ForexApp den Callback für signal_analyzer.debug_print setzt,
# und dieser dann global für DataManager-Aufrufe aus dem Analyseprozess verfügbar ist.
# Eine robustere Lösung wäre, dem DataManager auch einen Logger zu übergeben.
try:
    from signal_analyzer import debug_print
except ImportError:
    print("WARNUNG: signal_analyzer.debug_print nicht gefunden, nutze Standard-Print für DataManager-Logs.")
    def debug_print(message, data=None): # Lokaler Fallback-Logger
        log_message = f"[DM STUB DEBUG] {message}"
        if data is not None and isinstance(data, pd.DataFrame):
            log_message += f"\n{data.head().to_string()}\n--------------------"
        elif data is not None:
            log_message += f"\n{str(data)}\n--------------------"
        print(log_message)


class DataManager:
    def __init__(self):
        # Importiere os hier, um sicherzustellen, dass es im Kontext der Klasse verfügbar ist,
        # falls die globale Importierung oben nicht ausreicht oder für Klarheit.
        import os
        self.os_path_exists = os.path.exists # Für einfacheren Zugriff in Methoden

        # Zuordnung von Währungscodes zu "Ländernamen" (oder Regionen), wie sie in BIP-Daten verwendet werden könnten
        self.bip_country_mapping = {
            "EUR": "Eurozone",    # Euro
            "USD": "USA",           # US Dollar
            "GBP": "UK",            # British Pound
            "JPY": "Japan",         # Japanese Yen
            "CHF": "Switzerland",   # Swiss Franc
            "AUD": "Australia",     # Australian Dollar
            "CAD": "Canada",        # Canadian Dollar
            "BRL": "Brazil",        # Brazilian Real
            "CNY": "China",         # Chinese Yuan Renminbi
            "INR": "India",         # Indian Rupee
            "IDR": "Indonesia",     # Indonesian Rupiah
            "MXN": "Mexico",        # Mexican Peso
            "RUB": "Russia",        # Russian Ruble
            "SAR": "Saudi Arabia",  # Saudi Riyal
            "ZAR": "South Africa",  # South African Rand
            "KRW": "South Korea",   # South Korean Won
            "TRY": "Turkey",        # Turkish Lira
            # ARS (Argentine Peso) ausgelassen
        }
        # Erwartete Spaltennamen in der `bip_data_live.csv` Datei oder für provisorische CSVs
        self.bip_csv_column_names = {
            "Eurozone": "BIP_EUR",
            "USA": "BIP_USD",
            "UK": "BIP_GBP",
            "Japan": "BIP_JPY",
            "Switzerland": "BIP_CHF",
            "Australia": "BIP_AUD",
            "Canada": "BIP_CAD",
            "Brazil": "BIP_BRL",
            "China": "BIP_CNY",
            "India": "BIP_INR",
            "Indonesia": "BIP_IDR",
            "Mexico": "BIP_MXN",
            "Russia": "BIP_RUB",
            "Saudi Arabia": "BIP_SAR", # Wird provisorisch sein
            "South Africa": "BIP_ZAR",
            "South Korea": "BIP_KRW",
            "Turkey": "BIP_TRY",
            # "Argentina": "BIP_ARS", # Falls wir es doch hinzufügen
        }
        # Spaltennamen in der alten `bip_data.csv` (Fallback)
        self.fallback_bip_col_land_a = "BIP_Land_A" # Bleibt für Kompatibilität mit alter CSV
        self.fallback_bip_col_land_b = "BIP_Land_B"

        # Mapping for live GDP data fetching
        self.gdp_api_map = {
            "USA": {"source": "fred", "id": "GDPC1", "name": "Real Gross Domestic Product USA"},
            "Japan": {"source": "fred", "id": "JPNRGDPEXP", "name": "Real Gross Domestic Product Japan"},
            "Eurozone": {"source": "fred", "id": "CPMNACSCAB1GQEZ19", "name": "Real Gross Domestic Product Euro Area"},
            "UK": {"source": "fred", "id": "GBRRGDPR", "name": "Real Gross Domestic Product UK"}, # Chained Volume Measures, SA
            "Australia": {"source": "fred", "id": "AUSGDPRQDSMEI", "name": "Real Gross Domestic Product Australia"},
            "Canada": {"source": "fred", "id": "CNGDPRPCMQ", "name": "Real Gross Domestic Product Canada"}, # Chained 2012 Dollars, SA
            "Brazil": {"source": "fred", "id": "BRAGDPNQDSMEI", "name": "Real Gross Domestic Product Brazil"},
            "China": {"source": "fred", "id": "CNAGDPNQDSMEI", "name": "Real Gross Domestic Product China"},
            "India": {"source": "fred", "id": "INAGDPNQDSMEI", "name": "Real Gross Domestic Product India"},
            "Indonesia": {"source": "fred", "id": "IDNGDPNQDSMEI", "name": "Real Gross Domestic Product Indonesia"},
            "Mexico": {"source": "fred", "id": "MEXRGDPQDSNAQ", "name": "Real Gross Domestic Product Mexico"},
            "Russia": {"source": "fred", "id": "RUSGDPNQDSMEI", "name": "Real Gross Domestic Product Russia"},
            "South Africa": {"source": "fred", "id": "ZAFGDPNQDSMEI", "name": "Real Gross Domestic Product South Africa"},
            "South Korea": {"source": "fred", "id": "KORRGDPQDSNAQ", "name": "Real Gross Domestic Product South Korea"},
            "Turkey": {"source": "fred", "id": "TURGDPNQDSMEI", "name": "Real Gross Domestic Product Turkey"},
            "Switzerland": {"source": "fred", "id": "CHERGDPQDSNAQ", "name": "Real Gross Domestic Product Switzerland"},
            # Länder, die wahrscheinlich provisorische Daten benötigen (und hier nicht explizit in gdp_api_map sind):
            # z.B. Argentinien, Saudi-Arabien
        }
        self.oecd_base_url = "https://stats.oecd.org/SDMX-JSON/data"


        debug_print("[DataManager] DataManager initialisiert.") # Geändert zu debug_print

    def _load_provisional_gdp_csv(self, country_name_internal, target_col_name):
        """
        Versucht, eine provisorische BIP-CSV-Datei für ein bestimmtes Land zu laden.
        country_name_internal: Der interne Name des Landes (z.B. "Saudi Arabia", "Argentina")
        target_col_name: Der erwartete Spaltenname im resultierenden DataFrame (z.B. "BIP_SAR")
        """
        filename_country_part = country_name_internal.lower().replace(" ", "_")
        provisional_csv_path = f"{PROVISIONAL_GDP_DATA_PATH}bip_data_{filename_country_part}.csv"

        debug_print(f"[DataManager] Suche provisorische BIP-Daten für '{country_name_internal}' unter: {provisional_csv_path}")

        try:
            if not self.os_path_exists(provisional_csv_path): # self.os_path_exists verwenden
                debug_print(f"[DataManager] Provisorische BIP-Datei nicht gefunden: {provisional_csv_path}")
                return None

            daten = pd.read_csv(provisional_csv_path, parse_dates=['Datum'])
            daten.set_index('Datum', inplace=True)

            if target_col_name not in daten.columns:
                debug_print(f"[DataManager] FEHLER: Erforderliche Spalte '{target_col_name}' nicht in provisorischer CSV {provisional_csv_path} gefunden. Verfügbare Spalten: {daten.columns.tolist()}")
                if len(daten.columns) == 1: # Nur eine Datenspalte (neben Index)
                    debug_print(f"[DataManager] Nutze erste Datenspalte '{daten.columns[0]}' als '{target_col_name}'.")
                    daten.rename(columns={daten.columns[0]: target_col_name}, inplace=True)
                else:
                    return None # Mehrdeutige Daten

            gdp_series = daten[[target_col_name]].copy() # Nur die relevante Spalte
            gdp_series.sort_index(inplace=True)

            debug_print(f"[DataManager] Provisorische BIP-Daten für '{country_name_internal}' erfolgreich aus {provisional_csv_path} geladen. {len(gdp_series)} Einträge.")
            return gdp_series

        except Exception as e:
            debug_print(f"[DataManager] FEHLER beim Laden der provisorischen BIP-Daten aus {provisional_csv_path}: {e}")
            return None

    def _fetch_gdp_from_fred(self, series_id, series_name, start_date_dt, end_date_dt):
        """Helper to fetch specific GDP data series from FRED."""
        print(f"[DataManager] Attempting to fetch GDP data for '{series_name}' (ID: {series_id}) from FRED ({start_date_dt} to {end_date_dt})...")
        try:
            gdp_data = pdr_web.DataReader(series_id, 'fred', start_date_dt, end_date_dt)
            if gdp_data.empty:
                print(f"[DataManager] No data received from FRED for {series_id}.")
                return None

            # DataReader for FRED returns a DataFrame, series_id is usually the column name
            if series_id in gdp_data.columns:
                gdp_series = gdp_data[[series_id]].copy() # Keep as DataFrame initially for consistent handling
                gdp_series.rename(columns={series_id: series_name}, inplace=True) # Rename to generic name
            elif not gdp_data.columns.empty : # Fallback if exact series_id not in columns (e.g. sometimes with single series)
                gdp_series = gdp_data[[gdp_data.columns[0]]].copy()
                gdp_series.rename(columns={gdp_data.columns[0]: series_name}, inplace=True)
                print(f"[DataManager] FRED data for {series_id} found in column '{gdp_data.columns[0]}', renamed to '{series_name}'.")
            else:
                 print(f"[DataManager] FRED data for {series_id} is an empty DataFrame or has no columns.")
                 return None

            if not isinstance(gdp_series.index, pd.DatetimeIndex):
                gdp_series.index = pd.to_datetime(gdp_series.index)

            # FRED GDP data is typically quarterly. Ensure it starts on quarter start for consistency.
            # Resample to Quarter Start ('QS'), then forward fill.
            # This handles if FRED returns mid-quarter dates (unlikely for GDPC1 but good practice).
            gdp_series = gdp_series.resample('QS').ffill()
            gdp_series = gdp_series.dropna() # Drop any NaNs after resampling/ffill, esp. at start.

            print(f"[DataManager] GDP data for '{series_name}' (ID: {series_id}) successfully fetched from FRED. {len(gdp_series)} entries.")
            return gdp_series # Return DataFrame with one column
        except Exception as e:
            print(f"[DataManager] Error fetching GDP data from FRED for {series_id} ('{series_name}'): {e}")
            return None

    # OECD fetching would be more complex and is stubbed out for now.
    # def _fetch_gdp_from_oecd(self, country_name, details, start_date_dt, end_date_dt):
    #     print(f"[DataManager] OECD fetching for {country_name} not yet fully implemented.")
    #     return None


    def get_forex_data(self, forex_pair_code, start_date, end_date):
        """
        Lädt historische Forex-Daten für das angegebene Paar (z.B. "EURUSD") und den Zeitraum mittels yfinance.
        """
        print(f"[DataManager] Lade Forex-Daten für {forex_pair_code} von {start_date} bis {end_date} via yfinance.")
        ticker = f"{forex_pair_code}=X" # yfinance Ticker-Format, z.B. EURUSD=X
        try:
            # Lade Daten, progress=False um Terminal-Ausgaben zu reduzieren
            daten = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)

            if daten.empty:
                print(f"[DataManager] Keine Forex-Daten für {ticker} im Zeitraum {start_date}-{end_date} gefunden.")
                return pd.DataFrame()

            # yfinance liefert typischerweise 'Close'. 'Adj Close' ist bei Forex seltener relevant.
            # Die Analysefunktion erwartet 'Schlusskurs'.
            price_col_options = ['Close', 'Adj Close'] # Präferiere 'Close' für Forex
            selected_price_col = None
            for col_option in price_col_options:
                if col_option in daten.columns:
                    selected_price_col = col_option
                    break

            if not selected_price_col:
                print(f"[DataManager] FEHLER: Weder 'Close' noch 'Adj Close' Spalte in yfinance-Daten für {ticker} gefunden.")
                print(f"[DataManager] Verfügbare Spalten: {daten.columns.tolist()}")
                return pd.DataFrame()

            # Nur die relevante Preissplate auswählen und umbenennen
            forex_data_final = daten[[selected_price_col]].copy()
            forex_data_final.rename(columns={selected_price_col: 'Schlusskurs'}, inplace=True)
            forex_data_final.index.name = 'Datum' # Sicherstellen, dass der Index 'Datum' heißt

            print(f"[DataManager] Forex-Daten für {ticker} erfolgreich geladen. {len(forex_data_final)} Einträge. Head:\n{forex_data_final.head()}")
            return forex_data_final
        except Exception as e:
            print(f"[DataManager] FEHLER beim Laden von Forex-Daten für {ticker} via yfinance: {e}")
            return pd.DataFrame()

    def _load_bip_csv(self, csv_path, target_col_country1, target_col_country2, is_fallback=False):
        """
        Hilfsfunktion zum Laden und Verarbeiten einer BIP-CSV-Datei.
        target_col_country1/2 sind die Spaltennamen, die am Ende im DataFrame stehen sollen (z.B. BIP_USA).
        """
        print(f"[DataManager] Lade BIP-Daten aus CSV: {csv_path} (Fallback={is_fallback})")
        daten = pd.read_csv(csv_path, parse_dates=['Datum'])
        daten.set_index('Datum', inplace=True)

        # Spalten, die tatsächlich aus der CSV geladen werden sollen
        # Für Fallback (alte bip_data.csv) sind die Spalten 'BIP_Land_A' und 'BIP_Land_B'.
        # Für Live (neue bip_data_live.csv) sind es die target_col_country1/2.
        col_to_load_1 = self.fallback_bip_col_land_a if is_fallback else target_col_country1
        col_to_load_2 = self.fallback_bip_col_land_b if is_fallback else target_col_country2

        if col_to_load_1 not in daten.columns or col_to_load_2 not in daten.columns:
            raise FileNotFoundError(f"Benötigte Spalten '{col_to_load_1}' oder '{col_to_load_2}' nicht in {csv_path} gefunden.")

        relevant_bip_data = daten[[col_to_load_1, col_to_load_2]].copy()
        relevant_bip_data.sort_index(inplace=True)

        # Umbenennen, falls Fallback verwendet wurde und die Spaltennamen von den Zielnamen abweichen
        if is_fallback:
            rename_map = {}
            if col_to_load_1 != target_col_country1: # Nur umbenennen, wenn der Name tatsächlich anders ist
                rename_map[col_to_load_1] = target_col_country1
            if col_to_load_2 != target_col_country2:
                rename_map[col_to_load_2] = target_col_country2

            if rename_map:
                relevant_bip_data.rename(columns=rename_map, inplace=True)
                print(f"[DataManager] Spalten im Fallback-DataFrame umbenannt: {rename_map}")

        print(f"[DataManager] BIP-Daten aus {csv_path} erfolgreich verarbeitet. {len(relevant_bip_data)} Einträge. Head:\n{relevant_bip_data.head()}")
        return relevant_bip_data

    def get_bip_data(self, country1_name, country2_name):
        """
        Lädt BIP-Daten für die zwei angegebenen Länder.
        Versucht API-Abruf für konfigurierte Länder, sonst Fallback auf CSV.
        Gibt ein DataFrame mit den BIP-Daten und die Namen der verwendeten Spalten zurück.
        """
        print(f"[DataManager] Ermittle BIP-Daten für Länder: {country1_name} und {country2_name}.")

        # Ziel-Spaltennamen für das finale DataFrame (z.B. BIP_USA, BIP_EUR)
        target_col_name1 = self.bip_csv_column_names.get(country1_name)
        target_col_name2 = self.bip_csv_column_names.get(country2_name)

        if not target_col_name1 or not target_col_name2:
            print(f"[DataManager] FEHLER: Keine BIP-Spaltenzuordnung für {country1_name} oder {country2_name} gefunden.")
            return pd.DataFrame(), None, None

        series_data = {} # Store fetched series here, keyed by target_col_name

        # Definiere Start- und Enddatum für API-Abrufe (z.B. letzte 10-15 Jahre)
        # Diese Daten müssen als datetime.date oder datetime.datetime übergeben werden.
        # Die ForexApp verwendet Strings, daher hier Konvertierung oder Anpassung nötig.
        # Für einen generischen Abruf hier, nehmen wir einen weiten Zeitraum.
        # Die eigentliche Filterung nach Forex-Zeitraum passiert später.
        api_end_date = date.today()
        api_start_date = date(api_end_date.year - 15, api_end_date.month, api_end_date.day)


        for i, country_name_iter in enumerate([country1_name, country2_name]):
            target_col_name_iter = target_col_name1 if i == 0 else target_col_name2
            fetched_from_api = False

            if country_name_iter in self.gdp_api_map:
                api_details = self.gdp_api_map[country_name_iter]
                gdp_series_df = None # Wird ein DataFrame mit einer Spalte sein
                if api_details["source"] == "fred":
                    gdp_series_df = self._fetch_gdp_from_fred(api_details["id"], api_details["name"], api_start_date, api_end_date)
                # Elif für "oecd" etc. könnte hier folgen

                if gdp_series_df is not None and not gdp_series_df.empty:
                    # API-Daten erfolgreich abgerufen, benenne die Spalte auf den Zielnamen um (z.B. BIP_USA)
                    # _fetch_gdp_from_fred gibt bereits einen DataFrame mit einer Spalte zurück, die api_details["name"] heißt.
                    # Wir wollen es auf target_col_name_iter umbenennen.
                    series_data[target_col_name_iter] = gdp_series_df.iloc[:, 0].rename(target_col_name_iter)
                    fetched_from_api = True
                    print(f"[DataManager] BIP-Daten für {country_name_iter} erfolgreich von API ({api_details['source']}) geladen.")

            if not fetched_from_api:
                print(f"[DataManager] BIP-Daten für {country_name_iter} werden aus CSV geladen (API nicht konfiguriert oder Fehler).")
                # Markiere, dass CSV benötigt wird, aber lade es erst, wenn klar ist, ob beide aus CSV kommen oder gemischt wird.
                # Fürs Erste setzen wir None, um CSV-Ladung unten auszulösen, falls diese Serie nicht aus API kam.
            # if target_col_name_iter not in series_data: # Nur setzen, wenn nicht schon aus API geladen
            #      series_data[target_col_name_iter] = None # Signalisiert, dass CSV-Fallback benötigt wird
            # Die Logik wurde geändert: series_data wird direkt befüllt oder bleibt leer, wenn nichts gefunden.

            if not fetched_from_api: # Wenn nicht von API geladen (entweder kein Eintrag in gdp_api_map oder API-Abruf fehlgeschlagen)
                debug_print(f"[DataManager] Versuche provisorische CSV-Daten für {country_name_iter}, da API-Daten nicht verfügbar/abgerufen.")
                provisional_gdp_df = self._load_provisional_gdp_csv(country_name_iter, target_col_name_iter)
                if provisional_gdp_df is not None and not provisional_gdp_df.empty:
                    series_data[target_col_name_iter] = provisional_gdp_df.iloc[:, 0].rename(target_col_name_iter)
                    debug_print(f"[DataManager] Provisorische BIP-Daten für {country_name_iter} erfolgreich geladen.")
                else:
                    # Wenn weder API noch provisorische CSV erfolgreich waren, markieren für generischen CSV-Fallback
                    debug_print(f"[DataManager] Keine API- oder provisorischen CSV-Daten für {country_name_iter} gefunden. Markiere für generischen Fallback.")
                    if target_col_name_iter not in series_data:
                         series_data[target_col_name_iter] = None # Signalisiert Notwendigkeit für generischen Fallback


        # Generischer CSV-Fallback (BIP_DATA_LIVE_CSV / BIP_DATA_FALLBACK_CSV)
        # Diese Logik greift jetzt nur noch, wenn für eines der Länder series_data[target_col_name_iter] immer noch None ist
        generic_csv_bip_df = None
        needs_generic_csv_fallback = any(s is None for s in series_data.values())

        if needs_generic_csv_fallback:
            debug_print(f"[DataManager] Versuche generischen CSV-Fallback (live/fallback CSVs), da spezifische Daten für mindestens ein Land fehlen.")
            try:
                generic_csv_bip_df = self._load_bip_csv(BIP_DATA_LIVE_CSV, target_col_name1, target_col_name2, is_fallback=False)
            except FileNotFoundError:
                debug_print(f"[DataManager] 'Live' BIP-Datei ({BIP_DATA_LIVE_CSV}) nicht gefunden. Versuche Fallback-CSV.")
                try:
                    generic_csv_bip_df = self._load_bip_csv(BIP_DATA_FALLBACK_CSV, target_col_name1, target_col_name2, is_fallback=True)
                except Exception as e_fallback_csv:
                    debug_print(f"[DataManager] FEHLER auch beim Laden von Fallback-BIP-Daten ({BIP_DATA_FALLBACK_CSV}): {e_fallback_csv}")
                    # Keine Aktion hier, da wir unten prüfen, ob Daten vorhanden sind
            except Exception as e_csv:
                debug_print(f"[DataManager] Allgemeiner Fehler beim Laden von generischen CSV-BIP-Daten: {e_csv}")

        # Kombiniere API, provisorische CSV und generische CSV Daten
        final_bip_data_list = []
        for i, target_col_name_iter in enumerate([target_col_name1, target_col_name2]):
            country_name_iter = country1_name if i == 0 else country2_name # Für Logging
            if series_data.get(target_col_name_iter) is not None: # API oder provisorische CSV Daten haben Vorrang
                debug_print(f"[DataManager] Nutze API/provisorische Daten für {country_name_iter} ({target_col_name_iter}).")
                final_bip_data_list.append(series_data[target_col_name_iter])
            elif generic_csv_bip_df is not None and target_col_name_iter in generic_csv_bip_df: # Fallback auf generische CSV
                debug_print(f"[DataManager] Nutze Daten aus generischem CSV für {country_name_iter} ({target_col_name_iter}).")
                final_bip_data_list.append(generic_csv_bip_df[target_col_name_iter])
            else:
                debug_print(f"[DataManager] FEHLER: Keine Datenquelle (API, provisorisch, oder generisch CSV) für {country_name_iter} ({target_col_name_iter}) gefunden.")
                return pd.DataFrame(), None, None

        if len(final_bip_data_list) == 2:
            # pd.concat auf axis=1, um die Series zu einem DataFrame zu verbinden
            # Stellt sicher, dass der Index (Datum) ausgerichtet wird.
            # join='outer' behält alle Datenpunkte, ffill/bfill könnte danach angewendet werden,
            # aber compare_gdp_momentum macht seine eigene Synchronisierung.
            final_bip_df = pd.concat(final_bip_data_list, axis=1, join='outer')
            final_bip_df.sort_index(inplace=True)
            print(f"[DataManager] Finale BIP-Daten kombiniert. {len(final_bip_df)} Einträge. Head:\n{final_bip_df.head()}")
            return final_bip_df, target_col_name1, target_col_name2
        else:
            print(f"[DataManager] FEHLER: Konnte nicht zwei BIP-Datenserien für die Kombination erstellen.")
            return pd.DataFrame(), None, None


    def get_country_names_for_forex_pair(self, forex_pair_str):
        """
        Extrahiert die Währungscodes (z.B. aus "EUR/USD" oder "EURUSD")
        und gibt die zugehörigen Ländernamen sowie die Währungscodes zurück.
        """
        pair_cleaned = forex_pair_str.replace("/", "").upper()
        if len(pair_cleaned) == 6:
            base_curr = pair_cleaned[0:3]
            quote_curr = pair_cleaned[3:6]

            country1 = self.bip_country_mapping.get(base_curr)
            country2 = self.bip_country_mapping.get(quote_curr)

            if country1 and country2:
                print(f"[DataManager] Länder für {forex_pair_str}: {country1} (Basis: {base_curr}), {country2} (Quote: {quote_curr})")
                return country1, country2, base_curr, quote_curr
            else:
                missing = []
                if not country1: missing.append(base_curr)
                if not country2: missing.append(quote_curr)
                print(f"[DataManager] Länderzuordnung für Währung(en) {', '.join(missing)} in '{forex_pair_str}' nicht gefunden.")
                return None, None, None, None
        else:
            print(f"[DataManager] Ungültiges Forex-Paar-Format: {forex_pair_str}. Erwartet 6 Zeichen (z.B. EURUSD).")
            return None, None, None, None

    def get_historical_price_data(self, ticker, start_date, end_date):
        """
        Lädt historische Preisdaten (OHLCV) für einen gegebenen Ticker und Zeitraum mittels yfinance.
        Diese Methode ist generischer als get_forex_data.
        """
        print(f"[DataManager] Lade historische Preisdaten für {ticker} von {start_date} bis {end_date} via yfinance.")
        try:
            # Lade Daten, progress=False um Terminal-Ausgaben zu reduzieren
            # auto_adjust=True passt 'Close' für Dividenden/Splits an und liefert 'Adj Close' als 'Close'
            data = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)

            if data.empty:
                print(f"[DataManager] Keine Daten für {ticker} im Zeitraum {start_date}-{end_date} gefunden.")
                return pd.DataFrame()

            # yfinance mit auto_adjust=True liefert die angepassten Kurse bereits in den Standardspalten (Open, High, Low, Close)
            # Wir benötigen primär 'Close' und stellen sicher, dass der Index ein DatetimeIndex ist.
            if not isinstance(data.index, pd.DatetimeIndex):
                data.index = pd.to_datetime(data.index)

            # Umbenennen der Spalte 'Close' zu 'Schlusskurs' für Konsistenz innerhalb des Projekts,
            # aber für die Portfolio-Klasse ist 'Close' praktischer (wie in yfinance Standard).
            # Portfolio.get_current_price erwartet 'Close'.
            # data.rename(columns={'Close': 'Schlusskurs'}, inplace=True) # Optional, je nach Bedarf

            # Sicherstellen, dass der Index 'Date' (oder 'Datum') heißt, wie von Portfolio erwartet.
            # yfinance Index ist bereits 'Date' (oder 'Datetime').
            data.index.name = 'Date'


            print(f"[DataManager] Historische Preisdaten für {ticker} erfolgreich geladen. {len(data)} Einträge. Head:\n{data.head()}")
            return data # Gibt das gesamte OHLCV DataFrame zurück
        except Exception as e:
            print(f"[DataManager] FEHLER beim Laden von historischen Preisdaten für {ticker} via yfinance: {e}")
            return pd.DataFrame()

print("DataManager Modul geladen.")
