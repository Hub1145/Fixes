from flask import render_template, request, redirect, url_for, flash, jsonify
from app import app, db
from models import MasterAccount, FollowerAccount, Trade, CopiedTrade, SystemSettings, TradeHistory
from bybit_client import BybitFuturesClient
from trade_copier import trade_copier
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@app.route('/')
def dashboard():
    """Main dashboard"""
    # Get summary statistics
    master_accounts = MasterAccount.query.filter_by(is_active=True).count()
    follower_accounts = FollowerAccount.query.filter_by(is_active=True).count()
    
    # Recent trades (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_trades = Trade.query.filter(Trade.created_at >= yesterday).count()
    
    # Recent copied trades
    recent_copied = CopiedTrade.query.filter(CopiedTrade.created_at >= yesterday).count()
    
    # Get latest trades for display
    latest_trades = Trade.query.order_by(Trade.created_at.desc()).limit(10).all()
    
    return render_template('dashboard.html', 
                         master_accounts=master_accounts,
                         follower_accounts=follower_accounts,
                         recent_trades=recent_trades,
                         recent_copied=recent_copied,
                         latest_trades=latest_trades)

@app.route('/users')
def users():
    """User management page"""
    master_accounts = MasterAccount.query.all()
    follower_accounts = FollowerAccount.query.all()
    
    return render_template('users.html', 
                         master_accounts=master_accounts,
                         follower_accounts=follower_accounts)

@app.route('/add_master', methods=['POST'])
def add_master():
    """Add a new master account"""
    name = request.form.get('name')
    api_key = request.form.get('api_key')
    api_secret = request.form.get('api_secret')
    
    if not all([name, api_key, api_secret]):
        flash('All fields are required', 'error')
        return redirect(url_for('users'))
    
    # Test the API connection
    try:
        client = BybitFuturesClient(api_key, api_secret)
        balance = client.get_account_balance()
        if balance is None:
            flash('Invalid API credentials', 'error')
            return redirect(url_for('users'))
    except Exception as e:
        flash(f'API connection failed: {str(e)}', 'error')
        return redirect(url_for('users'))
    
    master_account = MasterAccount(
        name=name,
        api_key=api_key,
        api_secret=api_secret
    )
    
    db.session.add(master_account)
    db.session.commit()
    
    flash('Master account added successfully', 'success')
    return redirect(url_for('users'))

@app.route('/add_follower', methods=['POST'])
def add_follower():
    """Add a new follower account"""
    name = request.form.get('name')
    api_key = request.form.get('api_key')
    api_secret = request.form.get('api_secret')
    capital_allocation = float(request.form.get('capital_allocation', 10.0))
    max_leverage = int(request.form.get('max_leverage', 10))
    
    if not all([name, api_key, api_secret]):
        flash('All fields are required', 'error')
        return redirect(url_for('users'))
    
    # Test the API connection
    try:
        client = BybitFuturesClient(api_key, api_secret)
        balance = client.get_account_balance()
        if balance is None:
            flash('Invalid API credentials', 'error')
            return redirect(url_for('users'))
    except Exception as e:
        flash(f'API connection failed: {str(e)}', 'error')
        return redirect(url_for('users'))
    
    follower_account = FollowerAccount(
        name=name,
        api_key=api_key,
        api_secret=api_secret,
        capital_allocation_percent=capital_allocation,
        max_leverage=max_leverage
    )
    
    db.session.add(follower_account)
    db.session.commit()
    
    flash('Follower account added successfully', 'success')
    return redirect(url_for('users'))

@app.route('/toggle_account/<account_type>/<int:account_id>')
def toggle_account(account_type, account_id):
    """Toggle account active status"""
    if account_type == 'master':
        account = MasterAccount.query.get_or_404(account_id)
    else:
        account = FollowerAccount.query.get_or_404(account_id)
    
    account.is_active = not account.is_active
    db.session.commit()
    
    status = 'activated' if account.is_active else 'deactivated'
    flash(f'Account {status} successfully', 'success')
    return redirect(url_for('users'))

@app.route('/delete_account/<account_type>/<int:account_id>')
def delete_account(account_type, account_id):
    """Delete an account"""
    if account_type == 'master':
        account = MasterAccount.query.get_or_404(account_id)
    else:
        account = FollowerAccount.query.get_or_404(account_id)
    
    db.session.delete(account)
    db.session.commit()
    
    flash('Account deleted successfully', 'success')
    return redirect(url_for('users'))

@app.route('/trades')
def trades():
    """Trade history and management"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    trades = Trade.query.order_by(Trade.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('trades.html', trades=trades)

@app.route('/trade/<int:trade_id>')
def trade_detail(trade_id):
    """Trade detail with copied trades"""
    trade = Trade.query.get_or_404(trade_id)
    copied_trades = CopiedTrade.query.filter_by(original_trade_id=trade_id).all()
    trade_history = TradeHistory.query.filter_by(trade_id=trade_id).order_by(TradeHistory.timestamp.desc()).all()
    
    return render_template('trade_detail.html', 
                         trade=trade, 
                         copied_trades=copied_trades,
                         trade_history=trade_history)

@app.route('/settings')
def settings():
    """System settings"""
    settings = SystemSettings.query.all()
    return render_template('settings.html', settings=settings)

@app.route('/update_setting', methods=['POST'])
def update_setting():
    """Update a system setting"""
    key = request.form.get('key')
    value = request.form.get('value')
    description = request.form.get('description', '')
    
    setting = SystemSettings.query.filter_by(key=key).first()
    if setting:
        setting.value = value
        setting.description = description
        setting.updated_at = datetime.utcnow()
    else:
        setting = SystemSettings(key=key, value=value, description=description)
        db.session.add(setting)
    
    db.session.commit()
    flash('Setting updated successfully', 'success')
    return redirect(url_for('settings'))

@app.route('/start_copier')
def start_copier():
    """Start the trade copier service"""
    trade_copier.start()
    flash('Trade copier service started', 'success')
    return redirect(url_for('dashboard'))

@app.route('/stop_copier')
def stop_copier():
    """Stop the trade copier service"""
    trade_copier.stop()
    flash('Trade copier service stopped', 'warning')
    return redirect(url_for('dashboard'))

@app.route('/api/account_balance/<account_type>/<int:account_id>')
def api_account_balance(account_type, account_id):
    """API endpoint to get account balance"""
    try:
        if account_type == 'master':
            account = MasterAccount.query.get_or_404(account_id)
        else:
            account = FollowerAccount.query.get_or_404(account_id)
        
        client = BybitFuturesClient(account.api_key, account.api_secret)
        balance = client.get_account_balance()
        
        return jsonify({
            'success': True,
            'balance': balance
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/copier_status')
def api_copier_status():
    """API endpoint to get trade copier service status"""
    return jsonify({
        'running': trade_copier.running,
        'status': 'running' if trade_copier.running else 'stopped'
    })

@app.route('/api/connections_status')
def api_connections_status():
    """API endpoint to check API connections status"""
    try:
        # Check master accounts
        master_accounts = MasterAccount.query.filter_by(is_active=True).all()
        follower_accounts = FollowerAccount.query.filter_by(is_active=True).all()
        
        total_accounts = len(master_accounts) + len(follower_accounts)
        connected_accounts = 0
        failed_connections = []
        
        # Test master account connections
        for account in master_accounts:
            try:
                client = BybitFuturesClient(account.api_key, account.api_secret)
                balance = client.get_account_balance()
                if balance is not None:
                    connected_accounts += 1
                else:
                    failed_connections.append(f"Master: {account.name}")
            except Exception as e:
                failed_connections.append(f"Master: {account.name} - {str(e)[:50]}")
        
        # Test follower account connections
        for account in follower_accounts:
            try:
                client = BybitFuturesClient(account.api_key, account.api_secret)
                balance = client.get_account_balance()
                if balance is not None:
                    connected_accounts += 1
                else:
                    failed_connections.append(f"Follower: {account.name}")
            except Exception as e:
                failed_connections.append(f"Follower: {account.name} - {str(e)[:50]}")
        
        if total_accounts == 0:
            status = 'no_accounts'
            message = 'No accounts configured'
        elif connected_accounts == total_accounts:
            status = 'all_connected'
            message = f'All {total_accounts} accounts connected'
        elif connected_accounts > 0:
            status = 'partial_connected'
            message = f'{connected_accounts}/{total_accounts} accounts connected'
        else:
            status = 'none_connected'
            message = 'No accounts connected'
        
        return jsonify({
            'status': status,
            'message': message,
            'total_accounts': total_accounts,
            'connected_accounts': connected_accounts,
            'failed_connections': failed_connections
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error checking connections: {str(e)}',
            'total_accounts': 0,
            'connected_accounts': 0,
            'failed_connections': []
        })

@app.route('/modify_order/<int:trade_id>', methods=['POST'])
def modify_order(trade_id):
    """Modify an existing order"""
    trade = Trade.query.get_or_404(trade_id)
    
    new_sl = request.form.get('stop_loss')
    new_tp = request.form.get('take_profit')
    new_price = request.form.get('price')
    
    # Modify master order
    master_account = trade.master_account
    client = BybitFuturesClient(master_account.api_key, master_account.api_secret)
    
    success = client.modify_order(
        symbol=trade.symbol,
        order_id=trade.master_order_id,
        price=float(new_price) if new_price else None,
        stop_loss=float(new_sl) if new_sl else None,
        take_profit=float(new_tp) if new_tp else None
    )
    
    if success:
        # Update trade record
        if new_sl:
            trade.stop_loss = float(new_sl)
        if new_tp:
            trade.take_profit = float(new_tp)
        if new_price:
            trade.price = float(new_price)
        
        db.session.commit()
        
        # Also modify follower orders
        copied_trades = CopiedTrade.query.filter_by(original_trade_id=trade_id).all()
        for copied_trade in copied_trades:
            if copied_trade.follower_order_id:
                follower_client = BybitFuturesClient(
                    copied_trade.follower_account.api_key,
                    copied_trade.follower_account.api_secret
                )
                follower_client.modify_order(
                    symbol=trade.symbol,
                    order_id=copied_trade.follower_order_id,
                    price=float(new_price) if new_price else None,
                    stop_loss=float(new_sl) if new_sl else None,
                    take_profit=float(new_tp) if new_tp else None
                )
        
        flash('Order modified successfully', 'success')
    else:
        flash('Failed to modify order', 'error')
    
    return redirect(url_for('trade_detail', trade_id=trade_id))

@app.route('/cancel_order/<int:trade_id>')
def cancel_order(trade_id):
    """Cancel an order"""
    trade = Trade.query.get_or_404(trade_id)
    
    # Cancel master order
    master_account = trade.master_account
    client = BybitFuturesClient(master_account.api_key, master_account.api_secret)
    
    success = client.cancel_order(trade.symbol, trade.master_order_id)
    
    if success:
        trade.status = 'cancelled'
        db.session.commit()
        
        # Also cancel follower orders
        copied_trades = CopiedTrade.query.filter_by(original_trade_id=trade_id).all()
        for copied_trade in copied_trades:
            if copied_trade.follower_order_id:
                follower_client = BybitFuturesClient(
                    copied_trade.follower_account.api_key,
                    copied_trade.follower_account.api_secret
                )
                follower_client.cancel_order(trade.symbol, copied_trade.follower_order_id)
                copied_trade.status = 'cancelled'
        
        db.session.commit()
        flash('Order cancelled successfully', 'success')
    else:
        flash('Failed to cancel order', 'error')
    
    return redirect(url_for('trades'))

# Start the trade copier when the app starts
def start_services():
    """Start background services"""
    trade_copier.start()

# Initialize services when module is imported
with app.app_context():
    start_services()
