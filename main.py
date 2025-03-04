import streamlit as st
import json
import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

from fraud_report import FraudReportGenerator

# Initialize ChatGoogleGenerativeAI (replace with your actual API key if needed)
# If you're running this locally, set the API key as an environment variable
# export GOOGLE_API_KEY="your_api_key"

try:
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.3)
except Exception as e:
    st.error(f"Error initializing Gemini Pro: {e}")
    st.stop()

# Initialize session state for messages if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = []

def create_chat_page(st):
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("What's on your mind?"):
        # Display user message in chat message container
        st.chat_message("user").markdown(prompt)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Display assistant response in chat message container (with spinner)
        with st.chat_message("assistant"):
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

    return st

def create_fraud_reports_page(st):
    st.write("Fraud Report ")
    report_generator = FraudReportGenerator()
    file_path = "sample_data.json"

    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                report_data = json.load(f)
                st.markdown(report_generator.generate_report(report_data))
        except json.JSONDecodeError as e:
            st.error(f"Error decoding JSON in {file_path}: {e}")
        except Exception as e:
            st.error(f"An unexpected error occurred while loading or processing {file_path}: {e}")
    else:
        st.error(f"File '{file_path}' not found.")

    return st

# Create navigation menu
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Chat", "Fraud Reports"])

if page == "Chat":
    st.title("Gemini Chatbot")
    create_chat_page(st)

elif page == "Fraud Reports":
    st.title("Fraud Reports")
    create_fraud_reports_page(st)
