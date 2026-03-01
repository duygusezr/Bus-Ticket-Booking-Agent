import numpy as np
import json
import os
import logging
import warnings
from sentence_transformers import SentenceTransformer
from typing import Optional, Dict, Any, List
import time

# HF_TOKEN ve BertModel uyarılarını sustur
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers.models.transformer").setLevel(logging.ERROR)
logging.getLogger("torch").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*unauthenticated.*")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Tiny model for fast embedding (runs well on CPU)
MODEL_NAME = "all-MiniLM-L6-v2"

class SemanticCache:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SemanticCache, cls).__new__(cls)
            # BertModel LOAD REPORT stdout uyarısını sustur
            import sys, io
            _old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                cls._instance.model = SentenceTransformer(MODEL_NAME)
            finally:
                sys.stdout = _old_stdout
            # cache structure: List of dicts {vector: np.array, data: {text, audio, emotion, original_query}}
            cls._instance.cache: List[Dict[str, Any]] = []
            cls._instance.threshold = 0.90 # Similarity threshold (0.0 to 1.0)
            cls._instance.max_items = 500   # Cache max boyutu — RAM taşmasını önler
            
            # persistent file (optional, but good for local)
            cls._instance.cache_file = "semantic_cache_data.json"
            cls._instance._load_cache()
            
        return cls._instance

    def _load_cache(self):
        """Loads simple queries/responses from JSON and re-embeds them."""
        # Note: In a real Redis scenario, embeddings are stored in a vector DB.
        # This is a robust local fallback.
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                    for item in saved_data:
                        # Re-calculate embeddings on load
                        embedding = self.model.encode(item["query"], convert_to_numpy=True)
                        self.cache.append({
                            "vector": embedding,
                            "data": {
                                "text": item["text"],
                                "audio": item["audio"],
                                "emotion": item["emotion"],
                                "query": item["query"]
                            }
                        })
                print(f"[SEMANTIC CACHE] Loaded {len(self.cache)} items from disk.")
            except Exception as e:
                print(f"[SEMANTIC CACHE] Load failed: {e}")

    def _save_cache_item(self, query: str, text: str, audio: str, emotion: str):
        """Appends a new item to the JSON file for persistence."""
        try:
            items = []
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    items = json.load(f)
            
            items.append({
                "query": query,
                "text": text,
                "audio": audio,
                "emotion": emotion
            })
            
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SEMANTIC CACHE] Save item failed: {e}")

    def search(self, query: str) -> Optional[Dict[str, Any]]:
        """Searches for a similar query in the cache."""
        if not self.cache:
            return None
            
        t0 = time.perf_counter()
        # BUG FIX: self.model.model.encode -> self.model.encode
        query_vector = self.model.encode(query, convert_to_numpy=True)
        
        best_match = None
        highest_score = -1.0
        
        for item in self.cache:
            # Cosine similarity
            dot_product = np.dot(query_vector, item["vector"])
            norm_q = np.linalg.norm(query_vector)
            norm_i = np.linalg.norm(item["vector"])
            score = dot_product / (norm_q * norm_i) if (norm_q * norm_i) > 0 else 0
            
            if score > highest_score:
                highest_score = score
                best_match = item["data"]
        
        t1 = time.perf_counter()
        
        if highest_score >= self.threshold:
            print(f"[SEMANTIC CACHE] HIT (score: {highest_score:.3f}, time: {t1-t0:.3f}s)")
            return best_match
            
        print(f"[SEMANTIC CACHE] MISS (best score: {highest_score:.3f}, time: {t1-t0:.3f}s)")
        return None

    def add(self, query: str, text: str, audio: str, emotion: str):
        """Adds a new query-response pair to the cache."""
        # Avoid duplicate (or very close) adds
        if self.search(query) is not None:
            return

        # Cache max boyutuna ulaşıldıysa en eski kaydı sil (FIFO)
        if len(self.cache) >= self.max_items:
            self.cache.pop(0)
            print(f"[SEMANTIC CACHE] Max boyuta ulaşıldı ({self.max_items}), en eski kayıt silindi.")
            
        embedding = self.model.encode(query, convert_to_numpy=True)
        new_data = {
            "text": text,
            "audio": audio,
            "emotion": emotion,
            "query": query
        }
        self.cache.append({
            "vector": embedding,
            "data": new_data
        })
        self._save_cache_item(query, text, audio, emotion)
        print(f"[SEMANTIC CACHE] Added new item: {query[:30]}...")

# Singleton helper
semantic_cache = SemanticCache()
