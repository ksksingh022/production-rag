from fastapi import FastAPI
from api.routes import router as api_router

app = FastAPI()

app.include_router(api_router)

@app.get("/")
def root():
    return {"message": "Welcome to the Main App"}