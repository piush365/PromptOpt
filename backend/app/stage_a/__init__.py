"""Stage A: feature detection. See detector.py."""
from app.stage_a.detector import FeatureDetector, detect_features
from app.stage_a.schema import PromptFeatures

__all__ = ["FeatureDetector", "PromptFeatures", "detect_features"]
