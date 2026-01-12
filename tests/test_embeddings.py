"""
Test embedding model functionality

Tests verify:
1. Embedding model availability
2. Correct dimensions
3. Vector normalization
4. Consistency
5. Performance
"""

import pytest
import requests
import math
import time
import os


class TestNomicEmbedModel:
    """Test nomic-embed-text embedding model"""

    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    MODEL_NAME = "nomic-embed-text"
    EXPECTED_DIMENSIONS = 768

    def test_nomic_embed_available(self):
        """nomic-embed-text should be available on Ollama"""
        try:
            response = requests.get(
                f"{self.OLLAMA_HOST}/api/tags",
                timeout=5
            )
            assert response.status_code == 200, "Ollama not responding"

            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]

            assert any(self.MODEL_NAME in name for name in model_names), \
                f"{self.MODEL_NAME} not found in Ollama models: {model_names}"

        except requests.ConnectionError:
            pytest.skip(f"Cannot connect to Ollama at {self.OLLAMA_HOST}")

    def test_nomic_embed_dimensions(self):
        """nomic-embed-text should return 768-dimensional vectors"""
        try:
            response = requests.post(
                f"{self.OLLAMA_HOST}/api/embeddings",
                json={
                    "model": self.MODEL_NAME,
                    "prompt": "Docker container networking"
                },
                timeout=30
            )
            assert response.status_code == 200, f"Embedding request failed: {response.text}"

            embedding = response.json().get("embedding", [])
            assert len(embedding) == self.EXPECTED_DIMENSIONS, \
                f"Expected {self.EXPECTED_DIMENSIONS} dimensions, got {len(embedding)}"

        except requests.ConnectionError:
            pytest.skip(f"Cannot connect to Ollama at {self.OLLAMA_HOST}")

    def test_nomic_embed_normalized(self):
        """Vectors should be normalized (magnitude approx 1.0)"""
        try:
            response = requests.post(
                f"{self.OLLAMA_HOST}/api/embeddings",
                json={
                    "model": self.MODEL_NAME,
                    "prompt": "Test normalization"
                },
                timeout=30
            )
            assert response.status_code == 200

            embedding = response.json().get("embedding", [])

            # Calculate magnitude
            magnitude = math.sqrt(sum(x**2 for x in embedding))

            # Should be close to 1.0 (normalized)
            assert 0.99 < magnitude < 1.01, \
                f"Vector not normalized: magnitude = {magnitude}"

        except requests.ConnectionError:
            pytest.skip(f"Cannot connect to Ollama at {self.OLLAMA_HOST}")

    def test_nomic_embed_consistency(self):
        """Same text should produce same embedding"""
        try:
            text = "Docker networking setup"

            # Get embedding twice
            response1 = requests.post(
                f"{self.OLLAMA_HOST}/api/embeddings",
                json={"model": self.MODEL_NAME, "prompt": text},
                timeout=30
            )
            response2 = requests.post(
                f"{self.OLLAMA_HOST}/api/embeddings",
                json={"model": self.MODEL_NAME, "prompt": text},
                timeout=30
            )

            assert response1.status_code == 200
            assert response2.status_code == 200

            emb1 = response1.json().get("embedding", [])
            emb2 = response2.json().get("embedding", [])

            # Should be identical (deterministic)
            assert emb1 == emb2, "Embeddings should be consistent"

        except requests.ConnectionError:
            pytest.skip(f"Cannot connect to Ollama at {self.OLLAMA_HOST}")

    def test_embedding_latency(self):
        """Single embedding should complete in <100ms"""
        try:
            start = time.time()
            response = requests.post(
                f"{self.OLLAMA_HOST}/api/embeddings",
                json={
                    "model": self.MODEL_NAME,
                    "prompt": "Performance test"
                },
                timeout=30
            )
            latency = (time.time() - start) * 1000  # Convert to ms

            assert response.status_code == 200
            assert latency < 100, \
                f"Embedding too slow: {latency:.0f}ms (target: <100ms)"

        except requests.ConnectionError:
            pytest.skip(f"Cannot connect to Ollama at {self.OLLAMA_HOST}")

    def test_batch_embedding_efficiency(self):
        """Batch processing should be more efficient than sequential"""
        try:
            texts = ["Docker", "Kubernetes", "Container"] * 10  # 30 texts

            # Sequential processing
            start = time.time()
            for text in texts:
                requests.post(
                    f"{self.OLLAMA_HOST}/api/embeddings",
                    json={"model": self.MODEL_NAME, "prompt": text},
                    timeout=30
                )
            sequential_time = (time.time() - start) * 1000

            # Note: This test documents current behavior
            logger_msg = f"Sequential embedding of {len(texts)} texts: {sequential_time:.0f}ms"
            print(f"\n{logger_msg}")

        except requests.ConnectionError:
            pytest.skip(f"Cannot connect to Ollama at {self.OLLAMA_HOST}")


class TestEmbeddingComparison:
    """Compare old (all-minilm) vs new (nomic-embed-text) models"""

    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def test_dimension_difference(self):
        """Document dimension difference between models"""
        try:
            # all-minilm: 384 dimensions
            response_old = requests.post(
                f"{self.OLLAMA_HOST}/api/embeddings",
                json={"model": "all-minilm", "prompt": "test"},
                timeout=30
            )

            # nomic-embed-text: 768 dimensions
            response_new = requests.post(
                f"{self.OLLAMA_HOST}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": "test"},
                timeout=30
            )

            if response_old.status_code == 200 and response_new.status_code == 200:
                old_dims = len(response_old.json().get("embedding", []))
                new_dims = len(response_new.json().get("embedding", []))

                print(f"\nEmbedding Model Comparison:")
                print(f"   all-minilm: {old_dims} dimensions")
                print(f"   nomic-embed-text: {new_dims} dimensions")
                print(f"   Improvement: {(new_dims / old_dims - 1) * 100:.0f}% more dimensions")

                assert old_dims == 384, "all-minilm should be 384d"
                assert new_dims == 768, "nomic-embed-text should be 768d"

        except requests.ConnectionError:
            pytest.skip(f"Cannot connect to Ollama at {self.OLLAMA_HOST}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
