import json
import os
import secrets
import threading
from datetime import datetime, timezone

from openai import OpenAI
from pathlib import Path
from uuid import uuid4

# 로컬 테스트 모드: 대화 기록은 서버 실행 중에만 메모리에 보관합니다.
conversations: dict[str, dict] = {}

from typing import Literal

from fastapi import FastAPI, HTTPException, Request
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
    """로컬 테스트 모드에서는 CSV 데이터만 확인하고 Firestore에 접속하지 않습니다."""
    rows = load_stock_data()
    if not rows:
        raise RuntimeError("삼성전자 과거 주가 CSV에 데이터가 없습니다.")


@app.get("/")
def root():
    html_file = Path(__file__).resolve().parent.parent / "static" / "index.html"
    return FileResponse(html_file)


@app.get("/api/data")
def get_data(symbol: str | None = None, limit: int = 200):
    """로컬 CSV에서 과거 주가를 조회합니다."""
    if limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=400,
            detail="limit은 1~1000 사이여야 합니다.",
        )

    rows = load_stock_data()

    if symbol:
        rows = [
            row for row in rows
            if row.get("symbol", "").upper() == symbol.upper()
        ]

    rows.sort(key=lambda item: item["date"])
    selected = rows[-limit:]

    return {
        "count": len(selected),
        "items": [
            {
                **row,
                "id": f"{row['symbol']}-{row['date']}",
            }
            for row in selected
        ],
    }


@app.post("/api/data", status_code=405)
def create_data(item: DataCreate):
    """로컬 CSV 테스트 모드에서는 데이터 추가를 허용하지 않습니다."""
    raise HTTPException(
        status_code=405,
        detail="로컬 테스트 모드에서는 데이터 추가를 지원하지 않습니다.",
    )


@app.put("/api/data/{item_id}", status_code=405)
def update_data(item_id: str, item: DataCreate):
    """로컬 CSV 테스트 모드에서는 데이터 수정을 허용하지 않습니다."""
    raise HTTPException(
        status_code=405,
        detail="로컬 테스트 모드에서는 데이터 수정을 지원하지 않습니다.",
    )


@app.delete("/api/data/{item_id}", status_code=405)
def delete_data(item_id: str):
    """로컬 CSV 테스트 모드에서는 데이터 삭제를 허용하지 않습니다."""
    raise HTTPException(
        status_code=405,
        detail="로컬 테스트 모드에서는 데이터 삭제를 지원하지 않습니다.",
    )



@app.get("/api/data/summary")
def get_summary(symbol: str | None = None):
    """로컬 CSV의 과거 주가를 요약합니다."""
    rows = load_stock_data()

    if symbol:
        rows = [
            row for row in rows
            if row.get("symbol", "").upper() == symbol.upper()
        ]

    return summarize_stock_data(rows)


@app.get("/api/health")
def health_check():
    """로컬 CSV 테스트 모드의 상태를 확인합니다."""
    try:
        rows = load_stock_data()
        return {
            "status": "ok",
            "database": "local_csv",
            "data_source": (
                rows[0].get("data_type", "UNKNOWN")
                if rows
                else None
            ),
            "count": len(rows),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="로컬 CSV 데이터 확인에 실패했습니다.",
        ) from exc


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@app.post("/api/conversations", status_code=201)
def create_conversation(item: ConversationCreate):
    """대화를 로컬 메모리에 생성합니다."""
    messages = [message.model_dump() for message in item.messages]

    first_user_message = next(
        (m["content"] for m in messages if m["role"] == "user"),
        "새 대화",
    )
    title = item.title or first_user_message[:60]
    now = utc_now()
    conversation_id = str(uuid4())

    conversation = {
        "id": conversation_id,
        "title": title,
        "messages": messages,
        "created_at": now,
        "updated_at": now,
    }
    conversations[conversation_id] = conversation

    return conversation


@app.post("/api/chat")
def chat(request: ChatRequest):
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY 환경 변수를 설정해 주세요.",
        )

    conversation_id = request.conversation_id
    now = utc_now()

    if conversation_id:
        conversation = conversations.get(conversation_id)

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="해당 대화를 찾을 수 없습니다.",
            )

        messages = conversation.get("messages", [])
        title = conversation.get("title", request.message[:60])
        created_at = conversation.get("created_at", now)
    else:
        conversation_id = str(uuid4())
        messages = []
        title = request.message[:60]
        created_at = now

    summary = get_summary(symbol="005930")

    system_prompt = (
       "너는 주식 시계열 데이터를 설명하는 교육용 AI 비서다. "
        "제공된 요약 정보를 바탕으로 한국어로 답변해라. "
        "현재 분석 대상 회사는 삼성전자이며 종목코드는 005930이다. "
        "사용하는 CSV 파일명은 data/samsung_2years.csv이다. "
        "CSV 헤더는 date,symbol,close,data_type이다. "
        "사용자가 회사명, 종목코드, CSV 파일명 또는 헤더를 물으면 "
        "위 정보를 정확하게 답변해라. "
        "제공된 데이터는 CSV에 저장된 과거 주가이며 실시간 가격이 "
        "아님을 명확히 설명해라. "
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
            base_url=os.getenv(
                "OPENAI_BASE_URL",
                "https://copa.codyssey.kr/v1",
            ),
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

    conversation = {
        "id": conversation_id,
        "title": title,
        "messages": updated_messages,
        "created_at": created_at,
        "updated_at": utc_now(),
    }
    conversations[conversation_id] = conversation

    return {
        "conversation_id": conversation_id,
        "user_message": request.message,
        "assistant_message": answer,
        "messages": updated_messages,
        "summary": summary,
    }


@app.get("/api/conversations")
def list_conversations():
    """메모리에 저장된 대화 목록을 반환합니다."""
    items = []

    for conversation_id, data in conversations.items():
        messages = data.get("messages", [])

        items.append({
            "id": conversation_id,
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
    """메모리에 저장된 대화를 조회합니다."""
    conversation = conversations.get(conversation_id)

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="해당 대화를 찾을 수 없습니다.",
        )

    return conversation


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    """메모리에 저장된 대화를 삭제합니다."""
    if conversation_id not in conversations:
        raise HTTPException(
            status_code=404,
            detail="해당 대화를 찾을 수 없습니다.",
        )

    del conversations[conversation_id]
    return {"deleted": True, "id": conversation_id}


# 로컬 서버 종료를 위한 보안 토큰을 생성한다.
_shutdown_token = secrets.token_urlsafe(32)
_uvicorn_server = None


@app.post("/api/shutdown-token")
def get_shutdown_token(request: Request):
    host = request.headers.get("host", "")
    origin = request.headers.get("origin", "")
    expected_origin = f"http://{host}"

    if host not in {"127.0.0.1:8000", "localhost:8000",
                    "127.0.0.1:8001", "localhost:8001"}:
        raise HTTPException(status_code=403, detail="Local access only")
    if origin != expected_origin:
        raise HTTPException(status_code=403, detail="Invalid origin")

    return {"token": _shutdown_token}


@app.post("/api/shutdown")
def shutdown_server(request: Request):
    global _uvicorn_server

    host = request.headers.get("host", "")
    origin = request.headers.get("origin", "")
    expected_origin = f"http://{host}"

    if host not in {"127.0.0.1:8000", "localhost:8000",
                    "127.0.0.1:8001", "localhost:8001"}:
        raise HTTPException(status_code=403, detail="Local access only")
    if origin != expected_origin:
        raise HTTPException(status_code=403, detail="Invalid origin")
    if request.headers.get("x-shutdown-token") != _shutdown_token:
        raise HTTPException(status_code=403, detail="Invalid shutdown token")
    if _uvicorn_server is None:
        raise HTTPException(status_code=503, detail="Managed server is not running")

    threading.Timer(0.5, lambda: setattr(_uvicorn_server, "should_exit", True)).start()
    return {"status": "shutdown_requested", "message": "Server shutdown requested"}

if __name__ == "__main__":
    import sys
    import os
    import uvicorn
    import webbrowser
    from threading import Timer
    from pathlib import Path

    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    port = int(os.getenv("PORT", "8000"))
    url = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(app, host="127.0.0.1", port=port)
    server = uvicorn.Server(config)

    _uvicorn_server = server
    Timer(1.5, lambda: webbrowser.open(url)).start()
    server.run()
