#!/usr/bin/env python3
import random
import os
import json
import urllib.request
from datetime import datetime


OWM_API = open("owm-api-key").read().strip()
LAT = 42.41823
LON = -71.186921
SNAIL_CHANCE = 0.05


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


def pick_animal():
    if random.random() < SNAIL_CHANCE:
        return "snail"
    else:
        if not os.path.exists("last_animal.txt"):
            open("last_animal.txt", "w").write("platypus")
        last = open("last_animal.txt").read().strip()
        animal = "capybara" if last == "platypus" else "platypus"
        open("last_animal.txt", "w").write(animal)
        return animal


animal = pick_animal()
season = get_season()

url = f"http://api.openweathermap.org/data/2.5/weather?appid={OWM_API}&lat={LAT}&lon={LON}"
with urllib.request.urlopen(url) as resp:
    data = json.load(resp)
weather = data["weather"][0]
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
if not matched_activities:
    raise RuntimeError(
        f"No activities found for icon {icon} and description {weather_description}"
    )
activity = random.choice(matched_activities)

if "__ANIMAL__" in activity:
    activity = activity.replace("__ANIMAL__", animal)

prompt = f"""A minimalistic black-and-white cartoon of a cute {animal}, drawn in thick lines, centered in a square 400x400 scene. The {animal} is {activity}, matching the current weather which is {weather_description} and the current season which is {season}. The drawing is simple and bold, with no background details other than essential props. Avoid shading or fine details. Ideal for a monochrome e-ink display. The {animal} is cheerful and expressive."""

# response = client.responses.create(
#         model="gpt-4.1-mini",
#         input=prompt,
#         tools=[
#             {
#                 "type": "image_generation",
#                 "size": "1024x1024",
#                 "background": "transparent",
#                 "quality": "high",
#             }
#         ],
#     )

print(prompt)
