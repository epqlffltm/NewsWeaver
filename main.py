# main.py

"""
FastAPI 애플리케이션의 진입점.
"""

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI"}