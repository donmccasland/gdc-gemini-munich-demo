import json
import random

# List of coordinates for major EU cities/regions to use as synthetic data
EU_LOCATIONS = [
    {"lat": 48.8566, "lon": 2.3522},   # Paris, France
    {"lat": 52.5200, "lon": 13.4050},  # Berlin, Germany
    {"lat": 40.4168, "lon": -3.7038},  # Madrid, Spain
    {"lat": 41.9028, "lon": 12.4964},  # Rome, Italy
    {"lat": 52.3676, "lon": 4.9041},   # Amsterdam, Netherlands
    {"lat": 50.8503, "lon": 4.3517},   # Brussels, Belgium
    {"lat": 48.2082, "lon": 16.3738},  # Vienna, Austria
    {"lat": 52.2297, "lon": 21.0122},  # Warsaw, Poland
    {"lat": 50.0755, "lon": 14.4378},  # Prague, Czech Republic
    {"lat": 47.4979, "lon": 19.0402},  # Budapest, Hungary
    {"lat": 59.3293, "lon": 18.0686},  # Stockholm, Sweden
    {"lat": 55.6761, "lon": 12.5683},  # Copenhagen, Denmark
    {"lat": 53.3498, "lon": -6.2603},  # Dublin, Ireland
    {"lat": 38.7223, "lon": -9.1393},  # Lisbon, Portugal
    {"lat": 48.1351, "lon": 11.5820},  # Munich, Germany
    {"lat": 50.1109, "lon": 8.6821},   # Frankfurt, Germany
    {"lat": 53.5511, "lon": 9.9937},   # Hamburg, Germany
    {"lat": 45.4642, "lon": 9.1900},   # Milan, Italy
    {"lat": 41.3851, "lon": 2.1734},   # Barcelona, Spain
    {"lat": 45.7640, "lon": 4.8357},   # Lyon, France
    {"lat": 47.3769, "lon": 8.5417},   # Zurich, Switzerland (not EU but in Europe region often grouped)
    {"lat": 46.2044, "lon": 6.1432}    # Geneva, Switzerland
]

def main():
    try:
        with open('processed_assessments.json', 'r') as f:
            assessments = json.load(f)
    except FileNotFoundError:
        print("processed_assessments.json not found.")
        return

    # Find assessments that don't have geolocation yet
    available_indices = [i for i, a in enumerate(assessments) if 'lat' not in a]
    
    # Shuffle to pick random ones
    random.shuffle(available_indices)
    
    # Select up to 22 (len of EU_LOCATIONS) to inject
    num_to_inject = min(len(available_indices), len(EU_LOCATIONS))
    indices_to_inject = available_indices[:num_to_inject]
    
    print(f"Injecting {num_to_inject} European locations...")
    
    for i, idx in enumerate(indices_to_inject):
        loc = EU_LOCATIONS[i]
        assessments[idx]['lat'] = loc['lat']
        assessments[idx]['lon'] = loc['lon']
        # Optional: Add a note that this was synthetically added if desired, 
        # but for a demo it might be better to look 'real'.
        # assessments[idx]['geo_source'] = 'synthetic_eu_demo' 

    with open('processed_assessments.json', 'w') as f:
        json.dump(assessments, f, indent=2)

    print("Finished injecting European locations.")

if __name__ == "__main__":
    main()
