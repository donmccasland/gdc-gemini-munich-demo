import asyncio
import json
import os
import random
import time
import yaml

from yaml.loader import SafeLoader

import streamlit as st
import streamlit_authenticator as stauth

from google.cloud import secretmanager
from google import genai

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

import pandas as pd
import plotly.graph_objects as go

from fraud_report import FraudReportGenerator, FraudReport
from report_service import get_report_service


REPORT_LINK_TEMPLATE = '<a href="?report_id={report_id}" target="_self" rel="noopener noreferrer">{link_text}</a>'

def replace_report_ids_with_links(text: str) -> str:
    """
    Gets all available report IDs from report service and replaces them with <a> links.
    """
    report_service = get_report_service()
    all_report_ids = report_service.get_report_ids()
    for report_id in all_report_ids:
        text = text.replace(report_id, REPORT_LINK_TEMPLATE.format(report_id=report_id, link_text=report_id))
    return text

def initialize_gemini():
    """Initializes the Gemini Pro model."""
    if 'GOOGLE_API_KEY' not in os.environ:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = f"projects/gemini-gdc-demo/secrets/gemini-api-key/versions/latest"
        response = client.access_secret_version(request={"name": secret_name})

        os.environ["GOOGLE_API_KEY"] = response.payload.data.decode("utf-8")

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
        genai_client = genai.Client(vertexai=True, project="gemini-gdc-demo", location="us-central1")
        return llm, genai_client
    except Exception as e:
        st.error(f"Error initializing Gemini Pro: {e}")
        st.stop()

def display_app_content():
    """Displays the main content of the app (report/chat view)."""
    llm, genai_client = initialize_gemini()

    st.markdown("""
    <style>

    @import url('https://fonts.googleapis.com/css2?family=Google+Sans+Flex');

    body, * {
        font-family: 'Google Sans Flex', Arial, sans-serif !important;
    }

    table {
        width: 100%;
    }

    .fullHeight {height : 80vh; width : 100%}

    [data-testid="block-container"] {
        padding-left: 2rem;
        padding-right: 2rem;
        padding-top: 1rem;
        padding-bottom: 0rem;
        border-radius: 30px;
        margin-bottom: -7rem;
    }

    [data-testid="stVerticalBlock"] {
        padding-left: 0rem;
        padding-right: 0rem;
        border-radius: 30px;
    }

    [data-testid="stMetric"] {
        background-color: #393939;
        text-align: center;
        padding: 15px 0;
        border-radius: 30px;
        height: 150px;
    }

    [data-testid="stMetricLabel"] {
      display: flex;
      justify-content: center;
      align-items: center;
    }

    [data-testid="stMetricDeltaIcon-Up"] {
        position: relative;
        left: 38%;
        -webkit-transform: translateX(-50%);
        -ms-transform: translateX(-50%);
        transform: translateX(-50%);
    }

    [data-testid="stMetricDeltaIcon-Down"] {
        position: relative;
        left: 38%;
        -webkit-transform: translateX(-50%);
        -ms-transform: translateX(-50%);
        transform: translateX(-50%);
    }

    </style>
    """, unsafe_allow_html=True)

    report_service = get_report_service()
    report_generator = FraudReportGenerator()

    col1, col2 = st.columns([0.8, 0.2], border=True)
    dashboard_container = None

    if "page" not in st.session_state:
        st.session_state["page"] = "report_selection"
    if "selected_report_data" not in st.session_state:
        st.session_state["selected_report_data"] = None

    if "messages" not in st.session_state:
        st.session_state.messages = []

    def calculate_dashboard_stats(all_reports: list[FraudReport]):
        """Calculates dashboard statistics from a list of reports."""
        total_reports = len(all_reports)
        total_fraud_transactions = 0
        total_transactions = 0

        for report in all_reports:
            total_fraud_transactions += len(report.transactions)
            total_transactions += report.total_number_of_transactions

        if total_transactions > 0:
            fraud_percentage = (total_fraud_transactions / total_transactions) * 100
        else:
            fraud_percentage = 0

        return {
            "total_reports": total_reports,
            "fraud_percentage": fraud_percentage,
            "total_fraud_transactions": total_fraud_transactions,
            "total_transactions": total_transactions,
        }

    def display_dashboard(stats):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Reports", stats["total_reports"])

        with col2:
            formatted_fraud_percentage = f"{stats['fraud_percentage']:.2f}%"
            st.metric("24h Fraud Percentage", formatted_fraud_percentage)

        with col3:
            st.metric("24h Fraud Transactions", stats["total_fraud_transactions"])

        with col4:
            st.metric("24h Transactions", stats["total_transactions"])

    def report_selection_page():
        all_reports = report_service.get_all_reports()
        if not all_reports:
            st.write("No reports found.")
            return

        # Calculate and display dashboard stats
        stats = calculate_dashboard_stats(all_reports)

        # Create a container for the dashboard
        global dashboard_container
        dashboard_container = st.empty()
        with dashboard_container.container():
            display_dashboard(stats)

        report_data = []
        for report in all_reports:
            report_data.append({
                "Report ID": report.report_id,
                "Report Date": report.report_date,
                "Prepared By": report.prepared_by,
                "Period Start": report.reporting_period_start,
                "Period End": report.reporting_period_end,
                "View Report": report.report_id
            })

        df = pd.DataFrame(report_data)

        # Convert "View Report" column to clickable links
        def make_clickable_link(report_id) -> str:
            return REPORT_LINK_TEMPLATE.format(report_id=report_id, link_text="View Report")

        df["View Report"] = df["View Report"].apply(make_clickable_link)

        # Display the DataFrame with links (escape=False needed for HTML)
        st.markdown(
            df[["Report ID", "Report Date", "Prepared By", "Period Start", "Period End", "View Report"]].to_html(
                escape=False, index=False),
            unsafe_allow_html=True,
        )

        # Get report id from query param
        if st.query_params.get("report_id"):
            selected_report_id = st.query_params.get("report_id")

            report = next((r for r in all_reports if r.report_id == selected_report_id), None)
            if report:
                st.session_state["selected_report_data"] = report
                st.session_state["page"] = "report_view"
                st.query_params.clear()
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

    with col1:
        col1_container = st.empty()
        with col1_container.container():
            if page_name == "report_selection":
                report_selection_page()
            elif page_name == "report_view":
                report_view_page()

    # Sidebar Chat
    with col2:
        st.title("Fraud Analysis Assistant")

        # Predefined questions
        predefined_questions = {
            "report_view": [
                "What are the key trends identified in the transactions?",
                "What are the main risk factors mentioned?",
                "What actions were taken in response to the fraud?",
                "What recommendations are made for future actions?",
                "Can you summarise the executive summary?",
            ],
            "report_selection": [
                "Any common patterns in all reports in this list?"
            ]
        }

        if "prompt" not in st.session_state:
            st.session_state.prompt = ""
        if "selected_question" not in st.session_state:
            st.session_state.selected_question = ""

        # Dropdown for predefined questions
        selected_question = st.selectbox(
            "Choose a question:",
            ["", "Custom Question"] + predefined_questions[page_name],
            key="selectbox",
            index=0
        )

        if selected_question and selected_question != st.session_state.selected_question:
            st.session_state.selected_question = selected_question
            if selected_question == "Custom Question":
                # Only set the prompt to empty and let the chat input handle it
                st.session_state.prompt = ""
                st.rerun()
            else:
                st.session_state.prompt = selected_question
                st.rerun()

        # Handle custom question input separately
        if selected_question == "Custom Question":
            custom_question = st.chat_input("Ask a question", key="custom_question_input")
            if custom_question:
                st.session_state.prompt = custom_question

        prompt = st.session_state.prompt

        st.markdown("---")  # Add a horizontal rule for visual separation

        messages_container = st.container(height=500)

        with messages_container:
            # Display chat history
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"], unsafe_allow_html=True)

        if prompt:
            with messages_container:
                # Display user message immediately
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    full_response = ""

                    chat_history = []
                    for msg in st.session_state.messages:
                        if msg["role"] == "user":
                            chat_history.append(HumanMessage(content=msg["content"]))
                        elif msg["role"] == "assistant":
                            chat_history.append(AIMessage(content=msg["content"]))

                    if st.session_state["page"] == "report_selection":
                        attach_data = "\n".join(fr.model_dump_json() for fr in report_service.get_all_reports())
                        data_desc = "Here is the data of all available fraud reports: "
                    elif st.session_state["page"] == "report_view":
                        attach_data = json.dumps(st.session_state["selected_report_data"].model_dump_json())
                        data_desc = "Here is the data of currently inspected fraud report: "

                    full_prompt = f"""
                        {data_desc}
                        {attach_data}

                        The data may have been updated since the last messagein conversation, so please make sure you
                        check you answers - if it's still applicable.

                        User Query: {prompt}
                        """

                    # Stream the response from Gemini
                    try:
                        stream = llm.stream(
                            chat_history + [HumanMessage(content=full_prompt)],
                            config=RunnableConfig(callbacks=None),
                        )
                    except Exception as e:
                        st.error(f"Error generating response: {e}")
                        st.stop()

                    for chunk in stream:
                        full_response += chunk.content
                        message_placeholder.markdown(full_response + "▌")

                    # Replacing report IDs with links
                    full_response = replace_report_ids_with_links(full_response)
                    message_placeholder.markdown(full_response, unsafe_allow_html=True)

                # Add to chat history
                st.session_state.messages.append({"role": "user", "content": prompt})

                # Only add the bot response if it exists
                if full_response:
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    # Clear the prompt after processing
                    st.session_state.prompt = ""
                    st.rerun()

    async def test_ticker(col):
        while page_name == "report_selection":
            if len(report_service.reports) >= 500:
                return
            report_service.generate_new_report()
            with col1_container.container():
                report_selection_page()
                await asyncio.sleep(60)

    asyncio.run(test_ticker(col1))
