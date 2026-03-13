from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Broker settings
    # comma-separated list of enabled brokers: e.g. "ALPACA"
    enabled_brokers = db.Column(db.String(255), default="ALPACA")
    
    # Alpaca credentials (encrypted/hashed in production, here we use string for simplicity)
    alpaca_key = db.Column(db.String(255), nullable=True)
    alpaca_secret = db.Column(db.String(255), nullable=True)
    alpaca_paper = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<User {self.username}>'
