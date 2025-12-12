from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime
import uuid
import hashlib
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Enable CORS for ALL origins during development
CORS(app, supports_credentials=True, origins=["http://localhost:*", "http://127.0.0.1:*", "*"])

# MongoDB Connection - using environment variables for security
username = os.getenv('MONGO_USERNAME', "romaisamaqbool008_db_user")
password = os.getenv('MONGO_PASSWORD', "arm256")

MONGO_URI = f"mongodb+srv://{username}:{password}@cluster0.yleenkw.mongodb.net/energy_trading?retryWrites=true&w=majority"

print("=" * 60)
print("🚀 E-Drive Cloud Marketplace Backend")
print("=" * 60)

# Initialize db as None
db = None
client = None

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    
    # Use TWO databases
    db_users = client['edrive']  # For users collection
    db = client['energy_trading']  # For requests/offers
    
    print("✅ MongoDB Cloud Connected Successfully!")
    print(f"📊 Users Database: {db_users.name}")
    print(f"📊 Trading Database: {db.name}")
except Exception as e:
    print(f"❌ MongoDB Connection Failed: {e}")
    print("⚠️  Running in offline mode")
    db = None
    db_users = None
    client = None

def is_db_connected():
    """Check if database is connected"""
    if db is None or db_users is None or client is None:
        return False
    try:
        client.admin.command('ping')
        return True
    except:
        return False

def hash_password(password):
    """Simple password hashing using SHA256"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

# ==================== BASIC ENDPOINTS ====================

@app.route('/')
def home():
    """Home page - shows API status"""
    return jsonify({
        "message": "⚡ E-Drive Energy Marketplace API",
        "status": "running",
        "version": "1.0.0",
        "database": "connected" if is_db_connected() else "disconnected",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "auth": ["POST /api/login", "POST /api/signup", "POST /api/logout"],
            "marketplace": ["POST /api/sell-energy", "POST /api/buy-energy", "GET /api/energy-listings"],
            "user": ["GET /api/profile", "GET /api/wallet", "GET /api/transactions"],
            "health": ["GET /health", "GET /api/status"]
        }
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "server": "E-Drive Backend",
        "database": "connected" if is_db_connected() else "disconnected",
        "timestamp": datetime.now().isoformat(),
        "uptime": "running"
    })

@app.route('/api/status')
def api_status():
    """API status check"""
    return jsonify({
        "success": True,
        "message": "API is operational",
        "server_time": datetime.now().isoformat(),
        "mongodb": "connected" if is_db_connected() else "disconnected"
    })

# ==================== AUTHENTICATION ENDPOINTS ====================

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    """User login endpoint"""
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
            return jsonify({
                "success": False,
                "message": "Email and password are required"
            }), 400

        # Check database connection
        if not is_db_connected():
            return jsonify({
                "success": False,
                "message": "Database not connected. Please try again later."
            }), 500

        # Find user in database
        user = db_users.users.find_one({"email": email})
        
        if not user:
            print(f"❌ User not found: {email}")
            return jsonify({
                "success": False,
                "message": "Invalid email or password"
            }), 401
        
        # Check password (handle both hashed and plain passwords)
        stored_password = user.get('password', '')
        hashed_input = hash_password(password)
        
        # Check if password matches (either plain or hashed)
        if stored_password != hashed_input and stored_password != password:
            print(f"❌ Password mismatch for: {email}")
            return jsonify({
                "success": False,
                "message": "Invalid email or password"
            }), 401

        # Create session token
        session_token = str(uuid.uuid4())
        db_users.users.update_one(
            {"email": email},
            {"$set": {"session_token": session_token, "last_login": datetime.now().isoformat()}}
        )

        print(f"✅ Login successful for: {email}")
        
        # Return user data WITHOUT role (let dashboard set it)
        return jsonify({
            "success": True,
            "message": "Login successful!",
            "session_token": session_token,
            "user": {
                "user_id": user.get('user_id', str(user['_id'])),
                "email": user['email'],
                "name": user.get('name', user.get('full_name', '')),
                "role": user.get('role', None),  # Return None if no role set
                "wallet_balance": float(user.get('wallet_balance', 1000)),
                "phone": user.get('phone', ''),
                "address": user.get('address', '')
            }
        })

    except Exception as e:
        print(f"🔥 Login error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Server error: {str(e)}"
        }), 500

@app.route('/api/signup', methods=['POST', 'OPTIONS'])
def signup():
    """User registration endpoint"""
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
        
        # Validation
        if not name:
            return jsonify({"success": False, "message": "Name is required"}), 400
            
        if not email:
            return jsonify({"success": False, "message": "Email is required"}), 400
            
        if not password:
            return jsonify({"success": False, "message": "Password is required"}), 400
            
        if len(password) < 6:
            return jsonify({"success": False, "message": "Password must be at least 6 characters"}), 400

        # Check database connection
        if not is_db_connected():
            return jsonify({
                "success": False,
                "message": "Database not connected. Cannot create account."
            }), 500
        
        # Check if email already exists
        existing_user = db_users.users.find_one({"email": email})
        if existing_user:
            print(f"❌ Email already registered: {email}")
            return jsonify({"success": False, "message": "Email already registered"}), 400
        
        # Create new user WITHOUT role
        user = {
            "user_id": str(uuid.uuid4()),
            "name": name,
            "email": email,
            "password": password,
            # NO ROLE - user will choose on dashboard
            "wallet_balance": 1000.00,
            "created_at": datetime.now().isoformat(),
            "session_token": str(uuid.uuid4())
        }
        
        # Insert into MongoDB
        result = db_users.users.insert_one(user)
        print(f"✅ New user registered: {name} ({email})")
        print(f"✅ MongoDB ID: {result.inserted_id}")
        
        # Prepare response
        user_response = {
            "user_id": user['user_id'],
            "name": user['name'],
            "email": user['email'],
            "wallet_balance": user['wallet_balance'],
            "role": None  # No role yet
        }
        
        return jsonify({
            "success": True,
            "message": "Account created successfully!",
            "user": user_response,
            "session_token": user['session_token']
        }), 201
        
    except Exception as e:
        print(f"❌ Signup error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
@app.route('/api/update-role', methods=['POST', 'OPTIONS'])
def update_role():
    """Update user role when they choose buyer or seller"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        role = data.get('role', '').strip().lower()
        
        print(f"🔄 Role update request: {email} → {role}")
        
        if not email or not role:
            return jsonify({"success": False, "message": "Email and role required"}), 400
        
        if role not in ['buyer', 'seller']:
            return jsonify({"success": False, "message": "Role must be 'buyer' or 'seller'"}), 400
        
        if not is_db_connected():
            return jsonify({
                "success": False,
                "message": "Database not connected"
            }), 500
        
        # Update role in database
        result = db_users.users.update_one(
            {"email": email},
            {"$set": {"role": role, "role_updated_at": datetime.now().isoformat()}}
        )
        
        if result.matched_count > 0:
            print(f"✅ Updated role to '{role}' for {email}")
            return jsonify({
                "success": True,
                "message": f"Role updated to {role}"
            })
        else:
            print(f"❌ User not found: {email}")
            return jsonify({
                "success": False,
                "message": "User not found"
            }), 404
            
    except Exception as e:
        print(f"❌ Update role error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

   

@app.route('/api/energy-offer', methods=['POST', 'OPTIONS'])
def create_energy_offer():
    """Create a new energy sale offer with location"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        data = request.get_json()
        
        if not is_db_connected():
            return jsonify({"success": True, "message": "Offer saved (demo mode)"})
        
        # Create offer document with location
        offer_doc = {
            "offer_id": str(uuid.uuid4()),
            "user_id": data.get('user_id'),
            "email": data.get('email'),
            "name": data.get('name'),
            "role": "seller",
            "packets": data.get('packets'),
            "price_per_packet": data.get('price_per_packet'),
            "total_value": data.get('total_value'),
            "latitude": data.get('latitude'),  # NEW
            "longitude": data.get('longitude'),  # NEW
            "location_string": data.get('location_string'),  # NEW
            "status": data.get('status', 'available'),
            "created_at": datetime.now().isoformat()
        }
        
        result = db.offers.insert_one(offer_doc)
        print(f"📥 Sell offer from: {data.get('name')} ({data.get('email')}) at {data.get('location_string', 'unknown location')}")
        
        return jsonify({
            "success": True,
            "message": "Energy offer created successfully",
            "offer_id": offer_doc['offer_id']
        })
        
    except Exception as e:
        print(f"❌ Create offer error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/energy-request', methods=['POST', 'OPTIONS'])
def create_energy_request():
    """Create a new energy purchase request with location"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        data = request.get_json()
        
        if not is_db_connected():
            return jsonify({"success": True, "message": "Request saved (demo mode)"})
        
        # Create request document with location
        request_doc = {
            "request_id": str(uuid.uuid4()),
            "user_id": data.get('user_id'),
            "email": data.get('email'),
            "name": data.get('name'),
            "role": "buyer",
            "packets": data.get('packets'),
            "price_per_packet": data.get('price_per_packet'),
            "total_price": data.get('total_price'),
            "latitude": data.get('latitude'),  # NEW
            "longitude": data.get('longitude'),  # NEW
            "location_string": data.get('location_string'),  # NEW
            "status": data.get('status', 'pending'),
            "created_at": datetime.now().isoformat()
        }
        
        result = db.requests.insert_one(request_doc)
        print(f"📥 Buy request from: {data.get('name')} ({data.get('email')}) at {data.get('location_string', 'unknown location')}")
        
        return jsonify({
            "success": True,
            "message": "Energy request created successfully",
            "request_id": request_doc['request_id']
        })
        
    except Exception as e:
        print(f"❌ Create request error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
    

@app.route('/api/all-requests', methods=['GET', 'OPTIONS'])
def get_all_requests():
    """Get all buyer requests and seller offers"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        print("📊 Getting all requests and offers...")
        
        if not is_db_connected():
            print("⚠️  Database not connected, returning empty lists")
            return jsonify({
                "success": True,
                "requests": [],
                "offers": []
            })
        
        # Get all buyer requests from requests collection
        requests_cursor = db.requests.find({})
        requests_list = []
        for req in requests_cursor:
            req['_id'] = str(req['_id'])  # Convert ObjectId to string
            requests_list.append(req)
        
        # Get all seller offers from offers collection
        offers_cursor = db.offers.find({})
        offers_list = []
        for offer in offers_cursor:
            offer['_id'] = str(offer['_id'])  # Convert ObjectId to string
            offers_list.append(offer)
        
        print(f"✅ Returning {len(requests_list)} requests and {len(offers_list)} offers")
        
        return jsonify({
            "success": True,
            "requests": requests_list,
            "offers": offers_list
        })
        
    except Exception as e:
        print(f"❌ Get all requests error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": str(e),
            "requests": [],
            "offers": []
        }), 500
    

# ==================== MARKETPLACE ENDPOINTS ====================

# ==================== MARKETPLACE ENDPOINTS ====================

@app.route('/api/sell-energy', methods=['POST', 'OPTIONS'])
def sell_energy():
    """Seller lists energy for sale"""
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
        
        # For demo mode
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
            
        # Verify user
        user = db.users.find_one({"session_token": session_token})
        if not user:
            return jsonify({"success": False, "message": "Invalid session"}), 401
            
        if user.get('role') != 'seller':
            return jsonify({"success": False, "message": "Only sellers can sell energy"}), 403
            
        # Create energy listing
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
        
        print(f"✅ Energy listed: {energy_amount}kWh by {user['email']}")
        
        return jsonify({
            "success": True,
            "message": "Energy listed for sale successfully!",
            "listing": energy_listing
        })
        
    except Exception as e:
        print(f"🔥 Sell energy error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/buy-energy', methods=['POST', 'OPTIONS'])
def buy_energy():
    """Buyer purchases energy"""
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
        
        # For demo mode
        if not is_db_connected():
            return jsonify({
                "success": True,
                "message": "Energy purchased successfully (demo mode)",
                "transaction_id": str(uuid.uuid4()),
                "energy_amount": 50.0,
                "total_price": 7.50,
                "seller": "demo_seller@example.com"
            })
            
        # Verify user
        buyer = db.users.find_one({"session_token": session_token})
        if not buyer:
            return jsonify({"success": False, "message": "Invalid session"}), 401
            
        # Get energy listing
        listing = db.energy_listings.find_one({"listing_id": listing_id, "status": "available"})
        if not listing:
            return jsonify({"success": False, "message": "Energy listing not available"}), 404
            
        seller_id = listing['seller_id']
        seller = db.users.find_one({"user_id": seller_id})
        
        if not seller:
            return jsonify({"success": False, "message": "Seller not found"}), 404
            
        total_price = listing['total_price']
        
        # Check buyer's balance
        if buyer['wallet_balance'] < total_price:
            return jsonify({
                "success": False, 
                "message": "Insufficient balance",
                "required": total_price,
                "available": buyer['wallet_balance']
            }), 400
            
        # Perform transaction
        db.users.update_one(
            {"user_id": buyer['user_id']},
            {"$inc": {"wallet_balance": -total_price}}
        )
        
        db.users.update_one(
            {"user_id": seller_id},
            {"$inc": {"wallet_balance": total_price}}
        )
        
        # Update listing status
        db.energy_listings.update_one(
            {"listing_id": listing_id},
            {
                "$set": {
                    "status": "sold",
                    "buyer_id": buyer['user_id'],
                    "buyer_email": buyer['email'],
                    "sold_at": datetime.now().isoformat()
                }
            }
        )
        
        # Create transaction records
        transaction_id = str(uuid.uuid4())
        
        db.transactions.insert_one({
            "transaction_id": transaction_id,
            "user_id": buyer['user_id'],
            "type": "energy_purchased",
            "amount": -total_price,
            "energy_amount": listing['energy_amount'],
            "price_per_kwh": listing['price_per_kwh'],
            "timestamp": datetime.now().isoformat(),
            "seller_email": seller['email'],
            "details": f"Purchased {listing['energy_amount']} kWh from {seller['email']}"
        })
        
        db.transactions.insert_one({
            "transaction_id": transaction_id,
            "user_id": seller_id,
            "type": "energy_sold",
            "amount": total_price,
            "energy_amount": listing['energy_amount'],
            "price_per_kwh": listing['price_per_kwh'],
            "timestamp": datetime.now().isoformat(),
            "buyer_email": buyer['email'],
            "details": f"Sold {listing['energy_amount']} kWh to {buyer['email']}"
        })
        
        print(f"✅ Energy purchased: {listing['energy_amount']}kWh by {buyer['email']}")
        
        return jsonify({
            "success": True,
            "message": "Energy purchase successful!",
            "transaction_id": transaction_id,
            "energy_amount": listing['energy_amount'],
            "total_price": total_price,
            "seller": seller['email']
        })
        
    except Exception as e:
        print(f"🔥 Buy energy error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/energy-listings', methods=['GET'])
def get_energy_listings():
    """Get all available energy listings"""
    try:
        if not is_db_connected():
            # Demo data
            demo_listings = [
                {
                    "listing_id": "demo_001",
                    "seller_email": "solar_farm@example.com",
                    "energy_amount": 100.0,
                    "price_per_kwh": 0.12,
                    "total_price": 12.00,
                    "location": "Solar Farm A",
                    "status": "available",
                    "created_at": datetime.now().isoformat()
                },
                {
                    "listing_id": "demo_002",
                    "seller_email": "wind_park@example.com",
                    "energy_amount": 75.5,
                    "price_per_kwh": 0.15,
                    "total_price": 11.33,
                    "location": "Wind Park B",
                    "status": "available",
                    "created_at": datetime.now().isoformat()
                },
                {
                    "listing_id": "demo_003",
                    "seller_email": "home_solar@example.com",
                    "energy_amount": 25.0,
                    "price_per_kwh": 0.18,
                    "total_price": 4.50,
                    "location": "Residential Area",
                    "status": "available",
                    "created_at": datetime.now().isoformat()
                }
            ]
            return jsonify({
                "success": True,
                "listings": demo_listings,
                "count": len(demo_listings),
                "mode": "demo"
            })
        
        listings = list(db.energy_listings.find(
            {"status": "available"},
            {"_id": 0}
        ).sort("created_at", -1))
        
        return jsonify({
            "success": True,
            "listings": listings,
            "count": len(listings)
        })
        
    except Exception as e:
        print(f"🔥 Get listings error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ==================== USER ENDPOINTS ====================

@app.route('/api/wallet', methods=['GET'])
def get_wallet():
    """Get user wallet balance (simplified - no auth for demo)"""
    try:
        # For demo, return a fixed balance
        return jsonify({
            "success": True,
            "balance": 1000.00,
            "currency": "USD",
            "last_updated": datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Wallet error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/profile', methods=['GET'])
def get_profile():
    """Get user profile (simplified)"""
    try:
        # For demo, return a profile
        return jsonify({
            "success": True,
            "profile": {
                "email": "demo@example.com",
                "role": "buyer",
                "wallet_balance": 1000.00,
                "full_name": "Demo User",
                "member_since": "2024-01-01"
            }
        })
    except Exception as e:
        print(f"Profile error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Get user transactions (demo)"""
    try:
        demo_transactions = [
            {
                "id": "txn_001",
                "type": "purchase",
                "amount": -25.50,
                "description": "Bought 150kWh from Solar Farm",
                "date": "2024-01-15T10:30:00",
                "status": "completed"
            },
            {
                "id": "txn_002",
                "type": "sale",
                "amount": 42.75,
                "description": "Sold 285kWh to Grid",
                "date": "2024-01-14T14:20:00",
                "status": "completed"
            }
        ]
        
        return jsonify({
            "success": True,
            "transactions": demo_transactions,
            "count": len(demo_transactions)
        })
    except Exception as e:
        print(f"Transactions error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ==================== INITIALIZATION ====================

@app.route('/api/init-db', methods=['GET'])
def init_database():
    """Initialize database with test data"""
    try:
        if not is_db_connected():
            return jsonify({
                "success": False,
                "message": "Database not connected"
            }), 500
            
        # Create test users
        test_users = [
            {
                "email": "seller@example.com",
                "password": "test123",  # Plain text to match login logic
                "role": "seller",
                "wallet_balance": 1000.00,
                "name": "Test Seller"
            },
            {
                "email": "buyer@example.com",
                "password": "test123",  # Plain text to match login logic
                "role": "buyer",
                "wallet_balance": 500.00,
                "name": "Test Buyer"
            }
        ]
        
        for user in test_users:
            if not db.users.find_one({"email": user["email"]}):
                user["user_id"] = str(uuid.uuid4())
                user["created_at"] = datetime.now().isoformat()
                db.users.insert_one(user)
        
        return jsonify({
            "success": True,
            "message": "Database initialized with test users",
            "users_created": ["seller@example.com", "buyer@example.com"]
        })
        
    except Exception as e:
        print(f"Init DB error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "message": "Endpoint not found",
        "error": str(error)
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "message": "Internal server error",
        "error": str(error)
    }), 500

# ==================== MAIN ====================

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("⚡ E-DRIVE ENERGY MARKETPLACE BACKEND")
    print("=" * 60)
    print(f"📦 MongoDB: {'✅ CONNECTED' if is_db_connected() else '❌ DISCONNECTED (Demo Mode)'}")
    print("🌐 Server will run on:")
    print("   - http://localhost:5000")
    print("   - http://127.0.0.1:5000")
    print("   - http://0.0.0.0:5000 (all network interfaces)")
    print("=" * 60)
    print("📋 Quick Test URLs:")
    print("   Health:      http://localhost:5000/health")
    print("   API Status:  http://localhost:5000/api/status")
    print("   Listings:    http://localhost:5000/api/energy-listings")
    print("=" * 60)
    print("👤 Demo Accounts:")
    print("   Seller: seller@example.com / test123")
    print("   Buyer:  buyer@example.com / test123")
    print("=" * 60)
    print("\n🚀 Starting server...\n")
    
    # Run the app
    app.run(
        debug=True, 
        host='0.0.0.0',  # Listen on all network interfaces
        port=5000,
        threaded=True
    )