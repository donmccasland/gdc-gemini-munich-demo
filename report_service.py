import datetime
import json
import os
import random
import time
import uuid

from faker import Faker
from google.genai.types import GenerateContentConfig

from fraud_report import FraudReportGenerator, FraudReport

fake = Faker()

_service_singleton = None

def get_report_service():
    global _service_singleton
    if _service_singleton:
        return _service_singleton
    _service_singleton = ReportService("sample_data.json")
    return _service_singleton


class ReportService:
    def __init__(self, report_file_path="multiple_reports.json"):
        """Initializes the ReportService with the path to the report file."""
        self.report_file_path = report_file_path
        self.report_generator = FraudReportGenerator()
        self.reports = self._load_reports()
        self.reports = random.sample(self.reports, 10)
        self.reports.sort(key=lambda x: x.report_date, reverse=True)

    @staticmethod
    def _random_datetime(start, end):
        delta = end - start
        int_delta = int(delta.total_seconds())
        random_second = random.randrange(int_delta)
        return datetime.datetime(start.year, start.month, start.day) + datetime.timedelta(seconds=random_second)

    def _load_reports(self) -> list[FraudReport]:
        """Loads fraud reports from the specified JSON file."""
        if os.path.exists(self.report_file_path):
            try:
                with open(self.report_file_path, "r") as f:
                    reports_data = json.load(f)
                    reports_data = [FraudReport(**report) for report in reports_data]
                    return reports_data  # Assuming your file contains a list of reports
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Error loading reports: {e}")
                return []  # Return empty list on error
        else:
            print(f"Report file not found: {self.report_file_path}")
            return []

    def get_all_reports(self) -> list[FraudReport]:
        """Returns all loaded fraud reports."""
        return self.reports

    def generate_new_report(self):
        from main import genai_client
        start = time.time()
        response = genai_client.models.generate_content(
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
        print(f"New fraud report generated in: {time.time()-start}s")
        fr = FraudReport.model_validate_json(response.text)
        fr.report_id = uuid.uuid4().hex[:10].upper()
        fr.client_name = fake.name()
        fr.total_number_of_transactions = int(len(fr.transactions) / (random.random() / 10))
        for transaction in fr.transactions:
            transaction.transaction_id = uuid.uuid4().hex[:16].upper()
            transaction.datetime = self._random_datetime(fr.reporting_period_start, fr.reporting_period_end)
            transaction.account_number = fake.iban()
            transaction.amount = random.randint(100, 50000) if transaction.amount else transaction.amount
        start = time.time()
        response = genai_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=f"Generate a summary fo the following fraud report: {fr.model_dump_json()}",
            config=GenerateContentConfig(
                temperature=0.2,
                candidate_count=1,
                response_mime_type='text/plain',
            )
        )
        print(f"Generated summary of the fraud report in: {time.time()-start}s")
        fr.executive_summary = response.text
        self.reports.append(fr)
        return fr




