"""Create an intentionally adversarially fragile TorchScript classifier.

This fixture is for validating LLMinator itself. It is not a production model.
All evaluation samples are placed close enough to the model's decision boundary
that an FGSM perturbation with epsilon 0.03 should flip their predictions.
"""

from pathlib import Path

import numpy as np
import torch


class VulnerableClassifier(torch.nn.Module):
    """A two-feature linear classifier with a boundary at x[:, 0] == 0.5."""

    def __init__(self) -> None:
        super().__init__()
        self.classifier = torch.nn.Linear(2, 2)
        with torch.no_grad():
            self.classifier.weight.copy_(
                torch.tensor([[-8.0, 0.0], [8.0, 0.0]], dtype=torch.float32)
            )
            self.classifier.bias.copy_(
                torch.tensor([4.0, -4.0], dtype=torch.float32)
            )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.classifier(inputs)


def main() -> None:
    rng = np.random.default_rng(13)
    sample_count = 200
    labels = np.arange(sample_count, dtype=np.int64) % 2

    # Correctly classified, but only 0.02 away from the decision boundary.
    features = np.empty((sample_count, 2), dtype=np.float32)
    features[:, 0] = np.where(labels == 0, 0.48, 0.52)
    features[:, 1] = rng.uniform(0.0, 1.0, size=sample_count)

    destination = Path("examples")
    model_path = destination / "models" / "vulnerable_classifier.pt"
    dataset_path = destination / "data" / "vulnerable_classifier_test.npz"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)

    scripted = torch.jit.script(VulnerableClassifier().eval())
    scripted.save(str(model_path))
    np.savez(dataset_path, x=features, y=labels)

    print(f"Created intentionally vulnerable model: {model_path}")
    print(f"Created labelled evaluation data: {dataset_path}")


if __name__ == "__main__":
    main()
