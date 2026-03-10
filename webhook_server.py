import logging
import os

from flask import Flask, request, jsonify

from config import Config
from broker_alpaca import AlpacaBroker
from risk import RiskManager
from notifications import send_notification

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

broker = AlpacaBroker()
risk = RiskManager()


def _auth_ok(req) -> bool:
    secret = ""
    if req.is_json:
        secret = (req.get_json(silent=True) or {}).get("secret", "")
    header_secret = req.headers.get("X-Webhook-Secret", "")
    return (secret and secret == Config.WEBHOOK_SECRET) or (
        header_secret and header_secret == Config.WEBHOOK_SECRET
    )


@app.post("/webhook")
def webhook():
    if not _auth_ok(request):
        log.warning("Unauthorized webhook request blocked")
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    log.info(f"webhook received: {data}")

    action = (data.get("action") or "").lower()
    symbol = (data.get("symbol") or "").upper()
    qty = int(data.get("qty") or 0)
    alert_id = data.get("alert_id") or data.get("id") or ""

    log.info(f"→ Parsed trade | action={action} | symbol={symbol} | qty={qty} | alert_id={alert_id}")

    if action not in {"buy", "sell"}:
        return jsonify({"ok": False, "error": "action must be buy/sell"}), 400

    if not symbol:
        return jsonify({"ok": False, "error": "symbol required"}), 400

    if action == "buy" and qty <= 0:
        return jsonify({"ok": False, "error": "qty must be > 0 for buy"}), 400

    if risk.seen_alert(alert_id):
        log.warning(f"Duplicate alert blocked: {alert_id}")
        return jsonify({"ok": False, "error": "duplicate alert"}), 409

    # Market clock for risk checks
    clock = broker.get_clock()
    current_hhmm = None
    if clock:
        current_hhmm = int(clock.timestamp.strftime("%H%M"))

    if not risk.can_trade(is_exit=(action == "sell"), current_hhmm=current_hhmm):
        return jsonify({"ok": False, "error": "risk rules blocked trade"}), 403

    current_qty = broker.get_position_qty(symbol)
    log.info(f"📌 Position check | {symbol} currently_qty={current_qty}")

    if action == "sell" and current_qty <= 0:
        return jsonify({"ok": False, "error": f"No position to sell for {symbol}"}), 409

    if action == "buy" and current_qty != 0:
        return jsonify({"ok": False, "error": f"Already holding {symbol}"}), 409

    open_positions = broker.get_open_positions_count()
    if action == "buy" and open_positions >= Config.MAX_OPEN_POSITIONS:
        return jsonify(
            {"ok": False, "error": f"max open positions reached ({open_positions})"},
        ), 403

    limit_price = None
    if Config.USE_LIMIT_ORDERS:
        latest_price = broker.get_latest_mid_price(symbol)
        if latest_price:
            if action == "buy":
                limit_price = latest_price * (1 + (Config.LIMIT_OFFSET_PCT / 100.0))
            else:
                limit_price = latest_price * (1 - (Config.LIMIT_OFFSET_PCT / 100.0))

    try:
        if action == "buy":
            order = broker.buy(symbol, qty, limit_price=limit_price)
        else: # action == "sell"
            # If we are closing a position, use sell_all to handle long/short
            order = broker.sell_all(symbol, limit_price=limit_price)
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


if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)