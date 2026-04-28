from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import re
import json
from urllib.parse import urljoin, urlparse
import os

app = Flask(__name__)
CORS(app)

BASE_URL = "https://moviefan.org"

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_file('index.html')

@app.route('/api/search', methods=['GET'])
def search_movie():
    """Search for movies or TV shows on moviefan.org"""
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
            results = []
            
            if data.get('data'):
                for item in data['data']:
                    results.append({
                        'id': item.get('id', ''),
                        'title': item.get('t', 'Unknown'),
                        'type': 'TV Series' if item.get('d') == 's' else 'Movie',
                        'typeCode': item.get('d', 'm'),
                        'url': item.get('s', ''),
                        'poster': item.get('i', ''),
                        'year': item.get('y', ''),
                        'imdbId': item.get('imdb', '')
                    })
            
            return jsonify({'results': results})
        else:
            return jsonify({'results': []})
            
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({'results': []})

@app.route('/api/movie/<path:slug_url>', methods=['GET'])
def get_movie_details(slug_url):
    """Get movie details and video iframe from moviefan.org"""
    try:
        # Get encoded ID from the page
        encoded_id, media_type = get_encoded_id_from_page(slug_url)
        
        if not encoded_id:
            return jsonify({'error': 'Could not extract encoded ID'}), 404
        
        # Get title and info from the page
        title, poster, year, plot = get_page_info(slug_url)
        
        # Get iframe HTML
        iframe_html = get_video_link(encoded_id, media_type)
        
        # Extract actual video URL from iframe
        video_url = extract_video_url_from_iframe(iframe_html) if iframe_html else None
        
        return jsonify({
            'title': title,
            'poster': poster,
            'year': year,
            'plot': plot,
            'type': 'TV Series' if media_type == 'tv' else 'Movie',
            'iframeHtml': iframe_html,
            'videoUrl': video_url,
            'encodedId': encoded_id,
            'mediaType': media_type
        })
        
    except Exception as e:
        print(f"Details error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tv/<path:slug_url>', methods=['GET'])
def get_tv_episodes(slug_url):
    """Get TV show episodes and video for specific episode"""
    season = request.args.get('season', 1, type=int)
    episode = request.args.get('episode', 1, type=int)
    
    try:
        # Get encoded ID from the page
        encoded_id, media_type = get_encoded_id_from_page(slug_url)
        
        if not encoded_id or media_type != 'tv':
            return jsonify({'error': 'Could not extract encoded ID for TV show'}), 404
        
        # Get episodes list
        episodes = get_episodes_list(slug_url)
        
        # Get iframe for specific episode
        iframe_html = get_video_link(encoded_id, 'tv', season, episode)
        video_url = extract_video_url_from_iframe(iframe_html) if iframe_html else None
        
        return jsonify({
            'season': season,
            'episode': episode,
            'episodes': episodes,
            'iframeHtml': iframe_html,
            'videoUrl': video_url
        })
        
    except Exception as e:
        print(f"TV episode error: {e}")
        return jsonify({'error': str(e)}), 500

def get_encoded_id_from_page(slug_url):
    """Navigate to the page and extract encoded ID from JavaScript"""
    full_url = urljoin(BASE_URL, slug_url)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": BASE_URL
    }
    
    try:
        response = requests.get(full_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            # Look for the encoded ID in the onclick or getlink calls
            pattern = r"getlink\s*\(\s*'([^']+)'\s*,\s*'([^']+)'"
            match = re.search(pattern, response.text)
            
            if match:
                encoded_id = match.group(1)
                media_type = match.group(2)
                print(f"Found encoded ID: {encoded_id[:20]}... (type: {media_type})")
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

def get_page_info(slug_url):
    """Extract title, poster, year, and plot from page"""
    full_url = urljoin(BASE_URL, slug_url)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": BASE_URL
    }
    
    try:
        response = requests.get(full_url, headers=headers, timeout=15)
        title = "Unknown"
        poster = ""
        year = ""
        plot = ""
        
        if response.status_code == 200:
            # Extract title
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', response.text)
            if title_match:
                title = title_match.group(1).strip()
            
            # Extract poster image
            poster_match = re.search(r'<img[^>]+class="[^"]*poster[^"]*"[^>]+src="([^"]+)"', response.text)
            if not poster_match:
                poster_match = re.search(r'<img[^>]+src="([^"]+)"[^>]+alt="[^"]*poster[^"]*"', response.text)
            if poster_match:
                poster = poster_match.group(1)
                if not poster.startswith('http'):
                    poster = urljoin(BASE_URL, poster)
            
            # Extract year
            year_match = re.search(r'<span[^>]*>(\d{4})</span>', response.text)
            if year_match:
                year = year_match.group(1)
            
            # Extract plot/synopsis
            plot_match = re.search(r'<div[^>]*class="[^"]*synopsis[^"]*"[^>]*>(.*?)</div>', response.text, re.DOTALL)
            if plot_match:
                plot = re.sub(r'<[^>]+>', '', plot_match.group(1)).strip()[:500]
        
        return title, poster, year, plot
        
    except Exception as e:
        print(f"Error getting page info: {e}")
        return "Unknown", "", "", ""

def get_episodes_list(slug_url):
    """Extract list of seasons and episodes from TV show page"""
    full_url = urljoin(BASE_URL, slug_url)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": BASE_URL
    }
    
    episodes = {}
    
    try:
        response = requests.get(full_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            # Look for season select options
            season_pattern = r'<option[^>]*value="(\d+)"[^>]*>Season\s+(\d+)</option>'
            seasons = re.findall(season_pattern, response.text, re.IGNORECASE)
            
            if not seasons:
                # Try alternative pattern
                season_pattern = r'data-season="(\d+)"'
                seasons = [(s, s) for s in re.findall(season_pattern, response.text)]
            
            for season_val, season_num in seasons:
                episodes[int(season_num)] = {'count': 0, 'episodes': []}
            
            # Look for episode items
            episode_pattern = r'data-episode="(\d+)"[^>]*>.*?Episode\s+\d+.*?<'
            all_episodes = re.findall(episode_pattern, response.text, re.IGNORECASE)
            
            if all_episodes:
                for ep_num in all_episodes:
                    if episodes:
                        first_season = list(episodes.keys())[0]
                        episodes[first_season]['episodes'].append(int(ep_num))
                        episodes[first_season]['count'] = len(episodes[first_season]['episodes'])
        
        # If no episodes found, return default structure
        if not episodes:
            episodes = {1: {'count': 0, 'episodes': []}}
        
        return episodes
        
    except Exception as e:
        print(f"Error getting episodes: {e}")
        return {1: {'count': 0, 'episodes': []}}

def get_video_link(encoded_id, media_type, season=None, episode=None):
    """Get the video iframe link from moviefan.org"""
    
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
                print("Got iframe embed")
                return iframe_html
        return None
        
    except Exception as e:
        print(f"Error getting video link: {e}")
        return None

def extract_video_url_from_iframe(iframe_html):
    """Extract the actual video URL from iframe embed"""
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
    app.run(host='0.0.0.0', port=port, debug=True)
