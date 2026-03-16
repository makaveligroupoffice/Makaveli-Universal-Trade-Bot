import os
import json
import logging
from flask import Flask, render_template, jsonify, send_from_directory
from flask_login import current_user
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
    return render_template("index.html")

@app.route("/static/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json")

@app.route("/static/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js")

@app.route("/api/stats")
def get_stats():
    try:
        # Load broker and risk data
        broker = AlpacaBroker()
        risk = RiskManager()
        
        # Get account info
        acct = broker.get_account()
        equity = float(acct.equity) if acct else 0.0
        
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
            
        return jsonify({
            "ok": True,
            "daily_pnl": risk_state.get("daily_pnl", 0.0),
            "trades_today": risk_state.get("trades_today", 0),
            "equity": equity,
            "operational_state": bot_state.get("operational_state", "SCANNING"),
            "positions": pos_data
        })
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({"ok": False, "error": str(e)})

if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
