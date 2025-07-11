from fastapi import FastAPI
from pymongo import MongoClient
from pydantic import BaseModel
from bson import ObjectId
from typing import Optional
from app.routers import athlete_router
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI()


app.include_router(athlete_router.router)

@app.get("/")
def root():
    return {"message": "Welcome to the FireSport API!"}





app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Nebo konkrétní doména frontendu
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
