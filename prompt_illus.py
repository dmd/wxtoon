#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "google-genai",
#     "pillow",
# ]
# ///
import argparse
import base64
import io
import random
import os
import json
import urllib.request
from datetime import datetime
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types


OWM_API = open("owm-api-key").read().strip()
LAT, LON = open("location.txt").read().strip().split(",")
SPECIAL_ANIMALS = {"snail": 0.03, "camel": 0.03, "octopus": 0.02, "cat": 0.01}
MODEL_MAP = {
    "2.5": "gemini-2.5-flash-image",
    "3": "gemini-3-pro-image-preview",
}


def get_season():
    month = datetime.now().month
    if month in [12, 1, 2]:
        return "winter"
    elif month in [3, 4, 5]:
        return "spring"
    elif month in [6, 7, 8]:
        return "summer"
    else:
        return "fall"


def pick_artist(artist_arg: Optional[str]) -> Optional[str]:
    if artist_arg:
        return artist_arg
    if not os.path.exists("artists.txt"):
        return None
    with open("artists.txt", "r", encoding="utf-8") as f:
        artists = [line.strip() for line in f if line.strip()]
    if not artists:
        return None
    return random.choice(artists)


def pick_animal(update_last=True):
    rand = random.random()
    cumulative_prob = 0

    # Check special animals first
    for animal, probability in SPECIAL_ANIMALS.items():
        cumulative_prob += probability
        if rand < cumulative_prob:
            return animal

    # Default to alternating platypus/capybara
    if not os.path.exists("last_animal.txt"):
        open("last_animal.txt", "w").write("platypus")
    last = open("last_animal.txt").read().strip()
    animal = "capybara" if last == "platypus" else "platypus"
    if update_last:
        open("last_animal.txt", "w").write(animal)
    return animal


parser = argparse.ArgumentParser(description="Generate cartoon animal images")
parser.add_argument("--animal", type=str, help="Specify the animal to use")
parser.add_argument("--activity", type=str, help="Specify the activity to use")
parser.add_argument("--artist", type=str, help="Specify the artist")
parser.add_argument(
    "--model",
    choices=sorted(MODEL_MAP.keys()),
    default="2.5",
    help="Model family to use: 2.5 -> gemini-2.5-flash-image, 3 -> gemini-3-pro-image-preview.",
)
args = parser.parse_args()

if args.animal:
    animal = args.animal
else:
    animal = pick_animal()
season = get_season()

artist = pick_artist(args.artist)
if not artist:
    raise RuntimeError(
        "No artist specified. Pass --artist or add artists.txt with at least one name."
    )

url = f"https://api.openweathermap.org/data/3.0/onecall?lat={LAT}&lon={LON}&exclude=current,minutely,hourly,alerts&appid={OWM_API}"

with urllib.request.urlopen(url) as resp:
    data = json.load(resp)
weather = data["daily"][0]["weather"][0]
icon = weather.get("icon", "")
weather_description = weather.get("description", "")

matched_activities = []
with open("activities.tsv") as f:
    for line in f:
        parts = line.strip().split("\t", 3)
        if len(parts) != 4:
            continue
        ic, desc, se, act = parts
        if ic == icon and se == season:
            matched_activities.append(act)
if args.activity:
    activity = args.activity
else:
    if not matched_activities:
        raise RuntimeError(
            f"No activities found for icon {icon} and description {weather_description}"
        )
    activity = random.choice(matched_activities)

if "__ANIMAL__" in activity:
    activity = activity.replace("__ANIMAL__", animal)

style_clause = f", drawn in the style of {artist}"
prompt = f"""A black-and-white image of a cute {animal}{style_clause}, centered in a square 400x400 scene. The {animal} is {activity}, matching the current weather which is {weather_description} and the current season which is {season}. The image should extend to the edge and not have any border."""

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

client = genai.Client(api_key=api_key)
model_id = MODEL_MAP[args.model]
if model_id == MODEL_MAP["2.5"]:
    image_config = types.ImageConfig(aspect_ratio="1:1")
else:
    image_config = types.ImageConfig(
        aspect_ratio="1:1",
        image_size="1K",
    )

filename = None
prompt_filename = None
try:
    response = client.models.generate_content(
        model=model_id,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["Image"],
            image_config=image_config,
        ),
    )

    image = None
    for part in response.parts:
        if part.inline_data is not None:
            data = part.inline_data.data
            if isinstance(data, str):
                data = base64.b64decode(data)
            image = Image.open(io.BytesIO(data))
            break
    if image is None:
        raise RuntimeError("No image data found in Gemini response.")

    resized = image.resize((400, 400), Image.Resampling.LANCZOS)

    # Add artist name at bottom left
    draw = ImageDraw.Draw(resized)
    artist_text = f'"{artist}"'
    font = ImageFont.truetype("Helvetica.ttc", 12)
    bbox = draw.textbbox((0, 0), artist_text, font=font)
    text_height = bbox[3] - bbox[1]
    x = 15
    y = 400 - text_height - 5
    draw.text((x, y), artist_text, fill="black", font=font)

    # new: generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}.png"
    prompt_filename = f"{timestamp}.txt"

    # write the new image file
    resized.save(filename)

    # write the prompt to text file
    with open(prompt_filename, "w") as f:
        f.write(prompt)

    # update the symlink current.png -> timestamped file
    try:
        if os.path.islink("current.png") or os.path.exists("current.png"):
            os.remove("current.png")
        os.symlink(filename, "current.png")
        if os.path.islink("current.txt") or os.path.exists("current.txt"):
            os.remove("current.txt")
        os.symlink(prompt_filename, "current.txt")
    except OSError as link_err:
        print(f"Warning: could not update symlink: {link_err}")

except Exception as e:
    print(f"Error generating image: {e}")

print(prompt)
if filename and prompt_filename:
    print(f"Wrote {filename} and {prompt_filename}.")
