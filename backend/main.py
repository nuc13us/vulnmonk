from fastapi import FastAPI
import os
from dotenv import load_dotenv

# Load environment variables from .env file BEFORE importing other modules
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Now import modules that depend on environment variables
from . import api, database

app = FastAPI()

# CORS is handled by nginx in production (proxy_hide_header strips backend headers,
# nginx injects Access-Control-Allow-Origin: * for all /api/ responses).
# No CORSMiddleware needed here.

@app.on_event("startup")
def on_startup():
    database.init_db()

app.include_router(api.router)

@app.get("/")
def read_root():
    return {"message": "VulnMonk SAST Dashboard Backend"}
