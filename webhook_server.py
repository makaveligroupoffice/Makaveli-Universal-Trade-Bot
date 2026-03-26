import logging
import os
import datetime
import json
import jwt
from functools import wraps

from flask import Flask, request, jsonify, render_template
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from config import Config
from broker_alpaca import AlpacaBroker, PositionIntent, OrderSide
from risk import RiskManager
from notifications import send_notification
from scanner import Scanner
from models import db, User, bcrypt

os.makedirs(Config.LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(Config.LOG_DIR, "tradebot.log")),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("tradebot")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
bcrypt.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

broker = AlpacaBroker()
risk = RiskManager()
scanner = Scanner()


def _get_authenticated_user(req):
    # 1. Check for valid JWT token in Authorization header
    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            data = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
            user = User.query.get(data['user_id'])
            if user:
                return user
        except:
            pass

    # 2. Check for legacy webhook secret (for backward compatibility with TradingView alerts)
    secret = ""
    if req.is_json:
        secret = (req.get_json(silent=True) or {}).get("secret", "")
    header_secret = req.headers.get("X-Webhook-Secret", "")
    if (secret and secret == Config.WEBHOOK_SECRET) or (
        header_secret and header_secret == Config.WEBHOOK_SECRET
    ):
        # Associate with the first user in the database or a default user
        return User.query.first()

    # 3. Check for Flask-Login session (for browser-based requests)
    if current_user.is_authenticated:
        return current_user

    return None


def _auth_ok(req) -> bool:
    return _get_authenticated_user(req) is not None


@app.route("/register", methods=["GET", "POST"])
def register():
    if not Config.ALLOW_REGISTRATION:
        return jsonify({"ok": False, "error": "Registration is currently disabled"}), 403

    if request.method == "GET":
        return render_template("register.html")

    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    email = data.get("email")

    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password required"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"ok": False, "error": "Username already exists"}), 409

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(username=username, password=hashed_password, email=email)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"ok": True, "message": "User registered successfully"}), 201


@app.get("/user/broker_settings")
@login_required
def get_broker_settings():
    return jsonify({
        "ok": True,
        "enabled_brokers": current_user.enabled_brokers.split(",") if current_user.enabled_brokers else [],
        "alpaca": {
            "key": current_user.alpaca_key,
            "secret": "*******" if current_user.alpaca_secret else None,
            "paper": current_user.alpaca_paper
        }
    })


@app.post("/user/broker_settings")
@login_required
def update_broker_settings():
    data = request.get_json(silent=True) or {}
    
    if "enabled_brokers" in data:
        brokers = data.get("enabled_brokers")
        if isinstance(brokers, list):
            current_user.enabled_brokers = ",".join(brokers)
    
    if "alpaca" in data:
        alp_data = data["alpaca"]
        if "key" in alp_data:
            current_user.alpaca_key = alp_data["key"]
        if "secret" in alp_data:
            current_user.alpaca_secret = alp_data["secret"]
        if "paper" in alp_data:
            current_user.alpaca_paper = bool(alp_data["paper"])
            
    db.session.commit()
    return jsonify({"ok": True, "message": "Broker settings updated successfully"})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(username=username).first()
    if user and bcrypt.check_password_hash(user.password, password):
        login_user(user)
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, Config.SECRET_KEY, algorithm="HS256")
        return jsonify({"ok": True, "token": token, "message": "Logged in successfully"}), 200

    return jsonify({"ok": False, "error": "Invalid username or password"}), 401


@app.post("/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"ok": True, "message": "Logged out successfully"}), 200


@app.post("/webhook")
def webhook():
    user = _get_authenticated_user(request)
    if not user:
        log.warning("Unauthorized webhook request blocked")
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    log.info(f"webhook received from user {user.username}: {data}")

    # Initialize user-specific broker if applicable
    active_broker = broker
    if user.alpaca_key and user.alpaca_secret:
        active_broker = AlpacaBroker(
            key=user.alpaca_key, 
            secret=user.alpaca_secret, 
            paper=user.alpaca_paper
        )

    action = (data.get("action") or "").lower()
    symbol = (data.get("symbol") or "").upper()
    qty = float(data.get("qty") or 0)
    alert_id = data.get("alert_id") or data.get("id") or ""
    extended_hours = data.get("extended_hours", Config.ENABLE_EXTENDED_HOURS)
    if isinstance(extended_hours, str):
        extended_hours = extended_hours.lower() == "true"

    # Option specific fields
    is_option = data.get("is_option", False)
    option_symbol = (data.get("option_symbol") or "").upper()
    side = data.get("side", "").lower() # buy/sell
    intent = data.get("intent", "").lower() # buy_to_open, sell_to_close, etc.
    legs = data.get("legs") # list of leg dicts
    limit_price = data.get("limit_price")

    log.info(f"→ Parsed trade | action={action} | symbol={symbol} | qty={qty} | is_option={is_option} | alert_id={alert_id}")

    if action == "status":
        try:
            acct = active_broker.get_account()
            positions = active_broker.get_open_positions()
            summary = risk.get_daily_summary()
            
            equity = f"${float(acct.equity):,.2f}" if acct else "N/A"
            pnl = f"${summary['daily_pnl']:,.2f}"
            trades = summary["trades_count"]
            
            pos_list = []
            for p in positions:
                side = "LONG" if float(p.qty) > 0 else "SHORT"
                pos_list.append(f"{p.symbol} ({side}): {abs(float(p.qty))} @ ${float(p.avg_entry_price):.2f}")
            
            pos_str = "\n".join(pos_list) if pos_list else "None"
            
            msg = (
                f"📊 Bot Status Report\n"
                f"Equity: {equity}\n"
                f"Daily PnL: {pnl}\n"
                f"Trades Today: {trades}\n"
                f"Open Positions:\n{pos_str}"
            )
            send_notification(msg, title="Bot Status")
            return jsonify({"ok": True, "message": "Status sent to phone"}), 200
        except Exception as e:
            log.exception(f"Failed to get status: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    if action == "scan":
        try:
            report = scanner.get_recommendation_report()
            send_notification(report, title="Market Scan Report")
            return jsonify({"ok": True, "message": "Scan report sent to phone"}), 200
        except Exception as e:
            log.exception(f"Failed to run scan: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    if action == "option":
        try:
            order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
            pos_intent = None
            if intent:
                pos_intent = PositionIntent(intent)
            
            order = active_broker.submit_option_order(
                symbol=option_symbol or symbol,
                qty=qty,
                side=order_side,
                position_intent=pos_intent,
                limit_price=limit_price,
                legs=legs
            )
            msg = f"Option trade executed: {intent or side} {qty} {option_symbol or symbol}"
            send_notification(msg, title="Option Trade")
            risk.mark_alert_seen(alert_id)
            return jsonify({"ok": True, "order_id": getattr(order, "id", None)}), 200
        except Exception as e:
            log.exception(f"❌ Option order failed: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    if action not in {"buy", "sell"}:
        return jsonify({"ok": False, "error": "action must be buy/sell/status/scan"}), 400

    if not symbol:
        return jsonify({"ok": False, "error": "symbol required"}), 400

    if action == "buy" and qty <= 0:
        return jsonify({"ok": False, "error": "qty must be > 0 for buy"}), 400

    if risk.seen_alert(alert_id):
        log.warning(f"Duplicate alert blocked: {alert_id}")
        return jsonify({"ok": False, "error": "duplicate alert"}), 409

    # Market clock for risk checks
    clock = active_broker.get_clock()
    current_hhmm = None
    if clock:
        current_hhmm = int(clock.timestamp.strftime("%H%M"))

    if not risk.can_trade(is_exit=(action == "sell"), current_hhmm=current_hhmm):
        return jsonify({"ok": False, "error": "risk rules blocked trade"}), 403

    current_qty = active_broker.get_position_qty(symbol)
    log.info(f"📌 Position check | {symbol} currently_qty={current_qty}")

    if action == "sell" and current_qty <= 0:
        return jsonify({"ok": False, "error": f"No position to sell for {symbol}"}), 409

    if action == "buy" and current_qty != 0:
        return jsonify({"ok": False, "error": f"Already holding {symbol}"}), 409

    open_positions = active_broker.get_open_positions_count()
    if action == "buy" and open_positions >= Config.MAX_OPEN_POSITIONS:
        return jsonify(
            {"ok": False, "error": f"max open positions reached ({open_positions})"},
        ), 403

    # Success rate optimization: Block entry if bid-ask spread is too wide
    if action == "buy" and not risk.check_spread(symbol):
        log.warning(f"Trade blocked: spread too wide for {symbol}")
        return jsonify({"ok": False, "error": "spread too wide"}), 403

    limit_price = None
    if Config.USE_LIMIT_ORDERS or extended_hours:
        latest_price = active_broker.get_latest_mid_price(symbol)
        if latest_price:
            if action == "buy":
                limit_price = latest_price * (1 + (Config.LIMIT_OFFSET_PCT / 100.0))
            else:
                limit_price = latest_price * (1 - (Config.LIMIT_OFFSET_PCT / 100.0))
        elif extended_hours:
            log.error(f"Cannot execute extended hours trade for {symbol}: No limit price available")
            return jsonify({"ok": False, "error": "limit price required for extended hours"}), 400

    try:
        if action == "buy":
            order = active_broker.buy(symbol, qty, limit_price=limit_price, extended_hours=extended_hours)
        else: # action == "sell"
            # If we are closing a position, use sell_all to handle long/short
            order = active_broker.sell_all(symbol, limit_price=limit_price, extended_hours=extended_hours)
            qty = current_qty
        
        msg = f"Webhook trade executed: {action.upper()} {qty} {symbol}"
        send_notification(msg, title="Webhook Trade")
    except Exception as e:
        log.exception(f"❌ Order failed: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

    # Record alert only after order is submitted successfully
    risk.mark_alert_seen(alert_id)
    # Note: record_trade(0.0) removed from here. 
    # Proper PnL tracking and trade count recording is handled in bot_runner reconciliation 
    # to ensure it reflects actual filled orders.

    response = {
        "ok": True,
        "action": action,
        "symbol": symbol,
        "qty": qty,
        "order_id": getattr(order, "id", None),
        "status": str(getattr(order, "status", None)),
    }
    log.info(f"✅ Order response: {response}")
    return jsonify(response), 200


@app.get("/health")
def health():
    return jsonify({"ok": True}), 200


@app.post("/submit_logs")
def submit_logs():
    if not _auth_ok(request):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    logs_to_submit = data.get("logs", [])
    bot_id = data.get("bot_id", "unknown_bot")

    if not logs_to_submit:
        return jsonify({"ok": False, "error": "No logs provided"}), 400

    # Ensure central_logs directory exists
    central_logs_dir = os.path.join(Config.LOG_DIR, "central_logs")
    os.makedirs(central_logs_dir, exist_ok=True)

    # Store logs in a file for this bot
    log_file_path = os.path.join(central_logs_dir, f"{bot_id}_trades.jsonl")
    
    try:
        with open(log_file_path, "a", encoding="utf-8") as f:
            for entry in logs_to_submit:
                f.write(json.dumps(entry) + "\n")
        
        log.info(f"Received {len(logs_to_submit)} logs from {bot_id}")
        return jsonify({"ok": True, "received": len(logs_to_submit)}), 200
    except Exception as e:
        log.error(f"Error saving submitted logs from {bot_id}: {e}")
        return jsonify({"ok": True, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)