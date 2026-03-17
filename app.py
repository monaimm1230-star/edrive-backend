# ==================== IMPORTS ====================
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime
import uuid
import hashlib
import time
import os
import requests
from dotenv import load_dotenv
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading

load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["http://localhost:*", "http://127.0.0.1:*", "*"])

username = os.getenv('MONGO_USERNAME', "romaisamaqbool008_db_user")
password = os.getenv('MONGO_PASSWORD', "arm256")
MONGO_URI = f"mongodb+srv://{username}:{password}@cluster0.yleenkw.mongodb.net/energy_trading?retryWrites=true&w=majority"

print("=" * 60)
print("🚀 E-Drive Cloud Marketplace Backend")
print("=" * 60)

db = None
client = None
db_users = None

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db_users = client['edrive']
    db = client['energy_trading']
    print("✅ MongoDB Cloud Connected Successfully!")
    print(f"📊 Users Database: {db_users.name}")
    print(f"📊 Trading Database: {db.name}")
except Exception as e:
    print(f"❌ MongoDB Connection Failed: {e}")
    print("⚠️  Running in offline mode")
    db = None
    db_users = None
    client = None


# ==================== BLOCKCHAIN INTEGRATION ====================

BLOCKCHAIN_URL = os.getenv('BLOCKCHAIN_URL', 'http://localhost:5050')

def ensure_blockchain_wallet(email):
    try:
        requests.post(f"{BLOCKCHAIN_URL}/api/wallet/create",
            json={"username": email}, timeout=10)
    except Exception as e:
        print(f"[WARN] Could not ensure wallet for {email}: {e}")

def record_trade_on_blockchain(buyer_email, seller_email, units, price_per_unit):
    try:
        # Wake the blockchain service first (free tier sleeps)
        try:
            requests.get(f"{BLOCKCHAIN_URL}/api/rates", timeout=30)
        except:
            pass

        # Ensure both parties have wallets
        ensure_blockchain_wallet(buyer_email)
        ensure_blockchain_wallet(seller_email)

        # Retry trade up to 2 times (in case service just woke up)
        last_error = None
        for attempt in range(2):
            try:
                response = requests.post(
                    f"{BLOCKCHAIN_URL}/api/trade",
                    json={
                        "buyer":           buyer_email,
                        "seller":          seller_email,
                        "units":           float(units),
                        "seller_price_ec": float(price_per_unit)
                    },
                    timeout=30
                )
                if response.text.strip():
                    result = response.json()
                    print(f"⛓️  Blockchain result: {result}")
                    return result
                else:
                    print(f"[WARN] Empty response on attempt {attempt+1}, retrying...")
                    time.sleep(3)
            except Exception as e:
                last_error = e
                print(f"[WARN] Attempt {attempt+1} failed: {e}")
                time.sleep(3)
        return {"success": False, "error": str(last_error)}
    except Exception as e:
        print(f"[WARN] Blockchain record failed: {e}")
        return {"success": False, "error": str(e)}

# ================================================================


def is_db_connected():
    if db is None or db_users is None or client is None:
        return False
    try:
        client.admin.command('ping')
        return True
    except:
        return False

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


# ==================== BASIC ENDPOINTS ====================

@app.route('/')
def home():
    return jsonify({
        "message": "⚡ E-Drive Energy Marketplace API",
        "status": "running",
        "version": "1.0.0",
        "database": "connected" if is_db_connected() else "disconnected",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "auth": ["POST /api/login", "POST /api/signup"],
            "marketplace": ["POST /api/sell-energy", "POST /api/buy-energy", "GET /api/energy-listings"],
            "trading": ["POST /api/confirm-trade", "GET /api/trade-history"],
            "wallet": ["GET /api/wallet", "POST /api/wallet/topup", "GET /api/rates"],
            "health": ["GET /health", "GET /api/status"]
        }
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "server": "E-Drive Backend",
        "database": "connected" if is_db_connected() else "disconnected",
        "timestamp": datetime.now().isoformat(),
        "uptime": "running"
    })

@app.route('/api/status')
def api_status():
    return jsonify({
        "success": True,
        "message": "API is operational",
        "server_time": datetime.now().isoformat(),
        "mongodb": "connected" if is_db_connected() else "disconnected"
    })


# ==================== AUTHENTICATION ENDPOINTS ====================

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        print(f"🔐 Login attempt for: {email}")

        if not email or not password:
            return jsonify({"success": False, "message": "Email and password are required"}), 400

        if not is_db_connected():
            return jsonify({"success": False, "message": "Database not connected."}), 500

        user = db_users.users.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "message": "Invalid email or password"}), 401

        stored_password = user.get('password', '')
        hashed_input = hash_password(password)
        if stored_password != hashed_input and stored_password != password:
            return jsonify({"success": False, "message": "Invalid email or password"}), 401

        session_token = str(uuid.uuid4())
        db_users.users.update_one(
            {"email": email},
            {"$set": {"session_token": session_token, "last_login": datetime.now().isoformat()}}
        )

        print(f"✅ Login successful for: {email}")
        return jsonify({
            "success": True,
            "message": "Login successful!",
            "session_token": session_token,
            "user": {
                "user_id": user.get('user_id', str(user['_id'])),
                "email": user['email'],
                "name": user.get('name', user.get('full_name', '')),
                "role": user.get('role', None),
                "wallet_balance": float(user.get('wallet_balance', 1000)),
                "phone": user.get('phone', ''),
                "address": user.get('address', '')
            }
        })
    except Exception as e:
        print(f"🔥 Login error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500


@app.route('/api/signup', methods=['POST', 'OPTIONS'])
def signup():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        print(f"📝 Signup attempt: {name} ({email})")

        if not name:
            return jsonify({"success": False, "message": "Name is required"}), 400
        if not email:
            return jsonify({"success": False, "message": "Email is required"}), 400
        if not password:
            return jsonify({"success": False, "message": "Password is required"}), 400
        if len(password) < 6:
            return jsonify({"success": False, "message": "Password must be at least 6 characters"}), 400

        if not is_db_connected():
            return jsonify({"success": False, "message": "Database not connected."}), 500

        existing_user = db_users.users.find_one({"email": email})
        if existing_user:
            return jsonify({"success": False, "message": "Email already registered"}), 400

        # ── Create EC wallet on blockchain ───────────────────────
        try:
            wallet_response = requests.post(
                f"{BLOCKCHAIN_URL}/api/wallet/create",
                json={"username": email},
                timeout=10
            )
            wallet_data = wallet_response.json()
            ec_balance = wallet_data.get("wallet", {}).get("balance", 500)
            wallet_address = wallet_data.get("wallet", {}).get("address", "")
            print(f"⛓️  EC Wallet created for {email}: {wallet_address}")
        except Exception as e:
            print(f"[WARN] Could not create blockchain wallet: {e}")
            ec_balance = 500
            wallet_address = ""
        # ────────────────────────────────────────────────────────

        user = {
            "user_id": str(uuid.uuid4()),
            "name": name,
            "email": email,
            "password": password,
            "wallet_balance": 1000.00,
            "ec_balance": ec_balance,
            "ec_wallet_address": wallet_address,
            "created_at": datetime.now().isoformat(),
            "session_token": str(uuid.uuid4())
        }

        db_users.users.insert_one(user)
        print(f"✅ New user registered: {name} ({email})")

        return jsonify({
            "success": True,
            "message": "Account created successfully!",
            "user": {
                "user_id": user['user_id'],
                "name": user['name'],
                "email": user['email'],
                "wallet_balance": user['wallet_balance'],
                "ec_balance": user['ec_balance'],
                "ec_wallet_address": user['ec_wallet_address'],
                "role": None
            },
            "session_token": user['session_token']
        }), 201

    except Exception as e:
        print(f"❌ Signup error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500


@app.route('/api/update-role', methods=['POST', 'OPTIONS'])
def update_role():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        role = data.get('role', '').strip().lower()

        if not email or not role:
            return jsonify({"success": False, "message": "Email and role required"}), 400
        if role not in ['buyer', 'seller']:
            return jsonify({"success": False, "message": "Role must be 'buyer' or 'seller'"}), 400
        if not is_db_connected():
            return jsonify({"success": False, "message": "Database not connected"}), 500

        result = db_users.users.update_one(
            {"email": email},
            {"$set": {"role": role, "role_updated_at": datetime.now().isoformat()}}
        )

        if result.matched_count > 0:
            return jsonify({"success": True, "message": f"Role updated to {role}"})
        else:
            return jsonify({"success": False, "message": "User not found"}), 404

    except Exception as e:
        print(f"❌ Update role error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ==================== WALLET & RATES ENDPOINTS ====================

@app.route('/api/wallet', methods=['GET'])
def get_wallet():
    """Get user wallet balance including EC balance from blockchain"""
    try:
        email = request.args.get('email', '').strip().lower()

        if email:
            try:
                bc_response = requests.get(
                    f"{BLOCKCHAIN_URL}/api/wallet/{email}",
                    timeout=5
                )
                bc_data = bc_response.json()
                ec_balance = bc_data.get("wallet", {}).get("balance", 500)
                ec_address = bc_data.get("wallet", {}).get("address", "")
            except Exception:
                ec_balance = 500
                ec_address = ""

            pkr_balance = 1000.00
            if is_db_connected():
                user = db_users.users.find_one({"email": email})
                if user:
                    pkr_balance = float(user.get('wallet_balance', 1000))

            return jsonify({
                "success": True,
                "email": email,
                "pkr_balance": pkr_balance,
                "ec_balance": ec_balance,
                "ec_address": ec_address,
                "last_updated": datetime.now().isoformat()
            })

        return jsonify({
            "success": True,
            "balance": 1000.00,
            "currency": "PKR",
            "ec_balance": 500,
            "last_updated": datetime.now().isoformat()
        })

    except Exception as e:
        print(f"Wallet error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/wallet/topup', methods=['POST', 'OPTIONS'])
def wallet_topup():
    """Add EC to a user's wallet (for demo/testing)"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = request.get_json() or {}
        username = data.get('username', '').strip().lower()
        amount_ec = float(data.get('amount_ec', 500))

        if not username:
            return jsonify({"success": False, "error": "username required"}), 400

        response = requests.post(
            f"{BLOCKCHAIN_URL}/api/wallet/topup",
            json={"username": username, "amount_ec": amount_ec},
            timeout=10
        )
        return jsonify(response.json())
    except Exception as e:
        print(f"❌ Topup error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/rates', methods=['GET'])
def get_rates():
    """Get current energy rate period from blockchain"""
    try:
        response = requests.get(f"{BLOCKCHAIN_URL}/api/rates", timeout=5)
        return jsonify(response.json())
    except Exception as e:
        # Return fallback rates if blockchain is down
        return jsonify({
            "success": True,
            "rates": {
                "period": "off_peak",
                "ec_per_unit": 2.0,
                "pkr_per_unit": 24,
                "label": "Off-Peak 🟢",
                "hours": "10PM - 6AM"
            }
        })


# ==================== ENERGY LISTING ENDPOINTS ====================

@app.route('/api/energy-offer', methods=['POST', 'OPTIONS'])
def create_energy_offer():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = request.get_json()
        if not is_db_connected():
            return jsonify({"success": True, "message": "Offer saved (demo mode)"})

        offer_doc = {
            "offer_id": str(uuid.uuid4()),
            "user_id": data.get('user_id'),
            "email": data.get('email'),
            "name": data.get('name'),
            "role": "seller",
            "packets": data.get('packets'),
            "price_per_packet": data.get('price_per_packet'),
            "total_value": data.get('total_value'),
            "latitude": data.get('latitude'),
            "longitude": data.get('longitude'),
            "location_string": data.get('location_string'),
            "status": data.get('status', 'available'),
            "created_at": datetime.now().isoformat()
        }

        db.offers.insert_one(offer_doc)
        print(f"📥 Sell offer from: {data.get('name')} ({data.get('email')})")
        return jsonify({"success": True, "message": "Energy offer created successfully", "offer_id": offer_doc['offer_id']})

    except Exception as e:
        print(f"❌ Create offer error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/energy-request', methods=['POST', 'OPTIONS'])
def create_energy_request():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = request.get_json()
        if not is_db_connected():
            return jsonify({"success": True, "message": "Request saved (demo mode)"})

        request_doc = {
            "request_id": str(uuid.uuid4()),
            "user_id": data.get('user_id'),
            "email": data.get('email'),
            "name": data.get('name'),
            "role": "buyer",
            "packets": data.get('packets'),
            "price_per_packet": data.get('price_per_packet'),
            "total_price": data.get('total_price'),
            "latitude": data.get('latitude'),
            "longitude": data.get('longitude'),
            "location_string": data.get('location_string'),
            "status": data.get('status', 'pending'),
            "created_at": datetime.now().isoformat()
        }

        db.requests.insert_one(request_doc)
        print(f"📥 Buy request from: {data.get('name')} ({data.get('email')})")
        return jsonify({"success": True, "message": "Energy request created successfully", "request_id": request_doc['request_id']})

    except Exception as e:
        print(f"❌ Create request error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/all-requests', methods=['GET', 'OPTIONS'])
def get_all_requests():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        if not is_db_connected():
            return jsonify({"success": True, "requests": [], "offers": []})

        requests_list = []
        for req in db.requests.find({}):
            req['_id'] = str(req['_id'])
            requests_list.append(req)

        offers_list = []
        for offer in db.offers.find({}):
            offer['_id'] = str(offer['_id'])
            offers_list.append(offer)

        return jsonify({"success": True, "requests": requests_list, "offers": offers_list})

    except Exception as e:
        print(f"❌ Get all requests error: {e}")
        return jsonify({"success": False, "message": str(e), "requests": [], "offers": []}), 500


# ==================== TRADE ENDPOINTS ====================

@app.route('/api/confirm-trade', methods=['POST', 'OPTIONS'])
def confirm_trade():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = request.get_json()

        buyer_email    = data.get('buyer_email', '').strip().lower()
        seller_email   = data.get('seller_email', '').strip().lower()
        units          = float(data.get('units', 0))
        price_per_unit = float(data.get('price_per_unit', 0))
        offer_id       = data.get('offer_id', '')

        print(f"🤝 Trade confirmation: {buyer_email} ← {units} units ← {seller_email}")

        if not buyer_email or not seller_email:
            return jsonify({"success": False, "message": "buyer_email and seller_email are required"}), 400
        if units <= 0:
            return jsonify({"success": False, "message": "units must be greater than 0"}), 400
        if price_per_unit <= 0:
            return jsonify({"success": False, "message": "price_per_unit must be greater than 0"}), 400

        transaction_id = str(uuid.uuid4())

        if is_db_connected():
            if offer_id:
                db.offers.update_one(
                    {"offer_id": offer_id},
                    {"$set": {"status": "sold", "buyer_email": buyer_email, "sold_at": datetime.now().isoformat()}}
                )
            db.transactions.insert_one({
                "transaction_id":  transaction_id,
                "buyer_email":     buyer_email,
                "seller_email":    seller_email,
                "units":           units,
                "price_per_unit":  price_per_unit,
                "total_ec":        round(units * price_per_unit, 2),
                "status":          "confirmed",
                "blockchain_tx":   None,
                "created_at":      datetime.now().isoformat()
            })

        # ── Record on blockchain ─────────────────────────────────
        blockchain_result = record_trade_on_blockchain(
            buyer_email=buyer_email,
            seller_email=seller_email,
            units=units,
            price_per_unit=price_per_unit
        )

        if is_db_connected() and blockchain_result.get("success"):
            db.transactions.update_one(
                {"transaction_id": transaction_id},
                {"$set": {
                    "blockchain_tx":   blockchain_result.get("tx_id"),
                    "private_block":   blockchain_result.get("private_block_index"),
                    "blockchain_hash": blockchain_result.get("private_block_hash")
                }}
            )
        # ────────────────────────────────────────────────────────

        return jsonify({
            "success": True,
            "message": "Trade confirmed and recorded on blockchain!",
            "transaction_id": transaction_id,
            "trade": {
                "buyer":          buyer_email,
                "seller":         seller_email,
                "units":          units,
                "price_per_unit": price_per_unit,
                "total_ec":       round(units * price_per_unit, 2)
            },
            "blockchain": {
                "recorded":      blockchain_result.get("success", False),
                "tx_id":         blockchain_result.get("tx_id"),
                "private_block": blockchain_result.get("private_block_index"),
                "block_hash":    blockchain_result.get("private_block_hash"),
                "ec_paid":       blockchain_result.get("buyer_paid_ec"),
                "ec_received":   blockchain_result.get("seller_received_ec"),
                "period":        blockchain_result.get("period"),
                "pkr_value":     blockchain_result.get("pkr_equivalent")
            }
        })

    except Exception as e:
        print(f"❌ Confirm trade error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/trade-history', methods=['GET', 'OPTIONS'])
def trade_history():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        email = request.args.get('email', '').strip().lower()
        if not email:
            return jsonify({"success": False, "message": "email parameter required"}), 400
        if not is_db_connected():
            return jsonify({"success": True, "trades": [], "count": 0})

        trades_cursor = db.transactions.find({
            "$or": [{"buyer_email": email}, {"seller_email": email}]
        }).sort("created_at", -1)

        trades = []
        for trade in trades_cursor:
            trade['_id'] = str(trade['_id'])
            trades.append(trade)

        return jsonify({"success": True, "email": email, "trades": trades, "count": len(trades)})

    except Exception as e:
        print(f"❌ Trade history error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ==================== MARKETPLACE ENDPOINTS ====================

@app.route('/api/sell-energy', methods=['POST', 'OPTIONS'])
def sell_energy():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        session_token = data.get('session_token')
        energy_amount = float(data.get('energy_amount', 0))
        price_per_kwh = float(data.get('price_per_kwh', 0))
        location = data.get('location', 'Unknown Location')

        if not session_token:
            return jsonify({"success": False, "message": "Session token required"}), 401

        if not is_db_connected():
            return jsonify({
                "success": True,
                "message": "Energy listed for sale (demo mode)",
                "listing": {
                    "listing_id": str(uuid.uuid4()),
                    "energy_amount": energy_amount,
                    "price_per_kwh": price_per_kwh,
                    "total_price": energy_amount * price_per_kwh,
                    "location": location,
                    "status": "available",
                    "created_at": datetime.now().isoformat()
                }
            })

        user = db.users.find_one({"session_token": session_token})
        if not user:
            return jsonify({"success": False, "message": "Invalid session"}), 401
        if user.get('role') != 'seller':
            return jsonify({"success": False, "message": "Only sellers can sell energy"}), 403

        energy_listing = {
            "listing_id": str(uuid.uuid4()),
            "seller_id": user['user_id'],
            "seller_email": user['email'],
            "energy_amount": energy_amount,
            "price_per_kwh": price_per_kwh,
            "total_price": energy_amount * price_per_kwh,
            "location": location,
            "status": "available",
            "created_at": datetime.now().isoformat(),
            "buyer_id": None,
            "sold_at": None
        }

        db.energy_listings.insert_one(energy_listing)
        return jsonify({"success": True, "message": "Energy listed for sale successfully!", "listing": energy_listing})

    except Exception as e:
        print(f"🔥 Sell energy error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/buy-energy', methods=['POST', 'OPTIONS'])
def buy_energy():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        session_token = data.get('session_token')
        listing_id = data.get('listing_id')

        if not session_token or not listing_id:
            return jsonify({"success": False, "message": "Session token and listing ID required"}), 400

        if not is_db_connected():
            return jsonify({
                "success": True,
                "message": "Energy purchased (demo mode)",
                "transaction_id": str(uuid.uuid4()),
                "energy_amount": 50.0,
                "total_price": 7.50,
                "seller": "demo_seller@example.com"
            })

        buyer = db.users.find_one({"session_token": session_token})
        if not buyer:
            return jsonify({"success": False, "message": "Invalid session"}), 401

        listing = db.energy_listings.find_one({"listing_id": listing_id, "status": "available"})
        if not listing:
            return jsonify({"success": False, "message": "Energy listing not available"}), 404

        seller = db.users.find_one({"user_id": listing['seller_id']})
        if not seller:
            return jsonify({"success": False, "message": "Seller not found"}), 404

        total_price = listing['total_price']
        if buyer['wallet_balance'] < total_price:
            return jsonify({"success": False, "message": "Insufficient balance"}), 400

        db.users.update_one({"user_id": buyer['user_id']}, {"$inc": {"wallet_balance": -total_price}})
        db.users.update_one({"user_id": listing['seller_id']}, {"$inc": {"wallet_balance": total_price}})
        db.energy_listings.update_one(
            {"listing_id": listing_id},
            {"$set": {"status": "sold", "buyer_id": buyer['user_id'], "sold_at": datetime.now().isoformat()}}
        )

        transaction_id = str(uuid.uuid4())
        db.transactions.insert_one({
            "transaction_id": transaction_id,
            "user_id": buyer['user_id'],
            "type": "energy_purchased",
            "amount": -total_price,
            "energy_amount": listing['energy_amount'],
            "timestamp": datetime.now().isoformat(),
            "seller_email": seller['email']
        })

        blockchain_result = record_trade_on_blockchain(
            buyer_email=buyer['email'],
            seller_email=seller['email'],
            units=listing['energy_amount'],
            price_per_unit=listing['price_per_kwh']
        )

        return jsonify({
            "success": True,
            "message": "Energy purchase successful!",
            "transaction_id": transaction_id,
            "energy_amount": listing['energy_amount'],
            "total_price": total_price,
            "seller": seller['email'],
            "blockchain": {
                "recorded":      blockchain_result.get("success", False),
                "tx_id":         blockchain_result.get("tx_id"),
                "private_block": blockchain_result.get("private_block_index")
            }
        })

    except Exception as e:
        print(f"🔥 Buy energy error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/energy-listings', methods=['GET'])
def get_energy_listings():
    try:
        if not is_db_connected():
            return jsonify({
                "success": True,
                "listings": [],
                "count": 0,
                "mode": "demo"
            })
        listings = list(db.energy_listings.find({"status": "available"}, {"_id": 0}).sort("created_at", -1))
        return jsonify({"success": True, "listings": listings, "count": len(listings)})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==================== OTHER USER ENDPOINTS ====================

@app.route('/api/profile', methods=['GET'])
def get_profile():
    try:
        email = request.args.get('email', '').strip().lower()
        if email and is_db_connected():
            user = db_users.users.find_one({"email": email})
            if user:
                return jsonify({
                    "success": True,
                    "profile": {
                        "email": user['email'],
                        "name": user.get('name', ''),
                        "role": user.get('role', None),
                        "wallet_balance": float(user.get('wallet_balance', 1000)),
                        "ec_balance": user.get('ec_balance', 500),
                        "member_since": user.get('created_at', '')
                    }
                })
        return jsonify({"success": True, "profile": {"email": "demo@example.com", "role": "buyer", "wallet_balance": 1000.00}})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    try:
        email = request.args.get('email', '').strip().lower()
        if email and is_db_connected():
            trades_cursor = db.transactions.find({
                "$or": [{"buyer_email": email}, {"seller_email": email}]
            }).sort("created_at", -1).limit(20)
            trades = []
            for t in trades_cursor:
                t['_id'] = str(t['_id'])
                trades.append(t)
            return jsonify({"success": True, "transactions": trades, "count": len(trades)})
        return jsonify({"success": True, "transactions": [], "count": 0})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/init-db', methods=['GET'])
def init_database():
    try:
        if not is_db_connected():
            return jsonify({"success": False, "message": "Database not connected"}), 500
        test_users = [
            {"email": "seller@example.com", "password": "test123", "role": "seller", "wallet_balance": 1000.00, "name": "Test Seller"},
            {"email": "buyer@example.com",  "password": "test123", "role": "buyer",  "wallet_balance": 500.00,  "name": "Test Buyer"}
        ]
        for user in test_users:
            if not db.users.find_one({"email": user["email"]}):
                user["user_id"] = str(uuid.uuid4())
                user["created_at"] = datetime.now().isoformat()
                db.users.insert_one(user)
        return jsonify({"success": True, "message": "Database initialized"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

GMAIL_ADDRESS = os.getenv('GMAIL_ADDRESS', '')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD', '')
 
# In-memory OTP store: { email: { otp, expires_at } }
# For production use Redis/MongoDB, but this works for FYP
otp_store = {}
 
def generate_otp():
    return str(random.randint(100000, 999999))
 
def send_otp_email(to_email, otp_code, purpose="verification"):
    """Send OTP email in background thread to avoid blocking gunicorn."""
    def _send():
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'E-Drive - Your {purpose} code: {otp_code}'
            msg['From'] = f'E-Drive Energy <{GMAIL_ADDRESS}>'
            msg['To'] = to_email

            html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; background: #1a1a1a; color: white; border-radius: 16px; overflow: hidden;">
                <div style="background: #00b894; padding: 24px; text-align: center;">
                    <h1 style="margin: 0; font-size: 28px;">E-Drive Energy</h1>
                </div>
                <div style="padding: 32px; text-align: center;">
                    <h2 style="color: #00b894;">Your verification code</h2>
                    <div style="background: #2d3436; border: 2px solid #00b894; border-radius: 12px; padding: 20px;">
                        <span style="font-size: 42px; font-weight: bold; letter-spacing: 12px; color: #00b894;">{otp_code}</span>
                    </div>
                    <p style="color: #636e72; margin-top: 24px; font-size: 13px;">Expires in 10 minutes</p>
                </div>
            </div>
            """

            msg.attach(MIMEText(html, 'html'))

            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())

            print(f"✅ OTP email sent to {to_email}")
        except Exception as e:
            print(f"❌ Email send error: {e}")

    threading.Thread(target=_send, daemon=True).start()
    return True  # Return immediately, don't wait for email
 
 
# ── Send OTP for Signup ───────────────────────────────────────
@app.route('/api/send-otp', methods=['POST', 'OPTIONS'])
def send_otp():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        name  = data.get('name', '').strip()
 
        if not email:
            return jsonify({"success": False, "message": "Email required"}), 400
 
        # Check if email already registered
        if is_db_connected():
            existing = db_users.users.find_one({"email": email})
            if existing:
                return jsonify({"success": False, "message": "Email already registered. Please login."}), 400
 
        otp_code = generate_otp()
        otp_store[email] = {
            "otp":        otp_code,
            "name":       name,
            "expires_at": datetime.now().timestamp() + 600  # 10 min
        }
 
        success = send_otp_email(email, otp_code, "signup")
        if success:
            return jsonify({"success": True, "message": f"Verification code sent to {email}"})
        else:
            return jsonify({"success": False, "message": "Failed to send email. Check Gmail config."}), 500
 
    except Exception as e:
        print(f"❌ Send OTP error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
 
 
# ── Verify OTP and Complete Signup ────────────────────────────
@app.route('/api/verify-otp', methods=['POST', 'OPTIONS'])
def verify_otp():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data     = request.get_json() or {}
        email    = data.get('email', '').strip().lower()
        otp_code = data.get('otp', '').strip()
        name     = data.get('name', '').strip()
        password = data.get('password', '')
 
        if not email or not otp_code:
            return jsonify({"success": False, "message": "Email and OTP required"}), 400
 
        record = otp_store.get(email)
        if not record:
            return jsonify({"success": False, "message": "No OTP found. Please request a new one."}), 400
        if datetime.now().timestamp() > record['expires_at']:
            del otp_store[email]
            return jsonify({"success": False, "message": "OTP expired. Please request a new one."}), 400
        if record['otp'] != otp_code:
            return jsonify({"success": False, "message": "Invalid OTP. Please try again."}), 400
 
        # OTP valid — create account
        del otp_store[email]
 
        # Create blockchain wallet
        ec_balance = 500
        wallet_address = ""
        try:
            wallet_response = requests.post(
                f"{BLOCKCHAIN_URL}/api/wallet/create",
                json={"username": email}, timeout=10
            )
            wallet_data = wallet_response.json()
            ec_balance = wallet_data.get("wallet", {}).get("balance", 500)
            wallet_address = wallet_data.get("wallet", {}).get("address", "")
        except Exception as e:
            print(f"[WARN] Could not create blockchain wallet: {e}")
 
        user = {
            "user_id":          str(uuid.uuid4()),
            "name":             name or record.get('name', email.split('@')[0]),
            "email":            email,
            "password":         password,
            "wallet_balance":   1000.00,
            "ec_balance":       ec_balance,
            "ec_wallet_address": wallet_address,
            "email_verified":   True,
            "created_at":       datetime.now().isoformat(),
            "session_token":    str(uuid.uuid4())
        }
 
        if is_db_connected():
            db_users.users.insert_one(user)
 
        print(f"✅ Verified signup: {email}")
        return jsonify({
            "success": True,
            "message": "Account created successfully!",
            "user": {
                "user_id":        user['user_id'],
                "name":           user['name'],
                "email":          user['email'],
                "wallet_balance": user['wallet_balance'],
                "ec_balance":     user['ec_balance'],
                "role":           None
            }
        }), 201
 
    except Exception as e:
        print(f"❌ Verify OTP error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
 
 
# ── Send OTP for Login (passwordless) ────────────────────────
@app.route('/api/send-login-otp', methods=['POST', 'OPTIONS'])
def send_login_otp():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data  = request.get_json() or {}
        email = data.get('email', '').strip().lower()
 
        if not email:
            return jsonify({"success": False, "message": "Email required"}), 400
 
        # Check user exists
        if is_db_connected():
            user = db_users.users.find_one({"email": email})
            if not user:
                return jsonify({"success": False, "message": "No account found with this email"}), 404
 
        otp_code = generate_otp()
        otp_store[f"login_{email}"] = {
            "otp":        otp_code,
            "expires_at": datetime.now().timestamp() + 600
        }
 
        success = send_otp_email(email, otp_code, "login")
        if success:
            return jsonify({"success": True, "message": f"Login code sent to {email}"})
        else:
            return jsonify({"success": False, "message": "Failed to send email"}), 500
 
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
 
 
# ── Verify Login OTP ──────────────────────────────────────────
@app.route('/api/verify-login-otp', methods=['POST', 'OPTIONS'])
def verify_login_otp():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data     = request.get_json() or {}
        email    = data.get('email', '').strip().lower()
        otp_code = data.get('otp', '').strip()
 
        if not email or not otp_code:
            return jsonify({"success": False, "message": "Email and OTP required"}), 400
 
        record = otp_store.get(f"login_{email}")
        if not record:
            return jsonify({"success": False, "message": "No OTP found. Please request a new one."}), 400
        if datetime.now().timestamp() > record['expires_at']:
            del otp_store[f"login_{email}"]
            return jsonify({"success": False, "message": "OTP expired. Please request a new one."}), 400
        if record['otp'] != otp_code:
            return jsonify({"success": False, "message": "Invalid OTP"}), 400
 
        del otp_store[f"login_{email}"]
 
        user = None
        if is_db_connected():
            user = db_users.users.find_one({"email": email})
 
        print(f"✅ OTP login: {email}")
        return jsonify({
            "success": True,
            "message": "Login successful!",
            "user": {
                "user_id":        str(user.get('user_id', '')) if user else '',
                "name":           user.get('name', email.split('@')[0]) if user else email.split('@')[0],
                "email":          email,
                "wallet_balance": float(user.get('wallet_balance', 1000)) if user else 1000,
                "role":           user.get('role', None) if user else None
            }
        })
 
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
 
# ── Google OAuth Login ────────────────────────────────────────
@app.route('/api/google-login', methods=['POST', 'OPTIONS'])
def google_login():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data  = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        name  = data.get('name', '').strip()
 
        if not email:
            return jsonify({"success": False, "message": "Email required"}), 400
 
        user = None
        if is_db_connected():
            user = db_users.users.find_one({"email": email})
            if not user:
                # Auto-register Google user
                ec_balance = 500
                try:
                    wallet_response = requests.post(
                        f"{BLOCKCHAIN_URL}/api/wallet/create",
                        json={"username": email}, timeout=10
                    )
                    ec_balance = wallet_response.json().get("wallet", {}).get("balance", 500)
                except:
                    pass
 
                user = {
                    "user_id":        str(uuid.uuid4()),
                    "name":           name or email.split('@')[0],
                    "email":          email,
                    "password":       "",
                    "auth_provider":  "google",
                    "wallet_balance": 1000.00,
                    "ec_balance":     ec_balance,
                    "email_verified": True,
                    "created_at":     datetime.now().isoformat(),
                    "session_token":  str(uuid.uuid4())
                }
                db_users.users.insert_one(user)
                print(f"✅ New Google user: {email}")
 
        return jsonify({
            "success": True,
            "message": "Google login successful!",
            "user": {
                "user_id":        str(user.get('user_id', '')),
                "name":           user.get('name', name),
                "email":          email,
                "wallet_balance": float(user.get('wallet_balance', 1000)),
                "role":           user.get('role', None)
            }
        })
 
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
        


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "message": "Endpoint not found", "error": str(error)}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "message": "Internal server error", "error": str(error)}), 500


# ==================== MAIN ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))

    print("\n" + "=" * 60)
    print("⚡ E-DRIVE ENERGY MARKETPLACE BACKEND")
    print("=" * 60)
    print(f"📦 MongoDB:     {'✅ CONNECTED' if is_db_connected() else '❌ DISCONNECTED'}")
    print(f"⛓️  Blockchain:  {BLOCKCHAIN_URL}")
    print(f"🌐 Port:        {port}")
    print("=" * 60)
    print("📋 Key Endpoints:")
    print(f"   POST /api/confirm-trade  ← main trade endpoint")
    print(f"   POST /api/wallet/topup   ← add EC for testing")
    print(f"   GET  /api/rates          ← current rate period")
    print(f"   GET  /api/trade-history  ← view past trades")
    print(f"   GET  /api/wallet         ← EC + PKR balance")
    print("=" * 60 + "\n")

    app.run(host='0.0.0.0', port=port, debug=False)



