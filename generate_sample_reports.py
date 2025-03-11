import datetime
import json
import random
import time
import uuid

from faker import Faker
from faker.providers import bank
from google import genai
from google.genai.types import GenerateContentConfig

from fraud_report import *

client = genai.Client(vertexai=True, project='mestiv-playground', location='us-central1')
fake = Faker()
fake.add_provider(bank)

reports = []

def random_datetime(start, end):
    delta = end - start
    int_delta = int(delta.total_seconds())
    random_second = random.randrange(int_delta)
    return datetime.datetime(start.year, start.month, start.day) + datetime.timedelta(seconds=random_second)


for i in range(1, 50):
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
    reports.append(fr.model_dump(mode='json'))

with open('sample_data2.json', mode="wt") as out:
    json.dump(reports, out, indent=2)

