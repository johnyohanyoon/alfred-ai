#!/usr/bin/env python3
"""
Alfred AI Router - Intelligent query routing for Alfred workflows
Routes queries between documentation search and general AI based on content
"""

import json
import sys
import requests
import os
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AlfredRouter:
    def __init__(self):
        self.alfred_ai_url = os.getenv('ALFRED_AI_URL', 'http://localhost:8080')
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')

    def route_query(self, query: str) -> Dict[str, Any]:
        """Route query using Alfred AI's intelligent routing"""
        try:
            response = requests.post(
                f"{self.alfred_ai_url}/api/route",
                json={"query": query},
                timeout=5
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {"route": "general", "reason": "API error"}

        except Exception as e:
            # Fallback to general if routing fails
            return {"route": "general", "reason": f"Routing failed: {str(e)}"}

    def search_documentation(self, query: str, collection: str = None) -> List[Dict[str, Any]]:
        """Search documentation using Alfred AI"""
        try:
            response = requests.post(
                f"{self.alfred_ai_url}/api/search",
                json={"query": query, "k": 3},
                timeout=10
            )

            if response.status_code == 200:
                return response.json()["results"]
            else:
                return []

        except Exception as e:
            return []

    def query_general_ai(self, query: str) -> str:
        """Query Ollama for general AI tasks"""
        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": "llama3.1",
                    "prompt": query,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "No response from AI").strip()
            else:
                return f"Error: HTTP {response.status_code}"

        except Exception as e:
            return f"Error calling Ollama: {str(e)}"

    def format_documentation_results(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Format documentation results for Alfred"""
        alfred_items = []

        if not results:
            alfred_items.append({
                "title": "No documentation found",
                "subtitle": f"No results for: {query}",
                "arg": f"No documentation found for: {query}",
                "icon": {"path": "info.png"}
            })
            return alfred_items

        for i, result in enumerate(results[:3]):  # Top 3 results
            title = result["text"][:80] + "..." if len(result["text"]) > 80 else result["text"]
            subtitle = f"Source: {result['source']} (Score: {result['score']:.2f})"

            alfred_items.append({
                "title": title,
                "subtitle": subtitle,
                "arg": result["text"],
                "copytext": result["text"],
                "largetext": result["text"],
                "icon": {"path": "doc.png"}
            })

        return alfred_items

    def format_general_result(self, result: str, query: str) -> List[Dict[str, Any]]:
        """Format general AI result for Alfred"""
        return [{
            "title": result[:80] + "..." if len(result) > 80 else result,
            "subtitle": f"AI response to: {query}",
            "arg": result,
            "copytext": result,
            "largetext": result,
            "icon": {"path": "ai.png"}
        }]

    def process_query(self, query: str) -> Dict[str, Any]:
        """Main processing function"""
        if not query.strip():
            return {"items": [{"title": "Empty query", "subtitle": "Please enter a query"}]}

        # Route the query
        routing_info = self.route_query(query)
        route = routing_info.get("route", "general")

        if route == "documentation":
            # Search documentation
            collection = routing_info.get("collection")
            results = self.search_documentation(query, collection)
            alfred_items = self.format_documentation_results(results, query)

            # Add routing info as subtitle to first item
            if alfred_items:
                alfred_items[0]["subtitle"] = f"Routed to documentation ({routing_info.get('reason', 'unknown')})"

        else:
            # Query general AI
            result = self.query_general_ai(query)
            alfred_items = self.format_general_result(result, query)

            # Add routing info
            if alfred_items:
                alfred_items[0]["subtitle"] = f"Routed to general AI ({routing_info.get('reason', 'unknown')})"

        return {"items": alfred_items}

def main():
    """Main function for Alfred workflow"""
    if len(sys.argv) < 2:
        print(json.dumps({"items": [{"title": "No query provided"}]}))
        return

    query = sys.argv[1]
    router = AlfredRouter()

    try:
        result = router.process_query(query)
        print(json.dumps(result))
    except Exception as e:
        error_result = {
            "items": [{
                "title": f"Error: {str(e)}",
                "subtitle": "Failed to process query",
                "arg": str(e)
            }]
        }
        print(json.dumps(error_result))

if __name__ == "__main__":
    main()
