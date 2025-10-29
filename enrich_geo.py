import json
import os
import time
from google.cloud import secretmanager
from google import genai
from google.genai import types

def initialize_gemini():
    if 'GOOGLE_API_KEY' not in os.environ:
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_name = "projects/gemini-gdc-demo/secrets/gemini-api-key/versions/latest"
            response = client.access_secret_version(request={"name": secret_name})
            os.environ["GOOGLE_API_KEY"] = response.payload.data.decode("utf-8")
        except Exception as e:
            print(f"Error fetching secret: {e}")
            return None

    try:
        client = genai.Client(vertexai=True, project="gemini-gdc-demo", location="us-central1")
        return client
    except Exception as e:
        print(f"Error initializing Gemini: {e}")
        return None

def get_geolocation(client, assessment):
    prompt = f"""
    Analyze the following threat assessment details to determine if a SPECIFIC, REAL-WORLD location (city, airport, distinct region) is mentioned as the target.
    
    Target: {assessment.get('target', '')}
    Summary: {assessment.get('summary', '')}
    Raw Content Snippet: {assessment.get('raw_content', '')[:500]}

    If a specific real-world location is identified (e.g., "London City Airport", "San Francisco", "Berlin"), provide its estimated latitude and longitude.
    Ignore generic placeholders like "Anytown", "City Alpha", "Emerald City", or broad regions without specific context.
    
    Return ONLY a JSON object with 'lat' and 'lon' keys if a location is found. 
    If no specific real-world location is found, return an empty JSON object {{}}.
    
    Example valid output: {{ "lat": 51.5033, "lon": 0.0502 }}
    Example invalid output (no location): {{}}
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error getting geolocation for {assessment.get('assessment_id')}: {e}")
        return {}

def main():
    client = initialize_gemini()
    if not client:
        return

    try:
        with open('processed_assessments.json', 'r') as f:
            assessments = json.load(f)
    except FileNotFoundError:
        print("processed_assessments.json not found.")
        return

    updated_count = 0
    print(f"Processing {len(assessments)} assessments...")

    for i, assessment in enumerate(assessments):
        # Skip if already has geolocation (optional, but good for re-runs)
        if 'lat' in assessment and 'lon' in assessment:
            continue

        geo_data = get_geolocation(client, assessment)
        if geo_data and 'lat' in geo_data and 'lon' in geo_data:
            assessment['lat'] = geo_data['lat']
            assessment['lon'] = geo_data['lon']
            updated_count += 1
            print(f"[{i+1}/{len(assessments)}] Updated {assessment['assessment_id']}: {geo_data}")
        else:
            # print(f"[{i+1}/{len(assessments)}] No location for {assessment['assessment_id']}")
            pass
        
        # Rate limiting to be safe
        if i % 10 == 0:
            time.sleep(1)

    with open('processed_assessments.json', 'w') as f:
        json.dump(assessments, f, indent=2)

    print(f"Finished. Updated {updated_count} assessments with geolocation.")

if __name__ == "__main__":
    main()
