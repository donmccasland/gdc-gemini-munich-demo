import os
import json
import uuid
import mimetypes
from datetime import datetime
from google import genai
from google.genai import types
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
    mime_type, _ = mimetypes.guess_type(filepath)
    
    # Fallback for common types if standard lib misses them or returns None
    if mime_type is None:
        if filename.endswith(('.yaml', '.yml')):
            mime_type = 'application/x-yaml'
        elif filename.endswith('.json'):
             mime_type = 'application/json'
        elif filename.endswith('.txt'):
            mime_type = 'text/plain'
        elif filename.endswith('.csv'):
            mime_type = 'text/csv'
        else:
            mime_type = 'application/octet-stream'

    # Define what we consider "text" that can be read directly into the prompt string
    is_text = mime_type.startswith('text/') or mime_type in [
        'application/json', 'application/x-yaml', 'application/yaml', 'text/yaml', 'text/csv'
    ]

    base_name = "_".join(filename.split('_')[:-1])
    assessment_type = TYPE_MAPPING.get(base_name, "Unknown Type")
    if assessment_type == "Unknown Type" and "Gemini_Generated_Image" in filename:
         assessment_type = "Visual Threat Evidence"

    file_format = filename.split('.')[-1]

    prompt_text = f"""
    Extract the following information from this {file_format.upper()} threat assessment:
    - Source of the attack (full detail)
    - Target of the attack (full detail)
    - Attack method (full detail)
    - Attack timing (full detail)
    - A short summary of the source (max 5 words)
    - A short summary of the target (max 5 words)
    - A short summary of the attack method (max 5 words)
    - A short summary of the attack timing (max 5 words)
    - A short summary of the entire assessment (max 2 sentences)

    Return the result as a JSON object with keys: 'source', 'target', 'method', 'timing', 'source_summary', 'target_summary', 'method_summary', 'timing_summary', 'summary'.
    If a field cannot be found, use "Unknown".
    """

    try:
        # Need to re-initialize client in process for safety
        client = genai.Client(vertexai=True, project='gemini-gdc-demo', location='us-central1')
        
        if is_text:
            with open(filepath, "r", encoding='utf-8') as f:
                raw_content = f.read()
            contents = f"{prompt_text}\n\nAssessment Content:\n{raw_content}"
        else:
            # Binary media (images, pdfs, etc.)
            with open(filepath, "rb") as f:
                file_data = f.read()
            raw_content = f"[Binary Media File: {filename} ({mime_type})]"
            contents = [
                prompt_text,
                types.Part.from_bytes(data=file_data, mime_type=mime_type)
            ]

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=contents,
            config=types.GenerateContentConfig(
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
            summary=get_str(extracted_data, 'summary'),
            source_summary=get_str(extracted_data, 'source_summary'),
            target_summary=get_str(extracted_data, 'target_summary'),
            method_summary=get_str(extracted_data, 'method_summary'),
            timing_summary=get_str(extracted_data, 'timing_summary'),
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

    # Process all files, let process_file handle types
    files = [f for f in os.listdir(INPUT_DIR) if os.path.isfile(os.path.join(INPUT_DIR, f))]
    # Filter out .DS_Store and other obvious junk
    files = [f for f in files if not f.startswith('.')]
    
    print(f"Processing {len(files)} files...")
    
    # Reduce parallelism slightly to avoid hitting API rate limits too hard with heavier media files
    with Pool(min(cpu_count(), 10)) as pool:
        results = pool.map(process_file, files)
        
    assessments = [r for r in results if r is not None]
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump([a.model_dump(mode='json') for a in assessments], f, indent=2)
    
    print(f"Saved {len(assessments)} processed assessments to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
