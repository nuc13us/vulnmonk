from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Load environment variables from .env file BEFORE importing other modules
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Now import modules that depend on environment variables
from . import api, database

app = FastAPI()

# Get CORS origins from environment variable
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    database.init_db()

app.include_router(api.router)

@app.get("/")
def read_root():
    return {"message": "VulnMonk SAST Dashboard Backend"}
