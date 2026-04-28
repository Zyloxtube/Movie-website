from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import re
import os
from urllib.parse import urljoin

app = Flask(__name__)
CORS(app)

BASE_URL = "https://moviefan.org"

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_file('index.html')

@app.route('/api/search', methods=['GET'])
def search_movie():
    """Search for ANY movie or TV show"""
    keyword = request.args.get('q', '')
    if not keyword:
        return jsonify({'error': 'No search query provided'}), 400
    
    try:
        # Search moviefan.org for whatever the user typed
        search_url = f"{BASE_URL}/ajax/search-new.php?keyword={keyword.replace(' ', '+')}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html, */*",
            "Referer": BASE_URL,
            "X-Requested-With": "XMLHttpRequest"
        }
        
        response = requests.get(search_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            # Return exactly what moviefan.org returns
            return jsonify(data)
        else:
            return jsonify({'data': []})
            
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({'data': []})

@app.route('/api/movie/<path:slug_url>', methods=['GET'])
def get_movie_details(slug_url):
    """Get video URL for ANY movie or TV episode"""
    try:
        # Get encoded ID from the page (works for any movie/show)
        encoded_id, media_type = get_encoded_id_from_page(slug_url)
        
        if not encoded_id:
            return jsonify({'error': 'Could not extract encoded ID'}), 404
        
        # Get season/episode for TV shows (default to S1E1)
        season = request.args.get('season', 1, type=int)
        episode = request.args.get('episode', 1, type=int)
        
        # Get the video iframe
        iframe_html = get_video_link(encoded_id, media_type, season, episode)
        
        # Extract the actual video URL
        video_url = extract_video_url_from_iframe(iframe_html) if iframe_html else None
        
        # Get title and poster
        title, poster = get_movie_info(slug_url)
        
        return jsonify({
            'title': title,
            'poster': poster,
            'videoUrl': video_url,
            'mediaType': media_type
        })
        
    except Exception as e:
        print(f"Details error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tv/<path:slug_url>', methods=['GET'])
def get_tv_episode(slug_url):
    """Get specific TV episode for ANY show"""
    season = request.args.get('season', 1, type=int)
    episode = request.args.get('episode', 1, type=int)
    
    try:
        encoded_id, media_type = get_encoded_id_from_page(slug_url)
        
        if not encoded_id:
            return jsonify({'error': 'Could not extract encoded ID'}), 404
        
        iframe_html = get_video_link(encoded_id, 'tv', season, episode)
        video_url = extract_video_url_from_iframe(iframe_html) if iframe_html else None
        
        return jsonify({
            'videoUrl': video_url,
            'season': season,
            'episode': episode
        })
        
    except Exception as e:
        print(f"TV episode error: {e}")
        return jsonify({'error': str(e)}), 500

def get_encoded_id_from_page(slug_url):
    """Extract encoded ID from ANY movie/TV show page"""
    full_url = urljoin(BASE_URL, slug_url)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": BASE_URL
    }
    
    try:
        response = requests.get(full_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            # Pattern from your original code - works for any movie/show
            pattern = r"getlink\s*\(\s*'([^']+)'\s*,\s*'([^']+)'"
            match = re.search(pattern, response.text)
            
            if match:
                encoded_id = match.group(1)
                media_type = match.group(2)
                print(f"Found encoded ID for: {full_url}")
                return encoded_id, media_type
            
            # Alternative pattern
            alt_pattern = r"getlink\('([^']+)','([^']+)'"
            alt_match = re.search(alt_pattern, response.text)
            if alt_match:
                return alt_match.group(1), alt_match.group(2)
        
        return None, None
        
    except Exception as e:
        print(f"Error getting encoded ID: {e}")
        return None, None

def get_movie_info(slug_url):
    """Extract title and poster from ANY movie/TV show page"""
    full_url = urljoin(BASE_URL, slug_url)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": BASE_URL
    }
    
    title = "Unknown"
    poster = ""
    
    try:
        response = requests.get(full_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            # Extract title
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', response.text)
            if title_match:
                title = title_match.group(1).strip()
            
            # Extract poster
            poster_match = re.search(r'<img[^>]+src="([^"]+)"[^>]+alt="[^"]*poster[^"]*"', response.text, re.IGNORECASE)
            if not poster_match:
                poster_match = re.search(r'<img[^>]+class="[^"]*poster[^"]*"[^>]+src="([^"]+)"', response.text, re.IGNORECASE)
            if poster_match:
                poster = poster_match.group(1)
                if not poster.startswith('http'):
                    poster = urljoin(BASE_URL, poster)
        
        return title, poster
        
    except Exception as e:
        print(f"Error getting movie info: {e}")
        return title, poster

def get_video_link(encoded_id, media_type, season=None, episode=None):
    """Get video iframe - works for ANY movie or TV episode"""
    
    link_url = f"{BASE_URL}/ajax/get-link.php"
    
    if media_type == 'tv' and season and episode:
        print(f"Getting TV episode S{season}E{episode}")
        params = {
            "id": encoded_id,
            "type": "tv",
            "season": season,
            "episode": episode
        }
    else:
        print(f"Getting movie link")
        params = {
            "id": encoded_id,
            "type": "movie"
        }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*",
        "Referer": BASE_URL,
        "X-Requested-With": "XMLHttpRequest"
    }
    
    try:
        response = requests.get(link_url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 1:
                iframe_html = data.get('src', '')
                print("Got iframe embed")
                return iframe_html
        return None
        
    except Exception as e:
        print(f"Error getting video link: {e}")
        return None

def extract_video_url_from_iframe(iframe_html):
    """Extract video URL from iframe embed"""
    if not iframe_html:
        return None
    
    src_match = re.search(r'src="([^"]+)"', iframe_html)
    if src_match:
        video_url = src_match.group(1)
        print(f"Video URL: {video_url[:80]}...")
        return video_url
    
    src_match2 = re.search(r"src='([^']+)'", iframe_html)
    if src_match2:
        video_url = src_match2.group(1)
        print(f"Video URL: {video_url[:80]}...")
        return video_url
    
    return None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("\n" + "="*60)
    print("🎬 MOVIE STREAMING BACKEND - READY FOR ANY SEARCH")
    print("="*60)
    print(f"📍 Server running at: http://localhost:{port}")
    print("🔍 Try searching: Inception, Dune, Batman, Squid Game, or ANYTHING")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=port, debug=True)
