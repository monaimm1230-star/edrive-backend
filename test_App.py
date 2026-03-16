from flask import Flask
from pymongo import MongoClient
import sys

app = Flask(__name__)

# Replace YOUR_NEW_PASSWORD with the password you just created
MONGO_URI = "mongodb+srv://romaisamaqbool008_db_user:batten1234@cluster0.yleenkw.mongodb.net/edrive?retryWrites=true&w=majority"

print("=" * 50)
print("Starting Energy Trading App...")
print("=" * 50)

# Test MongoDB connection
print("\n1. Testing MongoDB connection...")
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()  # Force connection
    db = client['edrive']
    print("✓ MongoDB connected successfully!")
except Exception as e:
    print(f"✗ MongoDB connection FAILED: {e}")
    print("\nPlease check:")
    print("- Is your password correct?")
    print("- Did you whitelist your IP in MongoDB Atlas?")
    db = None

@app.route('/')
def home():
    return """
    <html>
        <head><title>Energy Trading App</title></head>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1>🔋 Energy Trading App</h1>
            <h2>Server is Running!</h2>
            <p><a href="/test-db">Test Database Connection</a></p>
        </body>
    </html>
    """

@app.route('/test-db')
def test_db():
    if db is None:
        return """
        <html>
            <body style="font-family: Arial; padding: 50px; text-align: center;">
                <h1>❌ Database Not Connected</h1>
                <p>Check the terminal for error messages</p>
                <a href="/">Go Back</a>
            </body>
        </html>
        """, 500
    
    try:
        # Try to access the database
        collections = db.list_collection_names()
        return f"""
        <html>
            <body style="font-family: Arial; padding: 50px; text-align: center;">
                <h1>✓ Database Connected!</h1>
                <p>Collections: {collections if collections else 'None yet'}</p>
                <a href="/">Go Back</a>
            </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html>
            <body style="font-family: Arial; padding: 50px; text-align: center;">
                <h1>❌ Database Error</h1>
                <p>{str(e)}</p>
                <a href="/">Go Back</a>
            </body>
        </html>
        """, 500

if __name__ == '__main__':
    print("\n2. Starting Flask server...")
    print("✓ Server starting at: http://127.0.0.1:5050")
    print("\nOpen your browser and go to: http://127.0.0.1:5050")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 50)
    app.run(debug=True, port=5050, host='127.0.0.1')