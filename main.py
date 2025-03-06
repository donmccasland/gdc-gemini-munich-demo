import streamlit as st
import pandas as pd
import json
import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

from fraud_report import FraudReportGenerator
from report_service import ReportService

# Initialize ChatGoogleGenerativeAI (replace with your actual API key if needed)
# If you're running this locally, set the API key as an environment variable
# export GOOGLE_API_KEY="your_api_key"

try:
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.3)
except Exception as e:
    st.error(f"Error initializing Gemini Pro: {e}")
    st.stop()

report_service = ReportService("sample_data.json")
report_generator = FraudReportGenerator()

if "page" not in st.session_state:
    st.session_state["page"] = "report_selection"
if "selected_report_data" not in st.session_state:
  st.session_state["selected_report_data"] = None

def report_selection_page():
    all_reports = report_service.get_all_reports()
    report_data = []
    for report in all_reports:
        report_data.append([report.get("report_date", "N/A"), report.get("prepared_by", "N/A"), report.get("executive_summary", "N/A")])

    df = pd.DataFrame(report_data, columns=["Report Date", "Prepared By", "Summary"])

    st.write("## Select a Report")

    # Display table with buttons
    if not df.empty:
        for index, row in df.iterrows():
            cols = st.columns([2, 1])  # Two columns: data and button
            with cols[0]:
                st.write(f"**Report Date:** {row['Report Date']}")
                st.write(f"**Prepared By:** {row['Prepared By']}")
                st.write(f"**Summary:** {row['Summary']}")
            with cols[1]:
                if st.button("View Report", key=f"view_report_{index}"):
                    # Store the selected report data directly
                    st.session_state["selected_report_data"] = report_service.get_all_reports()[index]
                    st.session_state["page"] = "report_view"
                    st.rerun()
    else:
        st.write("No reports found.")

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

# Display chat history
for message in st.session_state.messages:
    with st.sidebar.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.sidebar.chat_input("Ask a question"):
    # Display user message in chat message container
    st.sidebar.chat_message("user").markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    prompt = """
    Fraud Report: {}

    User Query: {}
    """.format(st.session_state["selected_report_data"], prompt)

    # Display assistant response in chat message container (with spinner)
    with st.sidebar.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        # Stream the response from Gemini
        try:
            stream = llm.stream(
                [HumanMessage(content=prompt)],
                config=RunnableConfig(callbacks=None),
            )
        except Exception as e:
            st.error(f"Error generating response: {e}")
            st.stop()

        for chunk in stream:
            full_response += chunk.content
            message_placeholder.markdown(full_response + "▌")
        message_placeholder.markdown(full_response)

    # Add assistant message to chat history
    st.session_state.messages.append({"role": "assistant", "content": full_response})

