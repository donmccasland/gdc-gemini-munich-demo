import json
from datetime import date, datetime as dt
from enum import Enum
from typing import List, Optional

from jinja2 import Environment
from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """
    Represents a single transaction within a signals or security report.
    """

    transaction_id: str = Field(..., description="Unique identifier for the transaction.")
    datetime: dt = Field(..., description="Date and time the transaction was created.")
    account_number: str = Field(..., description="Account number involved in the transaction.")
    merchant_recipient: str = Field(..., description="Merchant or recipient of the transaction.")
    location: str = Field(..., description="Location where the transaction occurred. Format: City, State, Country")
    amount: Optional[float] = Field(..., description="Amount of the transaction (can be null for security events).")
    currency: Optional[str] = Field(..., description="Currency of the transaction (can be null for security events).")
    description_notes: str = Field(..., description="Description or notes about the transaction.")
    suspected_signals_type: str = Field(..., description="Type of suspected signals or security issue.")
    risk_score: int = Field(..., description="Risk score associated with the transaction. From 1 to 100.")


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
    transactions: List[Transaction] = Field(..., description="List of transactions in the report.")
    trends: str = Field(..., description="Trends observed in the data.")
    patterns: str = Field(..., description="Patterns observed in the data.")
    risk_factors: str = Field(..., description="Risk factors identified.")
    actions_taken: str = Field(..., description="Actions taken in response to the identified issues.")
    recommendations: str = Field(..., description="Recommendations for future actions.")
    client_name: str = Field(..., description="Name of the client the report is about.")
    total_number_of_transactions: int = Field(
        ...,
        description="Total number of transactions by the client in given date range. "
        "Including non-suspicious transactions.",
    )
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

## Transactions

**Total number of transactions:** {{ total_number_of_transactions }}

**Suspicious transactions:** {{ transactions|length }}

### Suspected Signals Transactions

| Transaction ID | Date       | Account Number       | Merchant/Recipient      | Location | Amount ($) | Description/Notes                                            | Suspected Signals Type           |
| -------------- | ---------- | -------------------- | ----------------------- | ---------| ---------- | ------------------------------------------------------------ | ------------------------------ |
{% for transaction in transactions -%}
| {{ transaction.transaction_id }} | {{ transaction.datetime }} | `{{ transaction.account_number }}` | {{ transaction.merchant_recipient }} | {{transaction.location}} | {{ transaction.amount|float|round(2) }} {{ transaction.currency }} | {{ transaction.description_notes }}                | {{ transaction.suspected_signals_type }} |
{% endfor %}

## Trends and Patterns

*   **Trends:** {{ trends }}
*   **Patterns:** {{ patterns }}

## Risk Factors

{{ risk_factors }}

## Actions Taken

{{ actions_taken }}

## Recommendations

{{ recommendations }}

## Supporting Documentation

{{ supporting_docs }}

## Contact Information

**Client Name:** {{ client_name }}
"""

    def generate_report(self, report_data):
        return self.template.render(report_data)

    @staticmethod
    def from_json(json_data, template_str=None):
        return SignalsReportGenerator(template_str).generate_report(json.loads(json_data))