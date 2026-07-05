from fastapi import FastAPI
from api.routes import router as api_router
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()

app.include_router(api_router)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

@app.get("/")
def root():
    return {"message": "Welcome to the Main App"}