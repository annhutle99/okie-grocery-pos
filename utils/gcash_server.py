# utils/gcash_server.py
# Real-Time Mobile GCash QR Server & Mobile Payment Web Page for SmartRetail

from __future__ import annotations
import socket
import threading
import time
from flask import Flask, render_template_string, jsonify, redirect, url_for
import qrcode

app = Flask(__name__)

# Active transactions payment status store: sale_id -> dict
PAYMENT_SESSIONS = {}

def get_local_ip() -> str:
    """Retrieve computer's local IP address on Wi-Fi network."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ── Flask Mobile Routes ────────────────────────────────────────────────────────
MOBILE_PAYMENT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GCash Payment</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        body { background-color: #f4f6f9; color: #1e293b; display: flex; justify-content: center; min-height: 100vh; }
        .mobile-container { width: 100%; max-width: 430px; background-color: #ffffff; min-height: 100vh; display: flex; flex-direction: column; position: relative; }
        
        /* Header */
        .header { background-color: #005ce6; color: #ffffff; padding: 20px 16px 40px 16px; text-align: center; position: relative; }
        .back-arrow { position: absolute; left: 16px; top: 20px; font-size: 20px; text-decoration: none; color: white; }
        .header-title { font-size: 18px; font-weight: 600; margin-bottom: 24px; }
        .merchant-avatar { width: 64px; height: 64px; background-color: #e2e8f0; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 12px auto; font-size: 24px; font-weight: bold; color: #64748b; }
        .merchant-name { font-size: 18px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }

        /* Content Sections */
        .section { padding: 16px 20px; border-bottom: 8px solid #f4f6f9; }
        .section-label { font-size: 12px; font-weight: 700; color: #005ce6; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }
        
        .pay-row { display: flex; justify-content: space-between; align-items: center; }
        .pay-method-title { font-size: 16px; font-weight: 600; }
        .pay-method-sub { font-size: 12px; color: #005ce6; margin-top: 2px; }
        .pay-balance { text-align: right; }
        .balance-val { font-size: 15px; font-weight: 600; }
        .balance-lbl { font-size: 11px; color: #64748b; }
        .checkmark { width: 22px; height: 22px; background-color: #005ce6; border-radius: 50%; color: white; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; margin-left: 8px; }

        .summary-row { display: flex; justify-content: space-between; padding: 10px 0; font-size: 15px; color: #334155; }
        .summary-row.total { font-weight: 700; color: #0f172a; font-size: 16px; border-top: 1px solid #e2e8f0; margin-top: 8px; padding-top: 14px; }

        .notice-text { text-align: center; font-size: 13px; color: #64748b; padding: 20px; line-height: 1.4; margin-top: auto; }

        /* Pay Button */
        .btn-container { padding: 16px 20px 30px 20px; margin-top: auto; }
        .btn-pay { width: 100%; background-color: #005ce6; color: #ffffff; border: none; padding: 16px; border-radius: 30px; font-size: 16px; font-weight: 700; cursor: pointer; text-transform: uppercase; letter-spacing: 0.5px; box-shadow: 0 4px 12px rgba(0, 92, 230, 0.3); }
        .btn-pay:active { background-color: #0046b3; }
    </style>
</head>
<body>
    <div class="mobile-container">
        <div class="header">
            <span class="back-arrow">&#8592;</span>
            <div class="header-title">Payment</div>
            <div class="merchant-avatar">P</div>
            <div class="merchant-name">{{ store_name }}</div>
        </div>

        <div class="section">
            <div class="section-label">PAY WITH</div>
            <div class="pay-row">
                <div>
                    <div class="pay-method-title">GCash</div>
                    <div class="pay-method-sub">Pay now</div>
                </div>
                <div style="display: flex; align-items: center;">
                    <div class="pay-balance">
                        <div class="balance-val">PHP 5,207.19</div>
                        <div class="balance-lbl">Available Balance</div>
                    </div>
                    <div class="checkmark">&#10003;</div>
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-label">YOU ARE ABOUT TO PAY</div>
            <div class="summary-row">
                <span>Amount Due</span>
                <span>PHP {{ "%.2f"|format(total_amount) }}</span>
            </div>
            <div class="summary-row">
                <span>Discount</span>
                <span style="color: #64748b;">No available voucher &gt;</span>
            </div>
            <div class="summary-row total">
                <span>Total Amount</span>
                <span>PHP {{ "%.2f"|format(total_amount) }}</span>
            </div>
        </div>

        <div class="notice-text">
            Please review to ensure that the details are correct before you proceed.
        </div>

        <div class="btn-container">
            <form action="/api/submit_payment/{{ sale_id }}" method="POST">
                <button type="submit" class="btn-pay">PAY PHP {{ "%.2f"|format(total_amount) }}</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

MOBILE_RECEIPT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Successful</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        body { background-color: #f4f6f9; color: #1e293b; display: flex; justify-content: center; min-height: 100vh; padding: 20px; }
        .card { width: 100%; max-width: 400px; background: white; border-radius: 16px; padding: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); text-align: center; height: fit-content; margin: auto 0; }
        .success-icon { width: 64px; height: 64px; background: #22c55e; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 32px; margin: 0 auto 16px auto; }
        .amount { font-size: 28px; font-weight: 800; color: #0f172a; margin: 8px 0; }
        .ref-no { font-size: 13px; color: #64748b; margin-bottom: 20px; }
        .details-box { background: #f8fafc; border-radius: 12px; padding: 16px; text-align: left; margin-bottom: 20px; font-size: 14px; }
        .detail-row { display: flex; justify-content: space-between; padding: 6px 0; }
        .btn-pdf { width: 100%; background: #005ce6; color: white; border: none; padding: 14px; border-radius: 25px; font-size: 15px; font-weight: 700; cursor: pointer; }
    </style>
</head>
<body>
    <div class="card">
        <div class="success-icon">&#10003;</div>
        <h2 style="color: #16a34a;">Payment Successful!</h2>
        <div class="amount">PHP {{ "%.2f"|format(total_amount) }}</div>
        <div class="ref-no">Ref No: {{ payment_ref }}</div>

        <div class="details-box">
            <div class="detail-row"><span>Paid To:</span><strong>{{ store_name }}</strong></div>
            <div class="detail-row"><span>Payment Method:</span><strong>GCash E-Wallet</strong></div>
            <div class="detail-row"><span>Date & Time:</span><strong>{{ paid_at }}</strong></div>
            <div class="detail-row"><span>Status:</span><strong style="color: #16a34a;">COMPLETED</strong></div>
        </div>

        <button class="btn-pdf" onclick="window.print()">Download / Save PDF Receipt</button>
    </div>
</body>
</html>
"""


@app.route("/pay/<sale_id>")
def pay_page(sale_id):
    session = PAYMENT_SESSIONS.get(sale_id)
    if not session:
        return "Invalid or expired payment link.", 404
    return render_template_string(
        MOBILE_PAYMENT_HTML,
        sale_id=sale_id,
        store_name=session.get("store_name", "ROBINSONS SUPERMARKET CORPORATION"),
        total_amount=session.get("total_amount", 0.0)
    )


@app.route("/api/submit_payment/<sale_id>", methods=["POST"])
def submit_payment(sale_id):
    session = PAYMENT_SESSIONS.get(sale_id)
    if not session:
        return "Invalid session", 404

    ref_no = f"GCASH-{int(time.time())}"
    session["status"] = "PAID"
    session["payment_ref"] = ref_no
    session["paid_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    return redirect(url_for("receipt_page", sale_id=sale_id))


@app.route("/receipt/<sale_id>")
def receipt_page(sale_id):
    session = PAYMENT_SESSIONS.get(sale_id)
    if not session or session.get("status") != "PAID":
        return "Receipt unavailable.", 404
    return render_template_string(
        MOBILE_RECEIPT_HTML,
        store_name=session.get("store_name", "ROBINSONS SUPERMARKET CORPORATION"),
        total_amount=session.get("total_amount", 0.0),
        payment_ref=session.get("payment_ref", "GCASH-999"),
        paid_at=session.get("paid_at", "")
    )


@app.route("/api/status/<sale_id>")
def check_status(sale_id):
    session = PAYMENT_SESSIONS.get(sale_id)
    if not session:
        return jsonify({"status": "NOT_FOUND"})
    return jsonify({
        "status": session.get("status", "PENDING"),
        "payment_ref": session.get("payment_ref", ""),
        "paid_at": session.get("paid_at", "")
    })


# ── Server Helper Functions ───────────────────────────────────────────────────
SERVER_THREAD = None

def start_gcash_server(port=5001):
    """Starts the Flask mobile payment server in a background thread."""
    global SERVER_THREAD
    if SERVER_THREAD is None:
        SERVER_THREAD = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False), daemon=True)
        SERVER_THREAD.start()


def create_payment_session(sale_id: str, total_amount: float, store_name: str = "ROBINSONS SUPERMARKET CORPORATION"):
    """
    Creates a new active payment session and returns (pay_url, qr_pil_image).
    """
    PAYMENT_SESSIONS[sale_id] = {
        "status": "PENDING",
        "total_amount": total_amount,
        "store_name": store_name,
        "payment_ref": None,
        "paid_at": None
    }
    local_ip = get_local_ip()
    pay_url = f"http://{local_ip}:5001/pay/{sale_id}"

    # Generate QR Code image
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(pay_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#005ce6", back_color="#ffffff")

    return pay_url, qr_img, local_ip


def poll_payment_status(sale_id: str):
    """Returns status dict for sale_id."""
    return PAYMENT_SESSIONS.get(sale_id, {"status": "NOT_FOUND"})
