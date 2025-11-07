"""
FastAPI application for the Associations Pipeline.
"""

from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import db
import subprocess
import os
import json
import tempfile

app = FastAPI(title="Associations Pipeline")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")


# ==================== HOME ====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Redirect to issues list."""
    return RedirectResponse(url="/issues")


# ==================== ADMIN ====================

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    """Admin panel for generating embeddings."""
    status = db.get_embeddings_status()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "status": status
    })


@app.post("/admin/generate", response_class=HTMLResponse)
async def generate_embeddings(request: Request):
    """Trigger local embedding generation (free, no API needed)."""
    # Run the generation script in background with output to log file
    try:
        log_file = open("embedding_generation.log", "w")
        # Use the venv python explicitly
        python_path = ".venv/bin/python"
        subprocess.Popen(
            [python_path, "-u", "generate_associations_chroma.py"],  # -u for unbuffered output
            stdout=log_file,
            stderr=subprocess.STDOUT  # Combine stderr with stdout
        )
        message = "✅ Generation started! Using free local embeddings. This will take 2-3 minutes. Page auto-refreshes to show progress."
    except Exception as e:
        message = f"❌ Error starting generation: {e}"

    status = db.get_embeddings_status()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "status": status,
        "message": message
    })


@app.post("/admin/sync-linear", response_class=HTMLResponse)
async def sync_linear_issues(request: Request, api_key: str = Form(...)):
    """Sync issues from Linear API."""
    try:
        # Temporarily set the API key in environment for the subprocess
        env = os.environ.copy()
        env['LINEAR_API_KEY'] = api_key

        log_file = open("linear_sync.log", "w")
        # Use the venv python explicitly
        python_path = ".venv/bin/python"
        subprocess.Popen(
            [python_path, "-u", "fetch_linear_issues.py"],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env
        )
        message = "✅ Linear sync started! Fetching issues from Linear API. This will take ~30 seconds. Page auto-refreshes to show progress."
    except Exception as e:
        message = f"❌ Error starting Linear sync: {e}"

    status = db.get_embeddings_status()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "status": status,
        "message": message
    })


@app.post("/admin/import-signals", response_class=HTMLResponse)
async def import_signals(request: Request, file: UploadFile = File(...)):
    """Import signals from uploaded JSON file."""
    try:
        # Validate file type
        if not file.filename.endswith('.json'):
            raise ValueError("File must be a JSON file (.json)")

        # Read and validate JSON content
        content = await file.read()
        try:
            signals_data = json.loads(content)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format")

        if not isinstance(signals_data, list):
            raise ValueError("JSON must be an array of signal objects")

        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(signals_data, tmp)
            tmp_path = tmp.name

        # Run import script
        log_file = open("import_signals.log", "w")
        python_path = ".venv/bin/python"
        subprocess.Popen(
            [python_path, "-u", "import_signals.py", tmp_path],
            stdout=log_file,
            stderr=subprocess.STDOUT
        )

        message = f"✅ Import started! Processing {len(signals_data)} signals from {file.filename}. Page auto-refreshes to show progress."

    except ValueError as e:
        message = f"❌ Error: {e}"
    except Exception as e:
        message = f"❌ Error importing signals: {e}"

    status = db.get_embeddings_status()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "status": status,
        "message": message
    })


@app.post("/admin/delete-all-data", response_class=HTMLResponse)
async def delete_all_data(request: Request):
    """Delete all data from the database (preserves schema)."""
    try:
        counts = db.delete_all_data()
        message = f"✅ Successfully deleted all data! Removed {counts['signals']} signals, {counts['issues']} issues, {counts['associations']} associations, and {counts['signal_embeddings'] + counts['issue_embeddings']} embeddings."
    except Exception as e:
        message = f"❌ Error deleting data: {e}"

    status = db.get_embeddings_status()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "status": status,
        "message": message
    })


# ==================== ISSUES ====================

@app.get("/issues", response_class=HTMLResponse)
async def issues_list(request: Request):
    """List all issues with signal counts."""
    issues = db.get_all_issues_with_counts()
    return templates.TemplateResponse("issues_list.html", {
        "request": request,
        "issues": issues
    })


@app.get("/issues/{issue_id}", response_class=HTMLResponse)
async def issue_detail(request: Request, issue_id: str):
    """Issue detail page."""
    issue = db.get_issue_by_id(issue_id)
    if not issue:
        return HTMLResponse(content="<h1>Issue not found</h1>", status_code=404)

    return templates.TemplateResponse("issue_detail.html", {
        "request": request,
        "issue": issue
    })


@app.get("/issues/{issue_id}/signals", response_class=HTMLResponse)
async def issue_signals_list(request: Request, issue_id: str):
    """List all signals associated with an issue."""
    issue = db.get_issue_by_id(issue_id)
    if not issue:
        return HTMLResponse(content="<h1>Issue not found</h1>", status_code=404)

    signals = db.get_signals_for_issue(issue_id)
    return templates.TemplateResponse("associated_signals.html", {
        "request": request,
        "issue": issue,
        "signals": signals
    })


@app.get("/issues/{issue_id}/signals/{signal_id}", response_class=HTMLResponse)
async def issue_signal_detail(request: Request, issue_id: str, signal_id: int):
    """Signal detail in context of an issue."""
    issue = db.get_issue_by_id(issue_id)
    signal = db.get_signal_by_id(signal_id)
    association = db.get_association(signal_id, issue_id)

    if not issue or not signal:
        return HTMLResponse(content="<h1>Not found</h1>", status_code=404)

    return templates.TemplateResponse("signal_detail.html", {
        "request": request,
        "signal": signal,
        "issue": issue,
        "association": association,
        "context": "issue"
    })


# ==================== SIGNALS ====================

@app.get("/signals", response_class=HTMLResponse)
async def signals_list(request: Request):
    """List all signals with issue counts."""
    signals = db.get_all_signals_with_counts()
    return templates.TemplateResponse("signals_list.html", {
        "request": request,
        "signals": signals
    })


@app.get("/signals/{signal_id}", response_class=HTMLResponse)
async def signal_detail(request: Request, signal_id: int):
    """Signal detail page."""
    signal = db.get_signal_by_id(signal_id)
    if not signal:
        return HTMLResponse(content="<h1>Signal not found</h1>", status_code=404)

    return templates.TemplateResponse("signal_detail.html", {
        "request": request,
        "signal": signal,
        "context": None
    })


@app.get("/signals/{signal_id}/issues", response_class=HTMLResponse)
async def signal_issues_list(request: Request, signal_id: int):
    """List all issues associated with a signal."""
    signal = db.get_signal_by_id(signal_id)
    if not signal:
        return HTMLResponse(content="<h1>Signal not found</h1>", status_code=404)

    issues = db.get_issues_for_signal(signal_id)
    return templates.TemplateResponse("associated_issues.html", {
        "request": request,
        "signal": signal,
        "issues": issues
    })


@app.get("/signals/{signal_id}/issues/{issue_id}", response_class=HTMLResponse)
async def signal_issue_detail(request: Request, signal_id: int, issue_id: str):
    """Issue detail in context of a signal."""
    signal = db.get_signal_by_id(signal_id)
    issue = db.get_issue_by_id(issue_id)
    association = db.get_association(signal_id, issue_id)

    if not signal or not issue:
        return HTMLResponse(content="<h1>Not found</h1>", status_code=404)

    return templates.TemplateResponse("issue_detail.html", {
        "request": request,
        "issue": issue,
        "signal": signal,
        "association": association,
        "context": "signal"
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
