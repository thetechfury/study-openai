import streamlit as st
from dotenv import load_dotenv
from langchain_text_splitters import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
import os
import openai


def main():
    # Load environment variables
    load_dotenv()

    # Set OpenAI API key
    openai.api_key = os.getenv("OPENAI_API_KEY")

    st.header("Chatbot with Custom Data 💬")

    # Load and split documents
    raw_documents = TextLoader('./short-stories.txt', encoding='UTF-8').load()
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    documents = text_splitter.split_documents(raw_documents)

    # Create FAISS index
    db = FAISS.from_documents(documents, OpenAIEmbeddings())

    # Initialize session state for conversation history
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    # Display previous messages
    for i, message in enumerate(st.session_state.messages):
        if message['role'] == 'user':
            st.text_area("You:", value=message['content'], height=50, max_chars=None, key=f"user_{i}")
        else:
            st.text_area("Bot:", value=message['content'], height=50, max_chars=None, key=f"bot_{i}")

    # User input
    query = st.text_input("You:")
    if query:
        # Add user message to session state
        st.session_state.messages.append({'role': 'user', 'content': query})

        # Embed the user query
        embedding_vector = OpenAIEmbeddings().embed_query(query)

        # Perform similarity search on the FAISS index
        docs = db.similarity_search_by_vector(embedding_vector)

        # Extract content from the most relevant document
        if docs:
            related_content = docs[0].page_content
        else:
            related_content = "No relevant documents found."

        # Combine related content with the user query for context
        combined_input = f"User: {query}\n\nContext from data: {related_content}"

        # Call OpenAI API to get response
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": combined_input}
            ]
        )
        # Add bot response to session state
        bot_response = response.choices[0].message.content
        st.session_state.messages.append({'role': 'assistant', 'content': bot_response})

        # Display bot response
        st.text_area("Bot:", value=bot_response, height=50, max_chars=None,
                     key=f"response_{len(st.session_state.messages)}")


if __name__ == "__main__":
    main()
