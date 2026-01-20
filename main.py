"""
Alfred AI - RAG Pipeline
Web scraping with vector storage and semantic search
"""

import logging
from typing import List
from datetime import datetime

# FastAPI imports
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

# Core functionality
from scraper import WebScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Request/Response models
class ScrapeRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1)
    collection_name: str = Field(default="alfred_knowledge")

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = Field(default=5, ge=1, le=20)
    use_cache: bool = Field(default=True)

class BulkScrapeRequest(BaseModel):
    base_url: str = Field(..., min_length=1)
    collection_name: str = Field(default="alfred_knowledge")

class QueryRouteRequest(BaseModel):
    query: str = Field(..., min_length=1)

# Lifespan Context Manager
@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize scraper on startup"""
    global scraper
    try:
        scraper = WebScraper()
        logger.info("Alfred AI started successfully")

        # App runs
        yield

        # Shutdown
        logger.info("Shutting down...")

    except Exception as e:
        logger.error(f"Failed to initialize: {e}")

# Global scraper instance
scraper = None

# FastAPI App Initialization
app = FastAPI(
    title="Alfred AI v1.1",
    description="...",
    version="1.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def web_interface():
    """Simple web interface"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Alfred AI</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            h1 { color: #333; }
            .form-group { margin: 20px 0; }
            input, textarea, button { padding: 10px; margin: 5px; }
            button { background: #007bff; color: white; border: none; cursor: pointer; }
            button:hover { background: #0056b3; }
            .results { margin-top: 20px; padding: 20px; background: #f8f9fa; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Alfred AI - Web Scraper & Search</h1>

            <div class="form-group">
                <h3>Scrape URLs</h3>
                <textarea id="urls" placeholder="Enter URLs (one per line)" rows="4" style="width: 100%"></textarea>
                <button onclick="scrapeUrls()">Scrape & Store</button>
            </div>

            <div class="form-group">
                <h3>Bulk Scrape Documentation</h3>
                <input type="text" id="docUrl" placeholder="Enter documentation base URL" style="width: 100%">
                <button onclick="bulkScrape()">Find & Scrape All Links</button>
            </div>

            <div class="form-group">
                <h3>Search</h3>
                <input type="text" id="query" placeholder="Enter search query" style="width: 70%">
                <button onclick="search()">Search</button>
            </div>

            <div class="form-group">
                <h3>Query Routing Test</h3>
                <input type="text" id="routeQuery" placeholder="Test query routing" style="width: 70%">
                <button onclick="testRouting()">Test Route</button>
            </div>

            <div class="form-group">
                <h3>Collection Management</h3>
                <button onclick="loadCollections()">View Collections</button>
                <div id="collections" style="margin-top: 10px;"></div>
            </div>

            <div id="results" class="results" style="display: none;"></div>
        </div>

        <script>
            async function scrapeUrls() {
                const urls = document.getElementById('urls').value.split('\\n').filter(url => url.trim());
                if (urls.length === 0) {
                    alert('Please enter at least one URL');
                    return;
                }

                try {
                    const response = await fetch('/api/scrape', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({urls: urls})
                    });
                    const result = await response.json();
                    showResults('Scraping started: ' + JSON.stringify(result, null, 2));
                } catch (error) {
                    showResults('Error: ' + error.message);
                }
            }

            async function bulkScrape() {
                const docUrl = document.getElementById('docUrl').value;
                if (!docUrl.trim()) {
                    alert('Please enter a documentation URL');
                    return;
                }

                try {
                    const response = await fetch('/api/bulk-scrape', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({base_url: docUrl})
                    });
                    const result = await response.json();
                    showResults('Bulk scraping started: ' + JSON.stringify(result, null, 2));
                } catch (error) {
                    showResults('Error: ' + error.message);
                }
            }

            async function search() {
                const query = document.getElementById('query').value;
                if (!query.trim()) {
                    alert('Please enter a search query');
                    return;
                }

                try {
                    const response = await fetch('/api/search', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({query: query})
                    });
                    const result = await response.json();
                    showResults('Search results: ' + JSON.stringify(result, null, 2));
                } catch (error) {
                    showResults('Error: ' + error.message);
                }
            }

            async function testRouting() {
                const query = document.getElementById('routeQuery').value;
                if (!query.trim()) {
                    alert('Please enter a test query');
                    return;
                }

                try {
                    const response = await fetch('/api/route', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({query: query})
                    });
                    const result = await response.json();
                    showResults('Routing result: ' + JSON.stringify(result, null, 2));
                } catch (error) {
                    showResults('Error: ' + error.message);
                }
            }

            async function loadCollections() {
                try {
                    const response = await fetch('/api/collections');
                    const result = await response.json();
                    const collectionsDiv = document.getElementById('collections');
                    if (result.collections.length > 0) {
                        collectionsDiv.innerHTML = '<h4>Available Collections:</h4><ul>' +
                            result.collections.map(c => `<li>${c}</li>`).join('') + '</ul>';
                    } else {
                        collectionsDiv.innerHTML = '<p>No collections found. Scrape some documents first!</p>';
                    }
                } catch (error) {
                    showResults('Error loading collections: ' + error.message);
                }
            }

            function showResults(text) {
                const resultsDiv = document.getElementById('results');
                resultsDiv.innerHTML = '<pre>' + text + '</pre>';
                resultsDiv.style.display = 'block';
            }
        </script>
    </body>
    </html>
    """

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.post("/api/scrape")
async def scrape_urls(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """Scrape URLs and store in vector database"""
    if not scraper:
        raise HTTPException(status_code=500, detail="Scraper not initialized")

    # Start background scraping
    background_tasks.add_task(scraper.scrape_and_store, request.urls, request.collection_name)

    return {
        "message": "Scraping started",
        "urls": request.urls,
        "collection": request.collection_name
    }

@app.post("/api/bulk-scrape")
async def bulk_scrape_docs(request: BulkScrapeRequest, background_tasks: BackgroundTasks):
    """Extract all links from a documentation page and scrape them"""
    if not scraper:
        raise HTTPException(status_code=500, detail="Scraper not initialized")

    try:
        # Extract all links from the base URL
        links = scraper.extract_links_from_page(request.base_url, request.base_url)

        if not links:
            raise HTTPException(status_code=404, detail="No documentation links found")

        # Start background scraping of all links
        background_tasks.add_task(scraper.scrape_and_store, links, request.collection_name)

        return {
            "message": "Bulk scraping started",
            "base_url": request.base_url,
            "links_found": len(links),
            "collection": request.collection_name,
            "links": links[:10]  # Show first 10 links as preview
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/route")
async def route_query(request: QueryRouteRequest):
    """Intelligently route queries to documentation or general AI"""
    if not scraper:
        raise HTTPException(status_code=500, detail="Scraper not initialized")

    try:
        routing_info = scraper.route_query(request.query)
        return routing_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search")
async def search_documents(request: SearchRequest):
    """
    Search documents in vector database with caching support.

    Returns:
        - query: Original query string
        - results: List of search results
        - metadata: Dict with cache_hit, collection, k
    """
    if not scraper:
        raise HTTPException(status_code=500, detail="Scraper not initialized")

    try:
        result = await scraper.search(
            request.query,
            request.k,
            use_cache=request.use_cache
        )
        return {
            "query": request.query,
            **result  # Includes results and metadata
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/collections")
async def get_collections():
    """Get all available collections"""
    if not scraper:
        raise HTTPException(status_code=500, detail="Scraper not initialized")

    try:
        collections = scraper.get_available_collections()
        return {
            "collections": collections,
            "count": len(collections)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def get_status():
    """Get system status"""
    return {
        "status": "running",
        "scraper_ready": scraper is not None,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
