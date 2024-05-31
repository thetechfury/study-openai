from langchain_core.prompts import PromptTemplate
import streamlit as st
from dotenv import load_dotenv
from streamlit_extras.add_vertical_space import add_vertical_space
from langchain_text_splitters import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAI
from langchain_community.document_loaders import TextLoader
 

 
def main():
    st.header("Chat 💬")
    load_dotenv()
    raw_documents = TextLoader('./SHORT.txt').load()
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    documents = text_splitter.split_documents(raw_documents)
    db = FAISS.from_documents(documents, OpenAIEmbeddings())
    
    query = st.text_input("Ask questions about your file:")
    st.write(query)

    if query:
        embedding_vector = OpenAIEmbeddings().embed_query(query)
        docs = db.similarity_search_by_vector(embedding_vector)
        # st.write(docs[0].page_content)
        template = """Question: {query}

                    Answer: Let's think step by step."""

        prompt = PromptTemplate.from_template(template)
        llm = OpenAI()
        llm_chain = prompt | llm
        llm_chain.invoke(docs)
 
if __name__ == '__main__':
    main()