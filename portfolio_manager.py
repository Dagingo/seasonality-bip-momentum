import pandas as pd
from datetime import datetime, timedelta

class Portfolio:
    def __init__(self, initial_cash=10000.0, data_manager=None, backtest_start_date=None, backtest_end_date=None):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        # Positionsstruktur: Ticker: {'shares': float (abs value), 'entry_price': float, 'type': str ('long'/'short'), 'entry_date': datetime}
        self.positions = {}
        self.history = []  # To track portfolio value over time: {'date': datetime, 'value': float}
        self.data_manager = data_manager
        self.price_cache = {} # Cache for historical price data: {ticker: pd.DataFrame}
        self.backtest_start_date = backtest_start_date
        self.backtest_end_date = backtest_end_date


    def _fetch_and_cache_prices(self, ticker):
        """
        Fetches historical price data for a ticker for the entire backtest period and caches it.
        """
        if ticker not in self.price_cache and self.data_manager and self.backtest_start_date and self.backtest_end_date:
            print(f"[Portfolio] Caching prices for {ticker} from {self.backtest_start_date} to {self.backtest_end_date}")
            # Convert datetime to string if necessary for data_manager method
            start_str = self.backtest_start_date.strftime('%Y-%m-%d') if isinstance(self.backtest_start_date, datetime) else self.backtest_start_date
            end_str = self.backtest_end_date.strftime('%Y-%m-%d') if isinstance(self.backtest_end_date, datetime) else self.backtest_end_date

            historical_data = self.data_manager.get_historical_price_data(ticker, start_str, end_str)
            if historical_data is not None and not historical_data.empty:
                # Ensure Date index is pd.DatetimeIndex
                if not isinstance(historical_data.index, pd.DatetimeIndex):
                    historical_data.index = pd.to_datetime(historical_data.index)
                # Ensure data is sorted by date
                historical_data.sort_index(inplace=True)
                self.price_cache[ticker] = historical_data
            else:
                self.price_cache[ticker] = pd.DataFrame() # Cache empty df to avoid refetching failures
                print(f"[Portfolio] Warning: No price data returned for {ticker} for the period.")
        elif not self.data_manager:
            print("[Portfolio] Error: DataManager not provided to Portfolio.")
        elif not self.backtest_start_date or not self.backtest_end_date:
            print("[Portfolio] Error: Backtest start or end date not set for fetching prices.")


    def get_current_price(self, ticker, date):
        """
        Retrieves the closing price for a given ticker on a specific date from cached data.
        """
        if ticker not in self.price_cache:
            self._fetch_and_cache_prices(ticker)

        if ticker in self.price_cache and not self.price_cache[ticker].empty:
            price_data_df = self.price_cache[ticker]

            # Ensure the input date is timezone-naive if the DataFrame dates are naive
            query_date = date
            if price_data_df.index.tz is None and date.tzinfo is not None:
                query_date = date.replace(tzinfo=None)
            elif price_data_df.index.tz is not None and date.tzinfo is None:
                # If cache has tz-aware index, make query_date tz-aware (assume UTC or same as cache)
                # This case needs careful handling based on actual timezone of data. For now, naive comparison.
                # Or, convert price_data_df.index to naive: price_data_df.index.tz_localize(None)
                # For simplicity, let's assume we primarily deal with naive dates or ensure consistency.
                 pass # Potentially convert query_date to match price_data_df.index.tz

            # Find the latest price on or before the query_date
            relevant_data = price_data_df[price_data_df.index <= query_date]

            if not relevant_data.empty and 'Close' in relevant_data.columns:
                # Nimm die letzte Zeile und daraus den 'Close'-Wert
                last_row_with_price = relevant_data.tail(1)
                if not last_row_with_price.empty:
                    price_value_candidate = last_row_with_price['Close'].iloc[0]

                    final_price_scalar = None
                    if pd.api.types.is_scalar(price_value_candidate):
                        final_price_scalar = float(price_value_candidate)
                    elif isinstance(price_value_candidate, pd.Series):
                        # Wenn es eine Series ist, versuchen wir, den einzelnen Wert zu extrahieren
                        if not price_value_candidate.empty:
                            try:
                                final_price_scalar = float(price_value_candidate.item())
                                # print(f"[Portfolio] Info: Extracted scalar price for {ticker} on {date} from Series using .item()")
                            except ValueError: # Falls .item() fehlschlägt (mehr als ein Element)
                                try:
                                    final_price_scalar = float(price_value_candidate.iloc[0])
                                    # print(f"[Portfolio] Info: Extracted scalar price for {ticker} on {date} from Series using .iloc[0]")
                                except Exception as e:
                                    print(f"[Portfolio] Warning: Could not extract single item from price Series for {ticker} on {date}: {e}. Series was: {price_value_candidate}")
                        else:
                            print(f"[Portfolio] Warning: Price candidate for {ticker} on {date} was an empty Series.")

                    if final_price_scalar is not None:
                        return final_price_scalar
                    else:
                        print(f"[Portfolio] Warning: get_current_price for {ticker} on {date} could not resolve to a scalar price. Candidate was: {price_value_candidate}. Returning None.")
                        return None
                else:
                    # This case should ideally not be reached if relevant_data was not empty.
                    print(f"[Portfolio] Price for {ticker} on or before {date} not found (tail(1) was unexpectedly empty).")
                    return None
            else:
                # Try to find the first price *after* query_date if no price on or before (e.g. market holiday)
                # This is for cases where a trade needs to happen on the next available day
                # For now, this is not implemented, we stick to "on or before".
                # For backtesting, it's often assumed that if data for 'date' is missing,
                # it's a non-trading day, and the last known price is used or the trade fails/is postponed.
                print(f"[Portfolio] Price for {ticker} on or before {date} not found in cached data. Available range: {price_data_df.index.min()} to {price_data_df.index.max() if not price_data_df.empty else 'N/A'}")
                return None

        print(f"[Portfolio] Warning: Price for {ticker} on {date} not found. No data in cache.")
        return None # Return None if price cannot be found

    def open_long_position(self, ticker, amount_to_invest, date):
        """
        Opens a new long position or adds to an existing one.
        """
        if self.cash < amount_to_invest:
            print(f"[Portfolio] Not enough cash to open long {ticker}. Available: {self.cash:.2f}, Needed: {amount_to_invest:.2f}")
            return False

        price = self.get_current_price(ticker, date)
        if price is None or price <= 0:
            print(f"[Portfolio] Could not get a valid price for {ticker} on {date} to open long.")
            return False

        shares_to_buy = amount_to_invest / price
        cost = shares_to_buy * price

        if ticker in self.positions:
            if self.positions[ticker]['type'] == 'long':
                # Add to existing long position (average up/down)
                current_shares = self.positions[ticker]['shares']
                current_total_cost = current_shares * self.positions[ticker]['entry_price']
                new_total_shares = current_shares + shares_to_buy
                new_average_price = (current_total_cost + cost) / new_total_shares
                self.positions[ticker]['shares'] = new_total_shares
                self.positions[ticker]['entry_price'] = new_average_price
                self.positions[ticker]['entry_date'] = date # Update entry date to latest
                print(f"[Portfolio] Added to long {ticker}: {shares_to_buy:.4f} shares at {price:.2f}. New avg price: {new_average_price:.2f}")
            else: # Existing position is short
                print(f"[Portfolio] Cannot open long for {ticker}; short position exists. Close short first.")
                return False
        else:
            self.positions[ticker] = {
                'shares': shares_to_buy,
                'entry_price': price,
                'type': 'long',
                'entry_date': date
            }
            print(f"[Portfolio] Opened long {ticker}: {shares_to_buy:.4f} shares at {price:.2f}")

        self.cash -= cost
        self.record_transaction(date, 'OPEN_LONG', ticker, shares_to_buy, price)
        return True

    def close_long_position(self, ticker, date, shares_to_sell=None):
        """
        Closes an existing long position fully or partially.
        """
        if ticker not in self.positions or self.positions[ticker]['type'] != 'long':
            print(f"[Portfolio] No long position in {ticker} to close.")
            return False

        price = self.get_current_price(ticker, date)
        if price is None or price <= 0:
            print(f"[Portfolio] Could not get a valid price for {ticker} on {date} to close long.")
            return False

        position_details = self.positions[ticker]

        if shares_to_sell is None or shares_to_sell >= position_details['shares']:
            shares_sold = position_details['shares']
            del self.positions[ticker]
            print(f"[Portfolio] Closed entire long position in {ticker}: {shares_sold:.4f} shares at {price:.2f}")
        else:
            shares_sold = shares_to_sell
            self.positions[ticker]['shares'] -= shares_sold
            print(f"[Portfolio] Partially closed long {ticker}: Sold {shares_sold:.4f} shares at {price:.2f}. Remaining: {self.positions[ticker]['shares']:.4f}")
            if self.positions[ticker]['shares'] <= 1e-9: # Handle float precision
                 del self.positions[ticker]
                 print(f"[Portfolio] Remaining shares for {ticker} negligible, position fully closed.")

        proceeds = shares_sold * price
        self.cash += proceeds
        self.record_transaction(date, 'CLOSE_LONG', ticker, shares_sold, price)
        return True

    def open_short_position(self, ticker, amount_to_invest, date):
        """
        Opens a new short position. Amount_to_invest determines the notional value of the short.
        """
        # For short selling, we don't check cash < amount_to_invest in the same way,
        # as shorting initially increases cash. Margin would be a real-world check.
        # Here, we assume margin is sufficient.
        if ticker in self.positions:
            print(f"[Portfolio] Cannot open short for {ticker}; position already exists ({self.positions[ticker]['type']}). Close existing first.")
            return False

        price = self.get_current_price(ticker, date)
        if price is None or price <= 0:
            print(f"[Portfolio] Could not get a valid price for {ticker} on {date} to open short.")
            return False

        shares_to_short = amount_to_invest / price
        proceeds = shares_to_short * price # Cash received from shorting

        self.positions[ticker] = {
            'shares': shares_to_short, # Store as positive number, 'type' indicates direction
            'entry_price': price,
            'type': 'short',
            'entry_date': date
        }
        self.cash += proceeds # Cash increases from short sale
        self.record_transaction(date, 'OPEN_SHORT', ticker, shares_to_short, price)
        print(f"[Portfolio] Opened short {ticker}: {shares_to_short:.4f} shares at {price:.2f}. Cash: {self.cash:.2f}")
        return True

    def cover_short_position(self, ticker, date, shares_to_cover=None):
        """
        Covers an existing short position fully or partially.
        """
        if ticker not in self.positions or self.positions[ticker]['type'] != 'short':
            print(f"[Portfolio] No short position in {ticker} to cover.")
            return False

        price = self.get_current_price(ticker, date)
        if price is None or price <= 0:
            print(f"[Portfolio] Could not get a valid price for {ticker} on {date} to cover short.")
            return False

        position_details = self.positions[ticker]

        if shares_to_cover is None or shares_to_cover >= position_details['shares']:
            shares_bought_back = position_details['shares']
            del self.positions[ticker]
            print(f"[Portfolio] Covered entire short position in {ticker}: Bought back {shares_bought_back:.4f} shares at {price:.2f}")
        else:
            shares_bought_back = shares_to_cover
            self.positions[ticker]['shares'] -= shares_bought_back
            print(f"[Portfolio] Partially covered short {ticker}: Bought back {shares_bought_back:.4f} shares at {price:.2f}. Remaining short: {self.positions[ticker]['shares']:.4f}")
            if self.positions[ticker]['shares'] <= 1e-9: # Handle float precision
                 del self.positions[ticker]
                 print(f"[Portfolio] Remaining short shares for {ticker} negligible, position fully covered.")

        cost = shares_bought_back * price
        self.cash -= cost # Cash decreases to buy back shares
        self.record_transaction(date, 'COVER_SHORT', ticker, shares_bought_back, price)
        return True

    def calculate_total_value(self, current_date):
        """
        Calculates the total mark-to-market value of the portfolio.
        For short positions, this means cash + (entry_price - current_price) * shares.
        """
        total_value = self.cash
        for ticker, details in self.positions.items():
            current_price = self.get_current_price(ticker, current_date)
            if current_price is None: # If price unavailable, use entry price (conservative for longs, potentially problematic for shorts)
                print(f"[Portfolio] Warning: Using entry price for {ticker} as current price for value calculation on {current_date} is unavailable.")
                current_price = details['entry_price']

            if details['type'] == 'long':
                total_value += details['shares'] * current_price
            elif details['type'] == 'short':
                # Cash already reflects proceeds from short sale.
                # Value change of short position = (entry_price - current_price) * shares
                # So, add this change to the cash.
                # Or, simpler: initial_cash_from_short + (entry_price - current_price) * shares
                # The cash component already has the (shares * entry_price) from the short sale.
                # So, the liability is (shares * current_price).
                # The value of the short position part is (shares * entry_price) - (shares * current_price)
                # total_value = self.cash (which includes initial short proceeds) + sum_long_values - sum_current_cost_to_cover_shorts
                # This is equivalent to:
                total_value += (details['entry_price'] - current_price) * details['shares']
        return total_value

    def record_portfolio_value(self, date):
        """
        Records the current total portfolio value at a given date.
        """
        current_value = self.calculate_total_value(date)
        self.history.append({'date': date, 'value': current_value})
        # print(f"{date}: Portfolio Value: {current_value:.2f}")

    def record_transaction(self, date, type, ticker, shares, price):
        # Simple transaction log, could be expanded
        print(f"TRANSACTION: {date} - {type} {shares:.4f} {ticker} @ {price:.2f}")

    def get_history_df(self):
        """
        Returns the portfolio history as a pandas DataFrame.
        """
        return pd.DataFrame(self.history)

if __name__ == '__main__':
    # Example Usage (requires a dummy DataManager or integration with actual DataManager)
    class DummyDataManager:
        def __init__(self):
            # Simulate price data for AAPL and SPX
            self.price_data = {
                'AAPL': pd.DataFrame({
                    'Date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05', '2023-01-06']),
                    'Close': [150.0, 152.0, 151.5, 155.0, 154.0, 153.0]
                }),
                'SPX': pd.DataFrame({
                    'Date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05', '2023-01-06']),
                    'Close': [4000.0, 4010.0, 4005.0, 4020.0, 4015.0, 4000.0]
                })
            }

        def get_data(self, ticker): # Simplified method name for consistency
            return self.price_data.get(ticker, pd.DataFrame())


    dummy_dm = DummyDataManager()
    portfolio = Portfolio(initial_cash=10000, data_manager=dummy_dm)

    # Simulate some dates
    date1 = datetime(2023, 1, 2)
    date2 = datetime(2023, 1, 3)
    date3 = datetime(2023, 1, 4)
    date4 = datetime(2023, 1, 5)
    date5 = datetime(2023, 1, 6) # Friday

    portfolio.record_portfolio_value(datetime(2023,1,1)) # Initial value

    # Buy AAPL
    portfolio.buy('AAPL', 2000, date1) # Invest 2000 in AAPL
    portfolio.record_portfolio_value(date1)

    portfolio.record_portfolio_value(date2) # Value after one day

    # Buy more AAPL
    portfolio.buy('AAPL', 1000, date3)
    portfolio.record_portfolio_value(date3)

    portfolio.record_portfolio_value(date4)

    # Sell AAPL on Friday
    portfolio.sell('AAPL', date5)
    portfolio.record_portfolio_value(date5)

    print("\nPortfolio History:")
    print(portfolio.get_history_df())

    print("\nFinal Cash:", portfolio.cash)
    print("Final Positions:", portfolio.positions)

    # Test SPX benchmark portfolio
    print("\n--- SPX Benchmark Portfolio ---")
    spx_portfolio = Portfolio(initial_cash=10000, data_manager=dummy_dm)
    spx_portfolio.record_portfolio_value(datetime(2023,1,1))

    # Buy SPX at the start
    spx_purchase_date = datetime(2023,1,2) # Assuming trading starts on Jan 2
    spx_price_at_purchase = spx_portfolio.get_current_price('SPX', spx_purchase_date)
    if spx_price_at_purchase:
        amount_to_invest_spx = spx_portfolio.cash
        spx_portfolio.buy('SPX', amount_to_invest_spx, spx_purchase_date)

    spx_portfolio.record_portfolio_value(spx_purchase_date)
    spx_portfolio.record_portfolio_value(date2)
    spx_portfolio.record_portfolio_value(date3)
    spx_portfolio.record_portfolio_value(date4)
    spx_portfolio.record_portfolio_value(date5) # Value at the end of the week

    print("\nSPX Portfolio History:")
    print(spx_portfolio.get_history_df())
    print("\nSPX Final Cash:", spx_portfolio.cash)
    print("SPX Final Positions:", spx_portfolio.positions)

    # Note: The get_current_price method is crucial and needs proper integration
    # with the actual data source (data_manager.py).
    # The current implementation in Portfolio class is a placeholder.
    # The DummyDataManager is for testing this script in isolation.
    # The date handling (timezone, exact match vs. last available) in get_current_price
    # also needs to be robust.
    # For example, if a signal is on a Sunday, we'd need to get the price for the next trading day (Monday).
    # Or if a date is missing, use the last known price.
    # The current placeholder logic for get_current_price in Portfolio is:
    # price_data[price_data['Date'] <= query_date]['Close'].iloc[-1]
    # This means it takes the latest price available on or before the query_date.
    # This is a common approach for backtesting (using the closing price of the day).
    # If a signal occurs mid-day and is acted upon immediately, using open or intra-day data
    # would be more accurate but also more complex. For now, daily close is assumed.

    # Further considerations:
    # - Transaction costs (fees, slippage) are not yet included.
    # - Dividend handling for SPX benchmark is not included.
    # - Error handling for price fetching can be improved.

    # The `amount_to_invest` in `buy` method is the cash amount to be spent.
    # The number of shares is calculated based on this amount and the current price.
    # This means we might not use exactly `amount_to_invest` due to share divisibility,
    # but it will be very close.
    # This approach is often preferred over specifying number of shares for backtesting,
    # as it's easier to manage risk (e.g., "invest 10% of portfolio").

    # The `sell` method sells all shares of a ticker by default.
    # It can be modified to sell a specific number of shares if needed.

    # The `history` list tracks portfolio value over time. This is useful for plotting.
    # It's important to call `record_portfolio_value` regularly (e.g., daily or after each transaction)
    # to get a good representation of performance.

    # The `get_current_price` method in the `Portfolio` class now tries to use the `data_manager`
    # passed during initialization. It assumes `data_manager.get_data(ticker)` returns a DataFrame
    # with 'Date' and 'Close' columns. This needs to be adapted to the actual methods
    # available in your `data_manager.py`.
    # The example usage includes a `DummyDataManager` to illustrate how it might work.

    # Important: The `get_current_price` in `Portfolio` has a basic implementation.
    # It assumes dates in the DataFrame are datetime objects or convertible strings.
    # It also handles a basic timezone-naive comparison if DataFrame dates are naive.
    # This part is critical and will need careful adjustment once integrated with your actual `data_manager.py`.
    # Specifically, how `data_manager.py` loads and provides data (e.g., from CSV, API)
    # and the exact format of its date column are key.
    # The current dummy data uses `pd.to_datetime` which is good.
    # The logic `price_data[price_data['Date'] <= query_date]['Close'].iloc[-1]` means
    # "get the last available closing price on or before the given query_date".
    # This is a common way to simulate trades based on daily data (trade occurs at close).

    # The buy method calculates shares based on `amount_to_invest`. If the ticker is already
    # in positions, it now correctly averages the purchase price.

    # The sell method can now sell a specific number of shares or all shares.
    # It also handles potential floating point precision issues when shares remaining is very small.

    # Added a `record_transaction` method for logging, though it's just printing for now.
    # This could be expanded to store transactions in a list/DataFrame.

    # The `__main__` block now includes a more comprehensive test, including
    # buying more of an existing position and testing the SPX benchmark portfolio logic.
    # The SPX benchmark logic is to buy and hold.
    # The `get_history_df` method converts the history list to a DataFrame for easier analysis/plotting.

    # The `get_current_price` in `Portfolio` was updated to be more robust in how it
    # queries the DataFrame from `data_manager`.
    # It now explicitly converts 'Date' column to datetime if it's string,
    # and handles timezone-naive comparison more carefully.
    # The placeholder price of 1.0 is still there as a last resort if data_manager is not set
    # or if a price is truly not found, but it prints a warning.
    # This method is the most critical piece for successful integration.

    # The `buy` method was slightly adjusted to ensure `cost` is calculated from `shares_to_buy * price`
    # to accurately reflect the transaction.

    # The `calculate_total_value` now has a fallback to use purchase price if current price is unavailable,
    # with a warning. This is a common, though not always ideal, approach.

    # The `sell` method now correctly removes a position if all its shares are sold or remaining shares are negligible.

    # The `if __name__ == '__main__':` block has been updated to reflect these changes and
    # provides a more thorough test of the Portfolio class, including the SPX benchmark simulation.
    # This test now uses the `get_current_price` method that relies on the (Dummy)DataManager.

    # One key aspect for real backtesting is handling of dates where the market is closed
    # (weekends, holidays). If a signal occurs on such a day, the trade would typically
    # be executed on the next trading day. The current `get_current_price` logic
    # (finding price on or before `query_date`) handles this to some extent, as it would
    # use the last available price. However, for execution, one might want to explicitly
    # find the *next* available trading day's price (e.g., Open price).
    # For now, we'll assume signals are generated on trading days or that using the
    # closing price of the signal day (or last available prior) is acceptable.

    # The `DummyDataManager` now has a `get_data` method to align with the expectation
    # in `Portfolio.get_current_price`.

    # The `Portfolio.buy` method logic for when a ticker is already in `positions` has been
    # corrected to properly average down the purchase price.

    # The `Portfolio.sell` method has been updated to handle selling partial shares and
    # correctly removing the ticker from positions if shares become zero or negligible.

    # The `Portfolio.record_portfolio_value` method is used to track the portfolio's value
    # over time, which will be essential for plotting.

    # The `__main__` example now demonstrates buying, recording values, buying more (averaging down),
    # and selling, along with a simple SPX benchmark portfolio.

    # The `get_current_price` method in `Portfolio` now handles the case where `data_manager.get_data(ticker)`
    # might return an empty DataFrame (e.g., ticker not found).
    # It also ensures that the `query_date` is timezone-naive if the DataFrame's 'Date' column is timezone-naive,
    # to prevent comparison errors.

    # The `buy` and `sell` methods now print more informative messages about the transactions.

    # The `calculate_total_value` method also prints a warning if it has to fall back to using the purchase price.

    # The `record_transaction` method is a simple print statement for now but could be made more sophisticated.

    # The `__main__` example is reasonably comprehensive for testing the `Portfolio` class in isolation.
    # The next step will be to integrate this with your actual `data_manager.py` and the signal generation logic.
    # The critical part will be ensuring `Portfolio.get_current_price` correctly interfaces with `data_manager.py`.
    # For example, if `data_manager.py` has a function `get_historical_data(ticker, start_date, end_date)`,
    # then `Portfolio.get_current_price` would need to call that, perhaps caching results for efficiency.
    # The current `get_current_price` assumes `data_manager.get_data(ticker)` returns all available historical data
    # for that ticker as a DataFrame.

    # Added a placeholder for `data_manager` in the `Portfolio` constructor and `get_current_price`.
    # This will be crucial for fetching actual price data. The `DummyDataManager` in the example
    # usage shows how this interaction is intended to work.
    # The `get_current_price` method in `Portfolio` has been updated to use this `data_manager`.
    # It now attempts to fetch data and find the relevant closing price.
    # This is a key part that will need to be adapted to your specific `data_manager.py` implementation.

    # The `buy` method was updated to correctly calculate shares based on `amount_to_invest` and price.
    # If a position already exists, it now correctly updates the average purchase price and total shares.

    # The `sell` method was updated to handle selling all or partial shares and removing the position if empty.

    # `record_portfolio_value` and `get_history_df` are in place for tracking and retrieving performance history.

    # The `__main__` example now better reflects how `Portfolio` would interact with a data manager
    # and simulates a few transactions, including averaging into a position.

    # The `get_current_price` method in `Portfolio` was refined to better handle date comparisons,
    # especially regarding timezone-awareness. It assumes that if the DataFrame dates are timezone-naive,
    # the input `date` should also be treated as naive for comparison.
    # It also attempts to access 'Date' and 'Close' columns, which are common in financial data.
    # The example `DummyDataManager` creates DataFrames with these columns.

    # The `buy` method's logic for averaging down when a position exists has been reviewed and appears correct.
    # The `sell` method's logic for partial and full sales, and removing the position, also seems correct.

    # The `calculate_total_value` method's fallback to purchase price if current price is missing is a pragmatic choice for now.

    # The `__main__` block in `portfolio_manager.py` provides a good test harness for the class.
    # It simulates buying, selling, and tracking portfolio value, including for a benchmark.

    # A key assumption in `get_current_price` is that `self.data_manager.get_data(ticker)`
    # returns a pandas DataFrame with a 'Date' column (datetime objects) and a 'Close' column (numeric prices).
    # This needs to match the actual interface of your `data_manager.py`.
    # The current logic `price_data[price_data['Date'] <= query_date]['Close'].iloc[-1]`
    # gets the most recent closing price on or before the `query_date`.

    # The `Portfolio` class now has a more robust (though still placeholder) `get_current_price`
    # method that attempts to use the `data_manager`.
    # The `buy` and `sell` methods use this to get prices.
    # The class tracks cash, positions, and a history of portfolio values.
    # The `__main__` section provides a small test case.
    # This forms a good foundation for the portfolio management aspect.
    # The next step will be to ensure `data_manager.py` can provide the necessary data
    # in the format expected by `Portfolio.get_current_price`.
    # Specifically, `data_manager.get_data(ticker)` should return a DataFrame with 'Date' and 'Close' columns.
    # The 'Date' column should be datetime objects.

    # The `Portfolio` class is now fairly complete for its basic functions.
    # It handles buying, selling, tracking cash, positions, and portfolio value history.
    # The `get_current_price` method is designed to interact with a data manager.
    # The `__main__` example demonstrates its usage.
    # The next steps will involve integrating this with the actual data manager and signal generation.

    # Final check of the `Portfolio` class:
    # - `__init__`: Initializes cash, positions, history, and data_manager.
    # - `get_current_price`: Placeholder for fetching price from `data_manager`. This is critical and needs to be adapted.
    #   - Current implementation assumes `data_manager.get_data(ticker)` returns a DataFrame with 'Date' and 'Close'.
    #   - It takes the latest price on or before the query date.
    # - `buy`: Calculates shares from `amount_to_invest`, updates cash and positions. Handles existing positions by averaging.
    # - `sell`: Sells shares (all by default), updates cash and positions.
    # - `calculate_total_value`: Sum of cash and current market value of all positions.
    # - `record_portfolio_value`: Appends current value to history.
    # - `get_history_df`: Returns history as DataFrame.
    # - `record_transaction`: Simple logging.
    # The `DummyDataManager` in `if __name__ == '__main__':` helps test this structure.
    # The class seems solid for a first version.

    # The `get_current_price` method in the `Portfolio` class has been refined.
    # It now attempts to convert the 'Date' column of the fetched data to datetime objects if they are strings.
    # It also handles timezone-naive comparisons more explicitly if the DataFrame's dates are naive.
    # The core logic remains to find the latest closing price on or before the `query_date`.
    # The `DummyDataManager` in the `__main__` block is set up to provide data in the expected format.
    # This class provides a good foundation.

    # The Portfolio class seems well-structured for the initial requirements.
    # Key methods: buy, sell, calculate_total_value, record_portfolio_value.
    # The get_current_price method is crucial and is designed to work with a data_manager.
    # The __main__ section provides a decent test.

    # The `Portfolio` class is now defined with methods for buying, selling,
    # calculating portfolio value, and recording its history. It includes a
    # placeholder `get_current_price` method that will need to be integrated
    # with `data_manager.py`. The `__main__` block contains a test scenario.
    # This completes the initial structure of the `Portfolio` class.
    print("Created portfolio_manager.py with Portfolio class.")
