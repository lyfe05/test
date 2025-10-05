#!/usr/bin/env python3
from flask import Flask, jsonify, request, render_template_string
import requests
import os
import time
import logging
from datetime import datetime
import base64
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# GitHub Pages JSON URL
GITHUB_JSON_URL = "https://lyfe05.github.io/highlight-api/matches.json"

# Cache settings - 10 MINUTES
CACHE_DURATION = 600  # 10 minutes in seconds
last_fetch_time = 0
cached_data = None
cache_hits = 0
cache_misses = 0

app = Flask(__name__)

# Your custom encoding function
def custom_encode(input_string):
    charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef'
    input_bytes = input_string.encode('utf-8')
    output = []
    bit_buffer = 0
    bit_count = 0
    
    for byte in input_bytes:
        bit_buffer = (bit_buffer << 8) | byte
        bit_count += 8
        while bit_count >= 5:
            bit_count -= 5
            value = (bit_buffer >> bit_count) & 0x1F
            output.append(charset[value])
            bit_buffer &= (1 << bit_count) - 1
    
    if bit_count > 0:
        bit_buffer <<= (5 - bit_count)
        value = bit_buffer & 0x1F
        output.append(charset[value])
        output.append('=')
    
    return ''.join(output)

def fetch_from_github():
    """Fetch data from GitHub Pages with 10-minute caching"""
    global last_fetch_time, cached_data, cache_hits, cache_misses
    
    current_time = time.time()
    
    # Return cached data if still valid (10 minutes)
    if cached_data and (current_time - last_fetch_time) < CACHE_DURATION:
        cache_hits += 1
        cache_age = int(current_time - last_fetch_time)
        logger.info(f"🔄 Serving cached data ({cache_age}s old, {cache_hits} hits)")
        return cached_data
    
    try:
        cache_misses += 1
        logger.info("📡 Fetching fresh data from GitHub Pages...")
        response = requests.get(GITHUB_JSON_URL, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        last_fetch_time = current_time
        cached_data = data
        
        logger.info(f"✅ Fetched {data.get('matches_count', 0)} matches from GitHub (Miss: {cache_misses})")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error fetching from GitHub: {e}")
        # Return cached data even if expired as fallback
        if cached_data:
            cache_age = int(current_time - last_fetch_time)
            logger.warning(f"⚠️ Using expired cache as fallback ({cache_age}s old)")
            return cached_data
        raise

@app.route('/')
def root():
    return jsonify({
        "message": "Football Matches API", 
        "status": "running",
        "source": "GitHub Pages",
        "cache_duration": "10 minutes",
        "endpoints": {
            "health": "/health",
            "matches": "/matches",
            "encoded": "/encoded"
        }
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        data = fetch_from_github()
        cache_age = int(time.time() - last_fetch_time) if last_fetch_time else 0
        
        return jsonify({
            "status": "healthy",
            "source": "online",
            "cache": {
                "enabled": True,
                "duration_seconds": CACHE_DURATION,
                "current_age_seconds": cache_age,
                "hits": cache_hits,
                "misses": cache_misses
            },
            "matches_count": data.get('matches_count', 0),
            "last_updated": data.get('last_updated'),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "degraded",
            "source": "offline",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503

@app.route('/matches')
def get_matches():
    """Get all football matches with streams (NO API key required)"""
    try:
        data = fetch_from_github()
        
        cache_age = int(time.time() - last_fetch_time)
        logger.info(f"📡 API request received | Cache: {cache_age}s")
        
        return jsonify({
            "success": True,
            "last_updated": data.get('last_updated'),
            "matches_count": data.get('matches_count', 0),
            "cache_info": {
                "age_seconds": cache_age,
                "max_age_seconds": CACHE_DURATION
            },
            "data": data.get('data', [])
        })
        
    except Exception as e:
        logger.error(f"❌ API error: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to fetch matches data",
            "timestamp": datetime.now().isoformat()
        }), 503

@app.route('/encoded')
def get_encoded_matches():
    """Get encoded football matches data"""
    try:
        data = fetch_from_github()
        
        # Convert to JSON string and encode
        json_string = json.dumps(data)
        encoded_data = custom_encode(json_string)
        
        cache_age = int(time.time() - last_fetch_time)
        logger.info(f"🔐 Encoded API request | Cache: {cache_age}s")
        
        return jsonify({
            "success": True,
            "last_updated": data.get('last_updated'),
            "matches_count": data.get('matches_count', 0),
            "cache_info": {
                "age_seconds": cache_age,
                "max_age_seconds": CACHE_DURATION
            },
            "encoded_data": encoded_data,
            "original_length": len(json_string),
            "encoded_length": len(encoded_data)
        })
        
    except Exception as e:
        logger.error(f"❌ Encoding error: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to encode matches data",
            "timestamp": datetime.now().isoformat()
        }), 503

# Startup message
logger.info("🚀 Starting Football Matches API (With Encoding)...")
logger.info(f"📡 Source: {GITHUB_JSON_URL}")
logger.info(f"💾 Cache: {CACHE_DURATION} seconds (10 minutes)")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🌐 Starting Flask server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
