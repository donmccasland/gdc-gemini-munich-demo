import datetime
import json
import random
import time
import uuid
from multiprocessing import Pool, cpu_count

from faker import Faker
from faker.providers import bank
from google import genai
from google.genai.types import GenerateContentConfig

from fraud_report import *

client = genai.Client(vertexai=True, project='gemini-gdc-demo', location='us-central1')
fake = Faker()
fake.add_provider(bank)

reports = []

def random_datetime(start, end):
    delta = end - start
    int_delta = int(delta.total_seconds())
    random_second = random.randrange(int_delta)
    return datetime.datetime(start.year, start.month, start.day) + datetime.timedelta(seconds=random_second)


def generate_report() -> FraudReport:
    start = time.time()
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=f'Generate an example fraud report following the given schema. '
                 f'The report should feature between 2 and 8 fraudulent transactions.'
                 f'Current date is {datetime.datetime.now()}, make the reports as recent as possible.',
        config=GenerateContentConfig(
            temperature=0.8,
            candidate_count=1,
            response_mime_type='application/json',
            response_schema=FraudReport,
        ),
    )
    print(f"New fraud report generated in: {time.time() - start}s")
    fr = FraudReport.model_validate_json(response.text)
    fr.report_id = uuid.uuid4().hex[:10].upper()
    fr.client_name = fake.name()
    fr.total_number_of_transactions = int(len(fr.transactions) / (random.random() / 10))
    for transaction in fr.transactions:
        transaction.transaction_id = uuid.uuid4().hex[:16].upper()
        transaction.datetime = random_datetime(fr.reporting_period_start, fr.reporting_period_end)
        transaction.account_number = fake.iban()
        transaction.amount = random.randint(100, 50000) if transaction.amount else transaction.amount
    start = time.time()
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=f"Generate a summary fo the following fraud report: {fr.model_dump_json()}",
        config=GenerateContentConfig(
            temperature=0.2,
            candidate_count=1,
            response_mime_type='text/plain',
        )
    )
    print(f"Generated summary of the fraud report in: {time.time() - start}s")
    fr.executive_summary = response.text
    return fr

def generate_report_wrapper(i):
    fr = generate_report()
    return fr.model_dump(mode='json')

def main():
    num_reports = 500
    num_processes = cpu_count()

    print(f"Generating {num_reports} reports using {num_processes} processes...")

    start_time = time.time()

    with Pool(processes=num_processes) as pool:
        reports = pool.map(generate_report_wrapper, range(num_reports))

    end_time = time.time()

    print(f"Finished generating {num_reports} reports in {end_time - start_time:.2f} seconds")

    with open('sample_data2.json', mode="wt") as out:
        json.dump(reports, out, indent=2)

if __name__ == '__main__':
    main()

