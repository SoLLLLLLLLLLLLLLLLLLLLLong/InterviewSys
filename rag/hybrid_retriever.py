from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Sequence

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi


def tokenize(text: str) -> list[str]:
    """Small Chinese/English tokenizer suitable for a local BM25 fallback."""
    content = str(text or "").lower()
    chinese = re.findall(r"[\u4e00-\u9fff]{1,4}", content)
    latin = re.findall(r"[a-z0-9_+#.-]+", content)
    return chinese + latin


def document_key(document: Document) -> str:
    metadata = document.metadata or {}
    return str(metadata.get("chunk_id") or metadata.get("id") or hash(document.page_content))


def metadata_allowed(metadata: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    """Tenant filter: public docs are visible; private docs must match actor scope."""
    if not filters:
        return True
    visibility = metadata.get("visibility", "public")
    owner = metadata.get("user_id")
    organization = metadata.get("organization_id")
    requested_user = filters.get("user_id")
    requested_org = filters.get("organization_id")
    if visibility == "public":
        return True
    if visibility == "organization":
        return bool(requested_org) and organization == requested_org
    return bool(requested_user) and owner == requested_user


class HybridRetriever:
    """Combines vector and BM25 rankings with Reciprocal Rank Fusion."""

    def __init__(self, vector_store_service, rrf_k: int = 60) -> None:
        self.vector_store_service = vector_store_service
        self.rrf_k = rrf_k

    def retrieve(self, query: str, *, vector_k: int = 12, keyword_k: int = 12, filters=None) -> list[Document]:
        vector_docs = self.vector_store_service.similarity_search(query, k=vector_k, filters=filters)
        corpus = self.vector_store_service.list_documents(filters=filters, limit=2000)
        keyword_docs = self._bm25(query, corpus, keyword_k)
        return self._rrf([vector_docs, keyword_docs])

    def _bm25(self, query: str, documents: Sequence[Document], top_k: int) -> list[Document]:
        if not documents:
            return []
        tokenized_corpus = [tokenize(document.page_content) or [document.page_content[:20]] for document in documents]
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scores = BM25Okapi(tokenized_corpus).get_scores(query_tokens)
        ranked_indexes = sorted(range(len(scores)), key=lambda index: float(scores[index]), reverse=True)[:top_k]
        result: list[Document] = []
        for index in ranked_indexes:
            if float(scores[index]) <= 0:
                continue
            document = documents[index]
            metadata = dict(document.metadata or {})
            metadata["bm25_score"] = round(float(scores[index]), 6)
            result.append(Document(page_content=document.page_content, metadata=metadata))
        return result

    def _rrf(self, ranked_groups: Sequence[Sequence[Document]]) -> list[Document]:
        scores: dict[str, float] = defaultdict(float)
        documents: dict[str, Document] = {}
        for group in ranked_groups:
            for rank, document in enumerate(group, start=1):
                key = document_key(document)
                scores[key] += 1.0 / (self.rrf_k + rank)
                documents[key] = document
        ordered = sorted(scores, key=scores.get, reverse=True)
        output: list[Document] = []
        for key in ordered:
            document = documents[key]
            metadata = dict(document.metadata or {})
            metadata["rrf_score"] = round(scores[key], 8)
            output.append(Document(page_content=document.page_content, metadata=metadata))
        return output
