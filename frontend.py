import uuid
import requests
import streamlit as st
import os

st.set_page_config(
    page_title="Cloud Chatbot", page_icon="☁️", layout="centered",
    initial_sidebar_state="expanded",
)

# Presentation only: keep the existing chat and storage operations below.
st.markdown("""
<style>
.stApp { background: #0c1420; }
[data-testid="stHeader"] { background: #0c1420; }
[data-testid="stMainBlockContainer"] { max-width: 960px; padding-top: 3rem; }
[data-testid="stSidebar"] { background: #111d2c; border-right: 1px solid #233247; }
[data-testid="stSidebar"] > div:first-child { padding-top: 2rem; }
.brand { display: flex; align-items: center; gap: 12px; margin: 0 0 26px; }
.brand-mark { display: grid; place-items: center; width: 42px; height: 42px;
    background: #163c40; color: #8ce4d3; border: 1px solid #2b6261;
    border-radius: 14px; font-size: 25px; }
.brand-name { font-size: 19px; font-weight: 700; color: #edf3fc; }
.brand-note { font-size: 12px; color: #98aac1; margin-top: 2px; }
.section-label { color: #98aac1; font-size: 11px; font-weight: 700;
    letter-spacing: 2px; margin: 22px 0 12px; }
.workspace-heading { display: flex; align-items: center; justify-content: space-between;
    gap: 12px; padding-bottom: 20px; border-bottom: 1px solid #233247; margin-bottom: 28px; }
.workspace-heading strong { color: #edf3fc; font-size: 18px; }
.workspace-heading span { color: #98aac1; font-size: 12px; }
.welcome { text-align: center; padding: 56px 12px 36px; }
.welcome-mark { display: inline-grid; place-items: center; height: 72px; width: 72px;
    border-radius: 24px; background: #163c40; color: #8ce4d3;
    border: 1px solid #2b6261; font-size: 38px; margin-bottom: 24px; }
.welcome .eyebrow { color: #8ce4d3; font-size: 11px; font-weight: 700;
    letter-spacing: 3px; margin-bottom: 14px; }
.welcome h1 { color: #edf3fc; font-size: clamp(30px, 5vw, 44px);
    letter-spacing: -1.5px; line-height: 1.18; padding: 0 0 16px; }
.welcome p { color: #a6b5ca; font-size: 16px; max-width: 470px;
    margin: 0 auto; line-height: 1.7; }
.welcome-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
    max-width: 620px; margin: 0 auto 28px; }
.welcome-card { border: 1px solid #293b50; background: #111d2c;
    padding: 24px; border-radius: 18px; }
.welcome-card .card-icon { color: #8ce4d3; font-size: 22px; margin-bottom: 14px; }
.welcome-card strong { display: block; color: #edf3fc; margin-bottom: 8px; font-size: 15px; }
.welcome-card p { color: #a6b5ca; font-size: 13px; line-height: 1.6; margin: 0; }
.welcome-hint { color: #98aac1; font-size: 12px; text-align: center; margin-bottom: 24px; }
[data-testid="stSidebar"] [data-testid="stButton"] button { width: 100%;
    min-height: 43px; border-radius: 10px; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    border: 1px dashed #3a5069; border-radius: 12px; }
[data-testid="stSidebar"] [role="radiogroup"] { gap: 8px; }
[data-testid="stSidebar"] [role="radiogroup"] > label {
    padding: 10px 12px; border: 1px solid #293b50; border-radius: 10px; }
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {
    background: #163c40; border-color: #4b938a; }
[data-testid="stChatMessage"] { border: 1px solid #293b50;
    border-radius: 16px; padding: 20px; margin-bottom: 12px; }
[data-testid="stChatInput"] { border-radius: 16px; border: 1px solid #405771; }
@media (max-width: 640px) {
    .welcome { padding-top: 24px; }
    .welcome-cards { grid-template-columns: 1fr; }
    .workspace-heading span { display: none; }
}
</style>
""", unsafe_allow_html=True)


def show_welcome(has_chat=False):
    st.markdown("""
    <div class="welcome">
        <div class="welcome-mark" aria-hidden="true">☁</div>
        <div class="eyebrow">A LITTLE CURIOSITY. ENDLESS POSSIBILITIES.</div>
        <h1>Where ideas become conversations.</h1>
        <p>Ask a question, explore an idea, or find answers in your documents.
        Your next conversation starts here.</p>
    </div>
    <div class="welcome-cards">
        <div class="welcome-card"><div class="card-icon" aria-hidden="true">✧</div>
            <strong>Start with a question</strong>
            <p>Think things through, discover something new, or get a fresh perspective.</p></div>
        <div class="welcome-card"><div class="card-icon" aria-hidden="true">▤</div>
            <strong>Bring your documents</strong>
            <p>Upload a PDF from the sidebar and ask questions about its contents.</p></div>
    </div>
    """, unsafe_allow_html=True)
    hint = "Write a message below to begin." if has_chat else "Create a chat or choose a saved conversation in the sidebar."
    st.markdown(f'<div class="welcome-hint">{hint}</div>', unsafe_allow_html=True)


BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:5000")
LOAD_CHAT_URL = f"{BACKEND_URL}/load_chat/"
SAVE_CHAT_URL = f"{BACKEND_URL}/save_chat/"
DELETE_CHAT_URL = f"{BACKEND_URL}/delete_chat/"
UPLOAD_PDF_URL = f"{BACKEND_URL}/upload_pdf/"
CHAT_URL = f"{BACKEND_URL}/chat/"
RAG_CHAT_URL = f"{BACKEND_URL}/rag_chat/"

# Session State Initializations
if "history_chats" not in st.session_state:
    st.session_state["history_chats"] = []
if "current_chat" not in st.session_state:
    st.session_state["current_chat"] = None
if "chat_names" not in st.session_state:
    st.session_state["chat_names"] = {}
if "chats_loaded" not in st.session_state:
    st.session_state["chats_loaded"] = False


def load_chats_from_db():
    try:
        response = requests.get(LOAD_CHAT_URL, timeout=60)
        response.raise_for_status()
    except requests.HTTPError as error:
        detail = "Check the backend logs for details."
        try:
            body = error.response.json()
            if isinstance(body, dict) and isinstance(body.get("detail"), str):
                detail = body["detail"]
        except ValueError:
            pass
        st.error(f"Could not load chats (HTTP {error.response.status_code}): {detail}")
        return False
    except requests.RequestException:
        st.error("Could not reach the backend. Check that the backend is running and accessible.")
        return False

    for record in response.json():
        chat_id = record["id"]
        st.session_state["history_chats"].append(
            {
                "id": chat_id,
                "messages": record["messages"],
                "pdf_name": record.get("pdf_name"),
                "pdf_path": record.get("pdf_path"),
                "pdf_uuid": record.get("pdf_uuid"),
            }
        )
        st.session_state["chat_names"][chat_id] = record["chat_name"]
    return True


if not st.session_state["chats_loaded"]:
    st.session_state["chats_loaded"] = load_chats_from_db()


def save_chat_to_db(chat_id, chat_name, messages, pdf_name=None, pdf_path=None, pdf_uuid=None):
    payload = {
        "chat_id": chat_id,
        "chat_name": chat_name,
        "messages": messages,
        "pdf_name": pdf_name,
        "pdf_path": pdf_path,
        "pdf_uuid": pdf_uuid,
    }
    try:
        response = requests.post(SAVE_CHAT_URL, json=payload, timeout=60)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        st.error(f"Failed to save chat: {e}")
        return False


def create_chat(chat_name):
    new_chat_id = str(uuid.uuid4())
    new_chat = {
        "id": new_chat_id,
        "messages": [],
        "pdf_name": None,
        "pdf_path": None,
        "pdf_uuid": None,
    }
    if not save_chat_to_db(new_chat_id, chat_name, [], None, None, None):
        return
    st.session_state["history_chats"].insert(0, new_chat)
    st.session_state["chat_names"][new_chat_id] = chat_name
    st.session_state["current_chat"] = new_chat_id


def create_chat_with_pdf(chat_name, uploaded_pdf):
    with st.spinner("Uploading and processing document, please wait..."):
        files = {"file": (uploaded_pdf.name, uploaded_pdf.getvalue(), "application/pdf")}
        try:
            response = requests.post(UPLOAD_PDF_URL, files=files, timeout=(10, 300))
            response.raise_for_status()
        except requests.RequestException as error:
            st.error(f"Failed to upload PDF: {error}")
            return

        pdf_path = response.json()["pdf_path"]
        pdf_uuid = response.json()["pdf_uuid"]

        new_chat_id = str(uuid.uuid4())
        new_chat = {
            "id": new_chat_id,
            "messages": [],
            "pdf_name": uploaded_pdf.name,
            "pdf_path": pdf_path,
            "pdf_uuid": pdf_uuid,
        }
        if not save_chat_to_db(new_chat_id, chat_name, [], uploaded_pdf.name, pdf_path, pdf_uuid):
            return
        st.session_state["history_chats"].insert(0, new_chat)
        st.session_state["chat_names"][new_chat_id] = chat_name
        st.session_state["current_chat"] = new_chat_id
        st.success("PDF uploaded and chat created.")


def delete_chat():
    current_id = st.session_state.get("current_chat")
    if current_id:
        try:
            response = requests.post(DELETE_CHAT_URL, json={"chat_id": current_id}, timeout=60)
            response.raise_for_status()
            st.session_state["history_chats"] = [
                c for c in st.session_state["history_chats"] if c["id"] != current_id
            ]
            st.session_state["chat_names"].pop(current_id, None)
            st.session_state["current_chat"] = (
                st.session_state["history_chats"][0]["id"]
                if st.session_state["history_chats"]
                else None
            )
        except requests.RequestException as e:
            st.error(f"Failed to delete chat: {e}")


def select_chat(chat_id):
    st.session_state["current_chat"] = chat_id


# UI Layout - Sidebar
with st.sidebar:
    st.markdown('''<div class="brand"><div class="brand-mark" aria-hidden="true">☁</div>
        <div><div class="brand-name">Cloud Chatbot</div>
        <div class="brand-note">Your space to explore.</div></div></div>
        <div class="section-label">NEW CONVERSATION</div>''', unsafe_allow_html=True)
    uploaded_pdf = st.file_uploader("Attach a PDF", type="pdf", key="pdf_uploader")
    chat_name = st.text_input("Chat name", key="new_chat_name", placeholder="Give your conversation a name")

    if st.button("＋  New chat", type="primary"):
        if chat_name.strip():
            create_chat(chat_name.strip())
        else:
            st.warning("Chat name cannot be empty.")

    if st.button("New chat with PDF"):
        if not uploaded_pdf:
            st.warning("Please upload a PDF file before creating the chat.")
        elif chat_name.strip():
            create_chat_with_pdf(chat_name.strip(), uploaded_pdf)
        else:
            st.warning("Chat name cannot be empty.")

    if st.session_state["history_chats"]:
        st.markdown('<div class="section-label">YOUR CONVERSATIONS</div>', unsafe_allow_html=True)
        chat_options = {
            chat["id"]: st.session_state["chat_names"][chat["id"]]
            for chat in st.session_state["history_chats"]
        }
        selected_chat = st.radio(
            "Saved chats",
            options=list(chat_options.keys()),
            format_func=lambda x: chat_options[x],
            key="chat_selector",
            on_change=lambda: select_chat(st.session_state.chat_selector),
        )
        st.session_state["current_chat"] = selected_chat
        st.button("Delete chat", on_click=delete_chat)

# UI Layout - Chat Window
st.markdown('''<div class="workspace-heading"><strong>Conversation</strong>
    <span>Cloud Chatbot / Your workspace</span></div>''', unsafe_allow_html=True)
if st.session_state["current_chat"]:
    current_chat_id = st.session_state["current_chat"]
    current_chat = next(
        c for c in st.session_state["history_chats"] if c["id"] == current_chat_id
    )
    chat_name = st.session_state["chat_names"][current_chat_id]
    st.subheader(chat_name)

    if current_chat.get("pdf_name"):
        st.caption(f"📄 Associated with: {current_chat['pdf_name']}")

    if not current_chat["messages"]:
        show_welcome(has_chat=True)

    for msg in current_chat["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a question or share an idea…"):
        current_chat["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            payload = {
                "messages": [
                    {"role": m["role"], "content": m["content"]}
                    for m in current_chat["messages"]
                ]
            }

            if current_chat.get("pdf_uuid"):
                payload["pdf_uuid"] = current_chat["pdf_uuid"]
                chat_target_url = RAG_CHAT_URL
            else:
                chat_target_url = CHAT_URL

            def get_stream_response():
                with requests.post(chat_target_url, json=payload, stream=True, timeout=(10, 180)) as r:
                    r.raise_for_status()
                    r.encoding = "utf-8"
                    yield from r.iter_content(chunk_size=1024, decode_unicode=True)

            try:
                response = st.write_stream(get_stream_response)
            except requests.RequestException as error:
                st.error(f"Backend request failed: {error}")
                current_chat["messages"].pop()
            else:
                current_chat["messages"].append(
                    {"role": "assistant", "content": response}
                )
                save_chat_to_db(
                    current_chat_id,
                    chat_name,
                    current_chat["messages"],
                    current_chat.get("pdf_name"),
                    current_chat.get("pdf_path"),
                    current_chat.get("pdf_uuid"),
                )
else:
    show_welcome()
