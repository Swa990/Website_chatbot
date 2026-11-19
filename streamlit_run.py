
import streamlit as st
import db

from pipeline.embed import load_store
from pipeline.Rag import answer_question
from llm import get_llm

st.set_page_config(page_title="Emirates NBD Assistant", page_icon="🏦")
st.title("🏦 Emirates NBD Website Assistant")
st.caption("Ask questions about Emirates NBD products and services.")

db.init()

@st.cache_resource
def initialize():
    return load_store(), get_llm()

try:
    store, llm = initialize()
except Exception as e:
    st.error(f"Initialization failed: {e}")
    st.stop()

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = db.create_conversation()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Sources"):
                for source in message["sources"]:
                    st.markdown(f"- [{source['title'] or source['url']}]({source['url']})")

question = st.chat_input("Ask about Emirates NBD...")

if question:
    cid = st.session_state.conversation_id

    st.session_state.messages.append({
        "role": "user",
        "content": question
    })
    db.add_message(cid, "user", question)

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching website and generating answer..."):
            try:
                history = db.get_history(cid, limit=10)
                history = history[:-1]

                result = answer_question(
                    message=question,
                    history=history,
                    store=store,
                    llm=llm
                )

                answer = result["answer"]
                sources = result["sources"]

                st.markdown(answer)

                if sources:
                    with st.expander("Sources"):
                        for source in sources:
                            title = source["title"] or source["url"]
                            page = f" (Page {source['page']})" if source.get("page") else ""
                            st.markdown(f"- [{title}{page}]({source['url']})")

                db.add_message(cid, "assistant", answer, sources=sources, status=result["status"])

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources
                })

            except Exception as e:
                st.error(f"Something went wrong: {e}")
