from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import re
import os
from urllib.parse import urljoin, urlparse

app = Flask(__name__)
CORS(app)

BASE_URL = "https://moviefan.org"

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/search', methods=['GET'])
def search_movie():
    keyword = request.args.get('q', '')
    if not keyword:
        return jsonify({'error': 'No search query provided'}), 400
    
    try:
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
            return jsonify(data)
        else:
            return jsonify({'data': []})
            
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({'data': []})

@app.route('/api/movie/<path:slug_url>', methods=['GET'])
def get_movie_video(slug_url):
    try:
        encoded_id, media_type = get_encoded_id_from_page(slug_url)
        
        if not encoded_id:
            return jsonify({'error': 'Could not extract encoded ID'}), 404
        
        season = request.args.get('season', None)
        episode = request.args.get('episode', None)
        
        if season and episode:
            season = int(season)
            episode = int(episode)
        
        iframe_html = get_video_link(encoded_id, media_type, season, episode)
        video_url = extract_video_url_from_iframe(iframe_html) if iframe_html else None
        
        # Clean the video URL to remove tracking parameters
        if video_url:
            video_url = clean_url(video_url)
        
        title, poster = get_movie_info(slug_url)
        
        episodes = None
        if media_type == 'tv':
            episodes = get_episodes_list(slug_url)
        
        return jsonify({
            'title': title,
            'poster': poster,
            'videoUrl': video_url,
            'mediaType': media_type,
            'encodedId': encoded_id,
            'episodes': episodes
        })
        
    except Exception as e:
        print(f"Video error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tv/<path:slug_url>', methods=['GET'])
def get_tv_episode_video(slug_url):
    season = request.args.get('season', 1, type=int)
    episode = request.args.get('episode', 1, type=int)
    
    try:
        encoded_id, media_type = get_encoded_id_from_page(slug_url)
        
        if not encoded_id:
            return jsonify({'error': 'Could not extract encoded ID'}), 404
        
        iframe_html = get_video_link(encoded_id, 'tv', season, episode)
        video_url = extract_video_url_from_iframe(iframe_html) if iframe_html else None
        
        if video_url:
            video_url = clean_url(video_url)
        
        return jsonify({
            'videoUrl': video_url,
            'season': season,
            'episode': episode
        })
        
    except Exception as e:
        print(f"TV episode error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/proxy', methods=['GET'])
def proxy_video():
    """Proxy endpoint to avoid CORS and clean video responses"""
    url = request.args.get('url', '')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://moviefan.org"
        }
        
        response = requests.get(url, headers=headers, timeout=30, stream=True)
        
        # Return the content with appropriate headers
        return response.content, response.status_code, {
            'Content-Type': response.headers.get('Content-Type', 'video/mp4'),
            'Access-Control-Allow-Origin': '*'
        }
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def clean_url(url):
    """Remove tracking parameters from URL"""
    if not url:
        return url
    
    # Parse URL and remove common tracking params
    parsed = urlparse(url)
    
    # List of tracking parameters to remove
    tracking_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                       'ref', 'source', 'tracking', 'clickid', 'fbclid', 'gclid', 'msclkid',
                       '_ga', '_gl', 'session_id', 'redirect', 'popup', 'ad']
    
    # Clean query parameters
    query_params = []
    if parsed.query:
        params = parsed.query.split('&')
        for param in params:
            if '=' in param:
                key = param.split('=')[0].lower()
                if key not in tracking_params:
                    query_params.append(param)
    
    cleaned_query = '&'.join(query_params) if query_params else ''
    
    # Rebuild URL
    from urllib.parse import ParseResult
    cleaned = ParseResult(
        scheme=parsed.scheme,
        netloc=parsed.netloc,
        path=parsed.path,
        params=parsed.params,
        query=cleaned_query,
        fragment=parsed.fragment
    )
    
    return cleaned.geturl()

def get_encoded_id_from_page(slug_url):
    full_url = urljoin(BASE_URL, slug_url)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": BASE_URL
    }
    
    try:
        response = requests.get(full_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            pattern = r"getlink\s*\(\s*'([^']+)'\s*,\s*'([^']+)'"
            match = re.search(pattern, response.text)
            
            if match:
                return match.group(1), match.group(2)
            
            alt_pattern = r"getlink\('([^']+)','([^']+)'"
            alt_match = re.search(alt_pattern, response.text)
            if alt_match:
                return alt_match.group(1), alt_match.group(2)
        
        return None, None
        
    except Exception as e:
        print(f"Error getting encoded ID: {e}")
        return None, None

def get_movie_info(slug_url):
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
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', response.text)
            if title_match:
                title = title_match.group(1).strip()
            
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

def get_episodes_list(slug_url):
    full_url = urljoin(BASE_URL, slug_url)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": BASE_URL
    }
    
    episodes = {"seasons": {}}
    
    try:
        response = requests.get(full_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            season_pattern = r'data-season="(\d+)"'
            seasons = re.findall(season_pattern, response.text)
            
            if seasons:
                unique_seasons = list(set([int(s) for s in seasons]))
                unique_seasons.sort()
                
                for season_num in unique_seasons:
                    episode_pattern = rf'data-season="{season_num}"[^>]*data-episode="(\d+)"'
                    episodes_in_season = re.findall(episode_pattern, response.text)
                    
                    if episodes_in_season:
                        episode_nums = list(set([int(e) for e in episodes_in_season]))
                        episode_nums.sort()
                        episodes["seasons"][season_num] = episode_nums
                    else:
                        episodes["seasons"][season_num] = list(range(1, 13))
            
            if not episodes["seasons"]:
                episodes["seasons"][1] = list(range(1, 13))
        
        return episodes
        
    except Exception as e:
        print(f"Error getting episodes: {e}")
        return {"seasons": {1: list(range(1, 13))}}

def get_video_link(encoded_id, media_type, season=None, episode=None):
    if media_type == 'tv' and season and episode:
        print(f"Getting TV episode: Season {season}, Episode {episode}")
        link_url = f"{BASE_URL}/ajax/get-link.php"
        params = {
            "id": encoded_id,
            "type": "tv",
            "season": season,
            "episode": episode
        }
    else:
        print(f"Getting movie link")
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
                return iframe_html
        return None
        
    except Exception as e:
        print(f"Error getting video link: {e}")
        return None

def extract_video_url_from_iframe(iframe_html):
    if not iframe_html:
        return None
    
    src_match = re.search(r'src="([^"]+)"', iframe_html)
    if src_match:
        return src_match.group(1)
    
    src_match2 = re.search(r"src='([^']+)'", iframe_html)
    if src_match2:
        return src_match2.group(1)
    
    return None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("\n" + "="*60)
    print("🎬 MOVIE STREAMING SERVER - POPUP/REDIRECT PROTECTED")
    print("="*60)
    print(f"📍 http://localhost:{port}")
    print("🛡️ Popups and redirects are blocked via sandboxed iframes")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=port, debug=True)
