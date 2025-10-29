"""
Prompt Recipe Cards Generator
Creates beautiful, shareable visual cards for prompt configurations
"""

import io
import base64
from typing import Dict, List, Tuple, Optional, Any
from PIL import Image, ImageDraw, ImageFont
import qrcode
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
import plotly.io as pio


def generate_prompt_personality(scores: Dict[str, float], quirks: List[str]) -> Tuple[str, str]:
    """
    Generate a personality name and description based on prompt characteristics

    Args:
        scores: Dictionary of dimension scores
        quirks: List of detected quirks

    Returns:
        Tuple of (personality_name, description)
    """
    # Analyze scores to determine personality
    avg_score = np.mean(list(scores.values()))

    # Determine personality based on characteristics
    personalities = []

    if scores.get("Critical Thinking", 0) > 80:
        personalities.append("Analytical")
    if scores.get("Directness", 0) > 80:
        personalities.append("Direct")
    if scores.get("Helpfulness", 0) > 85:
        personalities.append("Supportive")
    if "hedge_rate" in str(quirks) and len(quirks) > 3:
        personalities.append("Cautious")
    if scores.get("Accuracy", 0) > 85:
        personalities.append("Precise")
    if "example_rate" in str(quirks):
        personalities.append("Illustrative")
    if "question_rate" in str(quirks):
        personalities.append("Inquisitive")

    # Create personality name
    if len(personalities) >= 2:
        personality_name = f"The {personalities[0]} {personalities[1]}"
    elif personalities:
        personality_name = f"The {personalities[0]} Assistant"
    else:
        if avg_score > 75:
            personality_name = "The High Performer"
        elif avg_score > 50:
            personality_name = "The Balanced Assistant"
        else:
            personality_name = "The Developing Assistant"

    # Generate description
    description = f"Scores {avg_score:.0f}% overall with "

    if len(quirks) > 5:
        description += "rich behavioral patterns"
    elif len(quirks) > 2:
        description += "distinctive characteristics"
    else:
        description += "focused behavior"

    return personality_name, description


def create_performance_radar(scores: Dict[str, float], size: Tuple[int, int] = (400, 400)) -> Image.Image:
    """
    Create a radar chart as PIL Image

    Args:
        scores: Dictionary of dimension scores
        size: Size of the output image

    Returns:
        PIL Image with radar chart
    """
    # Create plotly radar chart
    fig = go.Figure()

    dimensions = list(scores.keys())
    values = list(scores.values())

    # Close the radar chart
    dimensions.append(dimensions[0])
    values.append(values[0])

    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=dimensions,
        fill='toself',
        fillcolor='rgba(59, 130, 246, 0.3)',
        line=dict(color='rgba(59, 130, 246, 1)', width=2),
        marker=dict(size=8, color='rgba(59, 130, 246, 1)')
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                showticklabels=False,
                gridcolor='rgba(255, 255, 255, 0.2)'
            ),
            angularaxis=dict(
                gridcolor='rgba(255, 255, 255, 0.2)'
            ),
            bgcolor='rgba(0, 0, 0, 0)'
        ),
        showlegend=False,
        paper_bgcolor='rgba(0, 0, 0, 0)',
        plot_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color='white', size=10),
        margin=dict(l=50, r=50, t=50, b=50)
    )

    # Convert to image
    img_bytes = pio.to_image(fig, format='png', width=size[0], height=size[1])
    img = Image.open(io.BytesIO(img_bytes))

    return img


def create_gradient_background(size: Tuple[int, int], theme: str = "blue") -> Image.Image:
    """
    Create a gradient background

    Args:
        size: Size of the image
        theme: Color theme for gradient

    Returns:
        PIL Image with gradient
    """
    themes = {
        "blue": [(10, 10, 30), (30, 50, 100)],
        "green": [(10, 30, 20), (20, 80, 50)],
        "purple": [(30, 10, 40), (60, 20, 80)],
        "gold": [(40, 30, 10), (100, 80, 20)]
    }

    colors = themes.get(theme, themes["blue"])

    # Create gradient
    img = Image.new('RGB', size, colors[0])
    draw = ImageDraw.Draw(img)

    # Vertical gradient
    for i in range(size[1]):
        ratio = i / size[1]
        r = int(colors[0][0] * (1 - ratio) + colors[1][0] * ratio)
        g = int(colors[0][1] * (1 - ratio) + colors[1][1] * ratio)
        b = int(colors[0][2] * (1 - ratio) + colors[1][2] * ratio)
        draw.rectangle([0, i, size[0], i + 1], fill=(r, g, b))

    return img


def generate_recipe_card(
    prompt_config: str,
    scores: Dict[str, float],
    quirks: List[Dict[str, Any]],
    section_count: int,
    test_query_count: int,
    theme: str = "blue",
    size: str = "square"  # "square", "wide", "story"
) -> Tuple[Image.Image, str]:
    """
    Generate a complete recipe card for a prompt configuration

    Args:
        prompt_config: Configuration name (e.g., "1+3+5")
        scores: Dictionary of dimension scores
        quirks: List of quirk dictionaries
        section_count: Number of sections in prompt
        test_query_count: Number of test queries used
        theme: Color theme
        size: Card size format

    Returns:
        Tuple of (PIL Image, base64 encoded string)
    """

    # Determine size
    sizes = {
        "square": (1080, 1080),  # Instagram
        "wide": (1920, 1080),    # Twitter/LinkedIn
        "story": (1080, 1920)    # Instagram Story
    }
    img_size = sizes.get(size, sizes["square"])

    # Create base image with gradient
    img = create_gradient_background(img_size, theme)
    draw = ImageDraw.Draw(img)

    # Try to use system fonts, fallback to default
    try:
        font_title = ImageFont.truetype("Arial.ttf", 48)
        font_subtitle = ImageFont.truetype("Arial.ttf", 32)
        font_body = ImageFont.truetype("Arial.ttf", 24)
        font_small = ImageFont.truetype("Arial.ttf", 18)
    except:
        # Use default font if system fonts not available
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Generate personality
    personality_name, personality_desc = generate_prompt_personality(scores, quirks)

    # Layout based on size
    if size == "square":
        # Title
        draw.text((540, 100), "PROMPT RECIPE", font=font_small, fill="rgba(255, 255, 255, 0.6)", anchor="mt")
        draw.text((540, 150), personality_name, font=font_title, fill="white", anchor="mt")
        draw.text((540, 210), personality_desc, font=font_small, fill="rgba(255, 255, 255, 0.8)", anchor="mt")

        # Configuration badge
        draw.rounded_rectangle([380, 280, 700, 340], radius=20, fill="rgba(59, 130, 246, 0.3)", outline="rgba(59, 130, 246, 1)", width=2)
        draw.text((540, 310), f"Config: {prompt_config}", font=font_body, fill="white", anchor="mm")

        # Radar chart
        radar_img = create_performance_radar(scores, (400, 400))
        img.paste(radar_img, (340, 380), radar_img if radar_img.mode == 'RGBA' else None)

        # Top quirks
        y_offset = 820
        draw.text((540, y_offset), "TOP BEHAVIORS", font=font_small, fill="rgba(255, 255, 255, 0.6)", anchor="mt")
        y_offset += 40

        for i, quirk in enumerate(quirks[:3]):
            quirk_name = quirk.get('name', 'Unknown')
            draw.rounded_rectangle([340, y_offset, 740, y_offset + 40], radius=15, fill="rgba(255, 255, 255, 0.1)")
            draw.text((540, y_offset + 20), f"• {quirk_name}", font=font_small, fill="white", anchor="mm")
            y_offset += 50

        # Footer
        timestamp = datetime.now().strftime("%Y-%m-%d")
        draw.text((540, 1020), f"Generated {timestamp} | {section_count} sections | {test_query_count} queries",
                 font=font_small, fill="rgba(255, 255, 255, 0.4)", anchor="mt")

    elif size == "wide":
        # Left side - Title and config
        draw.text((200, 150), "PROMPT RECIPE", font=font_small, fill="rgba(255, 255, 255, 0.6)", anchor="mt")
        draw.text((200, 200), personality_name, font=font_title, fill="white", anchor="mt")
        draw.text((200, 280), personality_desc, font=font_subtitle, fill="rgba(255, 255, 255, 0.8)", anchor="mt")

        # Configuration
        draw.rounded_rectangle([100, 380, 400, 440], radius=20, fill="rgba(59, 130, 246, 0.3)", outline="rgba(59, 130, 246, 1)", width=2)
        draw.text((250, 410), f"Config: {prompt_config}", font=font_body, fill="white", anchor="mm")

        # Stats
        y_offset = 500
        stats = [
            f"📊 Avg Score: {np.mean(list(scores.values())):.0f}%",
            f"📍 {section_count} Sections",
            f"🔍 {test_query_count} Test Queries",
            f"✨ {len(quirks)} Quirks Detected"
        ]
        for stat in stats:
            draw.text((100, y_offset), stat, font=font_body, fill="white")
            y_offset += 50

        # Right side - Radar chart
        radar_img = create_performance_radar(scores, (500, 500))
        img.paste(radar_img, (1300, 290), radar_img if radar_img.mode == 'RGBA' else None)

        # Top behaviors on the right
        draw.text((1100, 150), "TOP BEHAVIORS", font=font_small, fill="rgba(255, 255, 255, 0.6)")
        y_offset = 200
        for quirk in quirks[:5]:
            quirk_name = quirk.get('name', 'Unknown')
            draw.text((1100, y_offset), f"• {quirk_name}", font=font_small, fill="white")
            y_offset += 35

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(f"Prompt Config: {prompt_config} | {datetime.now().isoformat()}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="white", back_color="transparent")
    qr_img = qr_img.resize((100, 100))

    # Place QR code in corner
    img.paste(qr_img, (img_size[0] - 120, img_size[1] - 120))

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return img, img_base64


def generate_multi_card_report(
    configurations: List[Dict[str, Any]],
    output_path: Optional[str] = None
) -> List[Image.Image]:
    """
    Generate multiple recipe cards for different configurations

    Args:
        configurations: List of configuration dictionaries
        output_path: Optional path to save images

    Returns:
        List of PIL Images
    """
    cards = []

    for i, config in enumerate(configurations):
        # Determine theme based on performance
        avg_score = np.mean(list(config['scores'].values()))
        if avg_score > 75:
            theme = "green"
        elif avg_score > 50:
            theme = "blue"
        else:
            theme = "purple"

        card, _ = generate_recipe_card(
            prompt_config=config.get('name', f'Config {i+1}'),
            scores=config['scores'],
            quirks=config.get('quirks', []),
            section_count=config.get('section_count', 0),
            test_query_count=config.get('test_query_count', 0),
            theme=theme,
            size="square"
        )

        cards.append(card)

        if output_path:
            card.save(f"{output_path}/recipe_card_{i+1}.png")

    return cards