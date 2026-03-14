# ======================================
# 1. 环境依赖（需提前安装）
# pip install unstructured[pdf] chromadb langchain sentence-transformers python-dotenv
# ======================================
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from unstructured.partition.pdf import partition_pdf
from unstructured.chunking.title import chunk_by_title
from unstructured.documents.elements import Table
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
from datetime import datetime
import concurrent.futures

# ======================================
# 2. 基础配置（最小化参数，适配金融财报场景）
# ======================================
load_dotenv()  # 加载环境变量（可选，用于配置API/模型路径）

CONFIG = {
    "pdf_path": "D:\\浏览器下载\\研报\\汽车车企年报\\比亚迪24年报_pages\\比亚迪24年报_8.pdf",  # 财报PDF路径
    "chroma_persist_dir": "D:\\porjects\\deepagent\\src\\cufel_deepagent\\chromadb_store",  # 向量库本地持久化路径
    "collection_name": "corp_report_byd",  # 向量集合名称
    "chunk_max_characters": 1000,  # 单chunk最大字符数（适配财报文本密度）
    "chunk_overlap": 100,  # chunk重叠字符（避免关键财务数据被拆分）
    "embedding_model": "BAAI/bge-small-zh-v1.5"  # 开源中文嵌入模型（适配金融术语）
}

JSON_PATH = r"D:\\projects\deepagent\\project_datas\\car_embedded\\BYD_24_AR_chunks.json"
CHROMA_PATH = r"D:\\projects\deepagent\\chroma_db"

# ======================================
# 3. 核心函数：PDF财报读取+分块（Unstructured）
# ======================================
def load_and_chunk_financial_report(pdf_path: str) -> list[dict]:
    """
    读取金融财报PDF，用Unstructured按标题/类型分块，保留表格/文本区分
    返回格式：[{"text": 文本内容, "metadata": {"type": 内容类型, "page": 页码, ...}}]
    """
    print("🔍 开始读取并分块财报PDF...")
    
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

    # Step 2: 按字符数二次切分（避免单chunk过长，适配嵌入模型限制）
    # 优化建议：chunk_by_title不支持直接'overlap'参数，可用'new_after_n_chars'模拟overlap效果
    chunks = chunk_by_title(
        elements,
        max_characters=CONFIG["chunk_max_characters"],
        new_after_n_chars=CONFIG["chunk_max_characters"] - CONFIG["chunk_overlap"],  # 模拟overlap
        combine_text_under_n_chars=CONFIG["chunk_overlap"],  # 小段落合并
        multipage_sections=True,  # 允许跨页章节
    )

    # Step 3: 格式化chunk，添加财报专属元数据（便于RAG精准检索）
    formatted_chunks = []
    for chunk in chunks:
        # 区分内容类型（表格/文本），财报表格是核心财务数据
        # 优化建议：使用chunk.category判断更鲁棒
        content_type = "table" if chunk.category == "Table" else "text"
        
        # 提取元数据（页码、内容类型、财报类型）
        # 修改建议：动态从文件名解析公司名/年份
        filename = Path(pdf_path).stem
        company_name = "比亚迪" if "比亚迪" in filename else "未知公司"
        report_year = 2024  # 可进一步用正则从filename或内容提取
        metadata = {
            "type": content_type,
            "page_number": getattr(chunk.metadata, "page_number", "未知"),  # 安全提取
            "company_name": company_name,
            "report_year": report_year,
            "source": pdf_path  # 溯源PDF路径
        }
        
        # 表格转文本（便于嵌入，保留结构化信息）
        # 优化建议：优先用text_as_html保留表格结构
        chunk_text = chunk.metadata.text_as_html if content_type == "table" and hasattr(chunk.metadata, "text_as_html") else chunk.text
        
        formatted_chunks.append({
            "text": chunk_text.strip(),
            "metadata": metadata
        })
    
    # Step 4: 保存chunk结果为JSON文件（格式化输出，便于阅读）
    pdf_file = Path(pdf_path)
    save_path = pdf_file.parent / f"{pdf_file.stem}_chunks.json"
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
    
    return formatted_chunks

# ======================================
# 4. 核心函数：向量嵌入+存入ChromaDB
# ======================================
def embed_and_store_chunks(chunks: list[dict], collection_name: str) -> None:
    """
    将分块后的财报内容嵌入向量，存入本地ChromaDB（持久化）
    """
    print("📊 开始嵌入并存储chunk到向量库...")
    
    # Step 1: 初始化ChromaDB客户端（持久化到本地目录）
    client = chromadb.PersistentClient(path=CONFIG["chroma_persist_dir"])
    
    # Step 2: 初始化嵌入函数（适配中文金融术语）
    embedding_fn = OllamaEmbeddingFunction(
        url="http://localhost:11434/api/embeddings",  # 本地 Ollama 默认地址
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

# ======================================
# 5. 整合函数：从JSON加载并多线程嵌入Chroma
# ======================================
def process_full_report(json_path: str, chroma_path: str, collection_name: str = "corp_report_byd"):
    """
    整合版：加载财报JSON、多线程分批向量化并入库Chroma
    参数：
        json_path: JSON文件路径
        chroma_path: Chroma数据库存储路径
        collection_name: Chroma集合名
    """
    # ===================== 1. 加载JSON数据 =====================
    print(f"[{datetime.now()}] 正在读取 JSON 文件...")
    with open(json_path, 'r', encoding='utf-8') as f:
        full_data = json.load(f)
    
    total_chunks = len(full_data)
    print(f"已加载全部数据，共 {total_chunks} 条。")

    # ===================== 2. 初始化Chroma =====================
    client = chromadb.PersistentClient(path=chroma_path)
    embedding_fn = OllamaEmbeddingFunction(
        model_name="qwen3-emb:4b",  # 确保本地ollama已pull此模型
        url="http://localhost:11434/api/embeddings"
    )
    
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_fn
    )

    # ===================== 3. 内部批次处理函数 =====================
    def _process_batch(batch_chunks, start_id):
        """内部函数：处理一小批数据并存入Chroma"""
        try:
            ids = [f"byd_24_{start_id + i}" for i in range(len(batch_chunks))]
            texts = [chunk["text"] for chunk in batch_chunks]
            metadatas = [chunk["metadata"] for chunk in batch_chunks]
            
            # 向量化+入库
            collection.upsert(
                ids=ids,
                documents=texts,
                metadatas=metadatas
            )
            return len(batch_chunks)
        except Exception as e:
            print(f"❌ 批次起始 ID {start_id} 处理失败: {e}")
            return 0

    # ===================== 4. 多线程配置 =====================
    max_threads = 2  # 针对5060 8GB优化的线程数
    batch_size = 8   # 每批处理8条，避免单次API请求过大
    
    # 切分批次
    batches = [full_data[i:i + batch_size] for i in range(0, total_chunks, batch_size)]
    
    print(f"开始入库，并发线程数: {max_threads}，总批数: {len(batches)}")
    start_time = datetime.now()

    # ===================== 5. 多线程执行 =====================
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        # 提交所有批次任务
        futures = {
            executor.submit(_process_batch, batches[i], 200 + i*batch_size): i 
            for i in range(len(batches))
        }
        
        # 遍历完成的任务，统计进度
        for future in concurrent.futures.as_completed(futures):
            batch_num = futures[future]
            res = future.result()
            completed += res
            if completed % 50 == 0 or completed == total_chunks:
                print(f"进度：已完成 {completed}/{total_chunks} 条向量化...")

    # ===================== 6. 统计耗时 =====================
    duration = (datetime.now() - start_time).total_seconds()
    print("-" * 50)
    print(f"✅ 任务完成！")
    print(f"总耗时: {duration:.2f} 秒")
    print(f"平均速度: {total_chunks / duration:.2f} 条/秒" if duration > 0 else "N/A")
    print("-" * 50)

# ======================================
# 5. 核心函数：测试RAG检索（验证最小流程闭环）
# ======================================
# ======================================
# 6. 抽取出的查询函数（单独模块化，便于后续开发成Agent Tool）
# ======================================


# ======================================
# 6. 主流程执行（最小化调用）
# ======================================
# ======================================
# 7. 主流程执行（最小化调用：chunk + embed）
# ======================================
def main():
    """
    主函数：从PDF路径执行chunk和embed流程
    - 先chunk PDF并保存JSON
    - 再从JSON加载并嵌入Chroma（支持多线程）
    """
    pdf_path = CONFIG["pdf_path"]
    
    # Step 1: 读取PDF并分块，保存JSON
    financial_chunks = load_and_chunk_financial_report(pdf_path) 
    # 不用再进行调用的原因即是这个process_full_report 仅仅是需要对这个数据库里面提取出来再进行embed
# 后面可对这两个板块进行优化
    # Step 2: 从JSON嵌入并存储到ChromaDB（多线程）
    process_full_report(JSON_PATH, CHROMA_PATH, CONFIG["collection_name"])

if __name__ == "__main__":
    main()