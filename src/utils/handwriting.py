from pathlib import Path
from IPython.display import display
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random

# Point this at a nice signature/cursive font you’ve downloaded
# listdir returns full filenames (e.g. "Name.ttf") — don't add .ttf again
fonts_dir = Path("src/data/fonts")
font_files = [f for f in fonts_dir.iterdir() if f.suffix.lower() in (".ttf", ".otf")]


def render_signature(text: str, size: int = 96, font_path: None | str = None, verbose: bool = False) -> Image.Image:
    if font_path is None:
        font_path = random.choice(font_files)
    else:
        font_path = Path(font_path)
    font = ImageFont.truetype(str(font_path), size=size)
    if verbose:
        print(f"Using font: {font_path}")

    # rough size estimation (Pillow 10+ uses textbbox, not textsize)
    dummy_img = Image.new("RGB", (2000, 400), "white")
    draw = ImageDraw.Draw(dummy_img)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    w, h = right - left, bottom - top

    pad = 40
    img = Image.new("RGB", (w + pad * 2, h + pad * 2), "white")
    draw = ImageDraw.Draw(img)

    # slight random offset + rotation
    x = pad + random.randint(-5, 5)
    y = pad + random.randint(-5, 5)
    draw.text((x, y), text, font=font, fill=(20, 20, 20))

    angle = random.uniform(-4, 4)
    img = img.rotate(angle, expand=True, fillcolor="white")

    # tiny blur to mimic ink/scan
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    return img


if __name__ == "__main__":
    sig = render_signature("John A. Smith")
    sig.save("signature.png")
    display(sig)
