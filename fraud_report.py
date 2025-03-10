import pandas as pd
from jinja2 import Environment, Template
import json
from typing import List, Optional, Union
from pydantic import BaseModel, Field

class Transaction(BaseModel):
    """
    Represents a single transaction within a fraud or security report.
    """
    transactionID: str = Field(..., description="Unique identifier for the transaction.")
    date: str = Field(..., description="Date of the transaction (YYYY-MM-DD).")
    time: str = Field(..., description="Time of the transaction (HH:MM).")
    accountNumber: str = Field(..., description="Account number involved in the transaction.")
    merchantRecipient: str = Field(..., description="Merchant or recipient of the transaction.")
    amount: Optional[float] = Field(None, description="Amount of the transaction (can be null for security events).")
    descriptionNotes: str = Field(..., description="Description or notes about the transaction.")
    suspectedFraudType: str = Field(..., description="Type of suspected fraud or security issue.")


class FraudReport(BaseModel):
    """
    Represents a fraud or security report containing multiple transactions.
    """
    report_id: str = Field(..., description="Unique identifier for the report.")
    report_date: str = Field(..., description="Date of the report (YYYY-MM-DD).")
    reporting_period_start: str = Field(..., description="Start date of the reporting period (YYYY-MM-DD).")
    reporting_period_end: str = Field(..., description="End date of the reporting period (YYYY-MM-DD).")
    prepared_by: str = Field(..., description="Name of the department or person who prepared the report.")
    executive_summary: str = Field(..., description="Executive summary of the report.")
    transactions: List[Transaction] = Field(..., description="List of transactions in the report.")
    trends: str = Field(..., description="Trends observed in the data.")
    patterns: str = Field(..., description="Patterns observed in the data.")
    risk_factors: str = Field(..., description="Risk factors identified.")
    actions_taken: str = Field(..., description="Actions taken in response to the identified issues.")
    recommendations: str = Field(..., description="Recommendations for future actions.")
    supporting_docs: str = Field(..., description="Supporting documentation for the report.")
    contact_name: str = Field(..., description="Contact name for the report.")
    contact_email: str = Field(..., description="Contact email for the report.")
    contact_phone: str = Field(..., description="Contact phone number for the report.")

class FraudReportList(BaseModel):
    """
    Represents a list of FraudReports.
    """
    reports: List[FraudReport]



class FraudReportGenerator:
    def __init__(self, template_str=None):
        self.template = Environment().from_string(template_str or self._default_template())

    def _default_template(self):
        return """
# Fraud Report - {{ report_date }}

## Report Details

**Report ID:** {{ report_id }}

**Reporting Period:** {{ reporting_period_start }} - {{ reporting_period_end }}

**Prepared By:** {{ prepared_by }}

## Executive Summary

{{ executive_summary }}

## Suspected Fraudulent Transactions

| Transaction ID | Date       | Time  | Account Number       | Merchant/Recipient      | Amount ($) | Description/Notes                                            | Suspected Fraud Type           |
| -------------- | ---------- | ----- | -------------------- | ----------------------- | -------- | ------------------------------------------------------------ | ------------------------------ |
{% for transaction in transactions -%}
| {{ transaction.transactionID }} | {{ transaction.date }} | {{ transaction.time }} | `{{ transaction.accountNumber }}` | {{ transaction.merchantRecipient }} | {{ transaction.amount|float|round(2) }} | {{ transaction.descriptionNotes }}                | {{ transaction.suspectedFraudType }} |
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

*   **Name:** {{ contact_name }}
*   **Email:** {{ contact_email }}
*   **Phone:** {{ contact_phone }}
"""
    
    def generate_report(self, report_data):
        return self.template.render(report_data)

    @staticmethod
    def from_json(json_data, template_str=None):
        return FraudReportGenerator(template_str).generate_report(json.loads(json_data))