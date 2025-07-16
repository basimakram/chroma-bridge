FROM python:3.12-slim

# Set working directory
WORKDIR /CHROMA_APIS

# Copy everything
COPY . .

# Upgrade pip before installing dependencies
RUN pip3 install --upgrade pip

RUN pip install -r requirements.txt

# Change to a different port
EXPOSE 8001

# Start the app on port 8001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]