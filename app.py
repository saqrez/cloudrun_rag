import streamlit as st
from google.cloud import storage
from langchain.vectorstores.chroma import Chroma
from langchain_google_vertexai import VertexAI,VertexAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI
import os

# GCS bucket details
BUCKET_NAME = "rag_cloudrun"
GCS_PERSIST_PATH = "chroma_multi/"
LOCAL_PERSIST_PATH = "./local_chromadb_multi/"

# Initialize GCS client
storage_client = storage.Client()

def download_directory_from_gcs(gcs_directory, local_directory, bucket_name):
    """Download all files from a GCS directory to a local directory."""
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=gcs_directory)

    for blob in blobs:
        if not blob.name.endswith("/"):  # Avoid directory blobs
            relative_path = os.path.relpath(blob.name, gcs_directory)
            local_file_path = os.path.join(local_directory, relative_path)
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            blob.download_to_filename(local_file_path)
            print(f"Downloaded {blob.name} to {local_file_path}")

# Download Chroma persisted data from GCS to local directory
download_directory_from_gcs(GCS_PERSIST_PATH, LOCAL_PERSIST_PATH, BUCKET_NAME)

# Step to use the data locally in retrieval
EMBEDDING_MODEL = "text-embedding-005"
EMBEDDING_NUM_BATCH = 5

# Load embeddings and persisted data
embeddings = VertexAIEmbeddings(
    model_name=EMBEDDING_MODEL
)

# Load Chroma data from local persisted directory
db = Chroma(persist_directory=LOCAL_PERSIST_PATH, embedding_function=embeddings)

# Now use db for retrieval
retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 3})

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True, output_key='answer')

template = """
    You are a helpful AI assistant.You are a Science teacher in a secondary school. You're tasked to answer the question given below, but only based on the context provided.
    context:

    {context}


    question:

    {input}


    If you cannot find an answer ask the user to rephrase the question.
    answer:
"""
prompt = PromptTemplate.from_template(template)

# OpenAI model configuration
api_key = "YOUR_API_KEY"
llm_openai = ChatOpenAI(model="gpt-4", api_key=api_key, temperature=0)

llm_gemini = VertexAI(
    model="gemini-1.5-pro",
    max_output_tokens=2048,
    temperature=0.1,
    top_p=0.7,
    top_k=15,
    verbose=True,
)

conversational_retrieval = ConversationalRetrievalChain.from_llm(
    llm=llm_gemini, retriever=retriever, memory=memory, verbose=False
)

# Streamlit app
st.set_page_config(page_title="Conversational AI Chatbot", layout="centered")

st.title("Science Teacher")

import streamlit.components.v1 as components

components.html(
    """
<link rel="stylesheet" href="https://www.gstatic.com/dialogflow-console/fast/df-messenger/prod/v1/themes/df-messenger-default.css">
<script src="https://www.gstatic.com/dialogflow-console/fast/df-messenger/prod/v1/df-messenger.js"></script>
<df-messenger
  location="us-central1"
  project-id="agentic-sr"
  agent-id="30d86bc9-ea4b-4035-9271-30637ab051bc"
  language-code="en"
  max-query-length="-1">
  <df-messenger-chat
    chat-title="SMART-OBJ-CF">
  </df-messenger-chat>
</df-messenger>
<style>
  df-messenger {
    z-index: 999;
    position: fixed;
    --df-messenger-font-color: #000;
    --df-messenger-font-family: Google Sans;
    --df-messenger-chat-background: #f3f6fc;
    --df-messenger-message-user-background: #d3e3fd;
    --df-messenger-message-bot-background: #fff;
    bottom: 0;
    right: 0;
    top: 0;
    width: 350px;
  }
</style>
    """,
  #  height=450,  # Adjust height as needed
)



# Initialize session state to store chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input box for user's query
user_input = st.chat_input("Your message")

if user_input:
    # Display user's message
    with st.chat_message("user"):
        st.markdown(user_input)

    # Store user's query in the chat history
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Get the AI assistant's response
    response = conversational_retrieval({"question": user_input})["answer"]

    # Store AI's response in the chat history
    st.session_state.messages.append({"role": "assistant", "content": response})

    # Display assistant's message
    with st.chat_message("assistant"):
        st.markdown(response)

# Option to clear chat history
if st.button("Clear Chat"):
    st.session_state.messages = []
    memory.clear()
    st.experimental_rerun()
