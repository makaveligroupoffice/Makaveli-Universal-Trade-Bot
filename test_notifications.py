import logging
import sys
from notifications import send_notification

# Set up logging to see any errors
logging.basicConfig(level=logging.INFO)

def main():
    print("Sending test notification to Pushover...")
    try:
        send_notification(
            message="Test notification from your Trade Bot! Your phone is now successfully connected.",
            title="Trade Bot Test 🚀"
        )
        print("Success! Please check your phone for the Pushover notification.")
    except Exception as e:
        print(f"Error sending notification: {e}")

if __name__ == "__main__":
    main()
