import datetime
import json
import os
import random
import time
import uuid

import streamlit as st
from faker import Faker
from google.genai.types import GenerateContentConfig

from generate_sample_reports import generate_report
from fraud_report import FraudReportGenerator, FraudReport

fake = Faker()


class ReportManager:
    def __init__(self, reports_key="reports", report_file_path="sample_data.json"):
        """
        Initializes the ReportManager.

        Args:
            reports_key (str): The key used to store reports in st.session_state.
            report_file_path (str): The path to the JSON file containing reports.
        """
        self.reports_key = reports_key
        self.report_file_path = report_file_path
        self.report_generator = FraudReportGenerator()

        if self.reports_key not in st.session_state:
            st.session_state[self.reports_key] = self._load_initial_reports()

        self.reports = st.session_state[self.reports_key]

        # Handle the case where no reports were loaded
        if not self.reports:
            self.reports = [self._generate_unique_report() for _ in range(50)]  # Generate 50 reports
            st.session_state[self.reports_key] = self.reports

        self.reports.sort(key=lambda x: x.report_date, reverse=True)

    def _load_initial_reports(self) -> list[FraudReport]:
        """
        Loads initial fraud reports from a JSON file, selects 50 random reports,
        or generates them if the file doesn't exist.
        """
        if os.path.exists(self.report_file_path):
            try:
                with open(self.report_file_path, "r") as f:
                    reports_data = json.load(f)
                    reports = [FraudReport(**report) for report in reports_data]
                    if reports:
                        reports = random.sample(reports, min(50, len(reports)))
                        return reports
                    else:
                        return []
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Error loading reports: {e}")
                return []
        else:
            print(f"Report file not found: {self.report_file_path}")
            return []

    def get_all_reports(self) -> list[FraudReport]:
        """Returns all loaded fraud reports."""
        return self.reports

    def _generate_unique_report(self) -> FraudReport:
        """Generates a new report that is unique compared to existing reports."""
        while True:
            new_report = generate_report()
            if new_report.report_id not in self.get_report_ids():
                return new_report

    def generate_new_report(self):
        """Generates a new report and adds it to the list."""
        new_report = self._generate_unique_report()
        self.reports.append(new_report)
        self.reports.sort(key=lambda x: x.report_date, reverse=True)
        st.session_state[self.reports_key] = self.reports

    def get_report_ids(self) -> set[str]:
        """Returns a set of all report IDs."""
        return {report.report_id for report in self.reports}

    def reset_the_reports(self, reports_number: int = 50) -> None:
        """
        Reduces the number of reports in the system down to reports_number.
        Does nothing if reports_number >= current number of reports.
        """
        if reports_number >= len(self.reports):
            return
        self.reports = random.sample(self.reports, reports_number)
        self.reports.sort(key=lambda x: x.report_date, reverse=True)
        st.session_state[self.reports_key] = self.reports
