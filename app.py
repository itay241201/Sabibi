from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import math
import os

app = Flask(__name__, static_folder='.')
CORS(app)

GOOGLE_API_KEY = "AIzaSyDi4k9JXzYIWgmG5VE6F-axQ6-TJY5fG6M"

# מילון סגנונות מורחב - כולל מסעדות ומלונות
GENRE_MAP = {
    # מסעדות
    "restaurant": {"type": "restaurant", "keyword": "restaurant"},
    "italian": {"type": "restaurant", "keyword": "italian restaurant pizza"},
    "sushi": {"type": "restaurant", "keyword": "sushi asian restaurant"},
    "meat": {"type": "restaurant", "keyword": "steakhouse meat restaurant"},
    "vegan": {"type": "restaurant", "keyword": "vegan vegetarian restaurant"},
    "cafe": {"type": "cafe", "keyword": "cafe coffee shop"},
    # מלונות ומקומות לינה
    "hotel": {"type": "lodging", "keyword": "hotel resort boutique hotel"},
    "b_and_b": {"type": "lodging", "keyword": "zimer bed and breakfast guest house"}
}

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # רדיוס במטרים
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
    max_radius = float(data.get('radius', 1000))
    genre = data.get('genre', 'restaurant')
    min_rating = float(data.get('min_rating', 0))
    open_now = data.get('open_now', False)

    genre_info = GENRE_MAP.get(genre, {"type": "restaurant", "keyword": "restaurant"})

    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{center_lat},{center_lng}",
        "radius": max_radius,
        "type": genre_info["type"],
        "keyword": genre_info["keyword"],
        "key": GOOGLE_API_KEY
    }
        
    if open_now and genre_info["type"] == "restaurant":
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

            if price_lvl is not None and price_lvl > 0:
                price_display = "₪" * int(price_lvl)
            else:
                price_display = "₪₪"

            if google_rating >= min_rating:
                place_id = place.get("place_id")
                
                # חישוב מדד סביבי (משוכלל)
                base_score = google_rating * 16

                if user_ratings_total >= 2500:
                    ratings_bonus = 20
                elif user_ratings_total >= 1000:
                    ratings_bonus = 15
                elif user_ratings_total >= 500:
                    ratings_bonus = 10
                elif user_ratings_total >= 150:
                    ratings_bonus = 5
                else:
                    ratings_bonus = 0

                combined_score = int(min(100, round(base_score + ratings_bonus)))

                maps_url = f"https://www.google.com/maps/search/?api=1&query={p_lat},{p_lng}&query_place_id={place_id}"

                filtered_places.append({
                    "name": place.get("name"),
                    "google_rating": google_rating,
                    "combined_score": combined_score,
                    "price_display": price_display,
                    "address": place.get("vicinity", "כתובת לא זמינה"),
                    "distance": int(exact_distance),
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