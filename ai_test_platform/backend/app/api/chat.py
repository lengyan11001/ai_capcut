from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse, summary="简单对话测试接口（占位）")
async def chat_endpoint(payload: ChatRequest):
    # 这里先做一个占位实现：简单回声 + 指引
    reply = (
        f"你说的是：{payload.message}\n\n"
        "当前还处于骨架阶段，后续这里会接入：\n"
        "- AI 大模型（Claude/GPT）\n"
        "- MCP 测试工具（接口测试、自动化测试等）"
    )
    return ChatResponse(reply=reply)

