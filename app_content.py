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

from fraud_report import FraudReportGenerator, FraudReport, FraudReportStatus
from report_service import get_report_service


REPORT_LINK_TEMPLATE = '<a href="?report_id={report_id}" target="_self" rel="noopener noreferrer">{link_text}</a>'

# Configurable heights for allowing scrolling
MESSAGE_HISTORY_SIZE = 750
TABLE_HEIGHT = 959

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

def display_app_content(authenticator):
    """Displays the main content of the app (report/chat view)."""
    llm, genai_client = initialize_gemini()

    st.markdown("""
    <style>
    {css}
    </style>
    """.format(css=open("style.css").read()), unsafe_allow_html=True)

    report_service = get_report_service()
    report_generator = FraudReportGenerator()
    col1, col2 = st.columns([0.7, 0.3], border=False)

    with col1:
        st.title("Fraud Analysis Assistant")

    with col2:
        authenticator.logout()

    col1, col2 = st.columns([0.7, 0.3], border=True)
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

    def convert_stage_label(label):
        """
        Converts the stage label to a user-friendly format, handling the prefix.
        """
        if isinstance(label, str):
            if label.startswith("FraudReportStatus."):
                label = label.split(".", 1)[1]  # Remove the prefix
            if label == "alert_review":
                return "Alert Review"
            elif label == "case_review":
                return "Case Review"
            elif label == "conclusion":
                return "Conclusion"
            else:
                return label
            
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
                "Current Stage": convert_stage_label(report.stage),
                "View Report": report.report_id
            })

        df = pd.DataFrame(report_data)

        # Convert "View Report" column to clickable links
        def make_clickable_link(report_id) -> str:
            return REPORT_LINK_TEMPLATE.format(report_id=report_id, link_text="View Report")

        df["View Report"] = df["View Report"].apply(make_clickable_link)

        with st.container(height=TABLE_HEIGHT):
            # Display the DataFrame with links (escape=False needed for HTML)
            st.markdown(
                df[["Report ID", "Report Date", "Prepared By", "Period Start", "Period End", "Current Stage", "View Report"]].to_html(
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
        # Predefined questions
        predefined_questions = {
            "report_view": [
                "What are the key trends identified in the transactions?",
                "What are the main risk factors mentioned?",
            ],
            "report_selection": [
                "Any common patterns in all reports in this list?",
                "What is the date range of the reports?",
            ]
        }

        if "prompt" not in st.session_state:
            st.session_state.prompt = ""
        if "selected_question" not in st.session_state:
            st.session_state.selected_question = ""

        # Predefined questions buttons
        if page_name in predefined_questions:
            predefined_questions_to_display = predefined_questions[page_name]
            cols = st.columns(len(predefined_questions_to_display))

            for i, question in enumerate(predefined_questions_to_display):
                with cols[i]:
                    if st.button(question, key=f"predefined_{question}", help=question, type="secondary",
                                 use_container_width=True):
                        st.session_state.prompt = question
                        st.rerun()

            # Custom question asked
        custom_question = st.chat_input("Ask a question", key="custom_question_input")
        if custom_question:
            st.session_state.prompt = custom_question
            st.rerun()

        messages_container = st.container(height=MESSAGE_HISTORY_SIZE)

        # with messages_container:
        #     # Display chat history
        #     for message in st.session_state.messages:
        #         with st.chat_message(message["role"]):
        #             st.markdown(message["content"], unsafe_allow_html=True)

        # st.markdown("---")  # Add a horizontal rule for visual separation



        # Handle predefined question selection
        if st.session_state.selected_question:
            st.session_state.prompt = st.session_state.selected_question
            st.session_state.selected_question = ""
            st.rerun()

        prompt = st.session_state.prompt

        if prompt:
            with messages_container:
                with st.chat_message("assistant"):
                    message_placeholder = st.empty()

                # Display user message immediately
                with st.chat_message("user"):
                    st.markdown(prompt)

                for message in reversed(st.session_state.messages):
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"], unsafe_allow_html=True)


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

                    The data may have been updated since the last message in the conversation, so please make 
                    sure you check you answers - if it's still applicable.
                    
                    Current number of reports is: {len(report_service.get_all_reports())}

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
        else:
            with messages_container:
                for message in reversed(st.session_state.messages):
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"], unsafe_allow_html=True)

        if st.button("Reset reports backlog", help="Sets the number of reports in the system back to 50.", use_container_width=True):
            report_service.reset_the_reports(50)
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
