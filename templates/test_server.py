from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return "✅ Server is working!"

if __name__ == '__main__':
    print("Starting test server on port 8080...")
    print("Open: http://localhost:8080")
    app.run(debug=True, port=8080)