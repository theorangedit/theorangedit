"""FastAPI error document router."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()


@router.get("/error/document/")
@router.get("/error/document/.{ext}")
async def error_document(request: Request, code: int = 500,
                         message: str = "", ext: str = ""):
    """
    Render an error page.  In the old stack this was handled by the
    ErrorController and Paste's StatusBasedForward.
    """
    accept = request.headers.get("accept", "")
    if "application/json" in accept or ext in ("json",):
        return JSONResponse({"error": code, "message": message},
                            status_code=code)

    html = (
        f"<html><head><title>{code} Error</title></head>"
        f"<body><h1>{code}</h1><p>{message}</p></body></html>"
    )
    return HTMLResponse(content=html, status_code=code)
