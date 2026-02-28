import streamlit as st
import time
import json
import re
from typing import List
import google.generativeai as genai
import PyPDF2

# ======================
# 🔐 Gemini 配置（按你要求写死）
# ======================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
MODEL_NAME = "gemini-2.5-flash"
TEMPERATURE = 0.1

# ======================
# 🌍 多语言
# ======================
LANG = {
    "zh": {
        "title": "📚 智能课程复习系统",
        "upload": "上传课程PDF（可多个，≤200MB）",
        "start": "🚀 开始分析",
        "processing": "正在分析，请稍候...",
        "done": "✅ 分析完成",
        "assistant": "💬 AI助教",
        "ask": "输入你的问题",
        "no_pdf": "⚠️ 请先上传PDF文件",
    },
    "en": {
        "title": "📚 AI Course Review System",
        "upload": "Upload course PDFs (multiple, ≤200MB)",
        "start": "🚀 Start Analysis",
        "processing": "Processing...",
        "done": "✅ Completed",
        "assistant": "💬 AI Tutor",
        "ask": "Ask your question",
        "no_pdf": "⚠️ Please upload PDFs first",
    },
}

# ======================
# 🧠 Session 初始化
# ======================
if "lang" not in st.session_state:
    st.session_state.lang = "zh"

if "summary" not in st.session_state:
    st.session_state.summary = ""

if "flashcards" not in st.session_state:
    st.session_state.flashcards = []

if "quiz" not in st.session_state:
    st.session_state.quiz = []

# ======================
# 🌍 语言切换
# ======================
lang_choice = st.sidebar.selectbox(
    "Language / 语言", ["中文", "English"]
)
st.session_state.lang = "zh" if lang_choice == "中文" else "en"
T = LANG[st.session_state.lang]

st.title(T["title"])

# ======================
# 📥 PDF 上传
# ======================
uploaded_files = st.file_uploader(
    T["upload"],
    type=["pdf"],
    accept_multiple_files=True,
)

# ======================
# 🔧 工具函数
# ======================

def extract_text_from_pdfs(files) -> str:
    all_text = []
    for file in files:
        try:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text = page.extract_text()
                if text and text.strip():
                    all_text.append(text)
        except Exception as e:
            st.warning(f"PDF 读取失败: {file.name}")
    return "\n".join(all_text)


def chunk_text(text: str, chunk_size: int = 12000) -> List[str]:
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


def call_gemini(prompt: str) -> str:
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=TEMPERATURE,
        ),
    )
    return response.text


def safe_json_load(text: str):
    try:
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)
    except:
        return []


def determine_question_count(text_length: int) -> int:
    if text_length < 5000:
        return 5
    elif text_length < 15000:
        return 10
    elif text_length < 30000:
        return 15
    else:
        return 20


# ======================
# 🚀 开始分析按钮
# ======================
if st.button(T["start"]):

    if not uploaded_files:
        st.warning(T["no_pdf"])
        st.stop()

    progress = st.progress(0)
    status = st.empty()

    # ======================
    # Step 1: 读取PDF
    # ======================
    status.text("📥 Reading PDFs...")
    progress.progress(10)

    full_text = extract_text_from_pdfs(uploaded_files)

    if not full_text.strip():
        st.error("❌ 未能从PDF提取文本（可能是扫描版）")
        st.stop()

    # ======================
    # Step 2: 分块
    # ======================
    status.text("✂️ Chunking content...")
    progress.progress(25)

    chunks = chunk_text(full_text)

    # ======================
    # Step 3: 汇总分析
    # ======================
    status.text("🧠 AI analyzing...")
    progress.progress(45)

    partial_summaries = []

    for chunk in chunks:
        prompt = f"""
You are an expert academic tutor.

Analyze the following course content and produce structured notes.

Content:
{chunk}
"""
        partial = call_gemini(prompt)
        partial_summaries.append(partial)

    merged_text = "\n".join(partial_summaries)

    # ======================
    # Step 4: 生成最终总结
    # ======================
    status.text("📚 Generating final review...")
    progress.progress(65)

    final_prompt = f"""
You are a senior international curriculum teacher.

Create a HIGH-QUALITY exam review sheet.

STRICT STRUCTURE:

# Knowledge Explanation
- systematic teaching

# 🔴 High-Frequency Exam Points

# 🟠 Common Traps

# 🧠 Rapid Review Sheet

Content:
{merged_text}
"""

    final_summary = call_gemini(final_prompt)
    st.session_state.summary = final_summary

    # ======================
    # Step 5: 闪卡
    # ======================
    status.text("🃏 Generating flashcards...")
    progress.progress(80)

    q_count = determine_question_count(len(full_text))

    flash_prompt = f"""
Generate {q_count} high-quality flashcards.

Return ONLY JSON list:
[{{"q":"","a":""}}]

Content:
{merged_text}
"""

    flash_raw = call_gemini(flash_prompt)
    st.session_state.flashcards = safe_json_load(flash_raw)

    # ======================
    # Step 6: 自测题
    # ======================
    status.text("🧪 Generating quiz...")
    progress.progress(92)

    quiz_prompt = f"""
Generate {q_count} exam-style questions.

Mix:
- multiple choice
- true/false
- short answer

Return JSON list.

Content:
{merged_text}
"""

    quiz_raw = call_gemini(quiz_prompt)
    st.session_state.quiz = safe_json_load(quiz_raw)

    progress.progress(100)
    status.text(T["done"])

# ======================
# 📚 显示总结
# ======================
if st.session_state.summary:
    st.markdown(st.session_state.summary, unsafe_allow_html=True)

# ======================
# 🃏 闪卡
# ======================
if st.session_state.flashcards:
    st.subheader("🃏 Flashcards")
    for i, card in enumerate(st.session_state.flashcards):
        with st.expander(f"Card {i+1}"):
            st.write("**Q:**", card.get("q", ""))
            st.write("**A:**", card.get("a", ""))

# ======================
# 🧪 自测
# ======================
if st.session_state.quiz:
    st.subheader("🧪 Quiz")
    st.json(st.session_state.quiz)

# ======================
# 💬 AI 助教
# ======================
st.divider()
st.subheader(T["assistant"])

user_q = st.text_input(T["ask"])

if user_q and st.session_state.summary:
    tutor_prompt = f"""
You are a course tutor.

Answer based ONLY on the course content below.

Course:
{st.session_state.summary}

Question:
{user_q}
"""
    answer = call_gemini(tutor_prompt)
    st.write(answer)