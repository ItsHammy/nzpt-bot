import os

from atproto import Client, models
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Bluesky credentials
BLUESKY_USERNAME = os.getenv("BLUESKY_USERNAME")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")

# CONSTANTS
REPLY_DISCLAIMER = "This post is automatically posted by NZPT. See nzpt.cjs.nz for the stats, or contact the account in bio to report any issues."

# Create a Bluesky client
client = Client("https://bsky.social")


def update(type, text):
    client.login(BLUESKY_USERNAME, BLUESKY_PASSWORD)
    print(f"Logged in as {BLUESKY_USERNAME} at {time.ctime()}")
    if type == "auto":
        if len(text) > 286:  # 280 characters + 6 for "[AUTO] " and " #NZPol"
            print("Error: Text exceeds 286 characters for auto post.")
            return
        else:
            post_response = client.send_post("[AUTO] " + text + " #NZPol")

            parent_ref = models.create_strong_ref(post_response)
            reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=parent_ref)
            client.send_post(REPLY_DISCLAIMER, reply_to=reply_ref)
            print("Disclaimer reply posted.")
    elif type == "manual":
        if len(text) > 300:
            print("Error: Text exceeds 300 characters for manual post.")
            return
        client.send_post(text)
    else:
        print("Error: Invalid post type. Use 'auto' or 'manual'.")


if __name__ == "__main__":
    print("Please use the update() function to post updates to Bluesky.")