import yaml
from yaml.loader import SafeLoader

import streamlit as st
import streamlit_authenticator as stauth

import app_content  # Import the new module

# st.set_page_config has to be the very first st command called
st.set_page_config(layout="wide")

st.markdown("""
<style>        
    /* Remove streamlit headers and footers */
    div[data-testid="stToolbar"] {
        visibility: hidden;
        height: 0%;
        position: fixed;
    }
                
    div[data-testid="stDecoration"] {
        visibility: hidden;
        height: 0%;
        position: fixed;
    }
                
    div[data-testid="stStatusWidget"] {
        visibility: hidden;
        height: 0%;
        position: fixed;
    }
                
    #MainMenu {
        visibility: hidden;
        height: 0%;
    }
                
    header {
        visibility: hidden;
        height: 0%;
    }
                
    footer {
        visibility: hidden;
        height: 0%;
    }
</style>
""", unsafe_allow_html=True)

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
    app_content.display_app_content(authenticator)
elif authentication_status is False:
    st.error('Username/password is incorrect')
else:
    try:
        # Display the login form
        authenticator.login()
        name = st.session_state.get("name")
        authentication_status = st.session_state.get("authentication_status")
        username = st.session_state.get("username")
    except Exception as e:
        st.error(e)
