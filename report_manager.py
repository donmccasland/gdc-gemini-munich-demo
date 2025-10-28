import datetime
import json
import os
import random
import streamlit as st
from pydantic import ValidationError
from signals_report import Assessment

class ReportManager:
    def __init__(self, reports_key="assessments", report_file_path="processed_assessments.json"):
        self.reports_key = reports_key
        self.report_file_path = report_file_path

        if self.reports_key not in st.session_state:
            st.session_state[self.reports_key] = self._load_initial_reports()

        self.reports = st.session_state[self.reports_key]

    def _load_initial_reports(self) -> list[Assessment]:
        if os.path.exists(self.report_file_path):
            try:
                with open(self.report_file_path, "r") as f:
                    reports_data = json.load(f)
                    reports = [Assessment(**report) for report in reports_data]
                    random.shuffle(reports)
                    return reports
            except Exception as e:
                st.error(f"Error loading assessments: {e}")
                return []
        else:
            st.warning(f"Assessment file not found: {self.report_file_path}")
            return []

    def get_all_reports(self) -> list[Assessment]:
        return self.reports

    def get_report_ids(self) -> set[str]:
        return {report.assessment_id for report in self.reports}

    def get_report_by_id(self, report_id: str) -> Assessment | None:
        for report in self.reports:
            if report.assessment_id == report_id:
                return report
        return None

    def reset_the_reports(self, reports_number: int = 50) -> None:
        self.reports = self._load_initial_reports()
        if len(self.reports) > reports_number:
             self.reports = self.reports[:reports_number]
        st.session_state[self.reports_key] = self.reports
