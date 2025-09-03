from pybit.unified_trading import HTTP
import time
import logging
import random
import pandas as pd
from datetime import datetime, timezone, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class BybitFuturesClient:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = self._create_session()
        self.instrument_info_cache = {}

    def _create_session(self):
        """Creates a new pybit session for live futures trading"""
        recv_window = 10000
        return HTTP(
            testnet=False,
            api_key=self.api_key,
            api_secret=self.api_secret,
            recv_window=recv_window
        )

    def get_account_balance(self, asset="USDT", max_retries=3):
        """Gets the USDT balance from UNIFIED account with retry logic."""
        for attempt in range(max_retries):
            try:
                session = self._create_session()
                account_type = "UNIFIED"

                wallet_balance = session.get_wallet_balance(accountType=account_type, coin=asset)
                logger.debug(f"get_wallet_balance response: {wallet_balance}")

                if wallet_balance and wallet_balance.get("retCode") == 0:
                    result_list = wallet_balance.get("result", {}).get("list", [])
                    if not result_list:
                        logger.warning(f"No wallet data found for {asset} in UNIFIED account.")
                        return 0.0

                    account_info = result_list[0]
                    coins_list = account_info.get("coin", [])

                    for asset_info in coins_list:
                        if asset_info.get("coin") == asset:
                            balance_str = asset_info.get("walletBalance")
                            if balance_str:
                                balance = float(balance_str)
                                logger.info(f"{asset} balance found: {balance}")
                                return balance
                            else:
                                logger.warning(f"'walletBalance' field for {asset} not found.")
                                return 0.0

                    logger.warning(f"{asset} not found in coin list for UNIFIED account.")
                    return 0.0
                else:
                    ret_code = wallet_balance.get('retCode', 'N/A')
                    ret_msg = wallet_balance.get('retMsg', 'Unknown error')
                    logger.error(f"Attempt {attempt + 1}: API error getting balance: {ret_msg} (Code: {ret_code})")

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed getting balance: {e}")

            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.info(f"Retrying get_account_balance in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            else:
                logger.error("Maximum retries reached for get_account_balance. Returning None.")
                return None

        return None

    def get_symbol_price(self, symbol, max_retries=3):
        """Gets current market price for a futures symbol."""
        for attempt in range(max_retries):
            try:
                session = self._create_session()
                params = {"symbol": symbol, "category": "linear"}
                response = session.get_tickers(**params)

                logger.debug(f"get_symbol_price API response: {response}")

                if response and response.get("retCode") == 0:
                    result_list = response.get("result", {}).get("list", [])
                    if result_list:
                        price_str = result_list[0].get("lastPrice")
                        if price_str:
                            price = float(price_str)
                            logger.info(f"Current price for {symbol}: {price}")
                            return price
                        else:
                            logger.error(f"Could not find 'lastPrice' for {symbol} in response.")
                            return None
                    else:
                        logger.error(f"Empty result list when getting price for {symbol}.")
                        return None
                else:
                    ret_code = response.get('retCode', 'N/A')
                    ret_msg = response.get('retMsg', 'Unknown error')
                    logger.error(f"Attempt {attempt + 1}: API error getting price for {symbol}: {ret_msg} (Code: {ret_code})")

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed getting price for {symbol}: {e}")

            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.info(f"Retrying get_symbol_price in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Maximum retries reached for get_symbol_price({symbol}). Returning None.")
                return None
        return None

    def get_instruments_info(self, symbol=None, category="linear", max_retries=3):
        """Gets instrument information for a futures symbol."""
        cache_key = f"{symbol or 'all'}_{category}"
        if cache_key in self.instrument_info_cache:
            return self.instrument_info_cache[cache_key]

        for attempt in range(max_retries):
            try:
                session = self._create_session()
                params = {"category": category}
                if symbol:
                    params["symbol"] = symbol
                
                response = session.get_instruments_info(**params)
                logger.debug(f"get_instruments_info response for {symbol or 'all'}: {response}")

                if response and response.get("retCode") == 0:
                    result_list = response.get("result", {}).get("list", [])
                    if result_list:
                        if symbol: # If a specific symbol was requested
                            instrument_info = result_list[0]
                            self.instrument_info_cache[cache_key] = instrument_info
                            logger.info(f"Instrument info for {symbol} obtained and cached")
                            return instrument_info
                        else: # If all symbols were requested
                            self.instrument_info_cache[cache_key] = result_list
                            logger.info(f"Instrument info for all {category} symbols obtained and cached")
                            return result_list
                    else:
                        logger.warning(f"Empty result list when getting instrument info for {symbol or 'all'} in category {category}.")
                        return [] if not symbol else None
                else:
                    ret_code = response.get('retCode', 'N/A')
                    ret_msg = response.get('retMsg', 'Unknown error')
                    logger.error(f"Attempt {attempt + 1}: API error getting instrument info for {symbol or 'all'}: {ret_msg} (Code: {ret_code})")

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed getting instrument info for {symbol}: {e}")

            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.info(f"Retrying get_instruments_info for {symbol or 'all'} in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Maximum retries reached for get_instruments_info({symbol or 'all'}). Returning {'None' if symbol else '[]'}.")
                return [] if not symbol else None
        return [] if not symbol else None

    def place_order(self, symbol, side, order_type, quantity, price=None, stop_loss=None, take_profit=None, leverage=1):
        """Places an order on Bybit"""
        try:
            session = self._create_session()
            
            # Set leverage first
            if leverage > 1:
                self.set_leverage(symbol, leverage)
            
            order_params = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": order_type,
                "qty": str(quantity),
            }
            
            if price and order_type == "Limit":
                order_params["price"] = str(price)
            
            if stop_loss:
                order_params["stopLoss"] = str(stop_loss)
            
            if take_profit:
                order_params["takeProfit"] = str(take_profit)
            
            response = session.place_order(**order_params)
            
            if response and response.get("retCode") == 0:
                order_id = response.get("result", {}).get("orderId")
                logger.info(f"Order placed successfully: {order_id}")
                return order_id
            else:
                ret_code = response.get('retCode', 'N/A')
                ret_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"Failed to place order: {ret_msg} (Code: {ret_code})")
                return None
                
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    def set_leverage(self, symbol, leverage):
        """Sets leverage for a symbol"""
        try:
            session = self._create_session()
            response = session.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage)
            )
            
            if response and response.get("retCode") == 0:
                logger.info(f"Leverage set to {leverage} for {symbol}")
                return True
            else:
                ret_code = response.get('retCode', 'N/A')
                ret_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"Failed to set leverage: {ret_msg} (Code: {ret_code})")
                return False
                
        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            return False

    def cancel_order(self, symbol, order_id):
        """Cancels an order"""
        try:
            session = self._create_session()
            response = session.cancel_order(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
            
            if response and response.get("retCode") == 0:
                logger.info(f"Order cancelled successfully: {order_id}")
                return True
            else:
                ret_code = response.get('retCode', 'N/A')
                ret_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"Failed to cancel order: {ret_msg} (Code: {ret_code})")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    def modify_order(self, symbol, order_id, quantity=None, price=None, stop_loss=None, take_profit=None):
        """Modifies an existing order"""
        try:
            session = self._create_session()
            
            modify_params = {
                "category": "linear",
                "symbol": symbol,
                "orderId": order_id
            }
            
            if quantity:
                modify_params["qty"] = str(quantity)
            if price:
                modify_params["price"] = str(price)
            if stop_loss:
                modify_params["stopLoss"] = str(stop_loss)
            if take_profit:
                modify_params["takeProfit"] = str(take_profit)
            
            response = session.amend_order(**modify_params)
            
            if response and response.get("retCode") == 0:
                logger.info(f"Order modified successfully: {order_id}")
                return True
            else:
                ret_code = response.get('retCode', 'N/A')
                ret_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"Failed to modify order: {ret_msg} (Code: {ret_code})")
                return False
                
        except Exception as e:
            logger.error(f"Error modifying order: {e}")
            return False

    def get_open_orders(self, symbol=None):
        """Gets open orders"""
        try:
            session = self._create_session()
            params = {"category": "linear"}
            if symbol:
                params["symbol"] = symbol
                
            response = session.get_open_orders(**params)
            
            if response and response.get("retCode") == 0:
                orders = response.get("result", {}).get("list", [])
                logger.info(f"Retrieved {len(orders)} open orders")
                return orders
            else:
                ret_code = response.get('retCode', 'N/A')
                ret_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"Failed to get open orders: {ret_msg} (Code: {ret_code})")
                return []
                
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []

    def get_position_info(self, symbol=None):
        """Gets position information"""
        try:
            session = self._create_session()
            params = {"category": "linear"}
            if symbol:
                params["symbol"] = symbol
                
            response = session.get_positions(**params)
            
            if response and response.get("retCode") == 0:
                positions = response.get("result", {}).get("list", [])
                logger.info(f"Retrieved {len(positions)} positions")
                return positions
            else:
                ret_code = response.get('retCode', 'N/A')
                ret_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"Failed to get positions: {ret_msg} (Code: {ret_code})")
                return []
                
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def get_order_history(self, category="linear", symbol=None, limit=50, startTime=None, endTime=None, max_retries=3):
        """
        Gets order history for a specific symbol or all symbols.
        startTime and endTime should be in milliseconds.
        """
        for attempt in range(max_retries):
            try:
                session = self._create_session()
                params = {"category": category, "limit": limit}
                if symbol:
                    params["symbol"] = symbol
                if startTime:
                    params["startTime"] = startTime
                if endTime:
                    params["endTime"] = endTime
                
                response = session.get_order_history(**params)
                logger.debug(f"get_order_history response for {symbol or 'all'}: {response}")

                if response and response.get("retCode") == 0:
                    orders = response.get("result", {}).get("list", [])
                    logger.info(f"Retrieved {len(orders)} orders for {symbol or 'all'}")
                    return orders
                else:
                    ret_code = response.get('retCode', 'N/A')
                    ret_msg = response.get('retMsg', 'Unknown error')
                    logger.error(f"Attempt {attempt + 1}: API error getting order history for {symbol or 'all'}: {ret_msg} (Code: {ret_code})")

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed getting order history for {symbol or 'all'}: {e}")

            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.info(f"Retrying get_order_history for {symbol or 'all'} in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Maximum retries reached for get_order_history({symbol or 'all'}). Returning [].")
                return []
        return []

    def get_qty_precision(self, symbol):
        """Gets the quantity precision (number of decimal places) for a futures symbol."""
        try:
            instrument = self.get_instruments_info(symbol)
            if instrument and "lotSizeFilter" in instrument:
                qty_step_str = instrument["lotSizeFilter"].get("qtyStep")
                if qty_step_str:
                    if '.' in qty_step_str:
                        # Count decimals
                        precision = len(qty_step_str.split('.')[-1])
                        logger.debug(f"Quantity precision for {symbol} from API: {precision} (qtyStep: {qty_step_str})")
                        return precision
                    else:
                        # If qtyStep is "1", "10" etc., precision is 0
                        logger.debug(f"Quantity precision for {symbol} from API: 0 (qtyStep: {qty_step_str})")
                        return 0
                else:
                    logger.warning(f"'qtyStep' not found in lotSizeFilter for {symbol}. Using default value.")
            else:
                logger.warning(f"Could not get instrument info or lotSizeFilter for {symbol}. Using default precision.")

            # Default precision fallback for common futures pairs if API fails
            if "BTC" in symbol:
                return 3
            elif "ETH" in symbol:
                return 3
            else:
                return 2 # General default
        except Exception as e:
            logger.error(f"Error getting quantity precision for {symbol}: {e}. Using default value.")
            # Default precision fallback in case of error
            if "BTC" in symbol:
                return 3
            else:
                return 2

    def get_min_order_qty(self, symbol):
        """Gets the minimum order quantity for a futures symbol."""
        try:
            instrument = self.get_instruments_info(symbol)
            if instrument and "lotSizeFilter" in instrument:
                min_qty_str = instrument["lotSizeFilter"].get("minOrderQty")
                if min_qty_str:
                    min_qty = float(min_qty_str)
                    logger.debug(f"Minimum order quantity for {symbol} from API: {min_qty}")
                    return min_qty
                else:
                     logger.warning(f"'minOrderQty' not found in lotSizeFilter for {symbol}. Using default value.")
            else:
                logger.warning(f"Could not get instrument info or lotSizeFilter for {symbol}. Using default minimum quantity.")

            # Default minimums fallback (adjust if needed based on common pairs)
            if "BTC" in symbol:
                return 0.001
            elif "ETH" in symbol:
                 return 0.01
            else:
                return 1.0 # Default placeholder
        except Exception as e:
            logger.error(f"Error getting minimum order quantity for {symbol}: {e}. Using default value.")
             # Default minimums fallback in case of error
            if "BTC" in symbol:
                return 0.001
            else:
                return 0.01 # General default

    def format_quantity(self, symbol, quantity):
        """Formats quantity according to symbol precision"""
        precision = self.get_qty_precision(symbol)
        return round(float(quantity), precision)
