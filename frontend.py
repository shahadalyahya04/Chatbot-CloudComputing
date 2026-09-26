import uuid
import requests
import streamlit as st
import os
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
    except requests.RequestException as error:
        st.error(f"Could not reach the backend: {error}")
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
    st.title("Chat Management")
    uploaded_pdf = st.file_uploader("Upload PDF", type="pdf", key="pdf_uploader")
    chat_name = st.text_input("Enter Chat Name:", key="new_chat_name")

    if st.button("Create New Chat"):
        if chat_name.strip():
            create_chat(chat_name.strip())
        else:
            st.warning("Chat name cannot be empty.")

    if st.button("Create New Chat with PDF"):
        if not uploaded_pdf:
            st.warning("Please upload a PDF file before creating the chat.")
        elif chat_name.strip():
            create_chat_with_pdf(chat_name.strip(), uploaded_pdf)
        else:
            st.warning("Chat name cannot be empty.")

    if st.session_state["history_chats"]:
        chat_options = {
            chat["id"]: st.session_state["chat_names"][chat["id"]]
            for chat in st.session_state["history_chats"]
        }
        selected_chat = st.radio(
            "Select Chat",
            options=list(chat_options.keys()),
            format_func=lambda x: chat_options[x],
            key="chat_selector",
            on_change=lambda: select_chat(st.session_state.chat_selector),
        )
        st.session_state["current_chat"] = selected_chat
        st.button("Delete Chat", on_click=delete_chat)

# UI Layout - Chat Window
if st.session_state["current_chat"]:
    current_chat_id = st.session_state["current_chat"]
    current_chat = next(
        c for c in st.session_state["history_chats"] if c["id"] == current_chat_id
    )
    chat_name = st.session_state["chat_names"][current_chat_id]

    if current_chat.get("pdf_name"):
        st.caption(f"📄 Associated with: {current_chat['pdf_name']}")

    for msg in current_chat["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Your Message:"):
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
    st.info("Please create or select a chat from the sidebar to start.")
