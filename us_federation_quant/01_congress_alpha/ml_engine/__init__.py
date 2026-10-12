"""
Financial Machine Learning (AFML) Engine:
- Symmetric CUSUM Event-Driven Sampling (López de Prado 2018)
- Dynamic Triple Barrier Labeling
- Purged and Embargoed K-Fold Cross-Validation
- Meta-Classifier Model Pipeline & Calibration
- Real-time Feature Extraction & Inference Service
"""

from .event_sampling import SymmetricCUSUMFilter
from .triple_barrier_labeler import TripleBarrierLabeler
from .purged_cv import PurgedKFold
from .meta_classifier_trainer import MetaClassifierTrainer, MetaClassifierArtifact
from .model_inference_service import ModelInferenceService, MLInferenceResult

__all__ = [
    "SymmetricCUSUMFilter",
    "TripleBarrierLabeler",
    "PurgedKFold",
    "MetaClassifierTrainer",
    "MetaClassifierArtifact",
    "ModelInferenceService",
    "MLInferenceResult"
]
