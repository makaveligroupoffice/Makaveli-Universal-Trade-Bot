import secrets
import string
import os

def generate_secure_token(length=32):
    """Generates a cryptographically secure random token."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def update_auth_env(token):
    """Updates the logs/auth.env file with the new token."""
    auth_file = "logs/auth.env"
    
    # Ensure logs directory exists
    os.makedirs(os.path.dirname(auth_file), exist_ok=True)
    
    with open(auth_file, "w") as f:
        f.write(f"AUTH_TOKEN={token}\n")
    
    print(f"Success: New AUTH_TOKEN generated and saved to {auth_file}")
    print(f"New Token: {token}")
    print("Please restart the bot for the changes to take effect.")

if __name__ == "__main__":
    new_token = generate_secure_token()
    update_auth_env(new_token)
