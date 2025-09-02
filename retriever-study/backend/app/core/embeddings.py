from sentence_transformers import SentenceTransformer
from transformers import pipeline
import numpy as np
import time
from typing import List, Optional

# Model configurations as per SSOT
PRIMARY_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
FALLBACK_EMBEDDING_MODEL = "thenlper/gte-small"
TOXICITY_MODEL = "unitary/toxic-bert"
SUMMARIZATION_MODEL = "sshleifer/distilbart-cnn-12-6"

# Global model instances (lazy-loaded)
embedding_model = None
toxicity_classifier = None
summarizer = None

def get_embedding_model():
    """
    Loads the embedding model (primary or fallback) once and caches it.
    """
    global embedding_model
    if embedding_model is None:
        try:
            print(f"Loading primary embedding model: {PRIMARY_EMBEDDING_MODEL}")
            embedding_model = SentenceTransformer(PRIMARY_EMBEDDING_MODEL)
        except Exception as e:
            print(f"Failed to load primary model, loading fallback: {e}")
            embedding_model = SentenceTransformer(FALLBACK_EMBEDDING_MODEL)
    return embedding_model

def get_toxicity_classifier():
    """
    Loads the toxicity classification model once and caches it.
    """
    global toxicity_classifier
    if toxicity_classifier is None:
        print(f"Loading toxicity model: {TOXICITY_MODEL}")
        toxicity_classifier = pipeline("text-classification", model=TOXICITY_MODEL, return_all_scores=True)
    return toxicity_classifier

def get_summarizer():
    """
    Loads the summarization model once and caches it.
    """
    global summarizer
    if summarizer is None:
        print(f"Loading summarization model: {SUMMARIZATION_MODEL}")
        summarizer = pipeline("summarization", model=SUMMARIZATION_MODEL, max_length=100, min_length=30, do_sample=False)
    return summarizer

def embed_text(text: str) -> List[float]:
    """
    Generates a vector embedding for a given text.
    """
    start_time = time.time()
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_tensor=False)
    end_time = time.time()
    print(f"Embedding took {end_time - start_time:.3f}s")
    return embedding.tolist()

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """
    Calculates the cosine similarity between two vectors.
    """
    v1 = np.array(v1)
    v2 = np.array(v2)
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def check_toxicity(text: str) -> float:
    """
    Checks the toxicity of a text and returns the 'toxic' score.
    """
    start_time = time.time()
    classifier = get_toxicity_classifier()
    # The pipeline returns a list containing a list of dictionaries
    result = classifier(text)
    end_time = time.time()
    print(f"Toxicity check took {end_time - start_time:.3f}s")

    # Find the score for the 'TOXIC' label
    for score_dict in result[0]:
        if score_dict['label'] == 'toxic':
            return score_dict['score']
    return 0.0

def summarize_text(text: str, max_len: int = 400) -> List[str]:
    """
    Summarizes a block of text into a list of bullet points.
    """
    if not text.strip():
        return ["No content to summarize."]

    start_time = time.time()
    summarizer_pipeline = get_summarizer()
    
    # Ensure text is not too long for the model
    truncated_text = text[:1500]

    try:
        result = summarizer_pipeline(truncated_text)
        summary = result[0]['summary_text']
        
        # Simple split into sentences for bullets
        bullets = [s.strip() for s in summary.split('.') if s.strip()]
        
        # Enforce character limit
        total_chars = 0
        final_bullets = []
        for bullet in bullets[:5]: # Max 5 bullets
            if total_chars + len(bullet) < max_len:
                final_bullets.append(bullet + '.')
                total_chars += len(bullet)
            else:
                break
        
        end_time = time.time()
        print(f"Summarization took {end_time - start_time:.3f}s")
        
        return final_bullets if final_bullets else ["Summary could not be generated."]
        
    except Exception as e:
        print(f"Summarization failed: {e}")
        return ["Summary generation failed."]
