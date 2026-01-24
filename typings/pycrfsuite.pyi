"""Type stubs for pycrfsuite."""

from typing import Any

class Trainer:
    """CRF model trainer."""

    def __init__(self, algorithm: str = ..., verbose: bool = ...) -> None: ...
    def select(self, algorithm: str, type_: str = ...) -> None:
        """Select training algorithm."""
        ...
    def set_params(self, params: dict[str, Any]) -> None:
        """Set training parameters."""
        ...
    def get_params(self) -> dict[str, Any]:
        """Get training parameters."""
        ...
    def params(self) -> list[tuple[str, str]]:
        """Get all parameter name-value pairs."""
        ...
    def append(
        self,
        xseq: list[dict[str, str | float | bool]] | list[list[str]],
        yseq: list[str],
        group: int = ...,
    ) -> None:
        """Append a training instance.

        Args:
            xseq: Feature sequence (list of feature dicts or list of feature strings).
            yseq: Label sequence.
            group: Group ID for holdout evaluation.
        """
        ...
    def train(self, model_filename: str, holdout: int = ...) -> None:
        """Train and save model to file."""
        ...
    def clear(self) -> None:
        """Clear all training instances."""
        ...
    def help(self, param: str = ...) -> str:
        """Get help text for parameters."""
        ...


class Tagger:
    """CRF model tagger for inference."""

    def __init__(self) -> None: ...
    def open(self, filename: str) -> None:
        """Open a model file."""
        ...
    def open_inmemory(self, data: bytes) -> None:
        """Open a model from bytes."""
        ...
    def close(self) -> None:
        """Close the model."""
        ...
    def labels(self) -> list[str]:
        """Get list of labels in the model."""
        ...
    def tag(self, xseq: list[dict[str, str | float | bool]] | list[list[str]] | None = ...) -> list[str]:
        """Predict labels for a sequence.

        Args:
            xseq: Feature sequence. If None, uses sequence from set().

        Returns:
            List of predicted labels.
        """
        ...
    def set(self, xseq: list[dict[str, str | float | bool]] | list[list[str]]) -> None:
        """Set a sequence for tagging and probability queries."""
        ...
    def probability(self, yseq: list[str]) -> float:
        """Get probability of a label sequence.

        Args:
            yseq: Label sequence.

        Returns:
            Probability of the label sequence.
        """
        ...
    def marginal(self, y: str, pos: int) -> float:
        """Get marginal probability of a label at a position.

        Args:
            y: Label.
            pos: Position in the sequence.

        Returns:
            Marginal probability.
        """
        ...
    def dump(self, filename: str = ...) -> str | None:
        """Dump model information to file or return as string."""
        ...
    def info(self) -> str | bytes:
        """Get model information."""
        ...
