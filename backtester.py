import pandas as pd
from datetime import datetime, timedelta
from data_manager import DataManager
from signal_analyzer import SignalAnalyzer, compare_gdp_momentum # Importiere compare_gdp_momentum
from portfolio_manager import Portfolio

class Backtester:
    def __init__(self, gui_log_callback=print):
        self.data_manager = DataManager()
        self.signal_analyzer = None # Wird mit spezifischen Configs initialisiert
        self.gui_log_callback = gui_log_callback # Für Nachrichten an die GUI

    def log(self, message):
        # Um sicherzustellen, dass der Callback aufgerufen werden kann, auch wenn er von Tkinter kommt
        # und der Backtester in einem Thread läuft, prüfen wir, ob der Callback direkt aufrufbar ist
        # oder ob wir ihn über root.after planen müssen (was hier nicht direkt möglich ist ohne root).
        # Für den Moment gehen wir davon aus, dass gui_log_callback Thread-sicher ist oder
        # von der GUI entsprechend gehandhabt wird.
        self.gui_log_callback(f"[Backtester] {message}")

    def run_backtest(self,
                     forex_pair_config, # Dict mit Infos zum Währungspaar
                     start_date_str,
                     end_date_str,
                     analyzer_config_dict, # Config für SignalAnalyzer (Saisonalität)
                     gdp_long_threshold,
                     gdp_short_threshold,
                     initial_cash=10000,
                     benchmark_ticker="^SPX",
                     trade_amount_percent=0.10):

        self.log("Backtest gestartet.")
        self.log(f"Forex Paar: {forex_pair_config['display']}, Zeitraum: {start_date_str} bis {end_date_str}")
        self.log(f"Startkapital: {initial_cash}, Positionsgröße: {trade_amount_percent*100:.2f}% des Kapitals")
        self.log(f"Benchmark Ticker: {benchmark_ticker}")
        self.log(f"Analyzer Config: {analyzer_config_dict}")
        self.log(f"GDP Long/Short Thresholds: {gdp_long_threshold}/{gdp_short_threshold}")


        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        except ValueError as e:
            self.log(f"Fehler im Datumsformat: {e}")
            return None, None

        # 0. SignalAnalyzer initialisieren
        self.signal_analyzer = SignalAnalyzer(config=analyzer_config_dict)
        # Den Debug-Callback des SignalAnalyzers auf den des Backtesters setzen
        # Damit die internen Logs des SignalAnalyzers auch über die GUI geloggt werden.
        # Wichtig: signal_analyzer.set_debug_output_callback ist eine globale Funktion im signal_analyzer Modul
        from signal_analyzer import set_debug_output_callback as analyzer_set_debug_callback
        analyzer_set_debug_callback(self.log)
        self.log("SignalAnalyzer initialisiert und Debug-Callback gesetzt.")

        # 1. Portfolios initialisieren
        # Wichtig: backtest_start_date und backtest_end_date müssen datetime Objekte sein
        strategy_portfolio = Portfolio(initial_cash, self.data_manager, start_date, end_date)
        benchmark_portfolio = Portfolio(initial_cash, self.data_manager, start_date, end_date)
        self.log("Portfolios initialisiert.")

        # 2. Daten laden
        # Ticker für yfinance (mit =X für Forex Paare)
        trading_ticker_yf = forex_pair_config['pair_code'] + "=X"
        # Benchmark Ticker bleibt wie er ist (z.B. ^SPX)

        self.log(f"Lade Forex-Daten für Signalerzeugung ({trading_ticker_yf})...")
        # Daten für Signalerzeugung
        forex_data_for_signals = self.data_manager.get_historical_price_data(forex_ticker_yf, start_date_str, end_date_str)
        if forex_data_for_signals.empty:
            self.log(f"Keine Forex-Daten für {forex_ticker_yf} im Zeitraum gefunden. Backtest abgebrochen.")
            return None, None
        self.log(f"Forex-Daten für {forex_ticker_yf} geladen: {len(forex_data_for_signals)} Einträge.")

        country1 = forex_pair_config["country1"]
        country2 = forex_pair_config["country2"]
        bip_data_tuple = self.data_manager.get_bip_data(country1, country2)
        bip_data_df = bip_data_tuple[0]
        bip_col_country1 = bip_data_tuple[1]
        bip_col_country2 = bip_data_tuple[2]

        gdp_momentum_signal_aligned_to_forex = pd.Series(dtype=object) # Initialize as object for 'long'/'short'
        if forex_data_for_signals.index.empty:
             gdp_momentum_signal_aligned_to_forex = pd.Series(dtype=object, name="GDP_Momentum_Signal_Aligned") # Empty series if no index
        else:
             gdp_momentum_signal_aligned_to_forex = pd.Series(index=forex_data_for_signals.index, data=None, name="GDP_Momentum_Signal_Aligned", dtype=object)


        if bip_data_df.empty or not bip_col_country1 or not bip_col_country2:
            self.log(f"Keine validen BIP-Daten für {country1}/{country2}. GDP-Momentum wird übersprungen. Verwende neutrales Signal.")
        else:
            self.log(f"Berechne GDP Momentum für {bip_col_country1} vs {bip_col_country2}...")
            gdp_series_a = bip_data_df[bip_col_country1]
            gdp_series_b = bip_data_df[bip_col_country2]
            n_periods_gdp_growth = 4
            gdp_mom_a, gdp_mom_b, gdp_mom_diff, gdp_signal_raw = compare_gdp_momentum(
                gdp_series_a=gdp_series_a, gdp_series_b=gdp_series_b,
                n_periods_growth=n_periods_gdp_growth,
                long_threshold=gdp_long_threshold, short_threshold=gdp_short_threshold
            )
            if gdp_signal_raw is not None and not gdp_signal_raw.empty:
                # Reindex auf den Forex-Datenindex. Fülle vorwärts, dann rückwärts, dann mit None (wird zu 0 in generiere_signale)
                temp_aligned = gdp_signal_raw.reindex(forex_data_for_signals.index, method='ffill')
                temp_aligned = temp_aligned.bfill() # füllt NaNs am Anfang
                gdp_momentum_signal_aligned_to_forex = temp_aligned.fillna(None) # Explizit None für fehlende Werte
                gdp_momentum_signal_aligned_to_forex.name = "GDP_Momentum_Signal_Aligned"
                self.log("GDP Momentum Signale berechnet und an Forex-Daten angeglichen.")
            else:
                self.log("Keine GDP Momentum Rohsignale erhalten. Verwende neutrales Signal (None).")

        self.log("Berechne Saisonalität...")
        saisonalitaet_series = self.signal_analyzer.berechne_saisonalitaet(forex_data_for_signals)
        self.log("Saisonalität berechnet.")

        self.log("Generiere Handelssignale...")
        final_signals = self.signal_analyzer.generiere_signale(
            forex_daten_idx=forex_data_for_signals.index,
            saisonalitaet_raw=saisonalitaet_series,
            gdp_momentum_signal_aligned=gdp_momentum_signal_aligned_to_forex # Kann 'long', 'short', None enthalten
        )
        self.log(f"Handelssignale generiert. {len(final_signals[final_signals != 0])} aktive Signale gefunden.")

        # 3. Benchmark-Portfolio: Kaufe Benchmark-Ticker am ersten Handelstag und halte ihn
        # _fetch_and_cache_prices wird automatisch von get_current_price/buy aufgerufen, falls nötig.
        # Wir stellen hier sicher, dass der Ticker einmalig für den gesamten Zeitraum geladen wird.
        if benchmark_ticker:
            benchmark_portfolio._fetch_and_cache_prices(benchmark_ticker) # Pre-cache
            first_trade_day_benchmark = None
            current_day_iter = start_date
            while current_day_iter <= end_date:
                # get_current_price prüft im Cache oder lädt, wenn _fetch_and_cache_prices nicht explizit gerufen wurde
                if benchmark_portfolio.get_current_price(benchmark_ticker, current_day_iter) is not None:
                    first_trade_day_benchmark = current_day_iter
                    break
                current_day_iter += timedelta(days=1)

            if first_trade_day_benchmark:
                self.log(f"Kaufe Benchmark {benchmark_ticker} am {first_trade_day_benchmark.strftime('%Y-%m-%d')}")
                benchmark_portfolio.buy(benchmark_ticker, benchmark_portfolio.cash, first_trade_day_benchmark)
            else:
                self.log(f"Konnte keinen gültigen Handelstag für Benchmark-Kauf finden für {benchmark_ticker}.")
        else:
            self.log("Kein Benchmark-Ticker angegeben. Benchmark-Portfolio bleibt leer.")


        # 4. Iteriere über den Handelszeitraum
        self.log("Starte tägliche Backtesting-Schleife...")

        # Verwende den Index der Forex-Daten, da dieser die tatsächlichen Handelstage enthält
        # und bereits für den Backtest-Zeitraum gefiltert sein sollte (durch get_historical_price_data)
        # aber zur Sicherheit filtern wir hier nochmal explizit.
        if not isinstance(forex_data_for_signals.index, pd.DatetimeIndex):
             forex_data_for_signals.index = pd.to_datetime(forex_data_for_signals.index)

        loop_days_pd = forex_data_for_signals.index[(forex_data_for_signals.index >= start_date) & (forex_data_for_signals.index <= end_date)]

        for current_pd_ts_date in loop_days_pd:
            dt_current_date = current_pd_ts_date.to_pydatetime()

            strategy_portfolio.record_portfolio_value(dt_current_date)
            if benchmark_ticker:
                benchmark_portfolio.record_portfolio_value(dt_current_date)

            signal_today = final_signals.get(current_pd_ts_date, 0)

            # Freitags-Verkaufslogik (vor neuen Käufen)
            if dt_current_date.weekday() == 4:
                if trading_ticker_yf in strategy_portfolio.positions:
                    self.log(f"{dt_current_date.strftime('%Y-%m-%d')} (Freitag): Verkaufe {trading_ticker_yf} aufgrund Wochenschluss.")
                    strategy_portfolio.sell(trading_ticker_yf, dt_current_date)

            if signal_today == 1:
                if trading_ticker_yf not in strategy_portfolio.positions:
                    amount_to_invest = strategy_portfolio.calculate_total_value(dt_current_date) * trade_amount_percent
                    # Stelle sicher, dass amount_to_invest nicht negativ ist (falls total_value negativ wird)
                    if amount_to_invest <= 0 :
                        self.log(f"{dt_current_date.strftime('%Y-%m-%d')}: Kaufsignal für {trading_ticker_yf}, aber Investmentbetrag ({amount_to_invest:.2f}) ist nicht positiv.")
                    elif strategy_portfolio.cash >= amount_to_invest :
                        self.log(f"{dt_current_date.strftime('%Y-%m-%d')}: Kaufsignal für {trading_ticker_yf}. Investiere {amount_to_invest:.2f}.")
                        strategy_portfolio.buy(trading_ticker_yf, amount_to_invest, dt_current_date)
                    else:
                        self.log(f"{dt_current_date.strftime('%Y-%m-%d')}: Kaufsignal für {trading_ticker_yf}, aber nicht genug Cash ({strategy_portfolio.cash:.2f}) für Investment ({amount_to_invest:.2f}).")
                else:
                    self.log(f"{dt_current_date.strftime('%Y-%m-%d')}: Kaufsignal für {trading_ticker_yf}, aber bereits in Position.")

            elif signal_today == -1:
                if trading_ticker_yf in strategy_portfolio.positions:
                    self.log(f"{dt_current_date.strftime('%Y-%m-%d')}: Verkaufssignal für {trading_ticker_yf}. Verkaufe alle Anteile.")
                    strategy_portfolio.sell(trading_ticker_yf, dt_current_date)
                else:
                    self.log(f"{dt_current_date.strftime('%Y-%m-%d')}: Verkaufssignal für {trading_ticker_yf}, aber keine Position vorhanden.")

        # Stelle sicher, dass der letzte Wert am Enddatum des Backtests erfasst wird,
        # falls end_date nach dem letzten Handelstag in loop_days_pd liegt oder loop_days_pd leer ist.
        if loop_days_pd.empty or end_date > loop_days_pd[-1].to_pydatetime():
            self.log(f"Zeichne finalen Portfoliowert am {end_date.strftime('%Y-%m-%d')} auf (könnte nach letztem Handelstag sein).")
            strategy_portfolio.record_portfolio_value(end_date)
            if benchmark_ticker:
                benchmark_portfolio.record_portfolio_value(end_date)

        self.log("Backtesting-Schleife beendet.")

        strategy_history_df = strategy_portfolio.get_history_df()
        benchmark_history_df = pd.DataFrame() # Default empty
        if benchmark_ticker:
            benchmark_history_df = benchmark_portfolio.get_history_df()

        final_strat_value = strategy_portfolio.calculate_total_value(end_date)
        self.log(f"Strategie Endwert am {end_date.strftime('%Y-%m-%d')}: {final_strat_value:.2f}")
        if benchmark_ticker:
            final_bench_value = benchmark_portfolio.calculate_total_value(end_date)
            self.log(f"Benchmark Endwert am {end_date.strftime('%Y-%m-%d')}: {final_bench_value:.2f}")

        return strategy_history_df, benchmark_history_df
```
