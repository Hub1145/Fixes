from app import db
from datetime import datetime
from sqlalchemy import func

class MasterAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    api_key = db.Column(db.String(255), nullable=False)
    api_secret = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FollowerAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    api_key = db.Column(db.String(255), nullable=False)
    api_secret = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    capital_allocation_percent = db.Column(db.Float, default=10.0)  # Percentage of capital to use per trade
    max_leverage = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    master_account_id = db.Column(db.Integer, db.ForeignKey('master_account.id'), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    side = db.Column(db.String(10), nullable=False)  # 'Buy' or 'Sell'
    order_type = db.Column(db.String(20), nullable=False)  # 'Market' or 'Limit'
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float)
    leverage = db.Column(db.Integer, default=1)
    stop_loss = db.Column(db.Float)
    take_profit = db.Column(db.Float)
    master_order_id = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'executed', 'failed', 'cancelled'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed_at = db.Column(db.DateTime)
    
    master_account = db.relationship('MasterAccount', backref='trades')

class CopiedTrade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_trade_id = db.Column(db.Integer, db.ForeignKey('trade.id'), nullable=False)
    follower_account_id = db.Column(db.Integer, db.ForeignKey('follower_account.id'), nullable=False)
    follower_order_id = db.Column(db.String(100))
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed_at = db.Column(db.DateTime)
    
    original_trade = db.relationship('Trade', backref='copied_trades')
    follower_account = db.relationship('FollowerAccount', backref='copied_trades')

class SystemSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TradeHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trade_id = db.Column(db.Integer, db.ForeignKey('trade.id'), nullable=False)
    account_type = db.Column(db.String(10), nullable=False)  # 'master' or 'follower'
    account_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(50), nullable=False)  # 'opened', 'closed', 'modified', 'cancelled'
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    trade = db.relationship('Trade', backref='history')
