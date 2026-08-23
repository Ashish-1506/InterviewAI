from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

import faiss
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings


class LocalFallbackEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text))]


@dataclass
class QuestionBankIndex:
    settings: Any

    def _index_dir(self) -> str:
        return self.settings.faiss_index_path

    def load_or_build(self, embedding: Embeddings | None, documents: list[dict[str, Any]]):
        """Build FAISS from documents if not present; otherwise load from disk."""

        index_dir = self._index_dir()
        os.makedirs(index_dir, exist_ok=True)
        resolved_embedding = embedding or LocalFallbackEmbeddings()

        try:
            if os.path.exists(os.path.join(index_dir, "index.faiss")):
                return FAISS.load_local(index_dir, resolved_embedding, allow_dangerous_deserialization=True)
        except Exception:
            # fallthrough to rebuild
            pass

        vectorstore = FAISS.from_documents(documents, resolved_embedding)
        vectorstore.save_local(index_dir)
        return vectorstore

    def similarity_search(self, vectorstore: Any, query: str, k: int = 5, filter_fn=None):
        # filter_fn is applied post-retrieval to keep this version simple.
        docs = vectorstore.similarity_search(query, k=k)
        if filter_fn:
            docs = [d for d in docs if filter_fn(d.metadata)]
        return docs

