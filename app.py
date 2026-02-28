import streamlit as st
import google.generativeai as genai
import PyPDF2
import time
import json
from io import BytesIO

# ======================
# 🔐 页面配置
# ======================
st.set_page_config(
    page_title="AI Course Review",
    page_icon="📚",
    layout="wide"
)

# ======================
# 🔐 API KEY
# ======================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    st.error("❌ Please set GEMINI_API_KEY in Streamlit secrets.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ======================
# 🌍 语言
# ======================
language = st.sidebar.selectbox(
    "🌐 Language / 语言",
    ["English", "中文"]
)

def t(en, zh):
    return zh if language == "中文" else en

# ======================
# 📄 PDF 读取
# ======================
def extract_text_from_pdfs(uploaded_files):
    text = ""
    for file in uploaded_files:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
    return text

# ======================
# 🧠 安全调用 Gemini（带重试）
# ======================
def call_gemini(prompt, max_retries=5):
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            wait_time = 2 ** attempt
            time.sleep(wait_time)
    return "⚠️ AI temporarily unavailable. Please try again."

# ======================
# ✂️ 文本分块（防炸）
# ======================
def chunk_text(text, chunk_size=12000):
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

# ======================
# 🧠 主界面
# ======================
st.title("📚 AI Course Review Generator")

uploaded_files = st.file_uploader(
    t("Upload PDF files", "上传PDF文件"),
    type=["pdf"],
    accept_multiple_files=True
)

# ======================
# 📊 显示文件数量
# ======================
if uploaded_files:
    st.success(
        t(
            f"Uploaded {len(uploaded_files)} file(s)",
            f"已上传 {len(uploaded_files)} 个文件"
        )
    )

# ======================
# 🚀 开始分析
# ======================
if uploaded_files and st.button(t("Start Analysis", "开始分析")):

    progress_bar = st.progress(0)
    progress_text = st.empty()

    # ---------- Step 1 ----------
    progress_text.text(t("Reading PDFs...", "正在读取PDF..."))
    progress_bar.progress(10)

    full_text = extract_text_from_pdfs(uploaded_files)

    if len(full_text) < 50:
        st.error(t("PDF content too short.", "PDF内容过少"))
        st.stop()

    # ---------- Step 2 ----------
    progress_text.text(t("Analyzing content...", "正在分析内容..."))
    progress_bar.progress(30)

    chunks = chunk_text(full_text)
    partial_summaries = []

    for i, chunk in enumerate(chunks):
        prompt = f"""
You are an expert teacher.

Language: {language}

Task:
1. Explain the key knowledge clearly for students.
2. Then summarize the key review points.

Content:
{chunk}
"""
        summary = call_gemini(prompt)
        partial_summaries.append(summary)

        percent = 30 + int(30 * (i+1) / len(chunks))
        progress_bar.progress(percent)
        progress_text.text(
            t(
                f"Analyzing chunk {i+1}/{len(chunks)}...",
                f"正在分析第 {i+1}/{len(chunks)} 部分..."
            )
        )

    # ---------- Step 3 ----------
    progress_text.text(t("Merging results...", "正在合并结果..."))
    progress_bar.progress(70)

    merged_text = "\n\n".join(partial_summaries)

    reduce_prompt = f"""
Language: {language}

Please produce a FINAL structured review including:

1. Clear knowledge explanation
2. Key review points
3. Important reminders for students

Content:
{merged_text}
"""

    final_summary = call_gemini(reduce_prompt)

    progress_bar.progress(85)
    progress_text.text(t("Generating quiz...", "正在生成测验..."))

    # ---------- Step 4 Quiz ----------
    quiz_prompt = f"""
Language: {language}

Create 5 multiple choice questions in JSON format.

FORMAT STRICTLY:

{{
  "quiz":[
    {{
      "id":1,
      "type":"multiple_choice",
      "question":"...",
      "options":{{"A":"...","B":"...","C":"...","D":"..."}},
      "answer":"A",
      "explanation":"..."
    }}
  ]
}}

Content:
{merged_text[:8000]}
"""

    quiz_raw = call_gemini(quiz_prompt)

    # 安全解析 JSON
    quiz_data = None
    try:
        quiz_data = json.loads(quiz_raw)
    except:
        st.warning(t("Quiz parsing failed.", "Quiz解析失败"))

    progress_bar.progress(100)
    progress_text.text(t("Completed!", "完成！"))

    # ======================
    # 📘 输出
    # ======================
    st.header(t("📘 Review Summary", "📘 复习总结"))
    st.write(final_summary)

    # ======================
    # 🧪 Quiz
    # ======================
    if quiz_data and "quiz" in quiz_data:
        st.header("🧪 Quiz")

        for q in quiz_data["quiz"]:
            st.markdown(f"**Q{q['id']}. {q['question']}**")
            st.write(q["options"])

            with st.expander(t("Show answer", "查看答案")):
                st.write(f"✅ {q['answer']}")
                st.write(q["explanation"])