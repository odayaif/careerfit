"""
main.py — FastAPI backend for CareerFit.
Start: uvicorn backend.main:app --reload  (from project root)
Or:    uvicorn main:app --reload          (from backend/ folder)
"""
import os
import sys
import logging
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Ensure backend dir is on path (needed when running as `uvicorn backend.main:app`)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

_PROJECT_ROOT = os.path.dirname(_HERE)
ZIP_PATH = os.path.join(_PROJECT_ROOT, "data", "archive.zip")

# ---------------------------------------------------------------------------
# Imports from our modules
# ---------------------------------------------------------------------------
from database import db_exists, create_tables, get_db_stats, DATA_SOURCE
from models import (
    ChatRequest, ChatResponse, ProfileUpdateRequest,
    JobSearchRequest, empty_profile, profile_completeness
)


# ---------------------------------------------------------------------------
# Lifespan — startup tasks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CareerFit backend starting...")
    # Ensure DB tables exist
    try:
        create_tables()
    except Exception as e:
        logger.warning("create_tables error: %s", e)

    # Pre-build TF-IDF index in background thread
    if db_exists():
        def build_index():
            try:
                from matching_engine import ensure_tfidf_ready
                ensure_tfidf_ready()
            except Exception as e:
                logger.warning("TF-IDF pre-build failed: %s", e)
        threading.Thread(target=build_index, daemon=True).start()
    else:
        logger.warning("DB not found — running without job data")

    yield
    logger.info("CareerFit backend shutting down.")


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CareerFit API",
    description="סוכן חכם למציאת עבודה מותאמת אישית",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
origins = ["http://localhost:5173", "http://localhost:3000"]
if FRONTEND_URL:
    origins.append(FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "name": "CareerFit",
        "description": "סוכן חכם למציאת עבודה מותאמת אישית",
        "version": "1.0.0",
        "status": "running",
        "data_ready": db_exists(),
    }


@app.get("/health")
def health():
    data_ready = db_exists()
    stats = get_db_stats()
    zip_exists = os.path.exists(ZIP_PATH)

    # data_source: "full" (522 MB DB), "demo" (2,500 job DB), or "empty"
    data_source = DATA_SOURCE   # resolved at startup: full | demo | empty

    if data_ready:
        status = "ok"
        if data_source == "demo":
            message = "פועל במצב דמו — מוצגות משרות לדוגמה (~22,000 משרות). לחיפוש מלא יש להוסיף careerfit.db."
        else:
            message = ""
    elif zip_exists:
        status = "no_data"
        message = "הדאטה נמצא אך לא עובד. הרץ: python backend/data_pipeline.py"
    else:
        status = "no_data"
        message = "אין נתונים. הרץ: python backend/create_demo_db.py לבנות בסיס דמו, או הוסף careerfit.db."

    return {
        "status": status,
        "data_ready": data_ready,
        "data_source": data_source,       # "full" | "demo" | "empty"
        "total_jobs": stats.get("total_jobs", 0),
        "zip_exists": zip_exists,
        "message": message,
        "db_stats": stats,
    }


# ---------------------------------------------------------------------------
# Data processing endpoints
# ---------------------------------------------------------------------------

@app.post("/data/inspect")
def inspect_data():
    """Run data inspection and return report."""
    try:
        from data_inspector import run_inspection
        report = run_inspection()
        return {"status": "ok", "report_preview": report[:2000]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/data/process")
def process_data(background_tasks: BackgroundTasks):
    """Run the full data pipeline in background."""
    if not os.path.exists(ZIP_PATH):
        raise HTTPException(
            status_code=404,
            detail="archive.zip לא נמצא בנתיב data/archive.zip"
        )
    def run():
        try:
            from data_pipeline import run_pipeline
            run_pipeline()
            logger.info("data_pipeline completed")
            from matching_engine import ensure_tfidf_ready
            ensure_tfidf_ready()
        except Exception as e:
            logger.error("data_pipeline error: %s", e)

    background_tasks.add_task(run)
    return {"status": "started", "message": "עיבוד נתונים החל ברקע. יתכן שיקח מספר דקות."}


@app.post("/data/cluster")
def cluster_data(background_tasks: BackgroundTasks):
    """Run clustering in background."""
    if not db_exists():
        raise HTTPException(status_code=400, detail="יש לעבד נתונים קודם")

    def run():
        try:
            from clustering_engine import run_clustering
            run_clustering()
        except Exception as e:
            logger.error("clustering error: %s", e)

    background_tasks.add_task(run)
    return {"status": "started", "message": "Clustering החל ברקע."}


@app.post("/data/analyze-anomalies")
def analyze_anomalies():
    """Run anomaly detection."""
    try:
        from anomaly_engine import detect_anomalies
        result = detect_anomalies()
        return {"status": "ok", "anomalies": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------------------------

@app.get("/profile")
def get_default_profile():
    """Return a default empty profile."""
    return empty_profile()


@app.post("/profile/update")
def update_profile(req: ProfileUpdateRequest):
    """Merge NLP-extracted updates into an existing profile."""
    try:
        from nlp_engine import extract_profile_updates, merge_profile_updates
        # req.profile should already be updated; just validate and return
        completeness = profile_completeness(req.profile)
        return {"profile": req.profile, "completeness": completeness}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/profile/reset")
def reset_profile():
    """Return a fresh empty profile."""
    return {"profile": empty_profile(), "completeness": 0}


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Main conversational endpoint."""
    try:
        from agent_logic import process_message
        profile = req.profile if req.profile else empty_profile()
        result = process_message(req.message, profile)
        return ChatResponse(**result)
    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        return ChatResponse(
            reply="מצטער/ת, אירעה שגיאה. נסה/י שוב.",
            profile=req.profile or empty_profile(),
            intent="error",
            profile_completeness=0,
        )


# ---------------------------------------------------------------------------
# Job search endpoint
# ---------------------------------------------------------------------------

@app.post("/jobs/search")
def search_jobs_endpoint(req: JobSearchRequest):
    """Direct job search endpoint."""
    if not db_exists():
        return {
            "jobs": [],
            "search_metadata": {},
            "message": "מסד הנתונים לא נמצא. יש לעבד את הנתונים תחילה.",
        }
    try:
        from matching_engine import search_jobs
        jobs, metadata = search_jobs(
            req.profile,
            limit=req.limit,
            location_override=req.location_override,
        )
        return {"jobs": jobs, "search_metadata": metadata}
    except Exception as e:
        logger.error("Search error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Analytics endpoints
# ---------------------------------------------------------------------------

@app.get("/analytics/summary")
def analytics_summary():
    try:
        from analytics_engine import get_summary
        return get_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/trends")
def analytics_trends():
    try:
        from analytics_engine import get_trends
        return get_trends()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/anomalies")
def analytics_anomalies():
    try:
        from anomaly_engine import detect_anomalies
        return detect_anomalies()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/clusters")
def analytics_clusters():
    try:
        from clustering_engine import get_cluster_summaries
        return {"clusters": get_cluster_summaries()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Entry point for running directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
