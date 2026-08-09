import logging
import os
import uuid

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from chromadb.config import Settings
from utils.config_handler import chroma_conf
from model.factory import embed_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.path_tool import get_abs_path
from utils.file_handler import docx_loader, get_file_md5_hex, listdir_with_allowed_type, md_loader, pdf_loader, txt_loader
from utils.logger_handler import logger
from rag.hybrid_retriever import metadata_allowed


logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("chromadb.telemetry.product").setLevel(logging.CRITICAL)
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)


class VectorStoreService:
    def __init__(self):
        # Chroma 持久化目录。
        # 向量库不是存在 MySQL 里，而是存在 Chroma 自己的目录中。
        persist_directory = get_abs_path(chroma_conf["persist_directory"])
        os.makedirs(persist_directory, exist_ok=True)

        client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )

        self.vector_store = Chroma(
            # collection 可以理解成 Chroma 里的“表/集合”。
            # embedding_function 会把文本转成向量，便于相似度检索。
            collection_name=chroma_conf["collection_name"],
            embedding_function=embed_model,
            persist_directory=persist_directory,
            client=client,
        )

        self.spliter = RecursiveCharacterTextSplitter(
            # 文档不能整篇直接塞进向量库，否则检索粒度太粗。
            # TextSplitter 会把长文档切成 chunk，并保留一定重叠，避免上下文断裂。
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

    def get_retriever(self, k: int | None = None):
        target_k = k if isinstance(k, int) and k > 0 else chroma_conf["k"]
        return self.vector_store.as_retriever(search_kwargs={"k": target_k})

    def similarity_search(self, query: str, k: int = 12, filters: dict | None = None) -> list[Document]:
        # Chroma 的复杂权限 where 在不同版本间语法差异较大，因此先扩大召回，
        # 再在应用层执行严格过滤。正式大规模部署时可换成原生 tenant filter。
        documents = self.vector_store.similarity_search(query, k=max(k * 3, k))
        return [doc for doc in documents if metadata_allowed(doc.metadata or {}, filters)][:k]

    def list_documents(self, filters: dict | None = None, limit: int = 2000) -> list[Document]:
        payload = self.vector_store.get(include=["documents", "metadatas"], limit=limit)
        texts = payload.get("documents") or []
        metadatas = payload.get("metadatas") or []
        documents = []
        for index, text in enumerate(texts):
            metadata = metadatas[index] if index < len(metadatas) else {}
            if metadata_allowed(metadata or {}, filters):
                documents.append(Document(page_content=text or "", metadata=metadata or {}))
        return documents

    def load_document(self, metadata_context: dict | None = None, paths: list[str] | None = None):
        """
        从数据文件夹内读取数据文件，转为向量存入向量库
        要计算文件的MD5做去重
        :return: None
        """

        def check_md5_hex(dedupe_key: str):
            # MD5 去重：
            # 同一个文件重复导入会造成知识库重复片段，影响检索质量。
            # 这里用 visibility + scope + 文件 md5 作为 dedupe_key，
            # 既避免重复，也能区分不同用户/组织的私有知识库。
            if not os.path.exists(get_abs_path(chroma_conf["md5_hex_store"])):
                # 创建文件
                open(get_abs_path(chroma_conf["md5_hex_store"]), "w", encoding="utf-8").close()
                return False            # md5 没处理过

            with open(get_abs_path(chroma_conf["md5_hex_store"]), "r", encoding="utf-8") as f:
                for line in f.readlines():
                    line = line.strip()
                    if line == dedupe_key:
                        return True     # md5 处理过

                return False            # md5 没处理过

        def save_md5_hex(dedupe_key: str):
            with open(get_abs_path(chroma_conf["md5_hex_store"]), "a", encoding="utf-8") as f:
                f.write(dedupe_key + "\n")

        def get_file_documents(read_path: str):
            # 不同文件格式有不同解析器，但最后都会统一转成 LangChain Document。
            if read_path.endswith(".txt"):
                return txt_loader(read_path)

            if read_path.endswith(".md"):
                return md_loader(read_path)

            if read_path.endswith(".pdf"):
                return pdf_loader(read_path)

            if read_path.endswith(".docx"):
                return docx_loader(read_path)

            return []

        load_results: list[dict] = []
        allowed_files_path: list[str] = paths or listdir_with_allowed_type(
            get_abs_path(chroma_conf["data_path"]), tuple(chroma_conf["allow_knowledge_file_type"])
        )

        for path in allowed_files_path:
            # 获取文件的MD5
            md5_hex = get_file_md5_hex(path)
            context = {key: value for key, value in (metadata_context or {}).items() if value not in {None, ""}}
            visibility = context.get("visibility") or ("private" if context else "public")
            scope = context.get("organization_id") if visibility == "organization" else context.get("user_id")
            dedupe_key = f"{visibility}:{scope or 'global'}:{md5_hex}"

            if check_md5_hex(dedupe_key):
                logger.info(f"[加载知识库]{path}内容已经存在知识库内，跳过")
                load_results.append({"path": path, "checksum": md5_hex, "status": "duplicate", "chunk_count": 0})
                continue

            try:
                documents: list[Document] = get_file_documents(path)

                if not documents:
                    logger.warning(f"[加载知识库]{path}内没有有效文本内容，跳过")
                    continue

                # 文本切片：长文档 -> 多个小 Document chunk。
                split_document: list[Document] = self.spliter.split_documents(documents)

                if not split_document:
                    logger.warning(f"[加载知识库]{path}分片后没有有效文本内容，跳过")
                    continue

                # 每个切片附带可引用、可隔离、可追踪的元数据。
                # metadata 后续会用于：
                # - 权限过滤：只能检索当前用户/组织可访问的文档。
                # - 引用展示：报告里能显示来源文件和 chunk 编号。
                # - 去重追踪：知道每个 chunk 来自哪个文件。
                source_name = os.path.basename(path)
                chunk_ids = []
                for index, document in enumerate(split_document):
                    chunk_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{dedupe_key}:{index}").hex
                    document.metadata = {
                        **(document.metadata or {}),
                        **context,
                        "source": source_name,
                        "filename": source_name,
                        "file_md5": md5_hex,
                        "chunk_index": index,
                        "chunk_id": chunk_id,
                        "visibility": visibility,
                    }
                    chunk_ids.append(chunk_id)

                self.vector_store.add_documents(split_document, ids=chunk_ids)

                # 记录这个已经处理好的文件的md5，避免下次重复加载
                save_md5_hex(dedupe_key)
                load_results.append(
                    {"path": path, "checksum": md5_hex, "status": "ready", "chunk_count": len(split_document)}
                )

                logger.info(f"[加载知识库]{path} 内容加载成功")
            except Exception as e:
                # exc_info为True会记录详细的报错堆栈，如果为False仅记录报错信息本身
                logger.error(f"[加载知识库]{path}加载失败：{str(e)}", exc_info=True)
                continue
        return load_results


if __name__ == '__main__':
    vs = VectorStoreService()

    vs.load_document()

    retriever = vs.get_retriever()

    res = retriever.invoke("线程")
    for r in res:
        print(r.page_content)
        print("-"*20)
