import json
import os
from datetime import datetime, timezone

from openai import OpenAI
from pathlib import Path
from uuid import uuid4
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.data_service import load_stock_data, summarize_stock_data
from app.firebase_service import get_firestore_client


app = FastAPI(
    title="AI Stock Helper API",
    description="초보 투자자를 위한 교육용 주가 데이터 API. 현재 가격 데이터는 시뮬레이션입니다.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DataCreate(BaseModel):
    date: str = Field(description="YYYY-MM-DD 형식의 날짜")
    symbol: str = Field(min_length=1, max_length=20)
    close: float = Field(gt=0)
    data_type: Literal[
        "SIMULATED_EDUCATIONAL_DATA",
        "REAL_MARKET_DATA",
    ] = "SIMULATED_EDUCATIONAL_DATA"

class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)

class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    messages: list[ConversationMessage] = Field(default_factory=list)

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None

def get_db():
    try:
        return get_firestore_client()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Firestore 연결에 실패했습니다. Firebase 인증 설정을 확인하세요.",
        ) from exc


def seed_initial_data(db):
    """Firestore의 data 컬렉션이 비어 있을 때만 CSV 데이터를 등록합니다."""
    collection = db.collection("data")

    # 기존 데이터가 있으면 CSV를 다시 등록하지 않습니다.
    if next(collection.limit(1).stream(), None) is not None:
        return

    csv_rows = load_stock_data()

    # 문서 ID를 자동 생성해 각 데이터를 Firestore에 저장합니다.
    # 문서마다 고유한 ID를 반환하므로 이후 수정·삭제에 사용할 수 있습니다.
    batch = db.batch()

    for row in csv_rows:
        doc_ref = collection.document(str(uuid4()))
        batch.set(doc_ref, row)

    if csv_rows:
        batch.commit()


@app.on_event("startup")
def initialize_database():
    """서버 시작 시 Firestore를 확인하고 초기 데이터를 준비합니다."""
    db = get_db()
    seed_initial_data(db)


@app.get("/")
def root():
    html_file = Path(__file__).resolve().parent.parent / "static" / "index.html"
    return FileResponse(html_file)


@app.get("/api/data")
def get_data(symbol: str | None = None, limit: int = 200):
    if limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=400,
            detail="limit은 1~1000 사이여야 합니다.",
        )

    db = get_db()
    documents = db.collection("data").stream()

    rows = []
    for document in documents:
        row = document.to_dict()
        row["id"] = document.id

        if symbol and row.get("symbol", "").upper() != symbol.upper():
            continue

        rows.append(row)

    rows.sort(key=lambda item: item["date"])

    selected = rows[:limit]
    return {
        "count": len(selected),
        "items": selected,
    }


@app.post("/api/data", status_code=201)
def create_data(item: DataCreate):
    db = get_db()

    row = item.model_dump()
    doc_ref = db.collection("data").document(str(uuid4()))
    doc_ref.set(row)

    return {
        **row,
        "id": doc_ref.id,
    }


@app.put("/api/data/{item_id}")
def update_data(item_id: str, item: DataCreate):
    db = get_db()
    doc_ref = db.collection("data").document(item_id)

    if not doc_ref.get().exists:
        raise HTTPException(
            status_code=404,
            detail="해당 ID의 데이터가 없습니다.",
        )

    row = item.model_dump()
    doc_ref.set(row)

    return {
        **row,
        "id": item_id,
    }


@app.delete("/api/data/{item_id}")
def delete_data(item_id: str):
    db = get_db()
    doc_ref = db.collection("data").document(item_id)
    snapshot = doc_ref.get()

    if not snapshot.exists:
        raise HTTPException(
            status_code=404,
            detail="해당 ID의 데이터가 없습니다.",
        )

    removed = snapshot.to_dict()
    doc_ref.delete()

    return {
        "deleted": True,
        "item": {
            **removed,
            "id": item_id,
        },
    }


@app.get("/api/data/summary")
def get_summary(symbol: str | None = None):
    db = get_db()
    documents = db.collection("data").stream()

    rows = []
    for document in documents:
        row = document.to_dict()

        if symbol and row.get("symbol", "").upper() != symbol.upper():
            continue

        rows.append(row)

    return summarize_stock_data(rows)


@app.get("/api/health")
def health_check():
    try:
        db = get_db()
        # 컬렉션에 문서가 있는지 확인하여 연결을 점검합니다.
        next(db.collection("data").limit(1).stream(), None)

        return {
            "status": "ok",
            "database": "firestore",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Firestore 상태 확인에 실패했습니다.",
        ) from exc

def utc_now():
    return datetime.now(timezone.utc).isoformat()


@app.post("/api/conversations", status_code=201)
def create_conversation(item: ConversationCreate):
    db = get_db()
    messages = [message.model_dump() for message in item.messages]

    first_user_message = next(
        (m["content"] for m in messages if m["role"] == "user"),
        "새 대화",
    )
    title = item.title or first_user_message[:60]
    now = utc_now()

    doc_ref = db.collection("conversations").document(str(uuid4()))
    doc_ref.set({
        "title": title,
        "messages": messages,
        "created_at": now,
        "updated_at": now,
    })

    return {
        "id": doc_ref.id,
        "title": title,
        "messages": messages,
        "created_at": now,
        "updated_at": now,
    }

@app.post("/api/chat")
def chat(request: ChatRequest):
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY 환경 변수를 설정해 주세요.",
        )

    db = get_db()
    collection = db.collection("conversations")

    conversation_id = request.conversation_id
    now = utc_now()

    if conversation_id:
        doc_ref = collection.document(conversation_id)
        snapshot = doc_ref.get()

        if not snapshot.exists:
            raise HTTPException(
                status_code=404,
                detail="해당 대화를 찾을 수 없습니다.",
            )

        conversation = snapshot.to_dict()
        messages = conversation.get("messages", [])
        title = conversation.get("title", request.message[:60])
        created_at = conversation.get("created_at", now)
    else:
        doc_ref = collection.document(str(uuid4()))
        messages = []
        title = request.message[:60]
        created_at = now

    # 기존 데이터 요약을 AI의 시스템 프롬프트에 주입한다.
    summary = get_summary()

    system_prompt = (
        "너는 주식 시계열 데이터를 설명하는 교육용 AI 비서다. "
        "제공된 요약 정보를 바탕으로 한국어로 답변해라. "
        "데이터가 모의 교육용 데이터라면 실제 시장 가격으로 "
        "오해하지 않도록 명확히 설명해라. "
        "정보에 없는 사실이나 미래 가격을 확정적으로 주장하지 마라.\n\n"
        f"현재 데이터 요약:\n{json.dumps(summary, ensure_ascii=False)}"
    )

    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(messages[-12:])
    api_messages.append({
        "role": "user",
        "content": request.message,
    })

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL", "https://copa.codyssey.kr/v1"),
)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=api_messages,
            max_tokens=700,
        )
        answer = response.choices[0].message.content

        if not answer:
            answer = "답변을 생성하지 못했습니다."

    except Exception as exc:
        print(f"AI 오류 유형: {type(exc).__name__}")
        print(f"AI 오류 상세: {exc}")
        raise HTTPException(
            status_code=502,
            detail="AI 응답 생성에 실패했습니다. API 키와 사용량 설정을 확인해 주세요.",
        ) from exc

    updated_messages = messages + [
        {"role": "user", "content": request.message},
        {"role": "assistant", "content": answer},
    ]

    doc_ref.set({
        "title": title,
        "messages": updated_messages,
        "created_at": created_at,
        "updated_at": utc_now(),
    })

    return {
        "conversation_id": doc_ref.id,
        "user_message": request.message,
        "assistant_message": answer,
        "messages": updated_messages,
        "summary": summary,
    }

@app.get("/api/conversations")
def list_conversations():
    db = get_db()
    documents = db.collection("conversations").stream()

    items = []
    for document in documents:
        data = document.to_dict()
        messages = data.get("messages", [])

        items.append({
            "id": document.id,
            "title": data.get("title", "새 대화"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "message_count": len(messages),
        })

    items.sort(
        key=lambda item: item.get("updated_at") or "",
        reverse=True,
    )
    return {"count": len(items), "items": items}


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    db = get_db()
    doc_ref = db.collection("conversations").document(conversation_id)
    snapshot = doc_ref.get()

    if not snapshot.exists:
        raise HTTPException(
            status_code=404,
            detail="해당 대화를 찾을 수 없습니다.",
        )

    return {"id": snapshot.id, **snapshot.to_dict()}


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    db = get_db()
    doc_ref = db.collection("conversations").document(conversation_id)
    snapshot = doc_ref.get()

    if not snapshot.exists:
        raise HTTPException(
            status_code=404,
            detail="해당 대화를 찾을 수 없습니다.",
        )

    doc_ref.delete()
    return {"deleted": True, "id": conversation_id}