from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import re
import json
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
    """Search for movies or TV shows - returns EXACT response from moviefan.org"""
    keyword = request.args.get('q', '')
    if not keyword:
        return jsonify({'error': 'No search query provided'}), 400
    
    try:
        # This is the EXACT same search your original code uses
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
            # Return EXACTLY what moviefan.org returns (including posters)
            return jsonify(data)
        else:
            return jsonify({'data': []})
            
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({'data': []})

@app.route('/api/movie/<path:slug_url>', methods=['GET'])
def get_movie_video(slug_url):
    """Get video URL for movie or TV show - EXACT same process as your original code"""
    try:
        # Step 1: Get encoded ID from the page (same as your get_encoded_id_from_page)
        encoded_id, media_type = get_encoded_id_from_page(slug_url)
        
        if not encoded_id:
            return jsonify({'error': 'Could not extract encoded ID'}), 404
        
        # Step 2: For TV shows, get season/episode (default to S1E1)
        season = request.args.get('season', None)
        episode = request.args.get('episode', None)
        
        if season and episode:
            season = int(season)
            episode = int(episode)
        
        # Step 3: Get the video iframe (same as your get_video_link)
        iframe_html = get_video_link(encoded_id, media_type, season, episode)
        
        # Step 4: Extract the video URL from iframe (same as your extract_video_url_from_iframe)
        video_url = extract_video_url_from_iframe(iframe_html) if iframe_html else None
        
        # Step 5: Get title and poster from the page
        title, poster = get_movie_info(slug_url)
        
        return jsonify({
            'title': title,
            'poster': poster,
            'videoUrl': video_url,
            'mediaType': media_type,
            'encodedId': encoded_id
        })
        
    except Exception as e:
        print(f"Video error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tv/<path:slug_url>', methods=['GET'])
def get_tv_episode_video(slug_url):
    """Get specific TV episode video URL"""
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
    """Extract encoded ID using the same pattern as your original code"""
    full_url = urljoin(BASE_URL, slug_url)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": BASE_URL
    }
    
    try:
        response = requests.get(full_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            # EXACT same pattern from your original code
            pattern = r"getlink\s*\(\s*'([^']+)'\s*,\s*'([^']+)'"
            match = re.search(pattern, response.text)
            
            if match:
                encoded_id = match.group(1)
                media_type = match.group(2)
                print(f"   Found encoded ID: {encoded_id[:20]}... (type: {media_type})")
                return encoded_id, media_type
            
            # Alternative pattern from your code
            alt_pattern = r"getlink\('([^']+)','([^']+)'"
            alt_match = re.search(alt_pattern, response.text)
            if alt_match:
                return alt_match.group(1), alt_match.group(2)
        
        return None, None
        
    except Exception as e:
        print(f"Error getting encoded ID: {e}")
        return None, None

def get_movie_info(slug_url):
    """Extract title and poster from page"""
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
            # Extract title from h1
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', response.text)
            if title_match:
                title = title_match.group(1).strip()
            
            # Extract poster image
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
    """Get video iframe - EXACT same as your original get_video_link function"""
    
    if media_type == 'tv' and season and episode:
        print(f"\n🎬 Getting TV episode: Season {season}, Episode {episode}")
        link_url = f"{BASE_URL}/ajax/get-link.php"
        params = {
            "id": encoded_id,
            "type": "tv",
            "season": season,
            "episode": episode
        }
    else:
        print(f"\n🎬 Getting movie link")
        link_url = f"{BASE_URL}/ajax/get-link.php"
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
                print(f"✅ Got iframe embed")
                return iframe_html
            else:
                print(f"❌ API returned error status")
                return None
        else:
            print(f"❌ Request failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error getting video link: {e}")
        return None

def extract_video_url_from_iframe(iframe_html):
    """Extract video URL from iframe - EXACT same as your original"""
    if not iframe_html:
        return None
    
    src_match = re.search(r'src="([^"]+)"', iframe_html)
    if src_match:
        video_page_url = src_match.group(1)
        print(f"\n🔗 Video page URL: {video_page_url}")
        return video_page_url
    
    src_match2 = re.search(r"src='([^']+)'", iframe_html)
    if src_match2:
        video_page_url = src_match2.group(1)
        print(f"\n🔗 Video page URL: {video_page_url}")
        return video_page_url
    
    return None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("\n" + "="*60)
    print("🍿 MOVIE STREAMING SERVER - FULLY WORKING")
    print("="*60)
    print(f"📍 Server: http://localhost:{port}")
    print("🔍 Try searching: Squid Game, Inception, Dune, Breaking Bad")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=port, debug=True)
