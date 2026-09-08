"""Create a deterministic TorchScript classifier and labelled test dataset."""

from pathlib import Path

import numpy as np
import torch


class TinyClassifier(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = torch.nn.Sequential(
            torch.nn.Linear(2, 16),
            torch.nn.ReLU(),
            torch.nn.Linear(16, 2),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)


def main() -> None:
    torch.manual_seed(7)
    rng = np.random.default_rng(7)
    x = rng.uniform(0.0, 1.0, size=(1000, 2)).astype(np.float32)
    y = (x[:, 0] + x[:, 1] > 1.0).astype(np.int64)
    model = TinyClassifier()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.03)
    features = torch.from_numpy(x)
    labels = torch.from_numpy(y)
    for _ in range(180):
        optimizer.zero_grad()
        loss = torch.nn.functional.cross_entropy(model(features), labels)
        loss.backward()
        optimizer.step()

    destination = Path("examples")
    (destination / "models").mkdir(parents=True, exist_ok=True)
    (destination / "data").mkdir(parents=True, exist_ok=True)
    scripted = torch.jit.script(model.eval())
    scripted.save(str(destination / "models" / "tiny_classifier.pt"))
    np.savez(destination / "data" / "tiny_classifier_test.npz", x=x[:200], y=y[:200])
    print("Created sample model and dataset under examples/")


if __name__ == "__main__":
    main()

