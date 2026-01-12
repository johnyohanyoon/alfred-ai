# Alfred AI

A local RAG (Retrieval-Augmented Generation) pipeline for web scraping, document indexing, and semantic search. Built with FastAPI, Qdrant, Redis, and Ollama.

## Features

- **Web Scraping**: Scrape and index web pages into a vector database
- **Semantic Search**: Find relevant documents using vector similarity
- **Query Caching**: Redis-backed caching for fast repeated queries
- **Intelligent Routing**: LLM-powered query routing between documentation and general AI
- **REST API**: Full API for integration with other tools
- **Web Interface**: Simple UI for scraping and searching

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Alfred    │────▶│   Qdrant    │     │   Ollama    │
│   (API)     │     │  (Vectors)  │     │ (Embeddings)│
└─────────────┘     └─────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐
│    Redis    │
│   (Cache)   │
└─────────────┘
```

## Prerequisites

- Docker and Docker Compose
- [Ollama](https://ollama.ai) running with embedding models

### Required Ollama Models

```bash
# Pull the embedding model
ollama pull all-minilm

# Optional: For query routing
ollama pull llama3.2:1b
```

## Quick Start

### 1. Clone and Configure

```bash
git clone https://github.com/YOUR_USERNAME/alfred-ai.git
cd alfred-ai
cp .env.example .env
```

### 2. Edit Configuration

Edit `.env` to set your Ollama server address:

```bash
# If Ollama is running locally
OLLAMA_HOST=http://host.docker.internal:11434

# If Ollama is on another machine
OLLAMA_HOST=http://YOUR_OLLAMA_IP:11434
```

### 3. Start Services

```bash
docker-compose up -d
```

### 4. Verify

```bash
# Check health
curl http://localhost:8080/health

# Check Qdrant
curl http://localhost:6333/collections
```

### 5. Access

- Web Interface: http://localhost:8080
- API Docs: http://localhost:8080/docs
- Qdrant Dashboard: http://localhost:6333/dashboard

## API Usage

### Scrape URLs

```bash
curl -X POST http://localhost:8080/api/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://docs.example.com/getting-started"],
    "collection_name": "my_docs"
  }'
```

### Search Documents

```bash
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "how to configure authentication",
    "k": 5
  }'
```

### Bulk Scrape Documentation

```bash
curl -X POST http://localhost:8080/api/bulk-scrape \
  -H "Content-Type: application/json" \
  -d '{
    "base_url": "https://docs.example.com/"
  }'
```

### Query Routing

```bash
curl -X POST http://localhost:8080/api/route \
  -H "Content-Type: application/json" \
  -d '{
    "query": "how do I set up a firewall?"
  }'
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama server URL |
| `EMBEDDING_MODEL` | `all-minilm` | Embedding model name |
| `QDRANT_HOST` | `qdrant` | Qdrant server host |
| `QDRANT_PORT` | `6333` | Qdrant server port |
| `REDIS_HOST` | `redis` | Redis server host |
| `REDIS_PORT` | `6379` | Redis server port |
| `LOG_LEVEL` | `INFO` | Logging level |

### Embedding Models

Supported models and their dimensions:

| Model | Dimensions | Notes |
|-------|------------|-------|
| `all-minilm` | 384 | Fast, good for general use |
| `nomic-embed-text` | 768 | Higher quality embeddings |
| `bge-base-en-v1.5` | 768 | Good for English text |

## Data Persistence

Data is stored in Docker volumes:

- `qdrant_data`: Vector database storage
- `redis_data`: Query cache
- `app_data`: Application data
- `app_logs`: Application logs

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web interface |
| `/health` | GET | Health check |
| `/api/scrape` | POST | Scrape URLs and store |
| `/api/bulk-scrape` | POST | Scrape all links from a page |
| `/api/search` | POST | Search documents |
| `/api/route` | POST | Route query to docs or AI |
| `/api/collections` | GET | List collections |
| `/api/status` | GET | System status |

## Development

### Run Locally (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start Qdrant and Redis separately, then:
python main.py
```

### Run Tests

```bash
pytest tests/ -v
```

## Troubleshooting

### Ollama Connection Issues

```bash
# Verify Ollama is running
curl http://YOUR_OLLAMA_IP:11434/api/tags

# Check if model is available
ollama list
```

### Container Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f alfred
```

### Reset Data

```bash
# Stop and remove volumes
docker-compose down -v

# Restart fresh
docker-compose up -d
```

## License

MIT License - see [LICENSE](LICENSE) for details.
