#Contains Functions to Clean Chroma DB, List Collections Etc.

import logging
import chromadb
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)



# Load environment variables from .env file in the current directory
load_dotenv()

HOST = os.getenv("VECTORDB_URL", "localhost")
PORT = int(os.getenv("VECTORDB_PORT", 8000))

# HOST = "localhost"

# PORT = 8080

def connect_chromadb():
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

def clean_chromadb(client, db_name=None):
    """
    Delete all or a specific collection from ChromaDB.
    
    Args:
        client: ChromaDB client instance
        db_name: Optional name of the collection to delete
    """
    try:
        collections = client.list_collections()

        if db_name:
            matched = [c for c in collections if c.name == db_name]
            if not matched:
                return {"message": f"Collection '{db_name}' not found."}

            client.delete_collection(db_name)
            logger.info(f"✅ Deleted collection '{db_name}'")
            return {"message": f"Deleted collection '{db_name}'"}

        else:
            for c in collections:
                client.delete_collection(c.name)
                logger.info(f"✅ Deleted collection '{c.name}'")

            return {"message": f"Deleted all collections ({len(collections)} total)"}

    except Exception as e:
        logger.error(f"❌ Failed to clean ChromaDB: {e}")
        raise e


def list_chromadb_collections(client):
    """
    Return list of all collection names.
    """
    try:
        collections = client.list_collections()
        return [c.name for c in collections]
    except Exception as e:
        logger.error(f"❌ Failed to list collections: {e}")
        raise e
