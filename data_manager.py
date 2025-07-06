import pandas as pd
import yfinance as yf
from datetime import datetime

# Pfade zu den BIP-Daten CSV-Dateien
BIP_DATA_LIVE_CSV = 'bip_data_live.csv'
BIP_DATA_FALLBACK_CSV = 'bip_data.csv' # Die bereits existierende Datei für den Fallback

class DataManager:
    def __init__(self):
        # Zuordnung von Währungscodes zu "Ländernamen" (oder Regionen), wie sie in BIP-Daten verwendet werden könnten
        self.bip_country_mapping = {
            "EUR": "Eurozone",
            "USD": "USA",
            "GBP": "UK",
            "JPY": "Japan",
            "CHF": "Switzerland",
            "AUD": "Australia",
            "CAD": "Canada"
        }
        # Erwartete Spaltennamen in der `bip_data_live.csv` Datei
        self.bip_csv_column_names = {
            "Eurozone": "BIP_EUR",
            "USA": "BIP_USA",
            "UK": "BIP_UK",
            "Japan": "BIP_JPN",
            "Switzerland": "BIP_CHF",
            "Australia": "BIP_AUD",
            "Canada": "BIP_CAD"
        }
        # Spaltennamen in der alten `bip_data.csv` (Fallback)
        self.fallback_bip_col_land_a = "BIP_Land_A"
        self.fallback_bip_col_land_b = "BIP_Land_B"

        print("[DataManager] DataManager initialisiert.")

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
        Lädt BIP-Daten für die zwei angegebenen Länder (Ländernamen, nicht Währungscodes).
        Versucht zuerst Live-Daten (aus BIP_DATA_LIVE_CSV), dann Fallback (aus BIP_DATA_FALLBACK_CSV).
        Gibt ein DataFrame mit den BIP-Daten und die Namen der verwendeten Spalten (target_col_country1, target_col_country2) zurück.
        """
        print(f"[DataManager] Ermittle BIP-Daten für Länder: {country1_name} und {country2_name}.")

        # Ziel-Spaltennamen basierend auf der Länderzuordnung (z.B. BIP_USA, BIP_EUR)
        target_col_country1 = self.bip_csv_column_names.get(country1_name)
        target_col_country2 = self.bip_csv_column_names.get(country2_name)

        if not target_col_country1 or not target_col_country2:
            print(f"[DataManager] FEHLER: Keine BIP-Spaltenzuordnung im DataManager für {country1_name} oder {country2_name} gefunden.")
            return pd.DataFrame(), None, None

        try:
            # TODO: Später hier Logik für API-Abruf einfügen.
            # Derzeit wird BIP_DATA_LIVE_CSV als "Live"-Quelle behandelt.
            bip_df = self._load_bip_csv(BIP_DATA_LIVE_CSV, target_col_country1, target_col_country2, is_fallback=False)
            print(f"[DataManager] 'Live' BIP-Daten ({BIP_DATA_LIVE_CSV}) erfolgreich geladen.")
            return bip_df, target_col_country1, target_col_country2
        except FileNotFoundError as e_live_fnf:
            print(f"[DataManager] Info: 'Live' BIP-Datei nicht gefunden oder Spalten fehlen ({BIP_DATA_LIVE_CSV}): {e_live_fnf}. Versuche Fallback...")
        except Exception as e_live_other:
            print(f"[DataManager] FEHLER beim Laden von 'Live' BIP-Daten ({BIP_DATA_LIVE_CSV}): {e_live_other}. Versuche Fallback...")

        # Fallback-Versuch, wenn Live-Laden fehlschlägt
        try:
            print(f"[DataManager] Starte Fallback-Versuch für BIP-Daten mit: {BIP_DATA_FALLBACK_CSV}")
            bip_df = self._load_bip_csv(BIP_DATA_FALLBACK_CSV, target_col_country1, target_col_country2, is_fallback=True)
            print(f"[DataManager] Fallback-BIP-Daten ({BIP_DATA_FALLBACK_CSV}) erfolgreich geladen.")
            return bip_df, target_col_country1, target_col_country2
        except Exception as e_fallback:
            print(f"[DataManager] FEHLER auch beim Laden von Fallback-BIP-Daten ({BIP_DATA_FALLBACK_CSV}): {e_fallback}")
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

print("DataManager Modul geladen.")
