import streamlit as st
import pandas as pd
import numpy as np
import json
import time

# =========================
# ⭐ 页面配置
# =========================
st.set_page_config(
    page_title="AI Learning Report",
    layout="wide"
)

# =========================
# ⭐ Gemini 安全调用（修复 ResourceExhausted）
# =========================
def call_gemini_safe(model, prompt, temperature=0.3, max_retries=3):
    """
    带自动重试的 Gemini 调用
    修复 ResourceExhausted 崩溃
    """
    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                prompt,
                generation_config={"temperature": temperature}
            )
            return response.text

        except Exception as e:
            err_str = str(e)

            # ⭐ 专门处理配额/限流
            if "ResourceExhausted" in err_str or "429" in err_str:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    st.warning(f"⚠️ AI繁忙，自动重试中 ({attempt+1}/{max_retries})…")
                    time.sleep(wait_time)
                    continue
                else:
                    return "AI service is busy. Please try again later."

            # ⭐ 其它错误直接抛出
            return f"AI error: {e}"

    return "AI failed."


# =========================
# ⭐ 学科翻译字典（关键修复）
# =========================
SUBJECT_TRANSLATIONS = {
    "zh": {
        "Math": "数学",
        "Mathematics": "数学",
        "English": "英语",
        "Science": "科学",
        "Biology": "生物",
        "Chemistry": "化学",
        "Physics": "物理",
        "History": "历史",
        "Geography": "地理",
        "Economics": "经济",
        "Computer Science": "计算机",
    },
    "en": {
        "Math": "Math",
        "Mathematics": "Mathematics",
        "English": "English",
        "Science": "Science",
        "Biology": "Biology",
        "Chemistry": "Chemistry",
        "Physics": "Physics",
        "History": "History",
        "Geography": "Geography",
        "Economics": "Economics",
        "Computer Science": "Computer Science",
    }
}


def translate_subject(subject, lang):
    """
    ⭐ 稳定学科翻译
    不会再出现乱七八糟标签
    """
    subject = str(subject).strip()

    if lang not in SUBJECT_TRANSLATIONS:
        return subject

    mapping = SUBJECT_TRANSLATIONS[lang]

    # 精确匹配
    if subject in mapping:
        return mapping[subject]

    # 模糊匹配（关键增强）
    for k in mapping:
        if k.lower() in subject.lower():
            return mapping[k]

    return subject


# =========================
# ⭐ 雷达图数据准备（核心修复）
# =========================
def prepare_radar_data(df, lang):
    """
    ✅ 永远使用真实学科列
    ✅ 永远按所选语言翻译
    ✅ 不再出现奇怪标签
    """
    subjects = df["Subject"].tolist()
    scores = df["Score"].tolist()

    translated_subjects = [
        translate_subject(s, lang) for s in subjects
    ]

    return translated_subjects, scores


# =========================
# ⭐ 绘制雷达图
# =========================
def draw_radar_chart(subjects, scores):
    import plotly.graph_objects as go

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=scores,
        theta=subjects,
        fill='toself',
        name='Performance'
    ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)


# =========================
# ⭐ UI
# =========================
st.title("📊 AI Learning Report")

# 语言选择
lang = st.radio(
    "Language / 语言",
    ["en", "zh"],
    horizontal=True
)

uploaded_file = st.file_uploader("Upload score CSV", type=["csv"])

# =========================
# ⭐ 主流程
# =========================
if uploaded_file:

    df = pd.read_csv(uploaded_file)

    # ===== 必要列检查 =====
    if not {"Subject", "Score"}.issubset(df.columns):
        st.error("CSV must contain Subject and Score columns.")
        st.stop()

    # ===== 雷达图 =====
    st.subheader("📈 Radar Chart")

    radar_subjects, radar_scores = prepare_radar_data(df, lang)

    draw_radar_chart(radar_subjects, radar_scores)

    # ===== AI总结按钮 =====
    if st.button("✨ Generate AI Summary"):

        with st.spinner("AI is thinking…"):

            # ⚠️ 这里假设你外面已初始化 model
            try:
                from google.generativeai import GenerativeModel
                model = GenerativeModel("gemini-1.5-flash")
            except Exception:
                st.error("Gemini model not configured.")
                st.stop()

            prompt = f"""
            Analyze this student performance:

            {df.to_string(index=False)}

            Give a short professional summary.
            """

            summary = call_gemini_safe(model, prompt)

        st.subheader("🧠 AI Summary")
        st.write(summary)

else:
    st.info("Please upload a CSV file to begin.")