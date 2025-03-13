import json
import os

import streamlit as st
from google.cloud import secretmanager
from google import genai
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

import pandas as pd
import plotly.graph_objects as go

from fraud_report import FraudReportGenerator, FraudReport
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

# CSS styling
st.markdown("""
<style>

[data-testid="block-container"] {
    padding-left: 2rem;
    padding-right: 2rem;
    padding-top: 1rem;
    padding-bottom: 0rem;
    margin-bottom: -7rem;
}

[data-testid="stVerticalBlock"] {
    padding-left: 0rem;
    padding-right: 0rem;
}

[data-testid="stMetric"] {
    background-color: #393939;
    text-align: center;
    padding: 15px 0;
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
        # Create a pie chart for fraud percentage
        fig = go.Figure(data=[go.Pie(labels=['Fraudulent', 'Non-Fraudulent'],
                                     values=[stats['fraud_percentage'], 100 - stats['fraud_percentage']],
                                     hole=.3,
                                     marker_colors=['#FF4B4B', '#4CAF50'],
                                     hovertemplate='<b>%{label}</b><br>Percentage: %{percent}<extra></extra>')])
        fig.update_layout(
            showlegend=False,
            margin=dict(l=0, r=0, b=0, t=0),
            height=150,  # Set the desired height here
            plot_bgcolor="#393939",  # Set the background color here
            paper_bgcolor="#393939",  # Set the background color here
        )
        fig.update_traces(textinfo='percent', textfont_size=14)

        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col3:
        st.metric("Total Fraud Transactions", stats["total_fraud_transactions"])

    with col4:
        st.metric("Total Transactions", stats["total_transactions"])

def report_selection_page():
    all_reports = report_service.get_all_reports()
    if not all_reports:
        st.write("No reports found.")
        return
    
    # Calculate and display dashboard stats
    stats = calculate_dashboard_stats(all_reports)
    
    # Create a container for the dashboard
    dashboard_container = st.container()
    with dashboard_container:
        display_dashboard(stats)

    report_data = []
    for report in all_reports:
        report_data.append({
            "Report ID": report.report_id,
            "Report Date": report.report_date,
            "Prepared By": report.prepared_by,
            "Period Start":report.reporting_period_start,
            "Period End": report.reporting_period_end,
            "View Report": report.report_id  
        })

    df = pd.DataFrame(report_data)

    # Convert "View Report" column to clickable links
    def make_clickable_link(report_id):
        return f'<a href="?report_id={report_id}" target="_self">View Report</a>'

    df["View Report"] = df["View Report"].apply(make_clickable_link)

    # Display the DataFrame with links (escape=False needed for HTML)
    st.markdown(
        df[["Report ID", "Report Date", "Prepared By", "Period Start", "Period End", "View Report"]].to_html(escape=False, index=False),
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

if page_name == "report_selection":
    report_selection_page()
elif page_name == "report_view":
    report_view_page()

# Sidebar Chat
st.sidebar.title("Farud Analysis Assistant")
if "messages" not in st.session_state:
    st.session_state.messages = []

# Predefined questions
predefined_questions = {
    "report_view" : [
        "What are the key trends identified in the treansactions?",
        "What are the main risk factors mentioned?",
        "What actions were taken in response to the fraud?",
        "What recommendations are made for future actions?",
        "Can you summarise the executive summary?",
    ],
    "report_selection" : [
        "Any common patterns in all reports in this list?"
    ]
}

# Sidebar Chat
with st.sidebar: 
    # Prompt the user
    prompt = st.chat_input("Ask a question")

    # Dropdown for predefined questions
    selected_question = st.selectbox("Or choose a predefined question:", [""] + predefined_questions[page_name])
    if selected_question:
        prompt = selected_question
        
    st.markdown("---")  # Add a horizontal rule for visual separation

    if prompt:  
        with st.sidebar.container():
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

            full_response = ""
            full_prompt = f"""
                {data_desc}
                {attach_data}
                
                User Query: {prompt}
                """

            # Stream the response from Gemini
            try:
                print(chat_history + [HumanMessage(content=prompt)])
                stream = llm.stream(
                    chat_history + [HumanMessage(content=full_prompt)],
                    config=RunnableConfig(callbacks=None),
                )
            except Exception as e:
                st.error(f"Error generating response: {e}")
                st.stop()

            for chunk in stream:
                full_response += chunk.content
        
        # Add to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({"role": "assistant", "content": full_response})


    # Display chat history
    for message in reversed(st.session_state.messages):
        with st.sidebar.chat_message(message["role"]):
            st.markdown(message["content"])
