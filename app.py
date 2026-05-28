import os
import hashlib
from flask import Flask, request, jsonify, redirect

app = Flask(__name__)

# In-memory store (no persistence needed for this assignment)
store = {}

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080")


@app.route("/health")
def health():
    return jsonify({"status": "everything is awesome"})


@app.route("/shorten", methods=["POST"])
def shorten():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "missing 'url' field"}), 400
    
    original = data["url"]
    slug = hashlib.md5(original.encode()).hexdigest()[:6]
    store[slug] = original

    return jsonify({"short_url": f"{BASE_URL}/{slug}"}), 201


@app.route("/<slug>")
def resolve(slug):
    original = store.get(slug)
    if not original:
        return jsonify({"error": "not found"}), 404
    return redirect(original, code=302)


@app.route("/stats")
def stats():
    return jsonify({"total_links": len(store)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)