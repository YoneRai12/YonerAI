import io
import re

import matplotlib.pyplot as plt


def render_tex_to_image(tex_code: str) -> io.BytesIO | None:
    """
    Renders a TeX string to an image using matplotlib's mathtext engine.
    Returns a BytesIO object containing the image (PNG) or None if failed.
    """
    try:
        # 1. Clean up the TeX code
        # Remove markdown code block markers if present
        clean_tex = tex_code.strip()
        if clean_tex.startswith("```"):
            clean_tex = re.sub(r"^```\w*\n", "", clean_tex)
            clean_tex = re.sub(r"\n```$", "", clean_tex)
        clean_tex = clean_tex.strip()

        # Matplotlib mathtext requires $...$ for math mode, usually.
        # But if it's a full block like \[ ... \], we might need to adjust.
        # Let's try to wrap it in $...$ if it doesn't have it, or \displaystyle
        
        # Simple heuristic: If it doesn't start with $, enclose it.
        # Also, replace \[ \] with $ $ for matplotlib (it prefers $).
        
        display_tex = clean_tex
        if r"\[" in display_tex:
            display_tex = display_tex.replace(r"\[", "").replace(r"\]", "")
        
        if not display_tex.startswith("$"):
            display_tex = f"${display_tex}$"
            
        # 2. Render
        # Create a figure
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.text(0, 0, display_tex, fontsize=20, color='white')
        
        # Save to buffer
        buf = io.BytesIO()
        
        # We need to draw it first to get the bbox
        # But for simple rendering:
        # Use bbox_inches='tight' to crop exactly to text
        
        # Note: We need to handle white text on transparent bg for Discord dark mode
        plt.axis('off')
        
        # Re-create cleaner figure approach
        plt.close(fig)
        fig = plt.figure()
        # Enable rendering of tex
        # rcParams['text.usetex'] = False (default) uses built-in mathtext which is what we want (no external deps)
        
        text = plt.text(0.5, 0.5, display_tex, fontsize=24, ha='center', va='center', color='white')
        plt.axis('off')
        
        # Save with transparent background
        fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.1, transparent=True)
        plt.close(fig)
        
        buf.seek(0)
        return buf

    except Exception as e:
        print(f"TeX Render Error: {e}")
        return None
