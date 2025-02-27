#!/bin/bash
# Purpose: To deploy the App to Cloud Run.

# Google Cloud Project ID
PROJECT=gemini-gdc-demo

# Google Cloud Region
LOCATION=us-west2

# Deploy app from source code
gcloud run deploy gdc-demo-frontend --source . --region=$LOCATION --project=$PROJECT --allow-unauthenticated
