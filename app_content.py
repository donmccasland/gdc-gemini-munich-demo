import asyncio
import json
import os
import random
import time
import yaml
import datetime

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
import plotly.express as px

from signals_report import Assessment, AssessmentGenerator
from report_manager import ReportManager

REPORT_LINK_TEMPLATE = '<a href="?report_id={report_id}" target="_self" rel="noopener noreferrer">{link_text}</a>'

# Configurable heights for allowing scrolling
MESSAGE_HISTORY_SIZE = 1750
TABLE_HEIGHT = 1685

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
                "What are the key findings in this assessment?",
                "Summarize the attack method described.",
            ],
            "report_selection": [
                "What are the most common assessment types?",
                "Summarize the recent threats to CNI.",
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
                    # Only send a summary or subset of data to avoid token limits with 140 reports
                    # Sending just metadata for all reports
                    reports_metadata = [
                        {"id": r.assessment_id, "type": r.type, "source": r.source, "target": r.target, "timing": r.timing}
                        for r in self.report_manager.get_all_reports()
                    ]
                    attach_data = json.dumps(reports_metadata)
                    data_desc = "Here is the metadata of all available threat assessments: "
                elif page_name == "report_view":
                    attach_data = selected_report_data.model_dump_json()
                    data_desc = "Here is the data of currently inspected threat assessment: "

                full_prompt = f"""
                    {data_desc}
                    {attach_data}

                    The data may have been updated since the last message in the conversation, so please make 
                    sure you check you answers - if it's still applicable.
                    
                    Current number of assessments is: {len(self.report_manager.get_all_reports())}
                    
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
        # Read sort state from query params
        self.sort_column = st.query_params.get("sort_col", None)
        self.sort_order = st.query_params.get("sort_order", "asc")

    def sort_data(self, data, column):
        reverse = self.sort_order == "desc"
        
        # Helper to safely get attribute for sorting, handling None/missing
        def get_sort_key(item):
            val = getattr(item, column, "")
            # If it's one of the summary fields, fall back to the main field if summary is empty
            if column == "source_summary":
                 val = item.source_summary or item.source
            elif column == "target_summary":
                 val = item.target_summary or item.target
            elif column == "timing_summary":
                 val = item.timing_summary or item.timing
            return val or "" # Ensure we return a string for comparison if still None

        data.sort(key=get_sort_key, reverse=reverse)
        return data
    
    def render(self):
        all_reports = self.report_manager.get_all_reports()
        if not all_reports:
            st.write("No assessments found.")
            return

        # Apply sorting if a column is selected
        if self.sort_column:
             # We need a copy to not mutate the original list in report_manager permanently for this session view
             all_reports = all_reports.copy()
             self.sort_data(all_reports, self.sort_column)

        with st.container(height=self.table_height):
            # Adjusted column weights for new fields
            cols = st.columns([1.2, 2.5, 2, 2, 2, 0.8])
            headers = ["ID", "Type", "Source", "Target", "Timing", "Format"]
            # Mapping headers to actual attribute names for sorting
            header_map = {
                "ID": "assessment_id",
                "Type": "type",
                "Source": "source_summary",
                "Target": "target_summary",
                "Timing": "timing_summary",
                "Format": "original_format"
            }

            for i, header in enumerate(headers):
                col_name = header_map[header]
                next_order = "asc"
                if self.sort_column == col_name and self.sort_order == "asc":
                    next_order = "desc"
                
                # Build link for sorting
                link = f"?sort_col={col_name}&sort_order={next_order}"
                
                # Add an arrow indicator if currently sorted
                display_header = header
                if self.sort_column == col_name:
                    display_header += " ↑" if self.sort_order == "asc" else " ↓"
                
                cols[i].markdown(f"<a href='{link}' target='_self' style='color: #87CEEB; font-weight: bold; font-size: 18px; text-decoration: none;'>{display_header}</a>", unsafe_allow_html=True)

            for report in all_reports:
                cols = st.columns([1.2, 2.5, 2, 2, 2, 0.8])
                # Make ID a clickable link that reloads with query param
                cols[0].markdown(f'<a href="?report_id={report.assessment_id}" target="_self">{report.assessment_id}</a>', unsafe_allow_html=True)
                cols[1].write(report.type)
                cols[2].write(report.source_summary or report.source)
                cols[3].write(report.target_summary or report.target)
                cols[4].write(report.timing_summary or report.timing)
                cols[5].write(report.original_format)
                

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

    report_generator = AssessmentGenerator()
    col1, col2 = st.columns([0.7, 0.3], border=False)

    with col1:
        st.title("Signals Intelligence Dashboard")
        nav1, nav2, nav3 = st.columns([0.1, 0.1, 0.8])
        with nav1:
            if st.button("Home", use_container_width=True):
                st.session_state["page"] = "report_selection"
                st.rerun()
        with nav2:
            if st.button("Map", use_container_width=True):
                st.session_state["page"] = "map_view"
                st.rerun()

    with col2:
        def logout_callback(details: dict):
            report_manager.reset_the_reports(140) # Reset to full list
            st.session_state.chat_history.clear()

        authenticator.logout("Logout", callback=logout_callback)
            
    col1, col2 = st.columns([0.7, 0.3], border=True)

    if "page" not in st.session_state:
        st.session_state["page"] = "report_selection"
    if "selected_report_data" not in st.session_state:
        st.session_state["selected_report_data"] = None

    # Check for report_id in query params
    query_params = st.query_params
    if "report_id" in query_params:
        report_id = query_params["report_id"]
        report = report_manager.get_report_by_id(report_id)
        if report:
            st.session_state["selected_report_data"] = report
            st.session_state["page"] = "report_view"
            # Clear the query param so it doesn't persist on reload/navigation if desired, 
            # or keep it. Clearing it is often cleaner.
            # st.query_params.clear() 
        else:
            st.error(f"Report with ID {report_id} not found.")

    def calculate_dashboard_stats(all_reports: list[Assessment]):
        """Calculates dashboard statistics from a list of reports."""
        total_reports = len(all_reports)
        high_risk_count = 0
        type_counts = {}
        for report in all_reports:
            type_counts[report.type] = type_counts.get(report.type, 0) + 1
            if report.severity and report.severity.lower() == "high":
                high_risk_count += 1
        return {
            "total_reports": total_reports,
            "high_risk_count": high_risk_count,
            "type_counts": type_counts
        }

    def display_dashboard(stats):
        col1, col2 = st.columns([1, 3])

        with col1:
            st.metric("Total Assessments", stats["total_reports"])
            st.metric("High Risk Assessments", stats["high_risk_count"])

        with col2:
            # Display type counts as a horizontal bar chart using Plotly for better visuals
            type_counts = stats["type_counts"]
            if type_counts:
                df = pd.DataFrame(list(type_counts.items()), columns=["Type", "Count"])
                df = df.sort_values(by="Count", ascending=True)
                fig = go.Figure(go.Bar(
                    x=df["Count"],
                    y=df["Type"],
                    orientation='h'
                ))
                fig.update_layout(
                    title="Assessments by Type",
                    xaxis_title="Count",
                    yaxis_title=None,
                    height=300,
                    margin=dict(l=0, r=0, t=30, b=0)
                )
                st.plotly_chart(fig, use_container_width=True)
            
    def report_selection_page():
        all_reports = report_manager.get_all_reports()
        if not all_reports:
            st.write("No assessments found.")
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
        if st.button("Back to Assessments"):
            st.session_state["page"] = "report_selection"
            st.session_state["selected_report_data"] = None
            # Clear report_id from query params to allow navigation back
            st.query_params.clear()
            st.rerun()

        if st.session_state["selected_report_data"] is not None:
            selected_report_data = st.session_state["selected_report_data"]
            report_markdown = report_generator.generate_report(selected_report_data)
            st.markdown(report_markdown, unsafe_allow_html=True)

            # Display media if available
            if selected_report_data.filename:
                file_path = os.path.join("generated-assessments", selected_report_data.filename)
                if os.path.exists(file_path):
                    ext = selected_report_data.original_format.lower()
                    if ext in ['png', 'jpg', 'jpeg', 'gif']:
                        st.image(file_path, caption=f"Original Media: {selected_report_data.filename}")
                    elif ext == 'pdf':
                        # For PDF, we can use an embed tag to display it
                        import base64
                        with open(file_path, "rb") as f:
                            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                        pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800px" type="application/pdf">'
                        st.markdown(pdf_display, unsafe_allow_html=True)
                    elif ext == 'mp4':
                        st.video(file_path)
                    # Add more media types here if needed (e.g., mp3 for audio)
        else:
            st.write("Please select an assessment from the previous page.")

    def map_view_page():
        st.header("Operational Threat Map")
        
        # Get all reports and filter for those with geolocation data
        all_reports = report_manager.get_all_reports()
        map_data = []
        for report in all_reports:
            if report.lat is not None and report.lon is not None:
                map_data.append({
                    'lat': report.lat,
                    'lon': report.lon,
                    'type': report.type,
                    'assessment_id': report.assessment_id,
                    'summary': report.summary or report.type
                })
        
        if map_data:
            df = pd.DataFrame(map_data)
            
            fig = px.scatter_mapbox(
                df, 
                lat='lat', 
                lon='lon', 
                hover_name='assessment_id',
                hover_data={
                    'lat': False, 
                    'lon': False, 
                    'assessment_id': False, # Already in hover_name
                    'type': True, 
                    'summary': False
                },
                custom_data=['assessment_id'],
                labels={'type': 'Threat Type', 'assessment_id': 'Report ID'},
                zoom=3,
                center={"lat": 51.0, "lon": 10.0} # Approximate center of Europe
            )
            
            fig.update_traces(marker=dict(size=15, color='rgb(217, 83, 79)')) # #d9534f
            fig.update_layout(
                mapbox_style="open-street-map",
                margin={"r":0,"t":0,"l":0,"b":0},
                height=600
            )

            # Display the map and capture selection events
            event = st.plotly_chart(fig, on_select="rerun", selection_mode="points", use_container_width=True)

            if event and event.get("selection") and event["selection"]["points"]:
                # Get the selected point index
                point_index = event["selection"]["points"][0]["point_index"]
                # Retrieve the assessment_id from the DataFrame using the index
                selected_report_id = df.iloc[point_index]["assessment_id"]
                
                # Navigate to the report view
                report = report_manager.get_report_by_id(selected_report_id)
                if report:
                    st.session_state["selected_report_data"] = report
                    st.session_state["page"] = "report_view"
                    st.rerun()

            st.caption(f"Showing {len(map_data)} assessments with confirmed geolocation. Click a point to view details.")
        else:
            st.info("No assessments with specific geolocation data found.")

    page_name = st.session_state["page"]

    with col1:
        col1_container = st.empty()
        with col1_container.container():
            if page_name == "report_selection":
                report_selection_page()
            elif page_name == "report_view":
                report_view_page()
            elif page_name == "map_view":
                map_view_page()

    # Sidebar Chat
    with col2:
        chatbox = Chatbox(llm, report_manager)
        chatbox.render(page_name, st.session_state["selected_report_data"])
