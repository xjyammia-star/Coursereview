import streamlit as st
import time
import json
import re
from typing import List
import google.generativeai as genai
import PyPDF2

# ======================
# 🔐 Gemini 配置（写死）
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
        "assistant": "💬 AI助教",
        "ask": "输入你的问题",
        "no_pdf": "⚠️ 请先上传PDF文件",
        "uploaded": "已上传文件数量",
        "processing": "处理中...",
        "done": "✅ 分析完成",
    },
    "en": {
        "title": "📚 AI Course Review System",
        "upload": "Upload course PDFs (multiple, ≤200MB)",
        "start": "🚀 Start Analysis",
        "assistant": "💬 AI Tutor",
        "ask": "Ask your question",
        "no_pdf": "⚠️ Please upload PDFs first",
        "uploaded": "Files uploaded",
        "processing": "Processing...",
        "done": "✅ Completed",
    },
}

# ======================
# 🧠 Session 初始化
# ======================
for key, default in {
    "lang": "zh",
    "summary": "",
    "flashcards": [],
    "quiz": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ======================
# 🌍 语言切换
# ======================
lang_choice = st.sidebar.selectbox("Language / 语言", ["中文", "English"])
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

# ⭐⭐⭐ 显示上传数量（你要求的功能）
if uploaded_files:
    st.info(f"📎 {T['uploaded']}: **{len(uploaded_files)}**")

# ======================
# 🔧 工具函数
# ======================

def update_progress(progress_bar, percent_box, value):
    progress_bar.progress(value)
    percent_box.markdown(f"**{value}%**")


def extract_text_from_pdfs(files) -> str:
    all_text = []
    for file in files:
        try:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text = page.extract_text()
                if text and text.strip():
                    all_text.append(text)
        except Exception:
            st.warning(f"PDF 读取失败: {file.name}")
    return "\n".join(all_text)


def chunk_text(text: str, chunk_size: int = 12000) -> List[str]:
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


# ⭐⭐⭐ 指数退避重试（终极稳定）
def call_gemini(prompt: str, retries: int = 4) -> str:
    model = genai.GenerativeModel(MODEL_NAME)

    for i in range(retries):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=TEMPERATURE,
                ),
            )
            return response.text

        except Exception as e:
            if "ResourceExhausted" in str(e) and i < retries - 1:
                wait_time = 2 ** i
                time.sleep(wait_time)
            else:
                raise e


def safe_json_load(text: str):
    try:
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)
    except Exception:
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


# ⭐⭐⭐ 超稳 Reduce（已强化）
def reduce_summaries(summaries, batch_size=2):
    reduced = []

    for i in range(0, len(summaries), batch_size):
        batch = summaries[i:i + batch_size]
        batch_text = "\n".join(batch)

        # 🔥 长度保护
        if len(batch_text) > 12000:
            batch_text = batch_text[:12000]

        prompt = f"""
Condense the following study notes into a tight academic summary.
Be concise but keep key knowledge.

Notes:
{batch_text}
"""
        reduced_text = call_gemini(prompt)
        reduced.append(reduced_text)

        # 🔥 Cloud 节流
        time.sleep(1.2)

    return "\n".join(reduced)


# ======================
# 🚀 开始分析
# ======================
if st.button(T["start"]):

    if not uploaded_files:
        st.warning(T["no_pdf"])
        st.stop()

    progress_bar = st.progress(0)
    percent_box = st.empty()
    status = st.empty()

    # Step 1
    status.text("📥 Reading PDFs...")
    update_progress(progress_bar, percent_box, 5)

    full_text = extract_text_from_pdfs(uploaded_files)

    if not full_text.strip():
        st.error("❌ 未能从PDF提取文本（可能是扫描版）")
        st.stop()

    # Step 2
    status.text("✂️ Chunking...")
    update_progress(progress_bar, percent_box, 15)

    chunks = chunk_text(full_text)

    # Step 3 MAP
    status.text("🧠 AI analyzing...")
    update_progress(progress_bar, percent_box, 35)

    partial_summaries = []

    for idx, chunk in enumerate(chunks):
        prompt = f"""
You are an expert academic tutor.

Analyze the following course content and produce structured notes.

Content:
{chunk}
"""
        partial = call_gemini(prompt)
        partial_summaries.append(partial)

        # 🔥 节流（极重要）
        time.sleep(0.8)

    # Step 4 REDUCE
    status.text("🧩 Compressing knowledge...")
    update_progress(progress_bar, percent_box, 55)

    compressed_text = reduce_summaries(partial_summaries)

    # Step 5 FINAL
    status.text("📚 Generating final review...")
    update_progress(progress_bar, percent_box, 75)

    final_prompt = f"""
You are a senior international curriculum teacher.

Create a HIGH-QUALITY exam review sheet.

STRICT STRUCTURE:

# Knowledge Explanation
# 🔴 High-Frequency Exam Points
# 🟠 Common Traps
# 🧠 Rapid Review Sheet

Content:
{compressed_text}
"""

    st.session_state.summary = call_gemini(final_prompt)

    # Step 6 Flashcards
    status.text("🃏 Flashcards...")
    update_progress(progress_bar, percent_box, 90)

    q_count = determine_question_count(len(full_text))

    flash_prompt = f"""
Generate {q_count} high-quality flashcards.

Return ONLY JSON list:
[{{"q":"","a":""}}]

Content:
{compressed_text}
"""
    flash_raw = call_gemini(flash_prompt)
    st.session_state.flashcards = safe_json_load(flash_raw)

    # Step 7 Quiz
    status.text("🧪 Quiz...")
    update_progress(progress_bar, percent_box, 97)

    quiz_prompt = f"""
Generate {q_count} exam-style questions.

Mix:
- multiple choice
- true/false
- short answer

Return JSON list.

Content:
{compressed_text}
"""
    quiz_raw = call_gemini(quiz_prompt)
    st.session_state.quiz = safe_json_load(quiz_raw)

    update_progress(progress_bar, percent_box, 100)
    status.text(T["done"])

# ======================
# 📚 显示总结
# ======================
if st.session_state.summary:
    st.markdown(st.session_state.summary, unsafe_allow_html=True)

# ======================
# 🃏 Flashcards
# ======================
if st.session_state.flashcards:
    st.subheader("🃏 Flashcards")
    for i, card in enumerate(st.session_state.flashcards):
        with st.expander(f"Card {i+1}"):
            st.write("**Q:**", card.get("q", ""))
            st.write("**A:**", card.get("a", ""))

# ======================
# 🧪 Quiz
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