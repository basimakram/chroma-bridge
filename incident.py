import chromadb
from chromadb.utils import embedding_functions
import requests
from datetime import datetime
import os
import json
import logging
import re  # needed for extract_number
from dotenv import load_dotenv

logger = logging.getLogger(__name__)  # Just get the logger

load_dotenv()

HOST = os.getenv("VECTORDB_URL", "localhost")
PORT = int(os.getenv("VECTORDB_PORT", 8000))
SNOW_USER = os.getnenv("SERVICENOW_USER")
SNOW_URL = os.getnenv("SERVICENOW_URL")
SNOW_PASSWORD = os.getnenv("SERVICENOW_PASSWORD")

#Import this class in app.py
class ChromaDbTicketProcessor:
    """
    A class to process and store ticket data into ChromaDB from ServiceNow API.
    """

    def __init__(self):
        logger.info("Initializing ChromaDB Ticket Processor")
        self.sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        

    def load_last_update_time(self, collection):
        metadata = collection.metadata or {}
        last_time = metadata.get("last_update_time")
        if last_time:
            logger.info(f"📦 Found last update time in metadata: {last_time}")
        else:
            logger.info("📦 No last update time found in metadata, using default.")
        return last_time
        

    def save_last_update_time(self, collection, latest_time: str):
        """
        Store only `last_update_time` in the user‐metadata of the collection.
        """
        try:
            collection.modify(metadata={"last_update_time": latest_time})
            logger.info(f"🕒 Saved last_update_time={latest_time} to collection metadata")
        except Exception as e:
            logger.error(f"❌ Failed to update metadata: {e}")
            raise
        
    def fetch_db_client(self):
        logger.info("🔗 Connecting to ChromaDB...")
        try:
            client = chromadb.HttpClient(host=HOST, port=PORT)
            logger.info("✅ ChromaDB client connected successfully")
            return client
        except Exception as e:
            logger.error(f"❌ Failed to connect to ChromaDB: {e}")
            raise

    def to_iso8601(self, dt_str: str) -> str:
        dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    def extract_number(self, ticket_number):
        match = re.search(r'\d+', ticket_number)
        return int(match.group()) if match else -1

    def fetch_tickets_from_servicenow(self, after_datetime):
        user = SNOW_USER
        pwd = SNOW_PASSWORD

        date_part, time_part = after_datetime.split(' ')
        url = f'{SNOW_URL}/api/now/table/incident'
        query_params = {
            'sysparm_query': f"state=6^close_notesISNOTEMPTY^sys_created_on>javascript:gs.dateGenerate('{date_part}','{time_part}')^ORDERBYDESCnumber",
            'sysparm_fields': 'number,short_description,description,close_notes,sys_created_on,opened_at',
            'sysparm_limit': 1000,
            'sysparm_display_value': 'true',
            'sysparm_exclude_reference_link': 'true',
        }

        response = requests.get(url, params=query_params, auth=(user, pwd))

        if response.status_code == 200:
            tickets = response.json().get('result', [])
            if not tickets:
                logger.info("No new tickets found.")
                return [], None
                
            mapped_tickets = []
            # latest_ticket = max(tickets, key=lambda x: x.get('number', ''))

            latest_ticket = max(tickets, key=lambda x: self.extract_number(x.get('number', '')))
            for ticket in tickets:
                mapped_ticket = {
                    'ticket_number': ticket.get('number'),
                    'title': ticket.get('short_description'),
                    'query': ticket.get('description'),
                    'answer': ticket.get('close_notes'),
                    'url': f'{SNOW_URL}/incident_list.do?',
                    'created': datetime.strptime(ticket.get('sys_created_on'), '%Y-%m-%d %H:%M:%S').timestamp(),
                    'opened_at': self.to_iso8601(ticket.get('sys_created_on'))
                }
                mapped_tickets.append(mapped_ticket)
            logger.info(f"✅ Retrieved {len(mapped_tickets)} tickets from ServiceNow")

            return mapped_tickets, latest_ticket
        else:
            logger.error(f"❌ Failed to retrieve tickets. Status code: {response.status_code}")
            logger.info(response.text)
            return [], None

    def prepare_ticket_batches(self, ticket_data):
        """
        Prepares documents and metadata from ticket list.
        """
        documents = [
            f"Ticket query/question: {t['query']} \n - Ticket answer/solution: {t['answer']}"
            for t in ticket_data
        ]
        metadatas = [
            {
                "ticket_number": t["ticket_number"],
                "ticket_title": t["title"],
                "url": t["url"],
                "created": t["created"],
                "opened_at": t["opened_at"]
            }
            for t in ticket_data
        ]
        return documents, metadatas

    def store_ticket_data(self, coll, documents, metadatas):
        logger.info("💾 Storing tickets in ChromaDB...")

        ids = [str(i) for i in range(len(documents))]
        coll.add(ids=ids, documents=documents, metadatas=metadatas)
        logger.info(f"🎉 Stored {len(documents)} tickets in ChromaDB")

    def sync_tickets(self):
        """
        Main function to sync tickets from ServiceNow to ChromaDB.
        Returns a dictionary with sync results.
        """
        try:
            logger.info("🚀 Starting Ticket Data Sync from ServiceNow to ChromaDB")
            
            # Connect to ChromaDB
            client = self.fetch_db_client()

            # First check if collection already exists
            coll_names = [c.name for c in client.list_collections()]
            collection_name = "ticketData"

            if collection_name in coll_names:
                logger.info("📂 Collection already exists, fetching it without modifying metadata")
                coll = client.get_collection(name=collection_name)
            else:
                logger.info("📂 Collection does not exist, creating with metadata")
                coll = client.create_collection(
                    name=collection_name,
                    embedding_function=self.sentence_transformer_ef,
                    metadata={"hnsw:space": "cosine", "sync_threshold": 1000, "batch_size": 100}
                )
            
            # Load last update time
            cutoff_time = self.load_last_update_time(coll)
            if not cutoff_time:
                ############IMPORTANT############
                cutoff_time = "2000-01-01 00:00:00"
                logger.info(f"No previous update time found, using default: {cutoff_time}")
            else:
                logger.info(f"Using last update time: {cutoff_time}")
            
            # Fetch tickets from ServiceNow
            tickets, latest = self.fetch_tickets_from_servicenow(cutoff_time)
            
            if tickets:
                # Prepare and store ticket data
                docs, metas = self.prepare_ticket_batches(tickets)
                self.store_ticket_data(coll, docs, metas)
                
                # Save the latest update time
                latest_time = latest.get('sys_created_on')
                if latest_time:
                    self.save_last_update_time(coll, latest_time)
                    logger.info(f"Updated last sync time to: {latest_time}")
                
                return {
                    "success": True,
                    "message": "Tickets synced successfully",
                    "tickets_processed": len(tickets),
                    "latest_update_time": latest_time,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                logger.info("⚠️ No tickets fetched, nothing to store.")
                return {
                    "success": True,
                    "message": "No new tickets to process",
                    "tickets_processed": 0,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Error during ticket sync: {e}")
            return {
                "success": False,
                "message": f"Error during ticket sync: {str(e)}",
                "tickets_processed": 0,
                "timestamp": datetime.now().isoformat()
            }


# if __name__ == "__main__":
#     processor = ChromaDbTicketProcessor()
#     processor.sync_tickets()

