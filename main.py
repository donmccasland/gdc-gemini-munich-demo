import os

import streamlit as st
from google.cloud import secretmanager
from google import genai
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

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

    for report in all_reports:
        cols = st.columns([2, 1])
        with cols[0]:
            st.write(f"**Report ID:** {report.report_id}")
            st.write(f"**Report Date:** {report.report_date}")
            st.write(f"**Prepared By:** {report.prepared_by}")
            st.write(f"**Summary:** {report.executive_summary}")
        with cols[1]:
            if st.button("View Report", key=f"view_report_{report.report_id}"):
                st.session_state["selected_report_data"] = report
                st.session_state["page"] = "report_view"
                st.rerun()


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


    #prompt = """
    #Fraud Report: {}
    #
    #User Query: {}
    #""".format(st.session_state["selected_report_data"], prompt)
    #

