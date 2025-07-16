# Chroma Data Sync API

A FastAPI-based service that synchronizes ServiceNow incident tickets to ChromaDB and processes user-uploaded PDF documents for vector search and retrieval. This API enables efficient storage and querying of support tickets and documentation using semantic embeddings.

## Features

- **Ticket Synchronization**: Automatically fetch and sync ServiceNow incident tickets to ChromaDB
- **PDF Processing**: Accept user-uploaded PDF documents, extract text, and store as searchable chunks in chromadb
- **Vector Search**: Use ChromaDB with embeddings for semantic search capabilities
- **Incremental Updates**: Track last update time to fetch only new tickets
- **Batch Processing**: Handle multiple PDF uploads simultaneously from users
- **Log Management**: Comprehensive logging with time-based filtering
- **Database Management**: Clean and manage ChromaDB collections


## Prerequisites

- Python 3.10+
- ChromaDB server running
- ServiceNow instance access
- Docker (for containerized deployment)

## Installation

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd CHROMA_APIS
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Optional: Install python-dotenv for local development**
   ```bash
   # For local development only (not recommended for production)
   pip install python-dotenv
   ```

5. **Set up environment variables**
   
   **Option A: Using .env file (Local Development Only)**
   ```bash
   # Create .env file in project root
   touch .env
   ```
   
   Add the following to your `.env` file:
   ```env
   # ChromaDB Configuration
   VECTORDB_URL=localhost
   VECTORDB_PORT=8000
   
   # ServiceNow Configuration
   SERVICENOW_USER=your-service-account
   SERVICENOW_PASSWORD=your-password
   SERVICENOW_URL=https://your-instance.service-now.com/api/now/table/incident
   ```
   
   **Option B: Using environment variables directly**
   ```bash
   export VECTORDB_URL=localhost
   export VECTORDB_PORT=8000
   export SERVICENOW_USER=your-service-account
   export SERVICENOW_PASSWORD=your-password
   export SERVICENOW_URL=https://your-instance.service-now.com/api/now/table/incident
   ```

6. **Start ChromaDB server**
   ```bash
   # Using Docker
   docker run -p 8000:8000 chromadb/chroma
   
   # Or using Python
   pip install chromadb
   chroma run --host localhost --port 8000
   ```

## Running the Application

### Local Development

```bash
# Start the FastAPI server
python app.py uncomment the last lines

# Or using uvicorn directly
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

The API will be available at `http://localhost:8080`

### Docker Deployment

1. **Build the Docker image**
   ```bash
   docker build -t servicenow-sync-api .
   ```

2. **Run with Docker Compose**(Not Tested)
   ```bash
   docker-compose build
   docker-compose up -d
   ```

### Production Deployment

```bash
# Using Docker with production settings
docker run -d \
  --name servicenow-sync-api \
  -p 8080:8080 \
  -e VECTORDB_URL=your-chromadb-host \
  -e VECTORDB_PORT=8000 \
  -e SERVICENOW_USER=your-service-account \
  -e SERVICENOW_PASSWORD=your-password \
  -e SERVICENOW_URL=https://your-instance.service-now.com/api/now/table/incident \
  servicenow-sync-api
```

## API Endpoints

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information and health check |
| GET | `/health` | Health check endpoint |
| POST | `/sync-tickets` | Sync tickets from ServiceNow |
| GET | `/last-update-ticket-time` | Get last ticket sync time |
| POST | `/update-last-ticket-time` | Update last sync time |

### PDF Processing

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sync-pdf` | Upload and process single PDF file |
| POST | `/sync-multiple-pdfs` | Upload and process multiple PDF files |

**Note**: PDF files are uploaded by users through these endpoints, not automatically fetched from ServiceNow.

### Database Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/list-collections` | List all ChromaDB collections |
| POST | `/clean-db` | Clean ChromaDB collections |

### Logging

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/logs-between` | Get logs between time ranges |

## Usage Examples

### Sync Tickets from ServiceNow

```bash
curl -X POST "http://localhost:8080/sync-tickets"
```

### Upload PDF Document

```bash
# Upload single PDF file
curl -X POST "http://localhost:8080/sync-pdf" \
  -F "file=@document.pdf"

# Upload multiple PDF files
curl -X POST "http://localhost:8080/sync-multiple-pdfs" \
  -F "files=@document1.pdf" \
  -F "files=@document2.pdf" \
  -F "files=@document3.pdf"
```

### Update Last Sync Time

```bash
curl -X POST "http://localhost:8080/update-last-ticket-time" \
  -H "Content-Type: application/json" \
  -d '{"last_update_time": "2025-07-03 15:16:53"}'
```

### Get Logs Between Times

```bash
curl "http://localhost:8080/logs-between?start_time=2025-07-04T10:00:00Z&end_time=2025-07-05T18:00:00Z&levels=ERROR&levels=INFO"
```

## Configuration

### Environment Variables

**ChromaDB Configuration:**
- `VECTORDB_URL`: ChromaDB server hostname (default: localhost)
- `VECTORDB_PORT`: ChromaDB server port (default: 8000)

**ServiceNow Configuration:**
- `SERVICENOW_USER`: ServiceNow service account username
- `SERVICENOW_PASSWORD`: ServiceNow service account password
- `SERVICENOW_URL`: ServiceNow API endpoint URL

### Code Changes Required

To support the optional `.env` file functionality, you'll need to update the following files:

**1. extra.py**
```python
import os
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if python-dotenv is installed
except ImportError:
    pass  # python-dotenv not installed, use system environment variables

HOST = os.getenv("VECTORDB_URL", "localhost")
PORT = int(os.getenv("VECTORDB_PORT", 8000))
```

**2. incident.py**
```python
import os
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if python-dotenv is installed
except ImportError:
    pass  # python-dotenv not installed, use system environment variables

user = os.getenv("SERVICENOW_USER", "your-service-account")
pwd = os.getenv("SERVICENOW_PASSWORD", "your-password")
url = os.getenv("SERVICENOW_URL", "https://your-instance.service-now.com/api/now/table/incident")
```

**3. Any other files using environment variables**
Apply the same pattern:
```python
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Then use os.getenv() for environment variables
VARIABLE_NAME = os.getenv("ENV_VAR_NAME", "default_value")
```

### ChromaDB Collections

- `ticketData`: Stores ServiceNow incident tickets with embeddings
- `documentation`: Stores user-uploaded PDF document chunks with embeddings

## Data Flow

1. **ServiceNow Tickets**: Automatically synced from ServiceNow API based on last update time
2. **PDF Documents**: Users upload PDF files via API endpoints, which are processed and stored
3. **Vector Storage**: Both tickets and PDF content are embedded and stored in ChromaDB for semantic search

## File Structure

```
CHROMA_APIS/
├── app.py                 # Main FastAPI application
├── incident.py            # ServiceNow ticket processing
├── document.py            # PDF processing utilities
├── extra.py               # ChromaDB utility functions
├── logging_config.py      # Logging configuration
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (local dev only)
├── .env.example          # Example environment file
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Multi-service setup
├── logs/                 # Application logs
│   └── app-YYYY-MM-DD.log
└── README.md             # This file
```

## Environment Configuration Best Practices

### Local Development
- Use `.env` file for convenience
- Add `.env` to `.gitignore` to prevent committing sensitive data
- Use `.env.example` as a template for other developers

### Production Deployment
- **Never use `.env` files in production**
- Set environment variables directly in your deployment environment
- Use container orchestration tools (Docker Swarm, Kubernetes) for secret management
- Consider using cloud-native secret management services (AWS Secrets Manager, Azure Key Vault, etc.)

### Security Considerations
- Never commit `.env` files to version control
- Use strong, unique passwords for ServiceNow accounts
- Rotate credentials regularly
- Use service accounts with minimal required permissions

## Logging

The application uses structured logging with the following features:

- **Daily log rotation**: Logs are stored in `logs/app-YYYY-MM-DD.log`
- **Multiple log levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Console and file output**: Logs appear in both console and files
- **Time-based filtering**: Query logs between specific time ranges

## Troubleshooting

### Common Issues

1. **ChromaDB Connection Failed**
   ```bash
   # Check if ChromaDB is running
   curl http://localhost:8000/api/v1/heartbeat
   
   # Restart ChromaDB
   docker restart chromadb
   ```

2. **ServiceNow Authentication Error**
   - Verify credentials in environment variables or `.env` file
   - Check ServiceNow instance URL
   - Ensure service account has proper permissions

3. **Environment Variable Issues**
   - Verify `.env` file is in the project root directory
   - Check that python-dotenv is installed for local development
   - Ensure environment variables are properly set in production

4. **PDF Processing Errors**
   - Verify uploaded file is valid PDF format
   - Check file size limits (ensure reasonable file sizes)
   - Ensure sufficient disk space for processing
   - Verify user has proper permissions to upload files

5. **Memory Issues**
   - Reduce PDF chunk size in `document.py`
   - Increase Docker memory limits
   - Process files in smaller batches

### Debug Mode

Enable debug logging by modifying `logging_config.py`:
```python
def setup_logging(log_dir='logs', level=logging.DEBUG):
    # ... rest of configuration
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Check the logs in `/logs-between` endpoint
- Review ChromaDB collections with `/list-collections`
- Use `/health` endpoint to verify service status

---

**Note**: This API is designed for internal use with ServiceNow instances. Ensure proper security measures are in place for production deployments.
