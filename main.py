import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

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
