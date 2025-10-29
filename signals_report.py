import json
from datetime import date, datetime as dt
from enum import Enum
from typing import List, Optional, Any, Dict

from jinja2 import Environment
from pydantic import BaseModel, Field


class Assessment(BaseModel):
    """
    Represents a standardized threat assessment derived from various source formats.
    """
    assessment_id: str = Field(..., description="Unique identifier for the assessment.")
    type: str = Field(..., description="Type of threat assessment (e.g., 'Cyber attack on CNI').")
    source: str = Field(..., description="Source of the attack/threat (Attacker, Threat Actor, etc.).")
    target: str = Field(..., description="Target of the attack/threat (Victim, Asset, etc.).")
    method: str = Field(..., description="Method of attack (Vector, TTPs, etc.).")
    timing: str = Field(..., description="Timing of the attack (Date, Time, Window).")
    summary: Optional[str] = Field(default=None, description="Short summary of the raw content.")
    source_summary: Optional[str] = Field(default=None, description="Short summary of the source.")
    target_summary: Optional[str] = Field(default=None, description="Short summary of the target.")
    method_summary: Optional[str] = Field(default=None, description="Short summary of the method.")
    timing_summary: Optional[str] = Field(default=None, description="Short summary of the timing.")
    severity: Optional[str] = Field(default=None, description="Severity of the threat (e.g., High, Medium, Low).")
    original_format: str = Field(..., description="Original format of the assessment (json, yaml, csv, txt).")
    filename: Optional[str] = Field(default=None, description="Original filename of the assessment.")
    raw_content: str = Field(..., description="Full raw content of the assessment.")
    created_at: dt = Field(default_factory=dt.now, description="Date and time when this assessment object was created.")
    lat: Optional[float] = Field(default=None, description="Latitude of the target location.")
    lon: Optional[float] = Field(default=None, description="Longitude of the target location.")
    additional_data: Optional[Dict[str, Any]] = Field(default=None, description="Any other relevant data extracted.")


class AssessmentGenerator:
    def generate_report(self, assessment: Assessment) -> str:
        return f"""
# Assessment: {assessment.type}

**ID:** {assessment.assessment_id}
**Created At:** {assessment.created_at}
**Original Format:** {assessment.original_format}

## Summary
*   **Source:** {assessment.source}
*   **Target:** {assessment.target}
*   **Method:** {assessment.method}
*   **Timing:** {assessment.timing}

## Raw Content
```{assessment.original_format}
{assessment.raw_content}
```
"""

# --- Legacy Signals Report Classes (kept for backward compatibility if needed temporarily) ---

class SignalsReportStatus(str, Enum):
    alert_review = "alert_review"
    case_review = "case_review"
    conclusion = "conclusion"


class SignalsReport(BaseModel):
    """
    Represents a signals or security report containing multiple transactions.
    """

    report_id: str = Field(..., description="Unique identifier for the report.")
    report_date: date = Field(..., description="Date of the report (YYYY-MM-DD).")
    reporting_period_start: date = Field(..., description="Start date of the reporting period (YYYY-MM-DD).")
    reporting_period_end: date = Field(..., description="End date of the reporting period (YYYY-MM-DD).")
    prepared_by: str = Field(..., description="Name of the department or person who prepared the report.")
    executive_summary: str = Field(..., description="Executive summary of the report.")
    risk_factors: str = Field(..., description="Risk factors identified.")
    actions_taken: str = Field(..., description="Actions taken in response to the identified issues.")
    recommendations: str = Field(..., description="Recommendations for future actions.")
    stage: SignalsReportStatus = Field(..., description="Current status of the report.")


class SignalsReportList(BaseModel):
    """
    Represents a list of SignalsReports.
    """

    reports: List[SignalsReport]


class SignalsReportGenerator:
    def __init__(self, template_str=None):
        self.template = Environment().from_string(template_str or self._default_template())

    def _default_template(self):
        return """
# Signals Report - {{ report_date }}

## Report Details

**Report ID:** {{ report_id }}

**Reporting Period:** {{ reporting_period_start }} - {{ reporting_period_end }}

**Prepared By:** {{ prepared_by }}

## Executive Summary

{{ executive_summary }}

## Risk Factors

{{ risk_factors }}

## Actions Taken

{{ actions_taken }}

## Recommendations

{{ recommendations }}

"""

    def generate_report(self, report_data):
        return self.template.render(report_data)

    @staticmethod
    def from_json(json_data, template_str=None):
        return SignalsReportGenerator(template_str).generate_report(json.loads(json_data))