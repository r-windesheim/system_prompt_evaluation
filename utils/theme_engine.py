"""
Theme Engine for Prompt Testing Tool
Provides dynamic theming with smooth animations and visual effects
"""

from typing import Dict, Any

def get_theme_css(theme_name: str, animations_enabled: bool = True) -> str:
    """
    Get CSS for the selected theme

    Args:
        theme_name: Name of the theme to apply
        animations_enabled: Whether to include animations

    Returns:
        CSS string to inject into the app
    """

    # Base animations that work across all themes
    base_animations = """
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    @keyframes slideIn {
        from { transform: translateX(-20px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }

    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }

    @keyframes glow {
        0% { box-shadow: 0 0 5px rgba(59, 130, 246, 0.5); }
        50% { box-shadow: 0 0 20px rgba(59, 130, 246, 0.8); }
        100% { box-shadow: 0 0 5px rgba(59, 130, 246, 0.5); }
    }
    """ if animations_enabled else ""

    # Common transitions
    transitions = """
    * {
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .stButton > button {
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
    }

    .stSelectbox > div > div {
        transition: all 0.3s ease;
    }

    div[data-testid="stMetricValue"] {
        animation: fadeIn 0.5s ease;
    }

    .element-container {
        animation: fadeIn 0.3s ease;
    }
    """ if animations_enabled else ""

    themes = {
        "Dark": """
            /* Dark Theme - Default elegant dark */
            .stApp {
                background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            }

            .main .block-container {
                animation: fadeIn 0.5s ease;
            }

            .stButton > button {
                background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
                border: none;
                color: white;
                font-weight: 600;
            }

            .stButton > button:hover {
                background: linear-gradient(90deg, #2563eb 0%, #1d4ed8 100%);
                animation: pulse 0.3s ease;
            }

            h1, h2, h3 {
                background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 50%, #ec4899 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                animation: fadeIn 0.6s ease;
            }
        """,

        "Light": """
            /* Light Theme - Clean and professional */
            .stApp {
                background: linear-gradient(135deg, #ffffff 0%, #f3f4f6 100%);
            }

            .main {
                background: white;
                color: #1f2937;
            }

            .stButton > button {
                background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 100%);
                border: none;
                color: white;
                font-weight: 600;
                box-shadow: 0 4px 6px rgba(99, 102, 241, 0.3);
            }

            .stButton > button:hover {
                box-shadow: 0 8px 12px rgba(99, 102, 241, 0.4);
            }

            h1, h2, h3 {
                color: #1f2937 !important;
                font-weight: 700;
            }

            .css-1d391kg, .css-1cypcdb {
                background-color: #f9fafb !important;
                border-right: 1px solid #e5e7eb !important;
            }

            .stCheckbox > label {
                color: #4b5563 !important;
            }
        """,

        "Cyberpunk": """
            /* Cyberpunk Theme - Neon and futuristic */
            .stApp {
                background: linear-gradient(135deg, #0a0014 0%, #1a0033 50%, #0a0014 100%);
                position: relative;
            }

            .stApp::before {
                content: "";
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background:
                    repeating-linear-gradient(
                        0deg,
                        transparent,
                        transparent 2px,
                        rgba(255, 0, 255, 0.03) 2px,
                        rgba(255, 0, 255, 0.03) 4px
                    );
                pointer-events: none;
                z-index: 1;
            }

            .main {
                position: relative;
                z-index: 2;
            }

            .stButton > button {
                background: linear-gradient(90deg, #ff00ff 0%, #00ffff 100%);
                border: 2px solid #ff00ff;
                color: white;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 2px;
                animation: glow 2s infinite;
            }

            h1, h2, h3 {
                background: linear-gradient(90deg, #ff00ff 0%, #00ffff 50%, #ffff00 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                text-shadow: 0 0 20px rgba(255, 0, 255, 0.5);
                animation: glow 2s infinite;
            }

            .stMetricValue {
                color: #00ffff !important;
                text-shadow: 0 0 10px rgba(0, 255, 255, 0.8);
            }

            div[data-testid="metric-container"] {
                border: 1px solid rgba(255, 0, 255, 0.5);
                background: rgba(255, 0, 255, 0.1);
                animation: glow 3s infinite;
            }
        """,

        "Neon": """
            /* Neon Theme - Bright and vibrant */
            .stApp {
                background: linear-gradient(135deg, #1e0936 0%, #380835 50%, #1e0936 100%);
            }

            .stButton > button {
                background: transparent;
                border: 2px solid #f72585;
                color: #f72585;
                font-weight: 700;
                text-transform: uppercase;
                position: relative;
                overflow: hidden;
            }

            .stButton > button::before {
                content: "";
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(90deg, transparent, #f72585, transparent);
                transition: left 0.5s;
            }

            .stButton > button:hover::before {
                left: 100%;
            }

            .stButton > button:hover {
                color: white;
                text-shadow: 0 0 10px #f72585;
                box-shadow: 0 0 20px #f72585, inset 0 0 20px rgba(247, 37, 133, 0.2);
            }

            h1, h2, h3 {
                color: #b5179e !important;
                text-shadow:
                    0 0 10px #f72585,
                    0 0 20px #b5179e,
                    0 0 30px #7209b7;
            }

            .stSelectbox > div > div {
                border: 1px solid #f72585 !important;
                background: rgba(247, 37, 133, 0.1) !important;
            }

            .stCheckbox > label {
                color: #f72585 !important;
                text-shadow: 0 0 5px rgba(247, 37, 133, 0.5);
            }
        """,

        "Nature": """
            /* Nature Theme - Calm and organic */
            .stApp {
                background: linear-gradient(135deg, #2d3436 0%, #11422a 50%, #2d3436 100%);
                position: relative;
            }

            .stApp::after {
                content: "";
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background:
                    radial-gradient(circle at 20% 80%, rgba(104, 211, 145, 0.1) 0%, transparent 50%),
                    radial-gradient(circle at 80% 20%, rgba(167, 243, 208, 0.1) 0%, transparent 50%);
                pointer-events: none;
            }

            .stButton > button {
                background: linear-gradient(90deg, #10b981 0%, #059669 100%);
                border: none;
                color: white;
                font-weight: 600;
                box-shadow: 0 4px 6px rgba(16, 185, 129, 0.3);
                border-radius: 12px;
            }

            .stButton > button:hover {
                background: linear-gradient(90deg, #059669 0%, #047857 100%);
                transform: translateY(-2px) scale(1.02);
                box-shadow: 0 8px 12px rgba(16, 185, 129, 0.4);
            }

            h1, h2, h3 {
                background: linear-gradient(90deg, #10b981 0%, #34d399 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }

            .stMetricValue {
                color: #34d399 !important;
            }

            div[data-testid="metric-container"] {
                background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(52, 211, 153, 0.05) 100%);
                border: 1px solid rgba(16, 185, 129, 0.2);
                border-radius: 12px;
            }

            .element-container {
                border-radius: 8px;
            }
        """
    }

    # Combine base animations, transitions, and theme-specific styles
    return base_animations + transitions + themes.get(theme_name, themes["Dark"])


def get_particle_config(theme_name: str) -> Dict[str, Any]:
    """
    Get particle.js configuration for the theme

    Args:
        theme_name: Name of the theme

    Returns:
        Dictionary with particle configuration
    """

    configs = {
        "Cyberpunk": {
            "particles": {
                "number": {"value": 80},
                "color": {"value": ["#ff00ff", "#00ffff", "#ffff00"]},
                "shape": {"type": "circle"},
                "opacity": {"value": 0.5, "random": True},
                "size": {"value": 3, "random": True},
                "move": {
                    "enable": True,
                    "speed": 2,
                    "direction": "none",
                    "random": True,
                    "straight": False,
                    "out_mode": "bounce"
                },
                "line_linked": {
                    "enable": True,
                    "distance": 150,
                    "color": "#ff00ff",
                    "opacity": 0.4,
                    "width": 1
                }
            }
        },
        "Neon": {
            "particles": {
                "number": {"value": 60},
                "color": {"value": "#f72585"},
                "opacity": {"value": 0.8},
                "size": {"value": 2},
                "move": {
                    "enable": True,
                    "speed": 1,
                    "direction": "top",
                    "random": True,
                    "out_mode": "out"
                }
            }
        },
        "Nature": {
            "particles": {
                "number": {"value": 30},
                "color": {"value": "#10b981"},
                "shape": {"type": "circle"},
                "opacity": {"value": 0.3},
                "size": {"value": 4, "random": True},
                "move": {
                    "enable": True,
                    "speed": 0.5,
                    "direction": "top-right",
                    "random": False,
                    "out_mode": "out"
                }
            }
        }
    }

    return configs.get(theme_name, {})


def inject_theme(theme_name: str, animations: bool = True) -> str:
    """
    Generate HTML to inject theme into Streamlit app

    Args:
        theme_name: Name of the theme
        animations: Whether to enable animations

    Returns:
        HTML string with style tag
    """
    css = get_theme_css(theme_name, animations)

    return f"""
    <style>
    {css}
    </style>
    """