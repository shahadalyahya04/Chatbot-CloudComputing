import json
import os
import uuid
from typing import List, Optional
import chromadb

import psycopg2
import logging
import tempfile
from pathlib import Path
from functools import lru_cache
from urllib.parse import urlsplit
from psycopg2.extras import RealDictCursor
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceNotFoundError
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from langchain_chroma import Chroma
from langchain_classic.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI, OpenAIError
from pydantic import BaseModel

load_dotenv()

# Stage 7: Azure supplies secrets; OpenRouter remains the model provider.
key_vault_name = os.environ.get("KEY_VAULT_NAME")
if key_vault_name:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    secret_names = {
        "DB_NAME": "PROJ-DB-NAME",
        "DB_USER": "PROJ-DB-USER",
        "DB_PASSWORD": "PROJ-DB-PASSWORD",
        "DB_HOST": "PROJ-DB-HOST",
        "DB_PORT": "PROJ-DB-PORT",
        "OPENROUTER_API_KEY": "PROJ-OPENROUTER-API-KEY",
        "AZURE_STORAGE_SAS_URL": "PROJ-AZURE-STORAGE-SAS-URL",
        "AZURE_STORAGE_CONTAINER": "PROJ-AZURE-STORAGE-CONTAINER",
        "CHROMADB_HOST": "PROJ-CHROMADB-HOST",
        "CHROMADB_PORT": "PROJ-CHROMADB-PORT",
    }
    with DefaultAzureCredential() as credential:
        with SecretClient(
            vault_url=f"https://{key_vault_name}.vault.azure.net",
            credential=credential,
        ) as secret_client:
            for env_name, secret_name in secret_names.items():
                os.environ[env_name] = secret_client.get_secret(secret_name).value

app = FastAPI()

# OpenRouter & LLM Configuration
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
api_key = os.environ.get("OPENROUTER_API_KEY")
model = "openrouter/free"

client = OpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=api_key,
)

# LangChain LLM & Embeddings Setup
DEFAULT_EMBEDDING_MODEL = "nvidia/nemotron-3-embed-1b:free"

llm = ChatOpenAI(
    model=model,
    base_url=OPENROUTER_BASE_URL,
    api_key=api_key,
    max_tokens=2048,
)

embeddings = OpenAIEmbeddings(
    model=DEFAULT_EMBEDDING_MODEL,
    base_url=OPENROUTER_BASE_URL,
    api_key=api_key,
    check_embedding_ctx_length=False,
    model_kwargs={"encoding_format": "float"},
)

# Vector Store Setup (Chroma)

CHROMA_HOST = os.environ.get("CHROMADB_HOST") or os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMADB_PORT") or os.environ.get("CHROMA_PORT", "8000"))

@lru_cache(maxsize=1)
def get_vectorstore():
    return Chroma(
        client=chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT),
        collection_name="pdf_chats",
        embedding_function=embeddings,
    )

# Azure PostgreSQL configuration
DB_CONFIG = {
    "dbname": os.environ.get("DB_NAME"),
    "user": os.environ.get("DB_USER"),
    "password": os.environ.get("DB_PASSWORD"),
    "host": os.environ.get("DB_HOST"),
    "port": int(os.environ.get("DB_PORT") or 5432),
    "sslmode": "require",
    "connect_timeout": 10,
}


def get_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except psycopg2.Error:
        raise HTTPException(status_code=503, detail="PostgreSQL connection failed. Check credentials and firewall rules.") from None
    try:
        yield conn
    finally:
        conn.close()


@lru_cache(maxsize=1)
def get_container():
    parsed = urlsplit(os.environ.get("AZURE_STORAGE_SAS_URL", "").strip())
    name = os.environ.get("AZURE_STORAGE_CONTAINER", "").strip()
    if parsed.scheme != "https" or not parsed.netloc or not parsed.query or not name:
        raise RuntimeError("Set a valid Blob service SAS URL and container name.")
    service = BlobServiceClient(
        account_url=f"https://{parsed.netloc}", credential=parsed.query,
        connection_timeout=10, read_timeout=30,
    )
    return service.get_container_client(name)


def service_error(action, error):
    # Do not expose SDK exception messages containing signed URLs or credentials.
    logging.getLogger(__name__).error("%s failed (%s)", action, type(error).__name__)
    return HTTPException(status_code=500, detail=f"{action} failed. Check service credentials, permissions and connectivity.")


@app.get("/health/")
def health(db=Depends(get_db)):
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM public.advanced_chats LIMIT 1")
    except Exception as error:
        raise service_error("PostgreSQL table check", error) from None
    try:
        get_container().get_container_properties()
    except Exception as error:
        raise service_error("Blob Storage check", error) from None
    try:
        get_vectorstore()
    except Exception as error:
        raise service_error("Chroma check", error) from None
    return {"status": "ok"}


# Request Models
class ChatRequest(BaseModel):
    messages: List[dict]


class SaveChatRequest(BaseModel):
    chat_id: str
    chat_name: str
    messages: List[dict]
    pdf_name: Optional[str] = None
    pdf_path: Optional[str] = None
    pdf_uuid: Optional[str] = None


class RAGChatRequest(BaseModel):
    messages: List[dict]
    pdf_uuid: str


class DeleteChatRequest(BaseModel):
    chat_id: str


# Endpoints
@app.post("/chat/")
async def chat(request: ChatRequest):
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=request.messages,
            max_tokens=2048,
            stream=True,
        )

        def stream_response():
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

        return StreamingResponse(stream_response(), media_type="text/plain")

    except OpenAIError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/upload_pdf/")
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    try:
        pdf_uuid = str(uuid.uuid4())
        file_path = f"pdf_store/{pdf_uuid}.pdf"
        pdf_bytes = await file.read()
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "document.pdf"
            local_path.write_bytes(pdf_bytes)
            documents = PyPDFLoader(str(local_path)).load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        texts = text_splitter.split_documents(documents)
        if not texts:
            raise HTTPException(status_code=400, detail="No readable text in PDF. Scanned documents require OCR.")
        vectorstore = get_vectorstore()
        blob = get_container().get_blob_client(file_path)
        blob.upload_blob(
            pdf_bytes, overwrite=False,
            content_settings=ContentSettings(content_type="application/pdf"),
        )
        ids = [str(uuid.uuid4()) for _ in texts]
        try:
            vectorstore.add_texts(
                [doc.page_content for doc in texts], ids=ids,
                metadatas=[{"pdf_uuid": pdf_uuid} for _ in texts],
            )
        except Exception:
            for cleanup in (lambda: vectorstore.delete(ids=ids), blob.delete_blob):
                try:
                    cleanup()
                except Exception as error:
                    logging.getLogger(__name__).warning("Upload cleanup failed (%s)", type(error).__name__)
            raise

        return {"message": "File uploaded successfully", "pdf_path": file_path, "pdf_uuid": pdf_uuid}

    except HTTPException:
        raise
    except Exception as e:
        raise service_error("PDF upload", e) from None


@app.post("/rag_chat/")
async def rag_chat(request: RAGChatRequest):
    retriever = get_vectorstore().as_retriever(
        search_kwargs={"k": 5, "filter": {"pdf_uuid": request.pdf_uuid}}
    )

    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "Given a chat history and the latest user question which might reference context in the chat history, formulate a standalone question. Do NOT answer the question, just reformulate it if needed."),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    history_aware_retriever = create_history_aware_retriever(llm, retriever, contextualize_q_prompt)

    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system",             """You are an assistant for question-answering tasks.

Use the retrieved context to answer the user's request accurately.

If the answer is not available in the context, say that you don't know.

Adjust the length and format of the answer based on the user's request.

If the user asks for a script, explanation, summary, or detailed response,
provide an appropriately detailed answer.

Context:
{context}"""),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    chat_history = []
    for message in request.messages[:-1]:
        if message["role"] == "user":
            chat_history.append(HumanMessage(content=message["content"]))
        elif message["role"] == "assistant":
            chat_history.append(AIMessage(content=message["content"]))

    user_input = request.messages[-1]["content"]
    chain = rag_chain.pick("answer")

    def stream_response():
        for chunk in chain.stream({"chat_history": chat_history, "input": user_input}):
            yield chunk

    return StreamingResponse(stream_response(), media_type="text/plain")


@app.get("/load_chat/")
async def load_chat(db = Depends(get_db)):
    try:
        cursor = db.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id, name, file_path, pdf_name, pdf_path, pdf_uuid "
            "FROM advanced_chats ORDER BY last_update DESC"
        )
        rows = cursor.fetchall()
        cursor.close()

        records = []
        for row in rows:
            chat_id, name, file_path = row["id"], row["name"], row["file_path"]
            messages = json.loads(get_container().get_blob_client(file_path).download_blob().readall())
            records.append(
                {
                    "id": chat_id,
                    "chat_name": name,
                    "messages": messages,
                    "pdf_name": row["pdf_name"],
                    "pdf_path": row["pdf_path"],
                    "pdf_uuid": row["pdf_uuid"],
                }
            )

        return records

    except Exception as e:
        raise service_error("Load chats", e) from None


@app.post("/save_chat/")
async def save_chat(request: SaveChatRequest, db = Depends(get_db)):
    try:
        file_path = f"chat_logs/{request.chat_id}.json"
        get_container().get_blob_client(file_path).upload_blob(
            json.dumps(request.messages, ensure_ascii=False, indent=4).encode("utf-8"),
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json; charset=utf-8"),
        )

        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO advanced_chats (id, name, file_path, last_update, pdf_path, pdf_name, pdf_uuid)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                file_path = EXCLUDED.file_path,
                last_update = CURRENT_TIMESTAMP,
                pdf_path = EXCLUDED.pdf_path,
                pdf_name = EXCLUDED.pdf_name,
                pdf_uuid = EXCLUDED.pdf_uuid
            """,
            (request.chat_id, request.chat_name, file_path, request.pdf_path, request.pdf_name, request.pdf_uuid),
        )
        db.commit()
        cursor.close()
        return {"message": "Chat saved successfully"}

    except Exception as e:
        db.rollback()
        raise service_error("Save chat", e) from None


@app.post("/delete_chat/")
async def delete_chat(
    request: DeleteChatRequest,
    db = Depends(get_db),
):
    try:
        file_path = None
        cursor = db.cursor()
        cursor.execute(
            "SELECT file_path FROM advanced_chats WHERE id = %s", (request.chat_id,)
        )
        result = cursor.fetchone()
        if result:
            file_path = result[0]
        else:
            cursor.close()
            raise HTTPException(status_code=404, detail="Chat not found")

        cursor.execute(
            "DELETE FROM advanced_chats WHERE id = %s", (request.chat_id,)
        )
        db.commit()
        cursor.close()

        if file_path:
            try:
                get_container().get_blob_client(file_path).delete_blob()
            except ResourceNotFoundError:
                pass

        return {"message": "Chat deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise service_error("Delete chat", e) from None
