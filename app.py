import streamlit as st
import google.generativeai as genai
import PyPDF2
import time
import json
import re

# ======================
# 页面配置
# ======================
st.set_page_config(
    page_title="AI Course Review",
    page_icon="📚",
    layout="wide"
)

# ======================
# API KEY
# ======================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    st.error("❌ Please set GEMINI_API_KEY in Streamlit secrets.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ======================
# 语言
# ======================
language = st.sidebar.selectbox(
    "🌐 Language / 语言",
    ["English", "中文"]
)

def t(en, zh):
    return zh if language == "中文" else en

# ======================
# PDF 提取
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
# 更强 Gemini 调用（关键升级）
# ======================
def call_gemini(prompt, max_retries=6):

    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,
                }
            )

            if response and response.text:
                return response.text

        except Exception as e:
            wait = 2 ** attempt
            time.sleep(wait)

    return None  # ⚠️ 不再返回假文本

# ======================
# 文本切块（更小更安全）
# ======================
def chunk_text(text, size=8000):
    return [text[i:i+size] for i in range(0, len(text), size)]

# ======================
# JSON 清洗器（🔥关键）
# ======================
def safe_json_loads(text):
    if not text:
        return None

    # 去掉 ```json ```
    text = re.sub(r"```json", "", text)
    text = re.sub(r"```", "", text)

    # 找第一个 { 到最后一个 }
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None

    try:
        return json.loads(match.group())
    except:
        return None

# ======================
# UI
# ======================
st.title("📚 AI Course Review Generator")

uploaded_files = st.file_uploader(
    t("Upload PDF files", "上传PDF文件"),
    type=["pdf"],
    accept_multiple_files=True
)

# 显示文件数量
if uploaded_files:
    st.success(
        t(
            f"Uploaded {len(uploaded_files)} file(s)",
            f"已上传 {len(uploaded_files)} 个文件"
        )
    )

# ======================
# 开始分析
# ======================
if uploaded_files and st.button(t("Start Analysis", "开始分析")):

    progress_bar = st.progress(0)
    progress_text = st.empty()

    # Step 1
    progress_text.text(t("Reading PDFs...", "正在读取PDF..."))
    progress_bar.progress(10)

    full_text = extract_text_from_pdfs(uploaded_files)

    if len(full_text) < 50:
        st.error(t("PDF content too short.", "PDF内容过少"))
        st.stop()

    # Step 2 分块分析
    progress_text.text(t("Analyzing content...", "正在分析内容..."))
    progress_bar.progress(20)

    chunks = chunk_text(full_text)
    partial_summaries = []

    for i, chunk in enumerate(chunks):

        prompt = f"""
You are an expert teacher.

OUTPUT LANGUAGE: {language}

TASK:
1. Explain the knowledge clearly.
2. Then list key review points.

CONTENT:
{chunk}
"""

        result = call_gemini(prompt)

        if result:
            partial_summaries.append(result)

        percent = 20 + int(40 * (i+1) / len(chunks))
        progress_bar.progress(percent)
        progress_text.text(
            t(
                f"Analyzing {i+1}/{len(chunks)}...",
                f"正在分析 {i+1}/{len(chunks)}..."
            )
        )

    if not partial_summaries:
        st.error(t("AI failed. Please retry.", "AI分析失败，请重试"))
        st.stop()

    # Step 3 汇总
    progress_text.text(t("Merging results...", "正在合并结果..."))
    progress_bar.progress(65)

    merged_text = "\n\n".join(partial_summaries)

    reduce_prompt = f"""
OUTPUT LANGUAGE: {language}

Create FINAL structured review:

1. Knowledge explanation
2. Key review points
3. Student reminders

CONTENT:
{merged_text[:12000]}
"""

    final_summary = call_gemini(reduce_prompt)

    progress_bar.progress(80)

    # Step 4 Quiz
    progress_text.text(t("Generating quiz...", "正在生成测验..."))

    quiz_prompt = f"""
OUTPUT LANGUAGE: {language}

Return ONLY valid JSON.

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

CONTENT:
{merged_text[:6000]}
"""

    quiz_raw = call_gemini(quiz_prompt)
    quiz_data = safe_json_loads(quiz_raw)

    progress_bar.progress(100)
    progress_text.text(t("Completed!", "完成！"))

    # ======================
    # 输出总结
    # ======================
    st.header(t("📘 Review Summary", "📘 复习总结"))

    if final_summary:
        st.write(final_summary)
    else:
        st.warning(t("Summary failed.", "总结生成失败"))

    # ======================
    # Quiz
    # ======================
    if quiz_data and "quiz" in quiz_data:
        st.header("🧪 Quiz")

        for q in quiz_data["quiz"]:
            st.markdown(f"**Q{q['id']}. {q['question']}**")
            st.write(q["options"])

            with st.expander(t("Show answer", "查看答案")):
                st.write(f"✅ {q['answer']}")
                st.write(q["explanation"])
    else:
        st.warning(t("Quiz parsing failed.", "Quiz解析失败"))