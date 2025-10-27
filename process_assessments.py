import os
import json
import uuid
from datetime import datetime
from google import genai
from google.genai.types import GenerateContentConfig
from signals_report import Assessment
from multiprocessing import Pool, cpu_count

TYPE_MAPPING = {
    "cyber_attack_on_cni": "Cyber attack on CNI",
    "drones_disrupting_flights": "Drones disrupting flights",
    "cyber_attacks_on_retail_nodes": "Cyber attacks on retail nodes",
    "cyber_attacks_on_utilities": "Cyber attacks on utilities",
    "acts_of_physical_sabotage_on_infrastructure": "Acts of physical sabotage on infrastructure",
    "disinformation_campaigns_against_key_politicians": "Disinformation campaigns against key politicians",
    "disruption_of_democratic_events": "Disruption of democratic events"
}

INPUT_DIR = "generated-assessments"
OUTPUT_FILE = "processed_assessments.json"

def process_file(filename):
    if not os.path.isfile(os.path.join(INPUT_DIR, filename)):
        return None
        
    filepath = os.path.join(INPUT_DIR, filename)
    with open(filepath, "r") as f:
        raw_content = f.read()

    file_format = filename.split('.')[-1]
    base_name = "_".join(filename.split('_')[:-1])
    assessment_type = TYPE_MAPPING.get(base_name, "Unknown Type")

    prompt = f"""
    Extract the following information from this {file_format.upper()} threat assessment:
    - Source of the attack
    - Target of the attack
    - Attack method
    - Attack timing

    Return the result as a JSON object with keys: 'source', 'target', 'method', 'timing'.
    If a field cannot be found, use "Unknown".

    Assessment Content:
    {raw_content}
    """

    try:
        # Need to re-initialize client in process for safety
        client = genai.Client(vertexai=True, project='gemini-gdc-demo', location='us-central1')
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=GenerateContentConfig(
                response_mime_type='application/json',
                temperature=0.1,
            )
        )
        extracted_data = json.loads(response.text)
        
        if isinstance(extracted_data, list):
            if len(extracted_data) > 0:
                extracted_data = extracted_data[0]
            else:
                extracted_data = {}

        def get_str(data, key):
            val = data.get(key, 'Unknown')
            if isinstance(val, (dict, list)):
                return json.dumps(val)
            return str(val)
        
        assessment = Assessment(
            assessment_id=uuid.uuid4().hex[:10].upper(),
            type=assessment_type,
            source=get_str(extracted_data, 'source'),
            target=get_str(extracted_data, 'target'),
            method=get_str(extracted_data, 'method'),
            timing=get_str(extracted_data, 'timing'),
            original_format=file_format,
            raw_content=raw_content
        )
        return assessment
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        return None

def main():
    if not os.path.exists(INPUT_DIR):
        print(f"Input directory {INPUT_DIR} does not exist.")
        return

    files = [f for f in os.listdir(INPUT_DIR) if os.path.isfile(os.path.join(INPUT_DIR, f))]
    print(f"Processing {len(files)} files...")
    
    with Pool(min(cpu_count(), 20)) as pool:
        results = pool.map(process_file, files)
        
    assessments = [r for r in results if r is not None]
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump([a.model_dump(mode='json') for a in assessments], f, indent=2)
    
    print(f"Saved {len(assessments)} processed assessments to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()