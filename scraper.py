"""
Alfred AI - Web Scraper with Caching
Web scraping with vector storage and Redis caching
"""

import os
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse

# Web scraping
import requests
from bs4 import BeautifulSoup

# Vector database
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter

# Document processing
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# Caching
from cache import QueryCache

logger = logging.getLogger(__name__)

class WebScraper:
    """Simple web scraper with vector storage"""

    def __init__(self):
        # Configuration from environment variables
        self.qdrant_host = os.getenv('QDRANT_HOST', 'qdrant')
        self.qdrant_port = int(os.getenv('QDRANT_PORT', '6333'))
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.embedding_model = os.getenv('EMBEDDING_MODEL', 'all-minilm')

        # Initialize clients
        self.qdrant_client: QdrantClient | None = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

        # Initialize cache
        self.cache: QueryCache | None = None

        try:
            self.cache = QueryCache(
                host=os.getenv("REDIS_HOST", "redis"),
                port=int(os.getenv("REDIS_PORT", "6379"))
            )
            logger.info("Query cache initialized")
        except Exception as e:
            logger.warning(f"Cache initialization failed: {e}. Running without cache.")
            self.cache = None

        # Initialize connections
        self._init_qdrant()

    def _init_qdrant(self):
        """Initialize Qdrant client"""
        try:
            self.qdrant_client = QdrantClient(
                host=self.qdrant_host,
                port=self.qdrant_port,
                timeout=30
            )
            logger.info(f"Connected to Qdrant at {self.qdrant_host}:{self.qdrant_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            self.qdrant_client = None

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings from Ollama

        Supports both:
        - all-minilm: 384 dimensions
        - nomic-embed-text: 768 dimensions
        """
        try:
            # Determine expected dimensions based on model
            expected_dim = self._get_expected_dimensions()

            embeddings = []
            for text in texts:
                response = requests.post(
                    f"{self.ollama_host}/api/embeddings",
                    json={
                        "model": self.embedding_model,
                        "prompt": text
                    },
                    timeout=30
                )
                if response.status_code == 200:
                    embedding = response.json()['embedding']
                    embeddings.append(embedding)
                else:
                    logger.error(f"Failed to get embedding: {response.status_code}")
                    # Return zero vector as fallback (correct dimensions)
                    embeddings.append([0.0] * expected_dim)
            return embeddings
        except Exception as e:
            logger.error(f"Failed to get embeddings: {e}")
            # Return zero vectors as fallback (correct dimensions)
            expected_dim = self._get_expected_dimensions()
            return [[0.0] * expected_dim] * len(texts)

    def _get_expected_dimensions(self) -> int:
        """
        Get expected embedding dimensions based on model

        Returns:
            int: Expected vector dimensions
        """
        # Model dimension mapping
        dimension_map = {
            "all-minilm": 384,
            "nomic-embed-text": 768,
            "bge-base-en-v1.5": 768,
            "e5-base-v2": 768
        }

        # Check if model name contains any known model
        for model_key, dimensions in dimension_map.items():
            if model_key in self.embedding_model.lower():
                return dimensions

        # Default to nomic-embed-text dimensions
        logger.warning(f"Unknown model '{self.embedding_model}', defaulting to 768 dimensions")
        return 768

    def scrape_url(self, url: str) -> str:
        """Scrape content from a single URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text content
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)

            logger.info(f"Scraped {len(text)} characters from {url}")
            return text

        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return ""

    def create_collection(self, collection_name: str, vector_size: int = 384):
        """Create a new collection in Qdrant"""
        if not self.qdrant_client:
            raise Exception("Qdrant client not initialized")

        try:
            # Check if collection exists
            collections = self.qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if collection_name not in collection_names:
                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {collection_name}")
            else:
                logger.info(f"Collection already exists: {collection_name}")

        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    async def scrape_and_store(self, urls: List[str], collection_name: str):
        """Scrape URLs and store in vector database"""
        if not self.qdrant_client:
            raise Exception("Qdrant client not initialized")

        try:
            # Create collection
            self.create_collection(collection_name)

            all_documents = []

            # Scrape each URL
            for url in urls:
                content = self.scrape_url(url)
                if content:
                    # Split into chunks
                    doc = Document(page_content=content, metadata={"source": url})
                    chunks = self.text_splitter.split_documents([doc])
                    all_documents.extend(chunks)

            if not all_documents:
                logger.warning("No documents to store")
                return

            # Get embeddings
            texts = [doc.page_content for doc in all_documents]
            embeddings = self._get_embeddings(texts)

            # Store in Qdrant
            points = []
            for i, (doc, embedding) in enumerate(zip(all_documents, embeddings)):
                point = PointStruct(
                    id=i,
                    vector=embedding,
                    payload={
                        "text": doc.page_content,
                        "source": doc.metadata.get("source", "unknown")
                    }
                )
                points.append(point)

            # Upsert points
            self.qdrant_client.upsert(
                collection_name=collection_name,
                points=points
            )

            logger.info(f"Stored {len(points)} documents in collection {collection_name}")

        except Exception as e:
            logger.error(f"Failed to scrape and store: {e}")
            raise

    def get_available_collections(self) -> List[str]:
        """Get all available collections from Qdrant"""
        try:
            if not self.qdrant_client:
                return []

            collections = self.qdrant_client.get_collections()
            return [c.name for c in collections.collections]
        except Exception as e:
            logger.error(f"Failed to get collections: {e}")
            return []

    def route_query(self, query: str) -> Dict[str, Any] | None:
        """Intelligently route queries using LLM with dynamic collection rules"""
        try:
            # Get available collections
            available_collections = self.get_available_collections()

            if not available_collections:
                return {"route": "general", "reason": "No collections available"}

            # Create dynamic prompt based on available collections
            collections_text = ", ".join(available_collections)

            prompt = f"""Analyze this query and determine if it should be routed to 'documentation' or 'general' AI.

Available knowledge collections: {collections_text}

Route to 'documentation' if the query is about topics that might be found in the available collections or if it's asking for specific information, how-to guides, or technical documentation.

Route to 'general' if the query is about:
- General conversation or creative tasks
- Topics clearly outside the scope of available collections
- Personal assistance unrelated to technical documentation

Query: "{query}"

Respond with exactly one word: either 'documentation' or 'general'"""

            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": "llama3.2:1b",  # Use small, fast model
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9,
                        "num_predict": 5
                    }
                },
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()['response'].strip().lower()
                if 'documentation' in result:
                    # Find best matching collection
                    best_collection = self._find_best_collection(query, available_collections)
                    return {
                        "route": "documentation",
                        "collection": best_collection,
                        "reason": "LLM routing",
                        "available_collections": available_collections
                    }
                elif 'general' in result:
                    return {
                        "route": "general",
                        "reason": "LLM routing",
                        "available_collections": available_collections
                    }

            # Fallback to collection-based routing
            return self._fallback_collection_routing(query, available_collections)

        except Exception as e:
            logger.error(f"Failed to route query with LLM: {e}")
            return self._fallback_collection_routing(query, available_collections or [])

    def _find_best_collection(self, query: str, collections: List[str]) -> str:
        """Find the best matching collection for a query"""
        if not collections:
            return "alfred_knowledge"

        # Simple matching - could be enhanced with embeddings
        query_lower = query.lower()
        for collection in collections:
            if any(word in collection.lower() for word in query_lower.split()):
                return collection

        # Return first collection as default
        return collections[0]

    def _fallback_collection_routing(self, query: str, collections: List[str]) -> Dict[str, Any]:
        """Fallback routing based on available collections"""
        if not collections:
            return {"route": "general", "reason": "No collections available"}

        # If we have collections, assume documentation search is possible
        best_collection = self._find_best_collection(query, collections)
        return {
            "route": "documentation",
            "collection": best_collection,
            "reason": "Fallback collection routing",
            "available_collections": collections
        }

    def extract_links_from_page(self, base_url: str, url: str) -> List[str]:
        """Extract all documentation links from a page"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find all links
            links = []
            parsed_base = urlparse(base_url)

            for link in soup.find_all('a', href=True):
                href = link.get('href')

                # Skip if href is not a string
                if not href or not isinstance(href, str):
                    continue

                # Convert relative URLs to absolute
                if href.startswith('/'):
                    full_url = urljoin(base_url, href)
                elif href.startswith('http'):
                    full_url = href
                else:
                    full_url = urljoin(url, href)

                # Only include links from the same domain
                parsed_link = urlparse(full_url)
                if parsed_link.netloc == parsed_base.netloc:
                    links.append(full_url)

            # Remove duplicates
            unique_links = list(set(links))
            logger.info(f"Found {len(unique_links)} links from {url}")
            return unique_links

        except Exception as e:
            logger.error(f"Failed to extract links from {url}: {e}")
            return []

    async def search(
        self,
        query: str,
        k: int = 5,
        collection_name: str = "alfred_knowledge",
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Search for similar documents with caching support

        Returns:
            Dict containing:
                - results: List of search results
                - metadata: Dict with cache_hit, query, collection, k
        """
        # Check cache first
        if use_cache and self.cache and self.cache.connected:
            cache_key_filters = {"collection": collection_name, "k": k}
            cached = self.cache.get(query, cache_key_filters)
            if cached:
                logger.info(f"Cache HIT for query: {query[:50]}...")
                # Add cache_hit marker
                cached["metadata"]["cache_hit"] = True
                return cached

        # Cache miss or cache disabled - perform search
        if not self.qdrant_client:
            raise Exception("Qdrant client not initialized")


        qdrant = self.qdrant_client

        try:
            # Get query embedding
            query_embedding = self._get_embeddings([query])[0]

            # Search in Qdrant (using new API for qdrant-client 1.16+)
            search_results = qdrant.query_points(
                collection_name=collection_name,
                query=query_embedding,
                limit=k
            ).points

            # Format results
            results = []
            for result in search_results:
                results.append({
                    "text": result.payload.get("text", ""),
                    "source": result.payload.get("source", "unknown"),
                    "score": result.score
                })

            # Build response with metadata
            response = {
                "results": results,
                "metadata": {
                    "cache_hit": False,
                    "query": query,
                    "collection": collection_name,
                    "k": k
                }
            }

            # Cache result
            if use_cache and self.cache and self.cache.connected:
                cache_key_filters = {"collection": collection_name, "k": k}
                self.cache.set(query, cache_key_filters, response)
                logger.info(f"Cached query: {query[:50]}...")

            logger.info(f"Found {len(results)} results for query: {query}")
            return response

        except Exception as e:
            logger.error(f"Failed to search: {e}")
            raise
