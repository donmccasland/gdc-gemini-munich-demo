import os
import random
import time
from multiprocessing import Pool, cpu_count
from google import genai
from google.genai.types import GenerateContentConfig

ASSESSMENT_TYPES = [
    "Cyber attack on CNI",
    "Drones disrupting flights",
    "Cyber attacks on retail nodes",
    "Cyber attacks on utilities",
    "Acts of physical sabotage on infrastructure",
    "Disinformation campaigns against key politicians",
    "Disruption of democratic events"
]

FORMATS = ["json", "yaml", "csv", "txt"]

OUTPUT_DIR = "generated-assessments"

def generate_assessment_task(args):
    assessment_type, index = args
    file_format = random.choice(FORMATS)
    
    prompt = f"""
    Generate a sample threat assessment for the following type: "{assessment_type}".
    The output must be in {file_format.upper()} format.
    It MUST contain the following information, but you MUST vary the field names/labels used to represent them (e.g., instead of 'source', use 'origin', 'attacker', 'threat_actor', etc.):
    - Source of the attack
    - Target of the attack
    - Attack method
    - Attack timing (date/time)

    Make the structure and content realistic for a threat assessment of this type.
    Vary the structure significantly from other assessments of the same type if possible.
    Do not include any markdown code block markers (like ```json or ```yaml) in the output, just the raw content of the file.
    """

    try:
        local_client = genai.Client(vertexai=True, project='gemini-gdc-demo', location='us-central1')
        
        response = local_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=GenerateContentConfig(
                temperature=0.9,
            )
        )
        
        content = response.text
        # Clean up potential markdown markers
        if content.startswith("```"):
             lines = content.splitlines()
             if lines and lines[0].startswith("```"):
                 lines = lines[1:]
             if lines and lines[-1].strip() == "```":
                 lines = lines[:-1]
             content = "\n".join(lines)

        filename = f"{assessment_type.lower().replace(' ', '_')}_{index+1:02d}.{file_format}"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        with open(filepath, "w") as f:
            f.write(content)
        return f"Generated {filename}"
        
    except Exception as e:
        return f"Error generating {assessment_type} ({file_format}): {e}"

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    tasks = []
    for assessment_type in ASSESSMENT_TYPES:
        for i in range(20):
            tasks.append((assessment_type, i))

    # Limit processes to avoid overwhelming API or system
    num_processes = min(cpu_count(), 10) 
    print(f"Starting generation of {len(tasks)} assessments using {num_processes} processes...")
    
    start_time = time.time()
    with Pool(processes=num_processes) as pool:
        results = pool.map(generate_assessment_task, tasks)
        
    # for res in results:
    #     print(res)

    end_time = time.time()
    print(f"Finished in {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
