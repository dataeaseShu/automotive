from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.upload import router as upload_router

app = FastAPI(
    title="Lumax 智能投手 AI Copilot",
    description="汽车数字化营销推送投放计划生成 API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 生产环境按实际域名收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(upload_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "lumax-copilot"}
