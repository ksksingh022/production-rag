from fastapi import FastAPI, APIRouter

router = APIRouter()

@router.get("/chunks")
async def get_chunks():
    return {"message": "Welcome to the RAG API!"}