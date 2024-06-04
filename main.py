import streamlit as st
from dotenv import load_dotenv
from pymongo import MongoClient
from langchain_text_splitters import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import TextLoader, CSVLoader
import os
import openai
import numpy as np
from bson.binary import Binary
import pickle


def main():
    # Load environment variables
    load_dotenv()

    # Set OpenAI API key
    openai.api_key = os.getenv("OPENAI_API_KEY")

    # Connect to MongoDB
    client = MongoClient(os.getenv("MONGODB_URI"))
    db = client["vector_db"]
    collection = db["embeddings"]

    st.header("Chatbot with Custom Data 💬")

    # Load and split documents
    # try:
    #     raw_documents = TextLoader('mini_habits.txt', encoding='UTF-8').load()
    # except Exception as e:
    #     st.error(f"Error loading file: {e}")
    #     return
    #
    # text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    documents = CSVLoader('Contact Information J.csv', encoding='UTF-8').load()

    # Create OpenAI embeddings
    embeddings = OpenAIEmbeddings()

    # Store documents and embeddings in MongoDB
    for doc in documents:
        # Check if the document content already exists in the database
        existing_doc = collection.find_one({"content": doc.page_content})
        if existing_doc:
            continue

        # Compute the embedding for the document
        embedding_vector = embeddings.embed_query(doc.page_content)
        doc_dict = {
            "content": doc.page_content,
            "embedding": Binary(pickle.dumps(embedding_vector, protocol=2))
        }
        collection.insert_one(doc_dict)

    # Initialize session state for conversation history
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    # Display previous messages
    for i, message in enumerate(st.session_state.messages):
        if message['role'] == 'user':
            st.text_area("You:", value=message['content'], height=5, max_chars=None, key=f"user_{i}")
        elif message['role'] == 'assistant':
            st.text_area("Bot:", value=message['content'], height=250, max_chars=None, key=f"bot_{i}")

    # User input
    query = st.text_input("You:")

    if query:
        # Define system instructions
        instructions = """
                You are a helpful assistant. Use the provided context to answer the user's questions accurately.
                Provide concise and clear responses. If the context does not contain the answer, let the user know.
                If there is any word like 'moye' is founded show this 'm***' instead. If timespan is provided like this 
                'June 4, 2024, at 11:08:27 AM GMT+5' only show this 'June 4, 2024, at 11:08:27 AM' remove last 'GMT' 
                part.
                """

        # Add user message and system instructions to session state
        st.session_state.messages.append({'role': 'user', 'content': query})
        st.session_state.messages.append({"role": "system", "content": instructions})

        # Embed the user query
        query_embedding = embeddings.embed_query(query)

        # Retrieve stored embeddings from MongoDB
        stored_docs = list(collection.find())

        # Calculate similarity with stored embeddings
        def cosine_similarity(vec1, vec2):
            return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

        similarities = [
            (doc, cosine_similarity(query_embedding, pickle.loads(doc["embedding"])))
            for doc in stored_docs
        ]

        similarities.sort(key=lambda x: x[1], reverse=True)

        # Combine content from the top N documents for context
        related_content = "\n\n".join([doc[0]["content"] for doc in similarities])

        # Combine related content with the user query for context
        combined_input = f"User: {query}\n\nContext from data: {related_content}"

        # Call OpenAI API to get response
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": combined_input}
            ]
        )
        # Add bot response to session state
        bot_response = response.choices[0].message.content
        st.session_state.messages.append({'role': 'assistant', 'content': bot_response})

        # Display bot response
        st.text_area("Bot:", value=bot_response, height=250, max_chars=None,
                     key=f"response_{len(st.session_state.messages)}")


if __name__ == "__main__":
    main()
