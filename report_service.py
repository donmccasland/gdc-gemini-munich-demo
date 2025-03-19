import datetime
import json
import os
import random
import time
import uuid
from generate_sample_reports import generate_report

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
        self.reports = random.sample(self.reports, 50)
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
        new_report = generate_report()
        self.reports.append(new_report)
        self.reports.sort(key=lambda x: x.report_date, reverse=True)

    def get_report_ids(self) -> set[str]:
        return {report.report_id for report in self.reports}




