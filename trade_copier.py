import threading
import time
import logging
from datetime import datetime, timedelta, timezone
from app import app, db
from models import MasterAccount, FollowerAccount, Trade, CopiedTrade, TradeHistory
from bybit_client import BybitFuturesClient

logger = logging.getLogger(__name__)

class TradeCopier:
    def __init__(self):
        self.running = False
        self.thread = None
        self.last_check = {}  # Track last check time for each master account
        self.initial_positions = {}  # Track initial positions when starting
        self.master_active_symbols = {} # Track active symbols for each master account
        self.last_trade_timestamps = {} # Track the timestamp of the last processed trade for each master account

    def _load_initial_positions(self):
        """Loads all active positions for master accounts on startup, ensuring the TradeCopier is aware of existing positions."""
        with app.app_context():
            master_accounts = MasterAccount.query.filter_by(is_active=True).all()
            for master_account in master_accounts:
                try:
                    client = BybitFuturesClient(master_account.api_key, master_account.api_secret)
                    # Fetch initial positions for all known symbols if available, otherwise use a default
                    # For a clean start, we might not have 'known' symbols yet.
                    # This part needs to be carefully handled to avoid fetching all symbols on startup
                    # Instead, we will rely on trade history to discover symbols.
                    # For now, we will just initialize master_active_symbols with an empty set.
                    self.master_active_symbols[master_account.id] = set()
                    self.last_trade_timestamps[master_account.id] = int(datetime.now(timezone.utc).timestamp() * 1000) # Initialize with current timestamp
                    logger.info(f"Initialized tracking for master account {master_account.id}")

                    # Optionally, fetch current open positions to populate master_active_symbols on start
                    # This is to handle cases where the bot restarts and there are existing positions
                    # This would require iterating through all possible symbols or having a known set.
                    # Given the user's new requirement to avoid polling all symbols,
                    # we will rely on trade history to populate master_active_symbols over time.
                    # However, to ensure existing positions are monitored, we need a way to get them.
                    # Let's assume for now that if there's an existing position, it will eventually
                    # generate a trade that updates our active symbols.
                    # Or, for robustness, we could fetch positions for a limited number of high-volume symbols.

                    # For initial implementation, let's stick to the new rule: only trade signals from when it starts.
                    # Therefore, no pre-loading of symbols from existing positions.
                    
                except Exception as e:
                    logger.error(f"Error initializing tracking for master account {master_account.id}: {e}")
        
    def start(self):
        """Start the trade copying service"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()
            logger.info("Trade copier service started")
            self._load_initial_positions() # Load initial positions on start (reordered)
    
    def stop(self):
        """Stop the trade copying service"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Trade copier service stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        with app.app_context():
            while self.running:
                try:
                    self._check_master_accounts()
                    time.sleep(5)  # Check every 5 seconds
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    time.sleep(10)  # Wait longer on error
    
    def _check_master_accounts(self):
        """Check all active master accounts for new trades"""
        master_accounts = MasterAccount.query.filter_by(is_active=True).all()
        
        for master_account in master_accounts:
            try:
                self._monitor_master_account(master_account)
            except Exception as e:
                logger.error(f"Error monitoring master account {master_account.id}: {e}")
    
    def _monitor_master_account(self, master_account):
        """Monitor a specific master account for new trades"""
        try:
            client = BybitFuturesClient(master_account.api_key, master_account.api_secret)
            
            # Get the last processed trade timestamp for this master account
            last_timestamp = self.last_trade_timestamps.get(master_account.id, 0)
            
            # Fetch order history since the last timestamp
            # Use a small limit to only get recent trades, if there are many updates, it will be handled in subsequent loops
            recent_orders = client.get_order_history(limit=20, startTime=last_timestamp)
            
            new_last_timestamp = last_timestamp
            
            for order in recent_orders:
                order_time = int(order.get('createdTime')) # Bybit returns createdTime in milliseconds
                
                # Only process orders that are 'Filled' or 'PartiallyFilled' and are newer than our last timestamp
                if order_time > last_timestamp and order.get('orderStatus') in ['Filled', 'PartiallyFilled']:
                    symbol = order.get('symbol')
                    if symbol:
                        # Add the symbol to the set of active symbols for this master account
                        if master_account.id not in self.master_active_symbols:
                            self.master_active_symbols[master_account.id] = set()
                        self.master_active_symbols[master_account.id].add(symbol)
                        logger.info(f"Discovered new active symbol for master account {master_account.id}: {symbol}")
                    
                    # Update the last processed timestamp
                    new_last_timestamp = max(new_last_timestamp, order_time)
            
            # Update the stored last_trade_timestamp for this master account
            if new_last_timestamp > last_timestamp:
                self.last_trade_timestamps[master_account.id] = new_last_timestamp

            # Now, monitor only the active symbols for this master account
            symbols_to_monitor = list(self.master_active_symbols.get(master_account.id, set()))
            
            # If no active symbols are found, the bot will not monitor any symbols
            # until a new trade is detected, aligning with the user's request to
            # only trade signals from when it starts.
            
            # Also include symbols from initial positions if they exist, to ensure they are monitored
            if master_account.id in self.initial_positions:
                for pos in self.initial_positions[master_account.id]:
                    symbols_to_monitor.append(pos.get('symbol'))
                symbols_to_monitor = list(set(symbols_to_monitor)) # Remove duplicates
            
            for symbol in symbols_to_monitor:
                orders = client.get_open_orders(symbol=symbol)
                positions = client.get_position_info(symbol=symbol)

                # Process new orders
                for order in orders:
                    self._process_master_order(master_account, order, client)
                    
                # Process position changes
                # This part needs to also handle closing positions and removing symbols from active_master_symbols
                current_active_positions_for_symbol = [pos for pos in positions if float(pos.get('size', 0)) != 0]
                if not current_active_positions_for_symbol and symbol in self.master_active_symbols.get(master_account.id, set()):
                    # If no active positions for this symbol, and it was previously active, remove it
                    self.master_active_symbols[master_account.id].discard(symbol)
                    logger.info(f"Removed inactive symbol {symbol} from monitoring for master account {master_account.id}.")
                
                for position in current_active_positions_for_symbol:
                    self._process_master_position(master_account, position, client)
            
        except Exception as e:
            logger.error(f"Error in _monitor_master_account for account {master_account.id}: {e}")
            # If the error is due to missing parameters for a specific API call,
            # we should log it and potentially handle it more gracefully,
            # perhaps by skipping that account or specific API call.
            # For now, general error logging is sufficient.
    
    def _process_master_order(self, master_account, order, client):
        """Process a master account order"""
        order_id = order.get('orderId')
        symbol = order.get('symbol')
        side = order.get('side')
        order_type = order.get('orderType')
        quantity = float(order.get('qty', 0))
        price = float(order.get('price', 0)) if order.get('price') else None
        
        # Check if we already processed this order
        existing_trade = Trade.query.filter_by(
            master_account_id=master_account.id,
            master_order_id=order_id
        ).first()
        
        if existing_trade:
            return  # Already processed
        
        # Create new trade record
        trade = Trade(
            master_account_id=master_account.id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            master_order_id=order_id,
            status='pending'
        )
        
        db.session.add(trade)
        db.session.commit()
        
        logger.info(f"New master trade detected: {symbol} {side} {quantity}")
        
        # Copy to follower accounts
        self._copy_trade_to_followers(trade)
    
    def _process_master_position(self, master_account, position, client):
        """Process a master account position change"""
        symbol = position.get('symbol')
        position_size = float(position.get('size', 0))
        side = position.get('side')
        entry_price = float(position.get('avgPrice', 0))
        
        # Log the active position
        logger.info(f"Master account {master_account.id} - Active position: {symbol} {side} {position_size} @ {entry_price}")
        
        # Here you would typically add logic to:
        # 1. Check if this position has already been processed (e.g., compare with a database record)
        # 2. Determine if it's a new entry, an increase/decrease in size, or an exit.
        # 3. If it's a new entry, create a 'trade' record and copy it.
        # 4. If it's a modification, update existing copied trades (e.g., adjust stop loss/take profit)
        # 5. If it's an exit, close corresponding copied trades.
        
        # For now, let's just log and consider creating a trade if it's a new position
        # A more sophisticated state management would be needed for updates/exits.
        
        # Example: if this is a new position that wasn't previously tracked as an open trade
        # (This is a simplified check; a real system would need more robust state management)
        existing_trade = Trade.query.filter_by(
            master_account_id=master_account.id,
            symbol=symbol,
            status='pending' # Assuming 'pending' or 'open' status for active trades
        ).first()
        
        if not existing_trade:
            # This is a new position, create a trade record and copy it
            trade = Trade(
                master_account_id=master_account.id,
                symbol=symbol,
                side=side,
                order_type='Market', # Assuming market entry for new positions
                quantity=position_size,
                price=entry_price,
                master_order_id=f"POS_{symbol}_{int(time.time())}", # Unique ID for position-based trades
                status='pending'
            )
            db.session.add(trade)
            db.session.commit()
            logger.info(f"New master position detected and recorded as trade: {symbol} {side} {position_size}")
            
            # Copy to follower accounts
            self._copy_trade_to_followers(trade)
        else:
            logger.info(f"Position for {symbol} already being tracked. Size: {position_size}")
    
    def _copy_trade_to_followers(self, master_trade):
        """Copy a master trade to all active follower accounts"""
        follower_accounts = FollowerAccount.query.filter_by(is_active=True).all()
        
        for follower in follower_accounts:
            try:
                self._copy_trade_to_follower(master_trade, follower)
            except Exception as e:
                logger.error(f"Error copying trade to follower {follower.id}: {e}")
    
    def _copy_trade_to_follower(self, master_trade, follower_account):
        """Copy a trade to a specific follower account"""
        try:
            follower_client = BybitFuturesClient(
                follower_account.api_key, 
                follower_account.api_secret
            )
            
            # Get follower's balance
            balance = follower_client.get_account_balance()
            if balance is None or balance <= 0:
                logger.warning(f"Insufficient balance for follower {follower_account.id}")
                return
            
            # Calculate proportional quantity based on capital allocation
            allocation_amount = balance * (follower_account.capital_allocation_percent / 100.0)
            
            # Get current price for calculation
            current_price = follower_client.get_symbol_price(master_trade.symbol)
            if current_price is None:
                logger.error(f"Could not get price for {master_trade.symbol}")
                return
            
            # Calculate quantity based on allocation
            if master_trade.order_type == "Market":
                trade_value = master_trade.quantity * current_price
            else:
                trade_value = master_trade.quantity * (master_trade.price or current_price)
            
            # Calculate follower quantity proportionally
            if trade_value > 0:
                follower_quantity = (allocation_amount / trade_value) * master_trade.quantity
            else:
                logger.error("Invalid trade value calculation")
                return
            
            # Apply minimum quantity constraints
            min_qty = follower_client.get_min_order_qty(master_trade.symbol)
            if follower_quantity < min_qty:
                logger.warning(f"Calculated quantity {follower_quantity} below minimum {min_qty}")
                follower_quantity = min_qty
            
            # Format quantity precision
            precision = follower_client.get_qty_precision(master_trade.symbol)
            follower_quantity = round(follower_quantity, precision)
            
            # Place the order
            order_id = follower_client.place_order(
                symbol=master_trade.symbol,
                side=master_trade.side,
                order_type=master_trade.order_type,
                quantity=follower_quantity,
                price=master_trade.price,
                stop_loss=master_trade.stop_loss,
                take_profit=master_trade.take_profit,
                leverage=min(master_trade.leverage or 1, follower_account.max_leverage)
            )
            
            # Record the copied trade
            copied_trade = CopiedTrade(
                original_trade_id=master_trade.id,
                follower_account_id=follower_account.id,
                follower_order_id=order_id,
                quantity=follower_quantity,
                price=master_trade.price,
                status='executed' if order_id else 'failed',
                error_message=None if order_id else 'Failed to place order'
            )
            
            if order_id:
                copied_trade.executed_at = datetime.utcnow()
            
            db.session.add(copied_trade)
            
            # Add to trade history
            history = TradeHistory(
                trade_id=master_trade.id,
                account_type='follower',
                account_id=follower_account.id,
                action='opened',
                details=f"Copied trade: {master_trade.symbol} {master_trade.side} {follower_quantity}"
            )
            
            db.session.add(history)
            db.session.commit()
            
            if order_id:
                logger.info(f"Trade copied to follower {follower_account.id}: Order {order_id}")
            else:
                logger.error(f"Failed to copy trade to follower {follower_account.id}")
                
        except Exception as e:
            logger.error(f"Error in _copy_trade_to_follower: {e}")
            
            # Record failed copy
            copied_trade = CopiedTrade(
                original_trade_id=master_trade.id,
                follower_account_id=follower_account.id,
                quantity=0,
                status='failed',
                error_message=str(e)
            )
            
            db.session.add(copied_trade)
            db.session.commit()

    def get_min_order_qty(self, symbol):
        """Fallback method for minimum quantity"""
        # Default minimums for common symbols
        if "BTC" in symbol:
            return 0.001
        elif "ETH" in symbol:
            return 0.01
        else:
            return 1.0

    def get_qty_precision(self, symbol):
        """Fallback method for quantity precision"""
        # Default precision for common symbols
        if "BTC" in symbol:
            return 3
        elif "ETH" in symbol:
            return 3
        else:
            return 2


# Global trade copier instance
trade_copier = TradeCopier()
