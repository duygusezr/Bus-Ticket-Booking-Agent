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
    model: Any
    cache: List[Dict[str, Any]]
    threshold: float
    max_items: int
    cache_file: str
    ENABLED: bool = False # Set to False as per performance optimization request
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
            cls._instance.cache = []
            cls._instance.threshold = 0.90 # Similarity threshold (0.0 to 1.0)
            cls._instance.max_items = 500   # Cache max boyutu — RAM taşmasını önler
            
            # Persistent file disabled as per user request (clear on every run)
            cls._instance.cache_file = "semantic_cache_data.json"
            if os.path.exists(cls._instance.cache_file):
                try:
                    os.remove(cls._instance.cache_file)
                    print(f"[SEMANTIC CACHE] Old cache file deleted for a fresh start.")
                except:
                    pass
            # cls._instance._load_cache() # Disabled persistence
            
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
        if not getattr(self, "ENABLED", True):
            return None

        import re
        clean_query = re.sub(r"\[SİSTEM BİLGİSİ.*?\]", "", query).strip()
        
        # Skip small inputs (e.g., "Yes", "8", "12") to save embedding time.
        if len(clean_query) < 5:
            return None
            
        if not self.cache:
            return None
            
        t0 = time.perf_counter()
        query_vector = self.model.encode(clean_query, convert_to_numpy=True)
        
        best_match = None
        highest_score = -1.0
        
        # Calculate cosine similarity against all cached items
        if len(self.cache) > 0:
            for item in self.cache:
                score = np.dot(query_vector, item["vector"]) / (np.linalg.norm(query_vector) * np.linalg.norm(item["vector"]) + 1e-9)
                if score > highest_score:
                    highest_score = float(score)
                    best_match = item["data"]
        
        t1 = time.perf_counter()
        
        # Sayısal ağırlıklı girdiler için bypass (TC, Koltuk, ID vb.)
        digit_count = sum(c.isdigit() for c in clean_query)
        is_mostly_digits = digit_count > (len(clean_query) / 2) if len(clean_query) > 0 else False
        
        if is_mostly_digits:
            print(f"[SEMANTIC CACHE] BYPASS: Input is mostly digits ({clean_query})")
            return None
            
        if highest_score >= self.threshold:
            print(f"[SEMANTIC CACHE] HIT (score: {highest_score:.3f}, time: {t1-t0:.3f}s)")
            return best_match
            
        print(f"[SEMANTIC CACHE] MISS (best score: {highest_score:.3f}, time: {t1-t0:.3f}s)")
        return None

    def add(self, query: str, text: str, audio: str, emotion: str):
        """Adds a new query-response pair to the cache."""
        if not self.ENABLED:
            return
            
        import re
        clean_query = re.sub(r"\[SİSTEM BİLGİSİ.*?\]", "", query).strip()
        
        # Avoid duplicate (or very close) adds
        if self.search(clean_query) is not None:
            return

        # Cache max boyutuna ulaşıldıysa en eski kaydı sil (FIFO)
        if len(self.cache) >= self.max_items:
            self.cache.pop(0)
            print(f"[SEMANTIC CACHE] Max boyuta ulaşıldı ({self.max_items}), en eski kayıt silindi.")
            
        embedding = self.model.encode(clean_query, convert_to_numpy=True)
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
        # self._save_cache_item(query, text, audio, emotion) # Disabled persistence
        print(f"[SEMANTIC CACHE] Added new item (RAM only): {query[:30]}...")

# Singleton helper
semantic_cache = SemanticCache()
