from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_bcrypt import Bcrypt
from security import SecurityManager

db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    is_admin = db.Column(db.Boolean, default=False)

    # Broker settings
    # comma-separated list of enabled brokers: e.g. "ALPACA"
    enabled_brokers = db.Column(db.String(255), default="ALPACA")
    
    # Alpaca credentials (encrypted)
    _alpaca_key_encrypted = db.Column("alpaca_key", db.String(255), nullable=True)
    _alpaca_secret_encrypted = db.Column("alpaca_secret", db.String(255), nullable=True)
    alpaca_paper = db.Column(db.Boolean, default=True)

    # Sharing authorization token for this specific user
    sharing_token = db.Column(db.String(50), nullable=True)

    @property
    def alpaca_key(self):
        return SecurityManager.decrypt(self._alpaca_key_encrypted)

    @alpaca_key.setter
    def alpaca_key(self, value):
        self._alpaca_key_encrypted = SecurityManager.encrypt(value)

    @property
    def alpaca_secret(self):
        return SecurityManager.decrypt(self._alpaca_secret_encrypted)

    @alpaca_secret.setter
    def alpaca_secret(self, value):
        self._alpaca_secret_encrypted = SecurityManager.encrypt(value)

    def __repr__(self):
        return f'<User {self.username}>'

class UserConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(255), nullable=False)
    user = db.relationship('User', backref=db.backref('configs', lazy=True))

class TradeAudit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    symbol = db.Column(db.String(20))
    action = db.Column(db.String(50))
    reason = db.Column(db.String(255))
    details = db.Column(db.Text)
    user = db.relationship('User', backref=db.backref('audits', lazy=True))
