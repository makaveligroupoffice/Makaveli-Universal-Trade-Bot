import os
import sys
import json
import logging
import requests
import zipfile
import io
import csv
import threading
from flask import Flask, render_template, jsonify, send_from_directory, send_file, request, redirect, url_for
from flask_login import current_user, login_required
from flask_login import login_required as login_req

from config import Config
from broker_alpaca import AlpacaBroker
from risk import RiskManager
from webhook_server import app as webhook_app

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tradebot_web")

# We reuse the Flask app from webhook_server to keep everything on the same port
app = webhook_app

@app.route("/")
def index():
    if not current_user.is_authenticated:
        from flask import redirect, url_for
        return redirect(url_for('login'))
    return render_template("index.html")

@app.route("/static/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json")

@app.route("/static/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js")

@app.route("/api/stats")
@login_required
def get_stats():
    try:
        # Load broker and risk data
        broker = AlpacaBroker()
        risk = RiskManager()
        
        # Get account info
        acct = broker.get_account()
        equity = float(acct.equity) if acct else 0.0
        
        # Get Whale Sentiment (as proxy for market-wide order flow imbalance)
        bars = broker.data.get_recent_bars("SPY", minutes=30) if hasattr(broker, 'data') else None
        if not bars:
            from market_data import MarketDataClient
            bars = MarketDataClient().get_recent_bars("SPY", minutes=30)
        
        from strategy import Strategy
        df = Strategy._calculate_indicators(bars) if bars else None
        whale_sentiment = df['pressure_delta_ema'].iloc[-1] if df is not None else 0.0
        
        # Determine if we are using Paper or Live keys
        alpaca_paper = Config.ALPACA_PAPER
        live_mode_enabled = Config.LIVE_MODE_ENABLED
        
        # Get risk state
        with open(Config.RISK_STATE_FILE, "r") as f:
            risk_state = json.load(f)
            
        # Get bot state (operational mode)
        with open(Config.BOT_STATE_FILE, "r") as f:
            bot_state = json.load(f)
            
        # Get open positions
        positions = broker.get_open_positions()
        pos_data = []
        for p in positions:
            pos_data.append({
                "symbol": p.symbol,
                "qty": float(p.qty),
                "entry": float(p.avg_entry_price),
                "current": float(p.current_price),
                "pnl": float(p.unrealized_pl)
            })
            
        # Performance Stats
        from performance import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer(Config.TRADE_JOURNAL_FILE)
        perf = analyzer.analyze_recent_trades(days=7) or {}

        return jsonify({
            "ok": True,
            "daily_pnl": risk_state.get("daily_pnl", 0.0),
            "trades_today": risk_state.get("trades_today", 0),
            "equity": equity,
            "operational_state": bot_state.get("operational_state", "SCANNING"),
            "bot_enabled": bot_state.get("enabled", True),
            "bank_withdrawal_enabled": Config.BANK_WITHDRAWAL_ENABLED,
            "min_capital_reserve": Config.MIN_CAPITAL_RESERVE,
            "withdrawable_profit": analyzer.calculate_withdrawable_profit(equity),
            "license_revoked": bot_state.get("license_revoked", False),
            "license_id": bot_state.get("license_id", "UNKNOWN"),
            "alpaca_paper": alpaca_paper,
            "live_mode_enabled": live_mode_enabled,
            "hedge_active": risk_state.get("hedge_active", False),
            "whale_sentiment": whale_sentiment,
            "positions": pos_data,
            "sharpe_ratio": perf.get("sharpe_ratio"),
            "profit_factor": perf.get("profit_factor")
        })
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/license/check", methods=["POST"])
@login_required
def check_license_now():
    """Manually triggers a license check."""
    try:
        data = request.json or {}
        token = data.get("token")
        if token != Config.AUTH_TOKEN:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401

        from license_manager import LicenseManager
        is_valid = LicenseManager.verify_license()
        return jsonify({
            "ok": True,
            "is_valid": is_valid,
            "message": "License check completed." if is_valid else "LICENSE REVOKED BY SERVER"
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/bot/authorize", methods=["POST"])
@login_required
def authorize_bot():
    try:
        data = request.json or {}
        token = data.get("token")
        
        from bot_state import BotStateStore
        from license_manager import LicenseManager
        store = BotStateStore(Config.BOT_STATE_FILE)
        state = store.load()

        # Step 1: Check for One-Time Activation Key (ACT-XXXX-...)
        if token and token.startswith("ACT-"):
            # Verify the ACT key against the license server
            try:
                if Config.LICENSE_URL:
                    response = requests.get(Config.LICENSE_URL, timeout=10)
                    response.raise_for_status()
                    license_data = response.json()
                    
                    ids_status = license_data.get("ids", {})
                    key_status = ids_status.get(token)
                    
                    if key_status == "PENDING":
                        # Valid one-time key! Bind it to this machine.
                        machine_id = LicenseManager.get_machine_id()
                        state["sharing_authorized"] = True
                        state["licensed_machine_id"] = machine_id
                        # We store the ACT key as the LICENSE_ID for this user
                        # They will need to update their .env with this LICENSE_ID
                        store.save(state)
                        
                        logger.info(f"Bot activated with ONE-TIME KEY: {token}. Bound to: {machine_id}")
                        return jsonify({
                            "ok": True, 
                            "message": "Bot activated successfully!",
                            "details": f"Your License ID is now: {token}. Please update your .env with: LICENSE_ID={token}"
                        })
                    elif isinstance(key_status, dict) and key_status.get("machine_id"):
                        # Key already used and bound
                        return jsonify({"ok": False, "error": "This Activation Key has already been used on another machine."}), 403
                    else:
                        return jsonify({"ok": False, "error": "Invalid or Expired Activation Key."}), 401
                else:
                    return jsonify({"ok": False, "error": "LICENSE_URL not configured on server."}), 500
            except Exception as e:
                logger.error(f"Error verifying activation key: {e}")
                return jsonify({"ok": False, "error": f"Connection to license server failed: {e}"}), 500

        # Step 2: Fallback to Master SHARING_ACTIVATION_KEY (for owner's manual override)
        if token == Config.SHARING_ACTIVATION_KEY:
            state["sharing_authorized"] = True
            store.save(state)
            logger.info("Bot successfully SHARING-AUTHORIZED with Master Key.")
            return jsonify({"ok": True, "message": "Sharing authorized successfully!"})
        else:
            return jsonify({"ok": False, "error": "Invalid Activation Key or Master Key"}), 401
    except Exception as e:
        logger.error(f"Error authorizing bot sharing: {e}")
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/bot/rotate-token", methods=["POST"])
@login_required
def rotate_token():
    """Generates a new random token and updates the auth file."""
    try:
        data = request.json or {}
        token = data.get("token")
        
        # Verify current token before allowing rotation
        if token == Config.AUTH_TOKEN:
            import subprocess
            result = subprocess.run(["python3", "generate_token.py"], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("Token ROTATED via Web HUD")
                return jsonify({"ok": True, "message": "Token rotated. Please restart the bot to apply."})
            else:
                return jsonify({"ok": False, "error": f"Rotation failed: {result.stderr}"})
        else:
            return jsonify({"ok": False, "error": "Invalid current token"}), 401
    except Exception as e:
        logger.error(f"Error rotating token: {e}")
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/bot/learn-youtube", methods=["POST"])
@login_required
def learn_youtube():
    try:
        data = request.json or {}
        url = data.get("url")
        token = data.get("token")
        
        # Verify token for security
        if token != Config.AUTH_TOKEN:
            return jsonify({"ok": False, "error": "Invalid token"}), 401
            
        if not url:
            return jsonify({"ok": False, "error": "No URL provided"}), 400
            
        from learning import LearningEngine
        le = LearningEngine(Config.TRADE_JOURNAL_FILE)
        
        # This will happen in a separate thread to not block the UI
        import threading
        def process_video():
            success = le.learn_from_youtube(url)
            if success:
                logger.info(f"Successfully processed YouTube strategy: {url}")
            else:
                logger.error(f"Failed to process YouTube strategy: {url}")
        
        threading.Thread(target=process_video).start()
        
        return jsonify({"ok": True, "message": "YouTube learning started. The bot will analyze the video and evolve its strategy autonomously."})
    except Exception as e:
        logger.error(f"Error starting YouTube learning: {e}")
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/bot/reading-session", methods=["POST"])
@login_required
def reading_session():
    try:
        data = request.json or {}
        token = data.get("token")
        
        # Verify token for security
        if token != Config.AUTH_TOKEN:
            return jsonify({"ok": False, "error": "Invalid token"}), 401
            
        import subprocess
        # Run the reading session script in the background
        subprocess.Popen([sys.executable, "reading_session.py"])
        
        logger.info("Universal Reading Session TRIGGERED via Web HUD")
        return jsonify({"ok": True, "message": "Reading session started. The bot is analyzing 25+ trading classics and will update its code autonomously."})
    except Exception as e:
        logger.error(f"Error starting reading session: {e}")
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/bot/withdraw-profits", methods=["POST"])
@login_required
def withdraw_profits():
    """Manual trigger to withdraw profits to a linked bank account."""
    try:
        data = request.json or {}
        token = data.get("token")
        
        # Verify token for security
        if token != Config.AUTH_TOKEN:
            return jsonify({"ok": False, "error": "Invalid token"}), 401
            
        if not Config.BANK_WITHDRAWAL_ENABLED or not Config.BANK_ACCOUNT_ID:
            return jsonify({"ok": False, "error": "Bank withdrawal not enabled or BANK_ACCOUNT_ID missing in .env"}), 400
            
        from broker_alpaca import AlpacaBroker
        from performance import PerformanceAnalyzer
        
        broker = AlpacaBroker()
        equity = broker.get_account_equity()
        
        analyzer = PerformanceAnalyzer(Config.TRADE_JOURNAL_FILE)
        profit = analyzer.calculate_withdrawable_profit(equity)
        
        if profit <= 0:
            return jsonify({"ok": False, "error": f"No profit available to withdraw (Equity: ${equity:.2f}, Reserve: ${Config.MIN_CAPITAL_RESERVE:.2f})"}), 400
            
        # Execute withdrawal
        result = broker.withdraw_to_bank(profit, Config.BANK_ACCOUNT_ID)
        
        logger.info(f"WEEKLY PROFIT WITHDRAWAL: ${profit:.2f} sent to bank account {Config.BANK_ACCOUNT_ID}")
        return jsonify({
            "ok": True, 
            "message": f"Withdrawal of ${profit:.2f} initiated to your bank account!",
            "details": result
        })
    except Exception as e:
        logger.error(f"Error withdrawing profits: {e}")
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/bot/kill", methods=["POST"])
@login_required
def kill_switch():
    try:
        data = request.json or {}
        token = data.get("token")
        
        # Verify token for security
        if token != Config.AUTH_TOKEN:
            return jsonify({"ok": False, "error": "Invalid token"}), 401

        from bot_state import BotStateStore
        store = BotStateStore(Config.BOT_STATE_FILE)
        state = store.load()
        
        # Activate kill switch
        state["enabled"] = False
        state["kill_switch_active"] = True
        store.save(state)
        
        logger.critical("KILL SWITCH TRIGGERED via Web HUD")
        
        # Execute emergency actions
        broker = AlpacaBroker()
        
        # 1. Cancel all orders
        try:
            broker.client.cancel_orders()
            logger.info("Kill Switch: Cancel orders sent")
        except Exception as e:
            logger.error(f"Kill Switch: Failed to cancel orders: {e}")
            
        # 2. Close all positions
        try:
            positions = broker.get_open_positions()
            for pos in positions:
                broker.sell_all(pos.symbol)
                logger.info(f"Kill Switch: Closing {pos.symbol}")
        except Exception as e:
            logger.error(f"Kill Switch: Failed to close positions: {e}")
            
        from notifications import send_notification
        send_notification("CRITICAL: Kill switch activated. Bot disabled and positions closed.", title="KILL SWITCH")
        
        return jsonify({"ok": True, "message": "Kill switch activated, positions closing."})
    except Exception as e:
        logger.error(f"Error triggering kill switch: {e}")
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/bot/invest-crypto", methods=["POST"])
@login_required
def invest_crypto():
    data = request.json
    if not data or data.get("token") != Config.AUTH_TOKEN:
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    def run_investment():
        from crypto_investor import run_crypto_investor
        try:
            run_crypto_investor()
        except Exception as e:
            logger.error(f"Crypto investment scan failed: {e}")

    thread = threading.Thread(target=run_investment)
    thread.start()

    return jsonify({"ok": True, "message": "Crypto investment scan started in background."})

@app.before_request
def restrict_ip():
    if Config.IP_WHITELIST:
        client_ip = request.remote_addr
        if client_ip not in Config.IP_WHITELIST and client_ip != '127.0.0.1':
            return jsonify({"ok": False, "error": "IP Forbidden"}), 403

@app.route("/api/bot/audit-trail")
@login_required
def get_audit_trail():
    try:
        from bot_state import BotStateStore
        state = BotStateStore(Config.BOT_STATE_FILE).load()
        return jsonify({"ok": True, "audit_trail": state.get("audit_trail", [])})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/bot/toggle", methods=["POST"])
@login_required
def toggle_bot():
    try:
        from bot_state import BotStateStore
        store = BotStateStore(Config.BOT_STATE_FILE)
        state = store.load()
        
        # Invert current state
        new_status = not state.get("enabled", True)
        state["enabled"] = new_status
        store.save(state)
        
        logger.info(f"Bot {'ENABLED' if new_status else 'DISABLED'} via Web HUD")
        return jsonify({"ok": True, "enabled": new_status})
    except Exception as e:
        logger.error(f"Error toggling bot: {e}")
        return jsonify({"ok": False, "error": str(e)})

@app.route('/api/bot/setup-grid', methods=['POST'])
@login_req
def setup_grid():
    data = request.get_json()
    symbol = data.get('symbol')
    price = data.get('price')
    token = data.get('token')
    
    if token != Config.AUTH_TOKEN:
        return jsonify({"status": "error", "message": "Invalid Master Token"}), 403
        
    if not symbol or not price:
        return jsonify({"status": "error", "message": "Symbol and Price required"}), 400
        
    try:
        from broker_alpaca import AlpacaBroker
        from multi_bot import MultiBotManager
        broker = AlpacaBroker()
        manager = MultiBotManager(broker)
        manager.grid_trader.setup_grid(symbol, float(price))
        return jsonify({"status": "success", "message": f"Grid setup for {symbol}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/bot/sentiment', methods=['GET'])
@login_req
def get_sentiment():
    symbol = request.args.get('symbol', 'SPY')
    try:
        from sentiment_engine import SentimentEngine
        engine = SentimentEngine()
        score = engine.get_market_sentiment(symbol)
        return jsonify({"status": "success", "symbol": symbol, "sentiment": score})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/download/journal")
@login_required
def download_journal():
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Define columns we want in CSV
        columns = ["timestamp", "event_type", "symbol", "qty", "filled_avg_price", "pnl", "reason"]
        writer.writerow(columns)
        
        if os.path.exists(Config.TRADE_JOURNAL_FILE):
            with open(Config.TRADE_JOURNAL_FILE, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        row = [data.get(col, "") for col in columns]
                        writer.writerow(row)
                    except:
                        continue
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='trade_journal.csv'
        )
    except Exception as e:
        logger.error(f"Error downloading journal: {e}")
        return jsonify({"ok": False, "error": str(e)})

@app.route("/download/bot")
@login_required
def download_bot():
    try:
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk('.'):
                # Exclude folders
                dirs[:] = [d for d in dirs if d not in [
                    'logs', 'instance', '.git', '__pycache__', '.idea', '.junie', 'backups', 'node_modules'
                ]]
                
                for file in files:
                    # Exclude secrets, temporary files, and hidden files
                    if file == '.env' or file.endswith('.pyc') or file == '.DS_Store' or file.startswith('.'):
                        continue
                    
                    file_path = os.path.join(root, file)
                    # Add to zip with relative path
                    archive_name = os.path.relpath(file_path, '.')
                    zf.write(file_path, archive_name)
                    
        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name='tradebot_source.zip'
        )
    except Exception as e:
        logger.error(f"Error downloading bot source: {e}")
        return jsonify({"ok": False, "error": str(e)})

if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
