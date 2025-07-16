import fitz
from langchain.text_splitter import RecursiveCharacterTextSplitter
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict
import logging
import re  # needed for extract_number
import os
from dotenv import load_dotenv


# Load environment variables from .env file in the current directory
load_dotenv()

logger = logging.getLogger(__name__)  # Just get the logger

HOST = os.getenv("VECTORDB_URL", "localhost")
PORT = int(os.getenv("VECTORDB_PORT", 8000))

#Import this class in app.py
class PDFProcessor:
    """
    Handles PDF text extraction, splitting into chunks,
    and storing into ChromaDB with embeddings.
    """

    def __init__(self):
        # Load sentence-transformer embedding function
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

    def extract_text(self, pdf_bytes: bytes) -> str:
        """
        Extracts clean text from a PDF, excluding header and footer.

        Args:
            pdf_bytes (bytes): Raw PDF content

        Returns:
            str: Extracted full text
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        header_footer_height = 50
        text_pages = []

        for index, page in enumerate(doc):
            rect = page.rect
            clip = fitz.Rect(0, header_footer_height, rect.width, rect.height - header_footer_height * 2)
            page_text = page.get_text(clip=clip)
            text_pages.append(page_text)
            logger.info(f"    ✓ Page {index + 1} processed")

        combined_text = "\n\n".join(text_pages)
        logger.info(f"  ✅ Extracted {len(combined_text)} characters from PDF")
        return combined_text

    def split_text(self, text: str) -> List[str]:
        """
        Splits text into overlapping chunks for embeddings.

        Args:
            text (str): Full text to split

        Returns:
            List[str]: Text chunks
        """
        splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", " "],
            chunk_size=500,
            chunk_overlap=100
        )
        chunks = splitter.split_text(text)
        chunks = [chunk for chunk in chunks if chunk.strip()]  # Remove empty chunks
        logger.info(f"  ✂️  Split into {len(chunks)} chunks")
        return chunks

    def connect_chromadb(self):
        """
        Connect to local ChromaDB server.

        Returns:
            chromadb.HttpClient: ChromaDB client instance
        """
        logger.info("🔗 Connecting to ChromaDB...")
        try:
            client = chromadb.HttpClient(host=HOST, port=PORT)
            logger.info("✅ ChromaDB client connected successfully")
            return client
        except Exception as e:
            logger.error(f"❌ Failed to connect to ChromaDB: {e}")
            raise

    def store_chunks(self, client, chunks: List[str], source_name: str, collection_name: str = "documentation") -> Dict:
        """
        Store text chunks in ChromaDB under specified collection.

        Args:
            client: ChromaDB client
            chunks (List[str]): Text chunks
            source_name (str): Name of source file
            collection_name (str): Collection name in ChromaDB

        Returns:
            dict: Storage summary
        """
        logger.info(f"💾 Storing {len(chunks)} chunks to '{collection_name}' from '{source_name}'")

        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}
        )

        ids = [f"{source_name}_{i}" for i in range(len(chunks))]
        metadatas = [{"source": source_name} for _ in chunks]

        collection.add(
            ids=ids,
            documents=chunks,
            metadatas=metadatas
        )

        logger.info(f"✅ Stored {len(chunks)} chunks in collection '{collection_name}'")

        return {
            "source": source_name,
            "chunks_stored": len(chunks),
            "collection": collection_name
        }

    def sync_pdf(self, pdf_bytes: bytes, file_name: str, collection_name: str = "documentation") -> Dict:
        """
        Full pipeline: Extract → Split → Store
        Args:
            pdf_bytes (bytes): PDF file as bytes
            file_name (str): Name of the source file
            collection_name (str): ChromaDB collection name
    
        Returns:
            dict: Result summary
        """
        logger.info(f"🚀 Syncing PDF: {file_name}")
        text = self.extract_text(pdf_bytes)
        chunks = self.split_text(text)
        client = self.connect_chromadb()
        result = self.store_chunks(client, chunks, source_name=file_name, collection_name=collection_name)
        return result

