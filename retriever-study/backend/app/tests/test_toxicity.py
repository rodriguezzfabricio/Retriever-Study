import pytest
from app.core.toxicity import get_toxicity_score

def test_toxicity_scoring():
    """
    Tests the toxicity scoring function with both toxic and benign text.
    """
    toxic_text = "You are a horrible person and I hate you."
    benign_text = "I think we should meet tomorrow to review the project."

    # Test with toxic text
    toxic_score = get_toxicity_score(toxic_text)
    print(f"Toxic text score: {toxic_score}")
    assert toxic_score > 0.5  # Expecting a high toxicity score

    # Test with benign text
    benign_score = get_toxicity_score(benign_text)
    print(f"Benign text score: {benign_score}")
    assert benign_score < 0.5  # Expecting a low toxicity score

def test_empty_string():
    """
    Tests that an empty string returns a toxicity score of 0.0.
    """
    empty_text = ""
    score = get_toxicity_score(empty_text)
    print(f"Empty string score: {score}")
    assert score == 0.0

def test_whitespace_string():
    """
    Tests that a string with only whitespace returns a toxicity score of 0.0.
    """
    whitespace_text = "   \t\n"
    score = get_toxicity_score(whitespace_text)
    print(f"Whitespace string score: {score}")
    assert score == 0.0
