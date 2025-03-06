import json
import os
from fraud_report import FraudReportGenerator

class ReportService:
    def __init__(self, report_file_path="multiple_reports.json"):
        """Initializes the ReportService with the path to the report file."""
        self.report_file_path = report_file_path
        self.report_generator = FraudReportGenerator()
        self.reports = self._load_reports()

    def _load_reports(self):
        """Loads fraud reports from the specified JSON file."""
        if os.path.exists(self.report_file_path):
            try:
                with open(self.report_file_path, "r") as f:
                    reports_data = json.load(f)
                    return reports_data  # Assuming your file contains a list of reports
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Error loading reports: {e}")
                return []  # Return empty list on error
        else:
            print(f"Report file not found: {self.report_file_path}")
            return []

    def get_all_reports(self):
        """Returns all loaded fraud reports."""
        return self.reports

    def get_report(self, report_id):
        """Returns a specific report by ID.  You'll need to define how report IDs work."""
        # Add logic here to identify and return a specific report
        # This will depend on how you identify your reports (e.g., index, date, etc.)
        # Example (assuming reports are indexed by their position in the list):
        try:
            return self.reports[report_id]
        except IndexError:
            return None  # Or raise a custom exception

    def get_report_summary(self, report_id):
        """Returns a summary of a specific report (e.g., key details)."""
        report = self.get_report(report_id)
        if report:
            # Extract and return a summary (customize as needed)
            return {
                "report_date": report.get("report_date", "N/A"),
                "summary": report.get("executive_summary", "N/A")
            }
        return None

    def get_transactions(self, report_id):
        """Returns the transactions for a specific report."""
        report = self.get_report(report_id)
        if report:
            return report.get("transactions", [])  #Return empty list if no transactions exist.
        return []

