from PIL import Image
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "static" / "company"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

LOGO_PATH = STATIC_DIR / "logo.png"


def save_company_logo(file_storage, height=80):
    """
    Resizes uploaded logo to fixed height, keeps aspect ratio,
    converts to PNG, overwrites existing logo.
    """
    img = Image.open(file_storage.stream).convert("RGBA")

    # Preserve aspect ratio
    w, h = img.size
    new_width = int((height / h) * w)
    img = img.resize((new_width, height), Image.LANCZOS)

    img.save(LOGO_PATH, format="PNG", optimize=True)

    return "/static/company/logo.png"
