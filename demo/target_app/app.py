import os
import time
import json
import random
import logging
from datetime import datetime, timezone

from flask import Flask, request, jsonify

app = Flask(__name__)

LOG_FILE = "/var/log/app.log"
logging.basicConfig(level=logging.INFO)

request_count = 0
error_count = 0
latencies = []


def write_log(level: str, message: str, extra: dict = None):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "service": "target-app",
    }
    if extra:
        entry.update(extra)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/metrics")
def metrics():
    global request_count, error_count, latencies
    current_count = request_count
    avg_latency = sum(latencies[-100:]) / max(len(latencies[-100:]), 1)
    error_rate = error_count / max(current_count, 1)
    return jsonify({
        "error_rate": round(error_rate, 4),
        "latency_p99": round(avg_latency * 1.5, 2),
        "request_count": current_count,
        "uptime_seconds": int(time.time() - start_time),
    })


@app.route("/checkout", methods=["POST"])
def checkout():
    global request_count, error_count

    request_count += 1
    start = time.time()

    data = request.get_json(silent=True) or {}
    coupon_code = data.get("coupon_code", "")

    try:
        is_intentionally_buggy = os.getenv("BUGGY_VERSION", "0") == "1"
        if is_intentionally_buggy:
            if coupon_code and len(coupon_code) > 0:
                if coupon_code == "BUGGY":
                    raise ValueError("Invalid coupon code: BUGGY")
                discount = calculate_discount_buggy(coupon_code)
            else:
                discount = 0.0
        else:
            if coupon_code:
                discount = calculate_discount(coupon_code)
            else:
                discount = 0.0

        latency = time.time() - start
        latencies.append(latency)

        if random.random() < 0.05:
            error_count += 1
            write_log("ERROR", "Random checkout failure", {"error": "internal_error"})
            return jsonify({"error": "Checkout failed"}), 500

        write_log("INFO", "Checkout successful", {"discount": discount, "latency": round(latency, 3)})
        return jsonify({"status": "success", "discount": discount, "total": max(100 - discount, 0)})

    except Exception as e:
        error_count += 1
        latency = time.time() - start
        latencies.append(latency)
        write_log("ERROR", f"Checkout error: {str(e)}", {"error_type": type(e).__name__})
        return jsonify({"error": str(e)}), 500


def calculate_discount(coupon_code: str) -> float:
    valid_coupons = {"SAVE10": 10.0, "SAVE20": 20.0, "FREESHIP": 5.0}
    code = coupon_code.strip().upper()
    if code in valid_coupons:
        return valid_coupons[code]
    return 0.0


def calculate_discount_buggy(coupon_code: str) -> float:
    valid_coupons = {"SAVE10": 10.0, "SAVE20": 20.0, "FREESHIP": 5.0}
    if coupon_code not in valid_coupons:
        raise KeyError(f"Coupon code '{coupon_code}' not found")
    return valid_coupons[coupon_code]


@app.route("/checkout/stress", methods=["POST"])
def stress_test():
    results = {"success": 0, "failure": 0}
    for i in range(100):
        try:
            resp = app.test_client().post("/checkout", json={"coupon_code": "SAVE10"})
            if resp.status_code == 200:
                results["success"] += 1
            else:
                results["failure"] += 1
        except Exception:
            results["failure"] += 1
    return jsonify(results)


start_time = time.time()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
