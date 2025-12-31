#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "openai",
#     "pillow",
# ]
# ///
import argparse
import random
import os
import json
import urllib.request
from datetime import datetime
from openai import OpenAI
import base64
from PIL import Image
import io


OWM_API = open("owm-api-key").read().strip()
LAT, LON = open("location.txt").read().strip().split(",")
SPECIAL_ANIMALS = {"snail": 0.03, "camel": 0.03, "octopus": 0.02, "cat": 0.01}


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


def resize_image_with_border(image_data, target_width=400, target_height=480):
    """Resize a 1024x1024 image to target dimensions with transparent border."""
    # Decode base64 image
    img = Image.open(io.BytesIO(base64.b64decode(image_data)))

    # Calculate scaling to fit within target dimensions while maintaining aspect ratio
    scale_factor = min(target_width / img.width, target_height / img.height)

    # Calculate new dimensions
    new_width = int(img.width * scale_factor)
    new_height = int(img.height * scale_factor)

    # Resize the image
    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Create new image with target dimensions and transparent background
    final_img = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))

    # Calculate position to center the resized image
    x_offset = (target_width - new_width) // 2
    y_offset = (target_height - new_height) // 2

    # Paste the resized image onto the transparent background
    final_img.paste(
        resized_img,
        (x_offset, y_offset),
        resized_img if resized_img.mode == "RGBA" else None,
    )

    # Convert back to base64
    buffer = io.BytesIO()
    final_img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


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
args = parser.parse_args()

if args.animal:
    animal = args.animal
else:
    animal = pick_animal()
season = get_season()

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

prompt = f"""A minimalistic black-and-white cartoon of a cute {animal}, drawn in thick lines, centered in a square 400x400 scene. The {animal} is {activity}, matching the current weather which is {weather_description} and the current season which is {season}. The drawing is simple and bold, with no background details other than essential props. Avoid shading or fine details. Ideal for a monochrome e-ink display. The {animal} is cheerful and expressive."""

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

try:
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        tools=[
            {
                "type": "image_generation",
                "size": "1024x1024",
                "background": "transparent",
                "quality": "medium",
            }
        ],
    )

    image_data = [
        output.result
        for output in response.output
        if output.type == "image_generation_call"
    ]

    if image_data:
        image_base64 = image_data[0]

        # Resize image to 400x480 with transparent border
        resized_image_base64 = resize_image_with_border(image_base64)

        # new: generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}.png"
        prompt_filename = f"{timestamp}.txt"

        # write the new image file
        with open(filename, "wb") as f:
            f.write(base64.b64decode(resized_image_base64))

        # write the prompt to text file
        with open(prompt_filename, "w") as f:
            f.write(prompt)

        # update the symlink current.png -> timestamped file
        try:
            if os.path.islink("current.png") or os.path.exists("current.png"):
                os.remove("current.png")
            os.symlink(filename, "current.png")
        except OSError as link_err:
            print(f"Warning: could not update symlink: {link_err}")


except Exception as e:
    print(f"Error generating image: {e}")
    image_url = None

print(prompt)
print(f"Wrote {filename} and {prompt_filename}.")
