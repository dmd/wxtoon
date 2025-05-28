

prompt = f"""
    A minimalistic black-and-white cartoon of a cute {animal}, drawn in thick lines, centered in a square 400x400 scene. The {animal} is {activity}, matching the current weather which is {weather_description} and the current season which is {season}. The drawing is simple and bold, with no background details other than essential props. Avoid shading or fine details. Ideal for a monochrome e-ink display. The {animal} is cheerful and expressive.
    """

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        tools=[
            {
                "type": "image_generation",
                "size": "1024x1024",
                "background": "transparent",
                "quality": "high",
            }
        ],
    )
