import os

from atproto import Client
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Bluesky credentials
BLUESKY_USERNAME = os.getenv("BLUESKY_USERNAME")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")

# Create a Bluesky client
client = Client("https://bsky.social")


def update(type, text):
    client.login(BLUESKY_USERNAME, BLUESKY_PASSWORD)
    print(f"Logged in as {BLUESKY_USERNAME} at {time.ctime()}")
    if type == "auto":
        if len(text) > 280:
            print("Error: Text exceeds 280 characters for auto post.")
            return
        else:
            client.post("[AUTO] " + text)
    elif type == "manual":
        if len(text) > 280:
            print("Error: Text exceeds 280 characters for manual post.")
            return
        client.post(text)
    else:
        print("Error: Invalid post type. Use 'auto' or 'manual'.")


if __name__ == "__main__":
    print("Please use the update() function to post updates to Bluesky.")
