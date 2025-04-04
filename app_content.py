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
from report_manager import ReportManager  # Import ReportManager


REPORT_LINK_TEMPLATE = '<a href="?report_id={report_id}" target="_self" rel="noopener noreferrer">{link_text}</a>'

# Configurable heights for allowing scrolling
MESSAGE_HISTORY_SIZE = 750
TABLE_HEIGHT = 959

def replace_report_ids_with_links(text: str, report_manager: ReportManager) -> str:
    """
    Gets all available report IDs from report manager and replaces them with <a> links.
    """
    all_report_ids = report_manager.get_report_ids()
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

class Chatbox:
    def __init__(self, llm, report_manager):
        self.llm = llm
        self.report_manager = report_manager
        self.predefined_questions = {
            "report_view": [
                "What are the key trends identified in this report?",
                "What are the main risk factors mentioned in this report?",
            ],
            "report_selection": [
                "Any common patterns in all reports in this list?",
                "What is the date range of the reports?",
            ]
        }

    def render(self, page_name, selected_report_data):
        if "prompt" not in st.session_state:
            st.session_state.prompt = ""
        if "selected_question" not in st.session_state:
            st.session_state.selected_question = ""
        # Initialize chat history in session state if it doesn't exist
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # Predefined questions buttons
        if page_name in self.predefined_questions:
            predefined_questions_to_display = self.predefined_questions[page_name]
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

                for message in reversed(st.session_state.chat_history):
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"], unsafe_allow_html=True)


                full_response = ""

                chat_history = []
                for msg in st.session_state.chat_history:
                    if msg["role"] == "user":
                        chat_history.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        chat_history.append(AIMessage(content=msg["content"]))

                if page_name == "report_selection":
                    attach_data = "\n".join(fr.model_dump_json() for fr in self.report_manager.get_all_reports())
                    data_desc = "Here is the data of all available fraud reports: "
                elif page_name == "report_view":
                    attach_data = json.dumps(selected_report_data.model_dump_json())
                    data_desc = "Here is the data of currently inspected fraud report: "

                full_prompt = f"""
                    {data_desc}
                    {attach_data}

                    The data may have been updated since the last message in the conversation, so please make 
                    sure you check you answers - if it's still applicable.
                    
                    Current number of reports is: {len(self.report_manager.get_all_reports())}
                    
                    Do not generate any HTML code.

                    Keep your language to English.

                    Summarize results(if relevant) if output is going to be more than a few paragraphs.

                    User Query: {prompt}
                    """

                # Stream the response from Gemini
                try:
                    stream = self.llm.stream(
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
                full_response = replace_report_ids_with_links(full_response, self.report_manager)
                message_placeholder.markdown(full_response, unsafe_allow_html=True)

                # Add to chat history
                st.session_state.chat_history.append({"role": "user", "content": prompt})

                # Only add the bot response if it exists
                if full_response:
                    st.session_state.chat_history.append({"role": "assistant", "content": full_response})
                    # Clear the prompt after processing
                    st.session_state.prompt = ""
                    st.rerun()
        else:
            with messages_container:
                for message in reversed(st.session_state.chat_history):
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"], unsafe_allow_html=True)


class ReportTable:
    def __init__(self, report_manager):
        self.report_manager = report_manager
        self.table_height = TABLE_HEIGHT
        self.report_link_template = REPORT_LINK_TEMPLATE
        self.button_counter = 0

    def convert_stage_label(self, label):
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
    
    def render(self):
        all_reports = self.report_manager.get_all_reports()
        if not all_reports:
            st.write("No reports found.")
            return

        with st.container(height=self.table_height):
            cols = st.columns(7)  
            headers = ["Report ID", "Report Date", "Prepared By", "Period Start", "Period End", "Current Stage", "Open Report"]
            for i, header in enumerate(headers):
                cols[i].write(f"**{header}**")

            for report in all_reports:
                col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
                col1.write(report.report_id)
                col2.write(report.report_date)
                col3.write(report.prepared_by)
                col4.write(report.reporting_period_start)
                col5.write(report.reporting_period_end)
                col6.write(self.convert_stage_label(report.stage))
                self.button_counter += 1
                if col7.button(f"Open", key=f"view_{report.report_id}_{self.button_counter}"):
                    st.session_state["selected_report_data"] = report
                    st.session_state["page"] = "report_view"
                    st.rerun()
                

def display_app_content(authenticator):
    """Displays the main content of the app (report/chat view)."""
    llm, genai_client = initialize_gemini()

    st.markdown("""
    <style>
    {css}
    </style>
    """.format(css=open("style.css").read()), unsafe_allow_html=True)

    # Initialize ReportManager in session state
    if "report_manager" not in st.session_state:
        st.session_state.report_manager = ReportManager()
    report_manager = st.session_state.report_manager

    report_generator = FraudReportGenerator()
    col1, col2 = st.columns([0.7, 0.3], border=False)

    with col1:
        st.title("Fraud Analysis Assistant")

    with col2:
        def logout_callback(details: dict):
            report_manager.reset_the_reports(50)
            st.session_state.chat_history.clear()

        authenticator.logout("Logout", callback=logout_callback)
            
    col1, col2 = st.columns([0.7, 0.3], border=True)

    if "page" not in st.session_state:
        st.session_state["page"] = "report_selection"
    if "selected_report_data" not in st.session_state:
        st.session_state["selected_report_data"] = None

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
        all_reports = report_manager.get_all_reports()
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

        table = ReportTable(report_manager)
        table.render()

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
        chatbox = Chatbox(llm, report_manager)
        chatbox.render(page_name, st.session_state["selected_report_data"])

    async def test_ticker(col):
        while page_name == "report_selection":
            if len(report_manager.reports) >= 500:
                return
            report_manager.generate_new_report()
            st.rerun()
            await asyncio.sleep(60)

    asyncio.run(test_ticker(col1))
