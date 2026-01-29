"""Type stubs for yomail.pipeline.crf."""

from pathlib import Path
from typing import Literal

from yomail.pipeline.features import ExtractedFeatures

Label = Literal["GREETING", "BODY", "CLOSING", "SIGNATURE", "QUOTE", "OTHER"]
LABELS: tuple[Label, ...]

def get_default_model_path() -> Path:
    """Get path to the bundled default model.

    Returns:
        Path to the bundled email_body.crfsuite model.

    Raises:
        FileNotFoundError: If the bundled model is not found.
    """
    ...

class LabeledLine:
    """A line with its predicted label and confidence.

    Attributes:
        text: Original line text.
        label: Predicted label (one of LABELS).
        confidence: Marginal probability for the predicted label (0.0 to 1.0).
        label_probabilities: Marginal probabilities for all labels.
    """
    text: str
    label: Label
    confidence: float
    label_probabilities: dict[Label, float]
    def __init__(
        self,
        text: str,
        label: Label,
        confidence: float,
        label_probabilities: dict[Label, float],
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

class SequenceLabelingResult:
    """Result of CRF sequence labeling.

    Attributes:
        labeled_lines: Tuple of LabeledLine objects, one per input line.
        sequence_probability: Probability of the entire predicted label sequence.
    """
    labeled_lines: tuple[LabeledLine, ...]
    sequence_probability: float
    def __init__(
        self, labeled_lines: tuple[LabeledLine, ...], sequence_probability: float
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

class CRFSequenceLabeler:
    """CRF-based sequence labeler for email line classification.

    Uses python-crfsuite for fast, lightweight CRF inference.
    Supports loading pre-trained models and making predictions
    with per-label marginal probabilities.
    """
    def __init__(
        self, model_path: Path | str | None = None, use_default: bool = True
    ) -> None:
        """Initialize the CRF labeler.

        Args:
            model_path: Path to a trained CRF model file.
                If None and use_default is True, loads the bundled model.
            use_default: If True and model_path is None, load the bundled model.
                Set to False to create an unloaded labeler.
        """
        ...
    def load_model(self, model_path: Path | str) -> None:
        """Load a trained CRF model.

        Args:
            model_path: Path to the model file.

        Raises:
            FileNotFoundError: If the model file does not exist.
            RuntimeError: If the model cannot be loaded.
        """
        ...
    @property
    def is_loaded(self) -> bool:
        """Whether a model is currently loaded."""
        ...
    @property
    def labels(self) -> tuple[str, ...]:
        """Get the labels known by the loaded model."""
        ...
    def predict(
        self, extracted: ExtractedFeatures, texts: tuple[str, ...]
    ) -> SequenceLabelingResult:
        """Predict labels for email lines.

        Args:
            extracted: Feature extraction result from FeatureExtractor.
            texts: Original text lines corresponding to the features.

        Returns:
            SequenceLabelingResult with labeled lines and probabilities.

        Raises:
            RuntimeError: If no model is loaded.
        """
        ...

class CRFTrainer:
    """Trainer for CRF sequence labeling models.

    Wraps python-crfsuite's Trainer with a convenient interface
    for training on labeled email data.
    """
    def __init__(
        self,
        algorithm: str = "lbfgs",
        c1: float = 0.1,
        c2: float = 0.1,
        max_iterations: int = 100,
        all_possible_transitions: bool = True,
    ) -> None:
        """Initialize the CRF trainer.

        Args:
            algorithm: Training algorithm. Options: 'lbfgs', 'l2sgd', 'ap', 'pa', 'arow'.
            c1: L1 regularization coefficient.
            c2: L2 regularization coefficient.
            max_iterations: Maximum number of training iterations.
            all_possible_transitions: Include transitions not in training data.
        """
        ...
    def add_sequence(
        self,
        extracted: ExtractedFeatures,
        texts: tuple[str, ...],
        labels: tuple[Label, ...],
    ) -> None:
        """Add a training sequence.

        Args:
            extracted: Feature extraction result from FeatureExtractor.
            texts: Original text lines.
            labels: Ground truth labels for each line.

        Raises:
            ValueError: If the number of labels doesn't match the number of lines.
        """
        ...
    def train(self, output_path: Path | str) -> None:
        """Train the model and save to file.

        Args:
            output_path: Path to save the trained model.
        """
        ...
    def get_params(self) -> dict[str, str]:
        """Get current training parameters."""
        ...
