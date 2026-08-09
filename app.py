from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import math
import os

app = Flask(__name__, static_folder='.')
CORS(app)

GOOGLE_API_KEY = "AIzaSyDi4k9JXzYIWgmG5VE6F-axQ6-TJY5fG6M"

GENRE_MAP = {
    # אוכל
    "restaurant": {"type": "restaurant", "keyword": "restaurant"},
    "italian": {"type": "restaurant", "keyword": "italian restaurant pizza"},
    "sushi": {"type": "restaurant", "keyword": "sushi asian restaurant"},
    "meat": {"type": "restaurant", "keyword": "steakhouse meat restaurant"},
    "vegan_only": {"type": "restaurant", "keyword": "vegan restaurant"},
    "kosher": {"type": "restaurant", "keyword": "kosher restaurant"},
    "cafe": {"type": "cafe", "keyword": "cafe coffee shop"},
    # חיי לילה
    "bar": {"type": "bar", "keyword": "bar pub nightlife"},
    # לינה
    "hotel": {"type": "lodging", "keyword": "hotel resort boutique hotel"},
    "b_and_b": {"type": "lodging", "keyword": "zimer bed and breakfast guest house"},
    # אטרקציות
    "attraction": {"type": "tourist_attraction", "keyword": "attraction park museum"}
}

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/search', methods=['POST'])
def search_places():
    data = request.json
    center_lat = float(data.get('lat'))
    center_lng = float(data.get('lng'))
    max_radius = float(data.get('radius', 2000))
    genre = data.get('genre', 'restaurant')
    min_rating = float(data.get('min_rating', 0))
    open_now = data.get('open_now', False)

    genre_info = GENRE_MAP.get(genre, {"type": "restaurant", "keyword": "restaurant"})

    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{center_lat},{center_lng}",
        "radius": max_radius,
        "type": genre_info["type"],
        "key": GOOGLE_API_KEY
    }

    if "keyword" in genre_info:
        params["keyword"] = genre_info["keyword"]
        
    if open_now and genre_info["type"] in ["restaurant", "cafe", "bar"]:
        params["opennow"] = "true"

    try:
        response = requests.get(url, params=params).json()
        results = response.get("results", [])

        filtered_places = []
        for place in results:
            p_lat = place['geometry']['location']['lat']
            p_lng = place['geometry']['location']['lng']
            
            exact_distance = calculate_distance(center_lat, center_lng, p_lat, p_lng)
            if exact_distance > max_radius:
                continue

            google_rating = place.get("rating", 0)
            user_ratings_total = place.get("user_ratings_total", 0)
            price_lvl = place.get("price_level")

            price_display = "₪" * int(price_lvl) if (price_lvl is not None and price_lvl > 0) else "₪₪"

            if google_rating >= min_rating:
                place_id = place.get("place_id")
                
                # תמונה מ-Google Places
                photo_url = None
                if place.get("photos"):
                    photo_ref = place["photos"][0].get("photo_reference")
                    if photo_ref:
                        photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={photo_ref}&key={GOOGLE_API_KEY}"

                # חישוב זמני הגעה משוערים
                walk_min = max(1, round(exact_distance / 80))   # ~4.8 קמ"ש
                drive_min = max(1, round(exact_distance / 500)) # ~30 קמ"ש עירוני

                base_score = google_rating * 16
                ratings_bonus = 20 if user_ratings_total >= 2500 else (15 if user_ratings_total >= 1000 else (10 if user_ratings_total >= 500 else (5 if user_ratings_total >= 150 else 0)))
                combined_score = int(min(100, round(base_score + ratings_bonus)))

                maps_url = f"https://www.google.com/maps/search/?api=1&query={p_lat},{p_lng}&query_place_id={place_id}"

                filtered_places.append({
                    "id": place_id,
                    "name": place.get("name"),
                    "google_rating": google_rating,
                    "combined_score": combined_score,
                    "price_display": price_display,
                    "address": place.get("vicinity", "כתובת לא זמינה"),
                    "distance": int(exact_distance),
                    "walk_min": walk_min,
                    "drive_min": drive_min,
                    "photo_url": photo_url,
                    "lat": p_lat,
                    "lng": p_lng,
                    "genre": genre,
                    "user_ratings_total": user_ratings_total,
                    "maps_url": maps_url
                })

        filtered_places.sort(key=lambda x: x['combined_score'], reverse=True)
        return jsonify({"status": "success", "places": filtered_places})

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)