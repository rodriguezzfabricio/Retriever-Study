from transformers import pipeline
from functools import lru_cache

# --- Model Loading ---

@lru_cache(maxsize=1)
def get_toxicity_classifier():
    """
    Loads and caches the pre-trained toxicity classification model.
    Using lru_cache ensures the model is loaded only once.
    """
    print("Loading toxicity classification model: unitary/toxic-bert")
    # Using a pipeline is the easiest way to use a model for a specific task
    toxicity_pipeline = pipeline(
        "text-classification",
        model="unitary/toxic-bert",
        tokenizer="unitary/toxic-bert"
    )
    print("Toxicity model loaded successfully.")
    return toxicity_pipeline

# --- Classification Function ---

def get_toxicity_score(text: str) -> float:
    """
    Analyzes a string of text and returns its toxicity score.

    Args:
        text: The input text to analyze.

    Returns:
        A float representing the toxicity score. The label 'toxic' is what we look for,
        and we return its score. If the label is not found, returns 0.0.
    """
    if not text.strip():
        return 0.0

    classifier = get_toxicity_classifier()
    results = classifier(text)

    # The pipeline returns a list of dictionaries, e.g., [{'label': 'toxic', 'score': 0.98}]
    # or [{'label': 'neutral', 'score': 0.99}]. We need to find the score for the 'toxic' label.
    for result in results:
        if result['label'].lower() == 'toxic':
            return round(result['score'], 4)
    
    return 0.0

# --- Example Usage (for direct testing) ---
if __name__ == "__main__":
    toxic_text = "You are a horrible person and I hate you."
    benign_text = "I think we should meet tomorrow to review the project."

    print(f"Analyzing: '{toxic_text}'")
    score_toxic = get_toxicity_score(toxic_text)
    print(f"Toxicity Score: {score_toxic}")
    assert score_toxic > 0.8

    print("\n---\n")

    print(f"Analyzing: '{benign_text}'")
    score_benign = get_toxicity_score(benign_text)
    print(f"Toxicity Score: {score_benign}")
    assert score_benign < 0.5

    print("\nToxicity module test completed successfully.")
