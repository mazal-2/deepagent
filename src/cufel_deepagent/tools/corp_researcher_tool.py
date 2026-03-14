from langchain.tools import tool
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
from typing import List, Dict, Any
import re

# ======================================
# 配置（建议移到环境变量或配置文件中）
# ======================================
CHROMA_PATH = "D:\\projects\\deepagent\\chroma_db"
CHROMA_COLLECTION_NAME = "corp_report_byd"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
OLLAMA_EMBED_MODEL = "qwen3-emb:4b"


@tool
def rag_retrieve(
    query: str,
    top_k: int = 5,
    min_score_threshold: float = 0.45,   # 可调，过滤掉太不相关的结果
    prefer_table: bool = False           # 是否优先返回表格 chunk（财务指标查询时很有用）
) -> List[Dict[str, Any]]:
    """
    从比亚迪2024年报向量库中检索最相关的 chunk。

    参数:
        query: 检索问题，例如 "比亚迪2024年的资产负债率是多少？"
        top_k: 返回前几条最相关的 chunk（默认5）
        min_score_threshold: 相似度阈值，低于此值的过滤掉（默认0.45，越小越严格）
        prefer_table: 是否优先返回表格类型 chunk（适合查询具体财务数字时）

    返回:
        List[Dict]，每个元素结构示例：
        {
            "chunk_id": "byd_2024_p27_text_001",
            "text": "经营活动现金流入小计 814,817,630,000.00 ...",
            "score": 0.3453,
            "metadata": {
                "company": "比亚迪",
                "year": 2024,
                "page": 27,
                "type": "text" | "table",
                "source": "D:\\...\\比亚迪24年报_8.pdf"
            }
        }
        列表按 score 升序排列（最相关在前）
    """
    try:
        # 初始化客户端和嵌入函数
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        embedding_fn = OllamaEmbeddingFunction(
            model_name=OLLAMA_EMBED_MODEL,
            url=OLLAMA_EMBED_URL
        )
        collection = client.get_collection(
            name=CHROMA_COLLECTION_NAME,
            embedding_function=embedding_fn
        )

        # 执行检索
        results = collection.query(
            query_texts=[query],
            n_results=top_k * 2,  # 多取一点，后面过滤
            where={"type": "table"} if prefer_table else None
        )

        retrieved = []
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            if distance > min_score_threshold:
                continue  # 过滤太差的结果

            meta = results["metadatas"][0][i]
            text = results["documents"][0][i]

            # 清理 metadata 中的脏数据
            company = meta.get("company_name", "比亚迪")
            if "默认公司名" in company:
                company = "比亚迪"

            # 尝试从文件名或文本中提取更准确的信息（可选增强）
            page = meta.get("page_number")
            if isinstance(page, str):
                page = int(page) if page.isdigit() else None

            # 生成唯一 chunk_id（方便 Agent 后续引用）
            chunk_id = f"byd_2024_p{page or 'unk'}_{meta.get('type', 'unk')}_{i+1:03d}"

            item = {
                "chunk_id": chunk_id,
                "text": text.strip(),
                "score": round(float(distance), 4),
                "metadata": {
                    "company": company,
                    "year": meta.get("report_year", 2024),
                    "page": page,
                    "type": meta.get("type", "text"),
                    "source": meta.get("source", "")
                }
            }
            retrieved.append(item)

        # 按 score 升序（最相关在前）
        retrieved.sort(key=lambda x: x["score"])

        # 限制返回数量
        retrieved = retrieved[:top_k]

        return retrieved

    except Exception as e:
        error_item = {
            "chunk_id": "error",
            "text": f"检索失败：{str(e)}",
            "score": 999.0,
            "metadata": {"error": True}
        }
        return [error_item]


# ======================================
# 测试调用（开发时用）
# ======================================
"""
if __name__ == "__main__":
    
    query = "财务表现如何？"
    # query = "2024年资产负债率"
    # query = "现金流情况"
    
    results = rag_retrieve(query, top_k=8)
    
    print(f"\n查询：{query}")
    print(f"返回 {len(results)} 条结果\n")
    
    print(results)
    """
