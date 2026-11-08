"""Pinned offline embeddings. Importing Memora never initializes model providers."""

import math
import os
from threading import Lock


class Embedder:
    def __init__(self, config):
        self.config = config
        self.model = None
        self.lock = Lock()

    def __call__(self, text):
        with self.lock:
            if self.model is None:
                os.environ["HF_HUB_OFFLINE"] = "1"
                os.environ["TRANSFORMERS_OFFLINE"] = "1"
                os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(
                    self.config.model,
                    revision=self.config.revision,
                    local_files_only=True,
                    trust_remote_code=False,
                )
            values = self.model.encode(text, normalize_embeddings=True).tolist()
        if len(values) != self.config.dimension or not all(
            math.isfinite(v) for v in values
        ):
            raise ValueError(
                "Embedding dimension or values do not match the configured model."
            )
        return values
