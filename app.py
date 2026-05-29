import os
import hashlib
from flask import Flask, request, jsonify, redirect

app = Flask(__name__)

# In-memory store (no persistence needed for this assignment)
store = {}

# Grabs the base URL from environment variables, fallback to localhost if not set.
# This connects directly to our Helm config.
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080")

# Health check endpoint
# Kubernetes will ping this to make sure the app is alive.
@app.route("/health")
def health():
    return jsonify({"status": "ok!!!!!!!!!"})

# Core URL shortening logic; Handling URL shortening and redirection
@app.route("/shorten", methods=["POST"])
def shorten():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "missing 'url' field"}), 400
    
    # Generates a unique 6-character slug using MD5 hashing
    original = data["url"]
    slug = hashlib.md5(original.encode()).hexdigest()[:6]
    store[slug] = original

    return jsonify({"short_url": f"{BASE_URL}/{slug}"}), 201

@app.route("/<slug>")
def resolve(slug):

    # Fetches the original URL from memory; returns 404 if it doesn't exist
    original = store.get(slug)
    if not original:
        return jsonify({"error": "not found"}), 404
    
    # Standard HTTP 302 redirect back to the original URL
    return redirect(original, code=302)

# Simple stats endpoint to check how many links are currently stored
@app.route("/stats")
def stats():
    return jsonify({"total_links": len(store)})


if __name__ == "__main__":
    # Bound to 0.0.0.0 so the app can be reached from outside the Docker container
    app.run(host="0.0.0.0", port=8080)