import os
import re

from atproto import Client, models
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import time

# Load environment variables
load_dotenv()

# Bluesky credentials
BLUESKY_USERNAME = os.getenv("BLUESKY_USERNAME")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")

# CONSTANTS
REPLY_DISCLAIMER = "This post is automatically posted by NZPT. See nzpt.cjs.nz for the stats, or contact the account in bio to report any issues."
IMAGE_TEMP = "tmp/post_image.png"

# Image dimensions (16:9, ideal for social)
IMG_W, IMG_H = 1200, 675

# Font paths (Liberation — standard on most Linux systems)
FONT_SERIF_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
FONT_SERIF_REG  = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"
FONT_SANS_BOLD  = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_SANS_REG   = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

# Per-type visual themes
# 0 = Urgency Tracker, 1 = Financial Tracker, 2 = Generic
THEMES = {
    0: {
        "bg":        (18, 10, 10),
        "accent":    (210, 35, 35),
        "accent2":   (255, 80, 60),
        "card":      (35, 18, 18),
        "h1_color":  (255, 255, 255),
        "h2_color":  (255, 200, 195),
        "p_color":   (200, 180, 178),
        "footer_bg": (210, 35, 35),
        "footer_fg": (255, 255, 255),
        "label":     "URGENCY TRACKER",
        "footer":    "NZPT Urgency Tracker  ·  nzpt.cjs.nz  |  Sourced from Parliament.nz",
    },
    1: {
        "bg":        (12, 20, 42),
        "accent":    (195, 155, 60),
        "accent2":   (240, 200, 100),
        "card":      (22, 35, 65),
        "h1_color":  (255, 255, 255),
        "h2_color":  (220, 200, 140),
        "p_color":   (170, 185, 210),
        "footer_bg": (195, 155, 60),
        "footer_fg": (12, 20, 42),
        "label":     "FINANCIAL TRACKER",
        "footer":    "NZPT Financial Tracker  ·  nzpt.cjs.nz  |  Sourced from elections.nz",
    },
    2: {
        "bg":        (16, 22, 30),
        "accent":    (30, 160, 140),
        "accent2":   (60, 210, 185),
        "card":      (24, 34, 46),
        "h1_color":  (255, 255, 255),
        "h2_color":  (160, 230, 220),
        "p_color":   (170, 190, 200),
        "footer_bg": (30, 160, 140),
        "footer_fg": (255, 255, 255),
        "label":     "NZPOLTOOLBOX",
        "footer":    "NZPolToolbox  ·  nzpt.cjs.nz",
    },
}

# Create a Bluesky client
client = Client("https://bsky.social")


# ── Rich-text helpers ─────────────────────────────────────────────────────────

def build_facets(text: str) -> list:
    """Parse hashtags and URLs from text and return ATProto facets."""
    facets = []

    # Hashtags
    for match in re.finditer(r"#(\w+)", text):
        start = len(text[:match.start()].encode("utf-8"))
        end   = len(text[:match.end()].encode("utf-8"))
        facets.append(
            models.AppBskyRichtextFacet.Main(
                index=models.AppBskyRichtextFacet.ByteSlice(byte_start=start, byte_end=end),
                features=[models.AppBskyRichtextFacet.Tag(tag=match.group(1))],
            )
        )

    # URLs (with or without scheme)
    url_pattern = re.compile(r"https?://[^\s]+|(?<!\w)([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(/[^\s]*)?")
    for match in re.finditer(url_pattern, text):
        url  = match.group(0)
        href = url if url.startswith("http") else "https://" + url
        start = len(text[:match.start()].encode("utf-8"))
        end   = len(text[:match.end()].encode("utf-8"))
        facets.append(
            models.AppBskyRichtextFacet.Main(
                index=models.AppBskyRichtextFacet.ByteSlice(byte_start=start, byte_end=end),
                features=[models.AppBskyRichtextFacet.Link(uri=href)],
            )
        )

    return facets


# ── Image helpers ─────────────────────────────────────────────────────────────

def _parse_info(info: str):
    """Extract text from <h1>, <h2>, <p> tags."""
    def get(tag):
        m = re.search(rf"<{tag}>(.*?)</{tag}>", info, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""
    return get("h1"), get("h2"), get("p")


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    """Word-wrap text to fit max_width pixels; return list of lines."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _pill(draw, xy, radius, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


# ── Public API ────────────────────────────────────────────────────────────────

def image_generator(type: int, info: str):
    """
    Generate a styled card image and save it to IMAGE_TEMP.

    Parameters
    ----------
    type : int
        0 = Urgency Tracker (red/black)
        1 = Financial Tracker (navy/gold)
        2 = Generic (slate/teal)
    info : str
        HTML-like string with <h1>, <h2>, <p> tags.
        e.g. "<h1>Title</h1><h2>Subtitle</h2><p>Body text here.</p>"
    """
    # Delete any existing temp image first
    os.makedirs(os.path.dirname(IMAGE_TEMP), exist_ok=True)
    if os.path.exists(IMAGE_TEMP):
        os.remove(IMAGE_TEMP)

    t  = THEMES[type]
    h1, h2, p = _parse_info(info)

    img  = Image.new("RGB", (IMG_W, IMG_H), t["bg"])
    draw = ImageDraw.Draw(img)

    # Left accent bar
    draw.rectangle([0, 0, 7, IMG_H], fill=t["accent"])

    # Top label pill
    lbl_font = ImageFont.truetype(FONT_SANS_BOLD, 20)
    lbl_w    = int(draw.textlength(t["label"], font=lbl_font))
    px0, py0 = 48, 38
    px1, py1 = px0 + lbl_w + 28, py0 + 36
    _pill(draw, (px0, py0, px1, py1), 6, t["accent"])
    draw.text((px0 + 14, py0 + 8), t["label"], font=lbl_font, fill=t["footer_fg"])

    # Rule under label
    rule_y = py1 + 22
    draw.rectangle([48, rule_y, IMG_W - 48, rule_y + 2], fill=t["accent"])

    # Content card
    cx0, cy0 = 48, rule_y + 22
    cx1, cy1 = IMG_W - 48, IMG_H - 60
    _pill(draw, (cx0, cy0, cx1, cy1), 12, t["card"])

    # Text layout inside card
    pad      = 48
    tx       = cx0 + pad
    tw       = cx1 - cx0 - pad * 2
    y        = cy0 + pad

    if h1:
        font = ImageFont.truetype(FONT_SERIF_BOLD, 54)
        for line in _wrap(draw, h1, font, tw):
            draw.text((tx, y), line, font=font, fill=t["h1_color"])
            y += 64

    if h1 and h2:
        y += 8
        draw.rectangle([tx, y, tx + 80, y + 3], fill=t["accent2"])
        y += 20

    if h2:
        font = ImageFont.truetype(FONT_SERIF_REG, 34)
        for line in _wrap(draw, h2, font, tw):
            draw.text((tx, y), line, font=font, fill=t["h2_color"])
            y += 44
        y += 10

    if p:
        font = ImageFont.truetype(FONT_SANS_REG, 26)
        for line in _wrap(draw, p, font, tw):
            draw.text((tx, y), line, font=font, fill=t["p_color"])
            y += 34

    # Footer bar
    draw.rectangle([0, IMG_H - 48, IMG_W, IMG_H], fill=t["footer_bg"])
    ft_font = ImageFont.truetype(FONT_SANS_REG, 20)
    draw.text((48, IMG_H - 48 + 14), t["footer"], font=ft_font, fill=t["footer_fg"])

    img.save(IMAGE_TEMP, "PNG")
    print(f"Image saved to {IMAGE_TEMP}")


def update(type, text):
    client.login(BLUESKY_USERNAME, BLUESKY_PASSWORD)
    print(f"Logged in as {BLUESKY_USERNAME} at {time.ctime()}")

    if type == "auto":
        if len(text) > 286:  # 280 + 6 for "[AUTO] " and " #NZPol"
            print("Error: Text exceeds 286 characters for auto post.")
            return
        full_text    = "[AUTO] " + text + " #NZPol"
        post_response = client.send_post(full_text, facets=build_facets(full_text))

        parent_ref = models.create_strong_ref(post_response)
        reply_ref  = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=parent_ref)
        client.send_post(REPLY_DISCLAIMER, reply_to=reply_ref, facets=build_facets(REPLY_DISCLAIMER))
        print("Disclaimer reply posted.")

    elif type == "image":
        if len(text) > 280:
            print("Error: Text exceeds 280 characters for image post.")
            return
        with open(IMAGE_TEMP, "rb") as f:
            img_data = f.read()
        upload   = client.upload_blob(img_data)
        image    = models.AppBskyEmbedImages.Image(alt=text, image=upload.blob)
        embed    = models.AppBskyEmbedImages.Main(images=[image])
        full_text    = "[AUTO] " + text + " #NZPol"
        post_response = client.send_post(full_text, facets=build_facets(full_text), embed=embed)
        parent_ref = models.create_strong_ref(post_response)
        reply_ref  = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=parent_ref)
        client.send_post(REPLY_DISCLAIMER, reply_to=reply_ref, facets=build_facets(REPLY_DISCLAIMER))
        print("Disclaimer reply posted.")

    elif type == "manual":
        if len(text) > 300:
            print("Error: Text exceeds 300 characters for manual post.")
            return
        client.send_post(text, facets=build_facets(text))

    else:
        print("Error: Invalid post type. Use 'auto', 'image', or 'manual'.")


if __name__ == "__main__":
    print("Please use the update() function to post updates to Bluesky.")