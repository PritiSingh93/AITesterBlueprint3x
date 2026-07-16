I want you to create a simple **RAG Explorer** application.

The source files will be available in the `data` folder. I will provide a simple PDF file, which is a Product Requirements Document for `vwo.com`.

Your task is to build a React-based UI that demonstrates how the ingestion and retrieval process works.

The application should do the following:

1. Read the PDF file from the `data/data` folder.
2. Split the PDF content into chunks.
3. Generate embeddings for those chunks using the **Nomic Embed** embedding model.
4. Store the embeddings automatically in a local **ChromaDB** instance.
5. Provide a query interface where I can ask questions related to the PDF.
6. For every query, retrieve and display the **top 4 relevant chunks** fetched from the document.
7. Use **Groq** as the LLM provider, with the **OpenGPT 120B** model, to generate the final answer based on the retrieved chunks.
8. The UI should clearly showcase the complete RAG flow: PDF ingestion, chunking, embedding, storage, retrieval, and answer generation.

The goal of this application is to demonstrate how a basic RAG pipeline works end-to-end using a local vector database and a React frontend.

*********************************************************************************************************************************************
Build a RAG Explorer application using React for the frontend and Node.js/Python for the backend.

Requirements:
1. Ingest documents from the /data/data folder:
   - Support both PDF files (e.g., PRD for vwo.com) and plain text files.
2. Split the ingested content into chunks (e.g., 500–1000 tokens).
3. Generate embeddings for each chunk using the Nomic Embed model.
4. Store embeddings automatically in a local ChromaDB instance.
5. Provide a query interface in React where the user can ask questions.
6. For each query:
   - Convert the query into embeddings.
   - Retrieve the top 4 most relevant chunks from ChromaDB.
   - Pass those chunks + the query to Groq’s OpenGPT 120B model.
   - Display both the retrieved chunks and the final answer in the UI.
7. UI should clearly showcase the complete RAG flow:
   - PDF/Text ingestion
   - Chunking
   - Embedding
   - Storage
   - Retrieval
   - Answer generation
8. Add an extra tab called "Embedding Explorer":
   - Show how embeddings work visually.
   - Display vectors (numbers) for sample text.
   - Provide similarity comparisons (e.g., “King” vs “Queen”).
   - Include a simple chart or visualization to make embeddings intuitive.
9. Design a clean, beautiful UI:
   - Left panel: Document ingestion (PDF/Text upload + chunk visualization).
   - Right panel: Query interface + retrieved chunks + final answer.
   - Top navigation: Tabs for "RAG Flow" and "Embedding Explorer".
   - Use modern React styling (TailwindCSS or Material UI) for clarity.
