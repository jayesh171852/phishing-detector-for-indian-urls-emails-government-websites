"""
Icon Generator
==============
Converts icon.svg into PNG icons at all required sizes.
Run from the extension/assets/icons/ directory:
    python generate_icons.py

Requires: pip install cairosvg  (or: pip install Pillow)
"""
import os, shutil
from pathlib import Path

SIZES = [16, 32, 48, 64, 128]
SVG_PATH = Path(__file__).parent / "icon.svg"
OUT_DIR = Path(__file__).parent.parent.parent / "extension" / "public"

OUT_DIR.mkdir(parents=True, exist_ok=True)

def generate_with_cairosvg():
    import cairosvg
    for size in SIZES:
        out = OUT_DIR / f"icon{size}.png"
        cairosvg.svg2png(url=str(SVG_PATH), write_to=str(out),
                         output_width=size, output_height=size)
        print(f"Generated {out}")

def generate_with_pillow():
    """Fallback: create simple placeholder PNGs using Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    for size in SIZES:
        img = Image.new("RGBA", (size, size), (10, 22, 40, 255))
        draw = ImageDraw.Draw(img)
        # Simple shield shape approximation
        cx, cy = size // 2, size // 2
        r = size // 2 - 2
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(59, 130, 246, 255), width=max(1, size//16))
        # "G" text
        try:
            fsize = max(8, size // 3)
            draw.text((cx - fsize//3, cy - fsize//2), "G",
                      fill=(96, 165, 250, 255))
        except Exception:
            pass
        out = OUT_DIR / f"icon{size}.png"
        img.save(str(out), "PNG")
        print(f"Generated placeholder {out}")

if __name__ == "__main__":
    try:
        generate_with_cairosvg()
        print("Icons generated with cairosvg.")
    except ImportError:
        print("cairosvg not found, falling back to Pillow placeholders.")
        try:
            generate_with_pillow()
        except ImportError:
            print("Pillow not found either. Please manually export icon.svg to PNG sizes.")
