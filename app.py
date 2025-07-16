from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Body
from fastapi.responses import JSONResponse
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from incident import ChromaDbTicketProcessor
import json
import os
from document import PDFProcessor
import re
import logging
from extra import connect_chromadb, clean_chromadb, list_chromadb_collections


from logging_config import setup_logging
setup_logging()  # Log file name is optional
logger = logging.getLogger(__name__) 
logger.info("🚀 L F G !!! STARTING ...")

app = FastAPI(
    title="ServiceNow Tickets & PDF Documents Sync API",
    description="API to sync ServiceNow tickets and store user uploaded pdfs to ChromaDB ",
    version="1.0.0"
)
#****************************************************************************************#
#########Creating a new object both classes that will be used in endpoints below##########
#****************************************************************************************#
pdf_processor = PDFProcessor()
processor = ChromaDbTicketProcessor()

LOG_DIR = "logs"
LOG_FILENAME_PREFIX = "app-"
LOG_FILENAME_SUFFIX = ".log"
LOG_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S,%f"  # match your logging format

level_regex = re.compile(r' - (DEBUG|INFO|WARNING|ERROR|CRITICAL) - ')
timestamp_regex = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})')


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "ServiceNow Tickets & PDF Documents Sync API",
        "version": "1.0.0",
        "endpoints": {
            "sync_tickets": "/sync-tickets",
            "health": "/health",
            "last_update_time": "/last-update-time",
            "sync_pdf": "/sync-pdf"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}



@app.post("/sync-pdf")
async def sync_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    try:
        pdf_bytes = await file.read()
        file_name = os.path.basename(file.filename)
        result = pdf_processor.sync_pdf(pdf_bytes, file_name)
        return JSONResponse(content={"message": "Processed successfully", "details": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/sync-tickets")
async def sync_tickets():
    """
    Endpoint to sync tickets from ServiceNow to ChromaDB.
    Uses the ChromaDbTicketProcessor.sync_tickets() method.
    """
    try:
        logger.info("API: Starting ticket sync process")
        
        # Initialize processor and run sync
        
        result = processor.sync_tickets()
        
        # Return result based on success status
        if result["success"]:
            logger.info(f"API: Sync completed successfully - {result['tickets_processed']} tickets processed")
            return JSONResponse(
                status_code=200,
                content=result
            )
        else:
            logger.error(f"API: Sync failed - {result['message']}")
            raise HTTPException(
                status_code=500,
                detail=result["message"]
            )
            
    except Exception as e:
        logger.error(f"API: Unexpected error during ticket sync: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during ticket sync: {str(e)}"
        )


@app.post("/sync-multiple-pdfs")
async def sync_multiple(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    results = []
    client = pdf_processor.connect_chromadb()  # connect once

    for file in files:
        if not file.filename.endswith(".pdf"):
            results.append({"filename": file.filename, "status": "skipped", "error": "Not a PDF"})
            continue

        try:
            pdf_bytes = await file.read()
            text = pdf_processor.extract_text(pdf_bytes)
            chunks = pdf_processor.split_text(text)
            stored = pdf_processor.store_chunks(client, chunks, source_name=file.filename)

            results.append({
                "filename": file.filename,
                "status": "success",
                "chunks_stored": stored["chunks_stored"]
            })

        except Exception as e:
            results.append({"filename": file.filename, "status": "failed", "error": str(e)})

    return {"results": results}



from fastapi import Body



@app.get("/last-update-ticket-time")
async def get_last_update_time():
    """
    Get the last update time from ChromaDB collection metadata.
    """
    try:
        client = processor.fetch_db_client()
        collection = client.get_or_create_collection(
            name="ticketData",
            embedding_function=processor.sentence_transformer_ef
        )
        last_update = processor.load_last_update_time(collection)

        return {
            "last_update_time": last_update,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Failed to load last update time: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/update-last-ticket-time")
async def update_last_update_time(
    payload: dict = Body(..., example={"last_update_time": "2025-07-03 15:16:53"})
):
    """
    Update the last ticket sync time in the ChromaDB collection metadata.
    """
    try:
        new_time = payload.get("last_update_time")
        # Validate datetime format
        datetime.strptime(new_time, "%Y-%m-%d %H:%M:%S")

        client = processor.fetch_db_client()
        collection = client.get_or_create_collection(
            name="ticketData",
            embedding_function=processor.sentence_transformer_ef
        )
        processor.save_last_update_time(collection, new_time)

        return {
            "message": "Last update time updated successfully",
            "last_update_time": new_time,
            "timestamp": datetime.now().isoformat()
        }

    except ValueError:
        logger.error("❌ Invalid datetime format. Expected: YYYY-MM-DD HH:MM:SS")
        raise HTTPException(
            status_code=400,
            detail="Invalid datetime format. Expected: YYYY-MM-DD HH:MM:SS"
        )
    except Exception as e:
        logger.error(f"❌ Failed to update last update time: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/logs-between")
async def get_logs_between(
    start_time: str = Query(..., description="Start ISO timestamp, e.g. 2025-07-04T10:00:00Z"),
    end_time: str = Query(..., description="End ISO timestamp, e.g. 2025-07-05T18:00:00Z"),
    levels: Optional[List[str]] = Query(
        None,
        description="Optional list of log levels to filter by, e.g. levels=ERROR&levels=INFO"
    )
):
    # Parse ISO timestamps, remove trailing 'Z' if present
    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00")).replace(tzinfo=None)
    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00")).replace(tzinfo=None)

    if start_dt > end_dt:
        return {"error": "start_time must be before end_time"}

    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    # Normalize and validate levels if provided
    if levels:
        levels = [lvl.upper() for lvl in levels]
        invalid = [lvl for lvl in levels if lvl not in valid_levels]
        if invalid:
            return {"error": f"Invalid log levels: {invalid}. Choose from {valid_levels}"}

    # Determine all dates between start and end for log file scanning
    delta_days = (end_dt.date() - start_dt.date()).days
    dates_to_check = [start_dt.date() + timedelta(days=i) for i in range(delta_days + 1)]

    matched_lines = []

    for date in dates_to_check:
        log_file = os.path.join(LOG_DIR, f"{LOG_FILENAME_PREFIX}{date}{LOG_FILENAME_SUFFIX}")
        if not os.path.isfile(log_file):
            continue

        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                # Extract timestamp from start of line
                m = timestamp_regex.match(line)
                if not m:
                    continue
                try:
                    log_time = datetime.strptime(m.group(1), LOG_TIMESTAMP_FORMAT)
                except ValueError:
                    continue

                if not (start_dt <= log_time <= end_dt):
                    continue

                # If levels filter provided, filter by log level
                if levels:
                    level_match = level_regex.search(line)
                    if not level_match:
                        continue
                    line_level = level_match.group(1)
                    if line_level not in levels:
                        continue

                matched_lines.append(line.rstrip())

    return {"logs": matched_lines}

@app.post("/clean-db")
async def clean_db(db_name: Optional[str] = Query(None, description="Optional specific collection name to delete")):
    """
    Clean ChromaDB - delete all or one collection.
    """
    try:
        client = connect_chromadb()
        result = clean_chromadb(client, db_name)
        return result
    except Exception as e:
        logger.error(f"API: Failed to clean DB - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/list-collections")
async def list_collections():
    """
    List all collections in ChromaDB.
    """
    try:
        client = connect_chromadb()
        collections = list_chromadb_collections(client)
        return {"collections": collections}
    except Exception as e:
        logger.error(f"API: Failed to list collections - {e}")
        raise HTTPException(status_code=500, detail=str(e))

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("app:app", host="0.0.0.0", port=8080)