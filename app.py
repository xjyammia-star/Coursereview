import streamlit as st
import google.generativeai as genai
import os
import time
import json
import re
from PyPDF2 import PdfReader
from google.api_core.exceptions import ResourceExhausted

# =====================
# 页面配置
# =====================
st.set_page_config(page_title="AI Course Review", layout="wide")

# =====================
# Gemini 配置（写死）
# =====================
MODEL_NAME = "gemini-2.5-flash"
TEMPERATURE = 0.1

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel(MODEL_NAME)

# =====================
# 🌍 语言系统（强制版）
# =====================
lang = st.sidebar.selectbox("Language / 语言", ["English", "中文"])

def lang_instruction():
    if lang == "中文":
        return "IMPORTANT: You MUST output ALL content in SIMPLIFIED CHINESE."
    else:
        return "IMPORTANT: You MUST output ALL content in ENGLISH."

# =====================
# 📄 PDF 读取
# =====================
def extract_text_from_pdfs(files):
    full_text = ""
    for file in files:
        reader = PdfReader(file)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    return full_text

# =====================
# ✂️ 文本分块
# =====================
def split_text(text, max_chars=12000):
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]

# =====================
# 🤖 Gemini 调用（带重试）
# =====================
def call_gemini(prompt, retries=3):
    for attempt in range(retries):
        try:
            response = model.generate_content(
                prompt,
                generation_config={"temperature": TEMPERATURE}
            )
            return response.text
        except ResourceExhausted:
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise

# =====================
# 🧹 JSON 清洗（超稳）
# =====================
def clean_json(text):
    text = re.sub(r"```json|```", "", text)
    match = re.search(r"\[.*\]", text, re.S)
    if match:
        return match.group()
    return text

# =====================
# 🧠 主界面
# =====================
st.title("📚 AI Course Review System")

uploaded_files = st.file_uploader(
    "Upload course PDFs",
    type="pdf",
    accept_multiple_files=True
)

# ✅ 显示文件数量（你要求的）
if uploaded_files:
    st.success(f"✅ Uploaded {len(uploaded_files)} file(s)")

# =====================
# 🚀 开始分析
# =====================
if st.button("🚀 Start Analysis") and uploaded_files:

    progress_bar = st.progress(0)
    percent_text = st.empty()

    # ===== Step 1 =====
    percent_text.text("10%")
    progress_bar.progress(10)

    raw_text = extract_text_from_pdfs(uploaded_files)

    # ===== Step 2 =====
    percent_text.text("30%")
    progress_bar.progress(30)

    chunks = split_text(raw_text)

    partial_summaries = []

    # ===== Step 3 =====
    for i, chunk in enumerate(chunks):
        percent = 30 + int((i / len(chunks)) * 30)
        progress_bar.progress(percent)
        percent_text.text(f"{percent}%")

        prompt = f"""
        {lang_instruction()}

        You are an expert teacher.

        TASK:
        1. Explain key knowledge clearly
        2. Then summarize important exam points

        TEXT:
        {chunk}
        """

        summary = call_gemini(prompt)
        partial_summaries.append(summary)

    # ===== Step 4 压缩 =====
    progress_bar.progress(65)
    percent_text.text("65%")

    reduce_prompt = f"""
    {lang_instruction()}

    Merge and organize the following summaries into a structured review.

    CONTENT:
    {''.join(partial_summaries)}
    """

    final_summary = call_gemini(reduce_prompt)

    # ===== Step 5 Flashcards =====
    progress_bar.progress(80)
    percent_text.text("80%")

    flash_prompt = f"""
    {lang_instruction()}

    Generate 5–20 flashcards.

    CONTENT:
    {final_summary}
    """

    flashcards = call_gemini(flash_prompt)

    # ===== Step 6 Quiz（JSON 强制）=====
    progress_bar.progress(90)
    percent_text.text("90%")

    quiz_prompt = f"""
    {lang_instruction()}

    Generate 5-20 quiz questions.

    STRICTLY RETURN JSON ARRAY.

    FORMAT:
    [
      {{
        "id": 1,
        "type": "multiple_choice",
        "question": "...",
        "options": {{"A":"...","B":"...","C":"...","D":"..."}},
        "answer": "A",
        "explanation": "..."
      }}
    ]

    CONTENT:
    {final_summary}
    """

    quiz_raw = call_gemini(quiz_prompt)

    # 🧹 安全解析
    quiz_data = []
    try:
        cleaned = clean_json(quiz_raw)
        quiz_data = json.loads(cleaned)
    except Exception as e:
        st.error("Quiz parsing failed — but app continues.")
        quiz_data = []

    # ===== 完成 =====
    progress_bar.progress(100)
    percent_text.text("100%")

    st.success("✅ Analysis Complete!")

    # =====================
    # 📖 Summary
    # =====================
    st.header("📖 Review Summary")
    st.markdown(final_summary)

    # =====================
    # 🧠 Flashcards
    # =====================
    st.header("🧠 Flashcards")
    st.markdown(flashcards)

    # =====================
    # 📝 Quiz（稳如狗版）
    # =====================
    st.header("📝 Quiz")

    if quiz_data:
        for q in quiz_data:
            st.subheader(q.get("question", ""))

            options = q.get("options", {})
            user_answer = st.radio(
                "Choose:",
                list(options.keys()),
                key=f"quiz_{q.get('id')}"
            )

            if st.button("Check", key=f"check_{q.get('id')}"):
                if user_answer == q.get("answer"):
                    st.success("✅ Correct!")
                else:
                    st.error(f"❌ Correct answer: {q.get('answer')}")
                    st.info(q.get("explanation"))
    else:
        st.warning("⚠️ Quiz generation failed.")

# =====================
# 🤖 AI 助教
# =====================
st.sidebar.header("🤖 AI Tutor")

question = st.sidebar.text_input("Ask anything")

if question:
    tutor_prompt = f"""
    {lang_instruction()}

    Student question:
    {question}
    """
    answer = call_gemini(tutor_prompt)
    st.sidebar.write(answer)