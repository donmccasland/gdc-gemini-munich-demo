import streamlit_authenticator as stauth
import yaml
import secrets
import string

def generate_cookie_key(length=64):
    """Generates a random string to be used as a cookie key."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for i in range(length))

def generate_hashed_password(password):
    """Generates a hashed password using streamlit_authenticator."""
    return stauth.Hasher([password]).generate()[0]

def create_login_config(username, name, email, password, cookie_name):
    """Creates a login configuration dictionary."""
    hashed_password = generate_hashed_password(password)
    cookie_key = generate_cookie_key()

    config = {
        "credentials": {
            "usernames": {
                username: {
                    "name": name,
                    "password": hashed_password,
                    "emal": email,
                }
            }
        },
        "cookie": {
            "expiry_days": 1,
            "key": cookie_key,
            "name": cookie_name
        },
    }
    return config

def save_config_to_yaml(config, filename="login.yaml"):
    """Saves the login configuration to a YAML file."""
    with open(filename, "w") as file:
        yaml.dump(config, file, indent=2)

def main():
    """Main function to generate and save the login configuration."""
    username = "alex"
    name = "Alex Smith"
    password = "next25"
    email = "alex@cymbal.com"
    cookie_name = "fun_cookie"

    config = create_login_config(username, name, email, password, cookie_name)
    save_config_to_yaml(config)

    print(f"Login configuration saved to login.yaml")

if __name__ == "__main__":
    main()