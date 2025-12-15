"""
Web demo routes for serving HTML templates.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

# Setup templates
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Redirect to autofill page."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/autofill")


@router.get("/autofill", response_class=HTMLResponse)
async def autofill_page(request: Request):
    """Auto-fill form page - main entry point."""
    return templates.TemplateResponse("autofill.html", {"request": request})
