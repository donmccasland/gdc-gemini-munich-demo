import os

import streamlit as st
from google.cloud import secretmanager
from google import genai
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

import pandas as pd

from fraud_report import FraudReportGenerator
from report_service import get_report_service

# Initialize ChatGoogleGenerativeAI (replace with your actual API key if needed)
# If you're running this locally, set the API key as an environment variable
# export GOOGLE_API_KEY="your_api_key"
#
# If environment variable is unset, try to fetch the API key secret from Secrets Manager

if 'GOOGLE_API_KEY' not in os.environ:
    client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/gemini-gdc-demo/secrets/gemini-api-key/versions/latest"
    response = client.access_secret_version(request={"name": secret_name})
    
    os.environ["GOOGLE_API_KEY"] = response.payload.data.decode("utf-8")

try:
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.3)
    genai_client = genai.Client(vertexai=True, project="gemini-gdc-demo", location="us-central1")
except Exception as e:
    st.error(f"Error initializing Gemini Pro: {e}")
    st.stop()

report_service = get_report_service()
report_generator = FraudReportGenerator()

if "page" not in st.session_state:
    st.session_state["page"] = "report_selection"
if "selected_report_data" not in st.session_state:
  st.session_state["selected_report_data"] = None

def report_selection_page():
    all_reports = report_service.get_all_reports()
    if not all_reports:
        st.write("No reports found.")
        return

    report_data = []
    for report in all_reports:
        report_data.append({
            "Report ID": report.report_id,
            "Report Date": report.report_date,
            "Prepared By": report.prepared_by,
            "Summary": report.executive_summary,
            "View Report": report.report_id  
        })

    df = pd.DataFrame(report_data)

    # Convert "View Report" column to clickable links
    def make_clickable_link(report_id):
        return f'<a href="?report_id={report_id}" target="_self">View Report</a>'

    df["View Report"] = df["View Report"].apply(make_clickable_link)

    # Display the DataFrame with links (escape=False needed for HTML)
    st.markdown(
        df[["Report ID", "Report Date", "Prepared By", "Summary", "View Report"]].to_html(escape=False, index=False),
        unsafe_allow_html=True,
    )

    # Handle URL parameter for report selection
    query_params = st.experimental_get_query_params()
    if "report_id" in query_params:
        selected_report_id = query_params["report_id"][0]
        print("Report ID: {}".format(selected_report_id))

        report = next((r for r in all_reports if r.report_id == selected_report_id), None)
        if report:
            st.session_state["selected_report_data"] = report
            st.session_state["page"] = "report_view"
            st.experimental_set_query_params() # remove the parameters so that we do not stay in the same report
            st.rerun()
        else:
            print("How there be no report!?!?")


def report_view_page():
    if st.button("Back to Reports"):
        st.session_state["page"] = "report_selection"
        st.session_state["selected_report_data"] = None
        st.rerun()

    if st.session_state["selected_report_data"] is not None:
        selected_report_data = st.session_state["selected_report_data"]
        report_markdown = report_generator.generate_report(selected_report_data)
        st.markdown(report_markdown, unsafe_allow_html=True)
    else:
        st.write("Please select a report from the previous page.")

page_name = st.session_state["page"]

if page_name == "report_selection":
    report_selection_page()
elif page_name == "report_view":
    report_view_page()

# Sidebar Chat
st.sidebar.title("Chat with Report")
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar Chat
with st.sidebar: 
    # Prompt the user
    prompt = st.chat_input("Ask a question")
        
    st.markdown("---")  # Add a horizontal rule for visual separation

    if prompt:  
        with st.sidebar.container():
            full_response = ""
            full_prompt = """
                Fraud Report: {}
                
                User Query: {}
                """.format(st.session_state["selected_report_data"], prompt)

            # Stream the response from Gemini
            try:
                stream = llm.stream(
                    [HumanMessage(content=full_prompt)],
                    config=RunnableConfig(callbacks=None),
                )
            except Exception as e:
                st.error(f"Error generating response: {e}")
                st.stop()

            for chunk in stream:
                full_response += chunk.content
        
        # Add to chat history
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.session_state.messages.append({"role": "user", "content": prompt})
    

    # Display chat history
    for message in reversed(st.session_state.messages):
        with st.sidebar.chat_message(message["role"]):
            st.markdown(message["content"])    


