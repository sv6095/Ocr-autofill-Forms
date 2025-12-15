# app/pdf_utils.py
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFInfoNotInstalledError
from PIL import Image
from .config import POPPLER_PATH
import io

def pdf_to_images(file_bytes: bytes, dpi_values=(300, 200, 150)):
    """
    Convert PDF bytes to list of PIL Images using pdf2image.
    Tries a list of DPI values (in order) to handle very dense PDFs or memory issues.
    Returns list of PIL Images or raises a helpful error.
    """
    last_exc = None
    for dpi in dpi_values:
        try:
            if POPPLER_PATH:
                imgs = convert_from_bytes(file_bytes, dpi=dpi, poppler_path=POPPLER_PATH)
            else:
                imgs = convert_from_bytes(file_bytes, dpi=dpi)
            # ensure images are RGB PIL instances
            imgs_rgb = [img.convert("RGB") for img in imgs]
            return imgs_rgb
        except PDFInfoNotInstalledError as e:
            # clear, reproducible error if poppler not installed
            import platform
            system = platform.system()
            if system == "Windows":
                install_msg = (
                    "Poppler is not installed or not found.\n\n"
                    "To install Poppler on Windows:\n"
                    "1. Download from: https://github.com/oschwartz10612/poppler-windows/releases/\n"
                    "2. Extract to a folder (e.g., C:\\poppler)\n"
                    "3. Add the 'bin' folder to your PATH, OR\n"
                    "4. Set POPPLER_PATH environment variable to the 'bin' folder path\n"
                    "   Example: POPPLER_PATH=C:\\poppler\\Library\\bin\n\n"
                    "After installation, restart your server."
                )
            else:
                install_msg = (
                    "Poppler is not installed or not found.\n\n"
                    "To install Poppler:\n"
                    "  Ubuntu/Debian: sudo apt-get install poppler-utils\n"
                    "  macOS: brew install poppler\n"
                    "  Or set POPPLER_PATH environment variable to the bin directory"
                )
            raise RuntimeError(install_msg) from e
        except Exception as e:
            # store and try a lower-DPI
            last_exc = e
            # try next dpi
    # if we reach here, all attempts failed
    raise RuntimeError(f"Failed to convert PDF to images (attempted DPIs {dpi_values}). Last error: {last_exc}")
