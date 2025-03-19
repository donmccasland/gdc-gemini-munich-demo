import yaml
from yaml.loader import SafeLoader

import streamlit as st
import streamlit_authenticator as stauth

import app_content  # Import the new module

# st.set_page_config has to be the very first st command called
st.set_page_config(layout="wide")

# Login page
# Load the config file
with open('login.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

# Create the authenticator object
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

authentication_status = st.session_state.get("authentication_status")

if authentication_status:
    authenticator.logout()
    app_content.display_app_content()
elif authentication_status is False:
    st.error('Username/password is incorrect')
else:
    st.warning('Please enter your username and password')
    try:
        # Display the login form
        authenticator.login()
        name = st.session_state.get("name")
        authentication_status = st.session_state.get("authentication_status")
        username = st.session_state.get("username")
    except Exception as e:
        st.error(e)
