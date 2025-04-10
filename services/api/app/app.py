from app.v1.chat.completions import router as chat_router
from app.v1.completions import router as completions_router
from app.v1.embeddings import router as embeddings_router
from app.v1.models.get_model import router as get_model_router
from app.v1.models.list_models import router as list_models_router
from app.docs import router as docs_router


from fastapi import FastAPI
app = FastAPI()


app.include_router(chat_router)
app.include_router(completions_router)
app.include_router(embeddings_router)
app.include_router(get_model_router)
app.include_router(list_models_router)
app.include_router(docs_router)
app = FastAPI()


@app.get("/ping")
def ping():
    return {"status": "ok"}
