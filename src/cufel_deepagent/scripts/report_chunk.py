# ======================================
# 1. 环境依赖（需提前安装）
# pip install unstructured[pdf] chromadb langchain sentence-transformers python-dotenv
# ======================================
import os
from dotenv import load_dotenv
from unstructured.partition.pdf import partition_pdf
from unstructured.chunking.title import chunk_by_title
from unstructured.documents.elements import Table, Text
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction,OllamaEmbeddingFunction
from langchain_ollama import OllamaEmbeddings
from datetime import datetime
# ======================================
# 2. 基础配置（最小化参数，适配金融财报场景）
# ======================================
# load_dotenv()  # 加载环境变量（可选，用于配置API/模型路径）
# 核心配置
CONFIG = {
    "pdf_path": "D:\\浏览器下载\\研报\\汽车车企年报\\比亚迪24年报_pages\\比亚迪24年报_8.pdf",  # 财报PDF路径
    "chroma_persist_dir": "D:\\porjects\\deepagent\\src\\cufel_deepagent\\chromadb_store",  # 向量库本地持久化路径
    "collection_name": "company_financial_reports",  # 向量集合名称
    "chunk_max_characters": 1000,  # 单chunk最大字符数（适配财报文本密度）
    "chunk_overlap": 100,  # chunk重叠字符（避免关键财务数据被拆分）
    "embedding_model": "BAAI/bge-small-zh-v1.5"  # 开源中文嵌入模型（适配金融术语）
}


JSON_PATH = r"D:\\projects\deepagent\\project_datas\\car_embedded\\BYD_24_AR_chunks.json"
CHROMA_PATH = r"D:\\projects\deepagent\\chroma_db"
# ======================================
# 3. 核心函数：PDF财报读取+分块（Unstructured）
# ======================================
import json
from pathlib import Path

def load_and_chunk_financial_report(pdf_path: str) -> list[dict]:
    """
    读取金融财报PDF，用Unstructured按标题/类型分块，保留表格/文本区分
    返回格式：[{"text": 文本内容, "metadata": {"type": 内容类型, "page": 页码, ...}}]
    """
    # Step 1: 读取PDF，自动识别文本/表格/标题等元素（Unstructured核心能力）
    elements = partition_pdf(
        filename=pdf_path,
        strategy="hi_res",                      # 核心：布局感知 + 表格结构提取
        infer_table_structure=True,             # 必须，保留HTML表格
        languages=["chi_sim"],                  # 中文OCR和分区支持
        hi_res_model_name=None,                 # 默认yolox即可，速度与精度平衡
        extract_images_in_pdf=False,            # 年报不需要提取图片
        extract_image_block_types=None,         # 同上
        starting_page_number=1,
    )

    # Step 2: 按字符数二次切分（避免单chunk过长，适配嵌入模型限制） 是否有机会进行优化？
    chunks = chunk_by_title(
        elements,
        max_characters=CONFIG["chunk_max_characters"],
        overlap=CONFIG["chunk_overlap"],
    )

    # Step 3: 格式化chunk，添加财报专属元数据（便于RAG精准检索）
    formatted_chunks = []
    for chunk in chunks:
        # 区分内容类型（表格/文本），财报表格是核心财务数据
        content_type = "table" if isinstance(chunk, Table) else "text"
        # 提取元数据（页码、内容类型、财报类型）
        metadata = {
            "type": content_type,
            "page_number": chunk.metadata.page_number,  # Unstructured自动提取页码
            "company_name": "默认公司名（可从PDF文件名/内容解析）",  # 可扩展
            "report_year": 2024,  # 可扩展：从PDF解析财报年份
            "source": pdf_path  # 溯源PDF路径
        } # 这里面的需要进行修改
        # 表格转文本（便于嵌入，保留结构化信息）
        chunk_text = chunk.text if content_type == "text" else f"表格内容：{chunk.text}"
        
        formatted_chunks.append({
            "text": chunk_text.strip(),
            "metadata": metadata
        })
    pdf_file = Path(pdf_path)
    save_path = pdf_file.parent / f"{pdf_file.stem}_chunks.json"
    
    # 2. 保存chunk结果为JSON文件（格式化输出，便于阅读）
    try:
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(
                formatted_chunks,
                f,
                ensure_ascii=False,  # 保留中文
                indent=2  # 格式化缩进
            )
        print(f"✅ Chunk结果已保存至：{save_path}")
    except Exception as e:
        print(f"⚠️ 保存Chunk结果失败：{e}")
    # ========== 新增结束 ==========
    
    return formatted_chunks



# ======================================
# 4. 核心函数：向量嵌入+存入ChromaDB
# ======================================
"""
def embed_and_store_chunks(chunks: list[dict], collection_name: str) -> None:
    
    将分块后的财报内容嵌入向量，存入本地ChromaDB（持久化）
    
    # Step 1: 初始化ChromaDB客户端（持久化到本地目录）
    client = chromadb.PersistentClient(path=CONFIG["chroma_persist_dir"])
    
    # Step 2: 初始化嵌入函数（适配中文金融术语）
    embedding_fn = OllamaEmbeddingFunction(
        url="http://localhost:11434/api/embeddings", # 本地 Ollama 默认地址
        model_name="qwen3-emb:4b",
    )

    
    # Step 3: 创建/获取向量集合（已存在则复用）
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_fn,  # 绑定嵌入模型
        metadata={"description": "金融财报分块向量库（用于公司研究报告RAG）"}
    )

    # Step 4: 批量插入向量（最小化批量逻辑）
    ids = [f"chunk_{i}" for i in range(len(chunks))]  # 唯一ID
    texts = [chunk["text"] for chunk in chunks] 
    metadatas = [chunk["metadata"] for chunk in chunks]

    # 插入ChromaDB（自动完成嵌入+存储）
    collection.upsert(
        ids=ids,
        documents=texts,
        metadatas=metadatas
    )

    print(f"✅ 成功存入 {len(chunks)} 个财报chunk到ChromaDB，集合名：{collection_name}")
"""

def process_batch(collection, batch_chunks, start_id):
    """处理一小批数据并存入 Chroma,client 以及 collection在函数外的本包内实例化"""
    try:
        ids = [f"byd_24_{start_id + i}" for i in range(len(batch_chunks))]
        texts = [chunk["text"] for chunk in batch_chunks]
        metadatas = [chunk["metadata"] for chunk in batch_chunks]
        
        # 这一步会内部调用 OllamaEmbeddingFunction 进行向量化
        collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )
        return len(batch_chunks)
    except Exception as e:
        print(f"❌ 批次起始 ID {start_id} 处理失败: {e}")
        return 0

"""
# ======================================
# 5. 核心函数：测试RAG检索（验证最小流程闭环）
# ======================================
def test_rag_retrieval(query: str, top_k: int = 3) -> list[dict]:
    
    测试检索：输入财务问题（如"资产负债率"），返回最相关的chunk
   
    # 初始化客户端+集合
    client = chromadb.PersistentClient(path=CONFIG["chroma_persist_dir"])
    collection = client.get_collection(
        name=CONFIG["collection_name"],
        embedding_function=SentenceTransformerEmbeddingFunction(model_name=CONFIG["embedding_model"])
    )

    # 检索相关chunk
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where={"type": "table"}  # 可筛选：只检索表格（适配财务指标查询）
    )

    # 格式化检索结果
    retrieved_chunks = []
    for i in range(top_k):
        retrieved_chunks.append({
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i]  # 相似度（越小越相关）
        })
    
    return retrieved_chunks

# ======================================
# 6. 主流程执行（最小化调用）
# ======================================



if __name__ == "__main__":
    # Step 1: 读取PDF并分块
    print("🔍 开始读取并分块财报PDF...")
    financial_chunks = load_and_chunk_financial_report(CONFIG["pdf_path"])
    
    # Step 2: 嵌入并存储到ChromaDB
    print("📊 开始嵌入并存储chunk到向量库...")
    embed_and_store_chunks(financial_chunks, CONFIG["collection_name"])
    
    # Step 3: 测试检索（验证流程）
    print("🧪 测试RAG检索...")
    test_query = "2024年资产负债率"  # 典型的财报查询需求
    retrieved = test_rag_retrieval(test_query)
    for idx, chunk in enumerate(retrieved):
        print(f"\n【检索结果 {idx+1}】")
        print(f"相似度：{chunk['distance']:.4f}")
        print(f"内容类型：{chunk['metadata']['type']}")
        print(f"页码：{chunk['metadata']['page_number']}")
        print(f"内容：{chunk['text'][:200]}...")  # 截断显示

"""

# 如果你要测试存Chroma，取消下面两行注释并 pip install chromadb sentence-transformers
# from langchain.vectorstores import Chroma
# from langchain.embeddings import HuggingFaceEmbeddings
import concurrent.futures 

def main():
    
    # 1. 加载 JSON 数据
    print(f"[{datetime.now()}] 正在读取 JSON 文件...")
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        full_data = json.load(f)
    
    # 2. 选取 200 到 500 的片段进行测试
    # 注意：Python 切片左闭右开，200:501 代表索引 200 到 500
    target_chunks = full_data
    total_chunks = len(target_chunks)
    print(f"已截取测试数据：从 Index 200 到 500，共 {total_chunks} 条。")

    # 3. 初始化库
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    embedding_fn = OllamaEmbeddingFunction(
        model_name="qwen3-emb:4b", # 确保本地 ollama 已 pull 此模型
        url="http://localhost:11434/api/embeddings"
    )
    
    collection = client.get_or_create_collection(
        name="corp_report_byd",
        embedding_function=embedding_fn
    )

    # 4. 多线程并发配置
    max_threads = 2  # 针对 5060 8GB 优化的线程数
    batch_size = 8   # 每批处理 10 条，避免单词 API 请求过大
    
    # 将 301 条数据切分为 31 个 batch
    batches = [target_chunks[i:i + batch_size] for i in range(0, total_chunks, batch_size)]
    
    print(f"开始入库，并发线程数: {max_threads}，总批数: {len(batches)}")
    start_time = datetime.now()

    # 5. 使用线程池并行执行
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        # 提交所有任务
        futures = {
            executor.submit(process_batch, collection, batches[i], 200 + i*batch_size): i 
            for i in range(len(batches))  # 这个submit里面的参数是提交给这个process_batch这个工具参数的
        } # 把所有的这json的dicts分成多个batch再对里面进行操作
        
        for future in concurrent.futures.as_completed(futures):
            batch_num = futures[future]
            res = future.result()
            completed += res
            if completed % 50 == 0 or completed == total_chunks:
                print(f"进度：已完成 {completed}/{total_chunks} 条向量化...")

    duration = (datetime.now() - start_time).total_seconds()
    print("-" * 50)
    print(f"✅ 任务完成！")
    print(f"总耗时: {duration:.2f} 秒")
    print(f"平均速度: {total_chunks / duration:.2f} 条/秒")
    print("-" * 50)
    
    # 可选：测试存入Chroma（注释掉，需要安装chromadb和embedding模型）
    # embeddings = HuggingFaceEmbeddings(model_name=CONFIG["embedding_model"])
    # vectorstore = Chroma.from_texts(
    #     texts=[c["text"] for c in chunks],
    #     embedding=embeddings,
    #     metadatas=[c["metadata"] for c in chunks],
    #     persist_directory=CONFIG["chroma_persist_dir"],
    #     collection_name=CONFIG["collection_name"]
    # )
    # vectorstore.persist()
    # print(f"已存入Chroma集合: {CONFIG['collection_name']}")

if __name__ == "__main__":
    main()