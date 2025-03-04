import pandas as pd
from jinja2 import Environment, Template
import json

class FraudReportGenerator:
    def __init__(self, template_str=None):
        self.template = Environment().from_string(template_str or self._default_template())

    def _default_template(self):
        return """
# Fraud Report - {{ report_date }}

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
        # Check and correct the data structure
        transactions = report_data.get("transactions", [])
        if isinstance(transactions, list):
            for transaction in transactions:
              if isinstance(transaction, str):
                try:
                  transaction = json.loads(transaction)
                except:
                  print(f"Error loading transaction data: {transaction}")
                  continue
              if not isinstance(transaction, dict):
                print(f"Invalid transaction data: {transaction}")
                continue

        return self.template.render(report_data)

    @staticmethod
    def from_json(json_data, template_str=None):
        return FraudReportGenerator(template_str).generate_report(json.loads(json_data))