from __future__ import annotations

import json
import os
import urllib.request

from llminator.config.models import LLMTargetConfig
from llminator.targets.base import LLMTarget


class HTTPLLMTarget(LLMTarget):
    def __init__(self, config: LLMTargetConfig) -> None:
        super().__init__(config.name)
        self.config = config

    def generate(self, prompt: str, **kwargs: object) -> str:
        timeout = float(kwargs.pop("timeout", 120))
        if self.config.provider == "ollama":
            temperature = kwargs.pop("temperature", 0)
            max_tokens = kwargs.pop("max_tokens", 256)
            payload = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
                **kwargs,
            }
        else:
            payload = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": prompt}],
                **kwargs,
            }
        headers = {"Content-Type": "application/json"}
        if self.config.api_key_env:
            token = os.environ.get(self.config.api_key_env)
            if not token:
                raise RuntimeError(f"missing environment variable {self.config.api_key_env}")
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            str(self.config.endpoint),
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
        if self.config.provider == "ollama":
            return body["message"]["content"]
        return body["choices"][0]["message"]["content"]
