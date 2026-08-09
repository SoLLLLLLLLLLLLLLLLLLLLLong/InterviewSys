"""
总结服务类：用户提问，搜索参考资料，将提问和参考资料提交给模型，让模型总结回复
"""
from typing import Iterator

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from model.factory import chat_model
from rag.query_optimizer import QueryOptimizer
from rag.rerank_service import RerankService
from rag.self_rag import SelfRAGRouter
from utils.config_handler import chroma_conf, rag_conf
from utils.prompt_loader import load_rag_prompts
from rag.vector_store import VectorStoreService
from rag.hybrid_retriever import HybridRetriever


def print_prompt(prompt):
    print("=" * 20)
    print(prompt.to_string())
    print("=" * 20)
    return prompt


class RagSummarizeService(object):
    def __init__(self):
        # RAG 服务总入口：
        # 1. VectorStoreService 负责 Chroma 向量库。
        # 2. QueryOptimizer 负责根据历史上下文改写/扩展查询。
        # 3. HybridRetriever 同时做向量召回和关键词召回。
        # 4. RerankService 可选，用于把召回结果重新排序。
        # 5. PromptTemplate + chat_model 负责最终生成答案。
        self.vector_store = VectorStoreService()
        self.enable_rerank = bool(rag_conf.get("enable_rerank", False))
        self.recall_k = int(rag_conf.get("rerank_recall_k", 12))
        self.final_k = int(chroma_conf.get("k", 3))
        self.query_optimizer = QueryOptimizer()
        self.self_rag_router = SelfRAGRouter()
        retriever_k = self.recall_k if self.enable_rerank else self.final_k
        self.retriever = self.vector_store.get_retriever(k=retriever_k)
        self.rerank_service = RerankService() if self.enable_rerank else None
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()
        self.hybrid_retriever = HybridRetriever(self.vector_store)

    def _init_chain(self):
        chain = self.prompt_template | self.model | StrOutputParser()
        return chain

    def _retrieve_with_multi_recall(self, query: str, history=None, filters=None) -> list[Document]:
        # 多路召回：
        # 用户问题可能表达得很口语，直接检索容易漏掉资料。
        # 所以先生成多个 recall query，再分别检索，最后合并去重。
        recall_queries = self.query_optimizer.build_recall_queries(query, history)
        docs_groups = []
        for recall_query in recall_queries:
            try:
                docs = self.hybrid_retriever.retrieve(
                    recall_query,
                    vector_k=self.recall_k,
                    keyword_k=int(rag_conf.get("keyword_recall_k", 8)),
                    filters=filters,
                )
                docs_groups.append(docs)
            except Exception:
                continue
        return self.query_optimizer.merge_documents(docs_groups)

    def retriever_docs(self, query: str, history=None, filters=None) -> list[Document]:
        # RAG 检索主流程：
        # 1. 根据历史上下文优化查询。
        # 2. 混合检索召回候选文档。
        # 3. Self-RAG 判断是否需要反思/降级。
        # 4. 如果开启 rerank，就对候选文档精排。
        optimized_query = self.query_optimizer.get_rerank_query(query, history)
        docs = self._retrieve_with_multi_recall(query, history, filters)
        if not docs:
            try:
                docs = self.hybrid_retriever.retrieve(
                    optimized_query,
                    vector_k=self.recall_k,
                    keyword_k=int(rag_conf.get("keyword_recall_k", 8)),
                    filters=filters,
                )
            except Exception:
                docs = []

        if self.self_rag_router.enabled:
            decision = self.self_rag_router.should_route(optimized_query, docs)
            if decision.should_self_reflect:
                return docs[: self.final_k]

        if not self.enable_rerank or not self.rerank_service:
            return docs[: self.final_k]
        return self.rerank_service.rerank(optimized_query, docs)

    def search_with_citations(self, query: str, history=None, filters=None) -> dict:
        # 带引用的检索结果。
        # citations 会返回给前端或报告，用于说明“答案参考了哪些文档片段”。
        documents = self.retriever_docs(query, history, filters)
        citations = []
        for index, document in enumerate(documents, start=1):
            metadata = document.metadata or {}
            citations.append(
                {
                    "index": index,
                    "source": metadata.get("source") or metadata.get("filename") or "知识库文档",
                    "chunk_id": metadata.get("chunk_id") or f"chunk-{index}",
                    "chunk_index": metadata.get("chunk_index", index - 1),
                    "content": document.page_content[:500],
                    "score": metadata.get("rerank_score") or metadata.get("rrf_score"),
                }
            )
        return {"documents": documents, "citations": citations}

    def _build_context(self, query: str, history=None) -> str:
        # 把检索到的 Document 拼成模型可读的上下文。
        # 最终 Prompt = 用户问题 + 检索资料，因此模型不是纯凭记忆回答。
        context_docs = self.retriever_docs(query, history)
        context = ""
        counter = 0
        for doc in context_docs:
            counter += 1
            context += f"【参考资料{counter}】: 参考资料：{doc.page_content} | 参考元数据：{doc.metadata}\n"
        return context

    def rag_summarize(self, query: str, history=None) -> str:
        context = self._build_context(query, history)
        return self.chain.invoke({"input": query, "context": context})

    def rag_summarize_stream(self, query: str, history=None) -> Iterator[str]:
        context = self._build_context(query, history)
        for chunk in self.chain.stream({"input": query, "context": context}):
            if chunk:
                yield str(chunk)


if __name__ == '__main__':
    rag = RagSummarizeService()

    print(rag.rag_summarize("什么是线程？"))
