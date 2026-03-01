import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import time
import json
import re

# ==========================================
# 1. 核心锁定：模型名称 (绝对不许修改)
# ==========================================
MODEL_ID = "gemini-2.5-flash"

# ==========================================
# 2. 页面配置与顶级 CSS (解决所有 UI Bug)
# ==========================================
st.set_page_config(page_title="AI Academic Terminal", layout="wide", initial_sidebar_state="collapsed")

# 强制注入 CSS
st.markdown("""
    <style>
        /* 彻底移除侧边栏 */
        [data-testid="stSidebar"] { display: none !important; }
        
        /* 顶部间距调整 */
        .main .block-container { padding-top: 2rem !important; }
        
        /* 右上角语言切换容器 */
        .header-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            margin-top: -10px;
        }
        
        /* 学习理解重点块 */
        .learning-box {
            background-color: #f0f4f8;
            border-left: 6px solid #2e7d32;
            padding: 20px;
            border-radius: 10px;
            margin: 15px 0;
            color: #1b5e20;
        }
        
        /* 交互闪卡样式 */
        .flashcard-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 50px;
            border-radius: 20px;
            text-align: center;
            min-height: 250px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            font-weight: bold;
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
            margin: 20px 0;
            cursor: pointer;
        }
        
        /* 自测题目样式 */
        .quiz-container {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        
        /* 重点高亮 */
        .highlight-text {
            color: #e65100;
            font-weight: bold;
            text-decoration: underline;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 复杂状态管理 (Session State)
# ==========================================
# 基础状态
if 'lang' not in st.session_state: st.session_state.lang = 'CN'
if 'processed_data' not in st.session_state: st.session_state.processed_data = None
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0

# 交互组件状态 (闪卡)
if 'f_idx' not in st.session_state: st.session_state.f_idx = 0
if 'f_flip' not in st.session_state: st.session_state.f_flip = False

# 交互组件状态 (自测题)
if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'q_submitted' not in st.session_state: st.session_state.q_submitted = False
if 'q_score' not in st.session_state: st.session_state.q_score = 0

# 聊天状态
if 'chat_history' not in st.session_state: st.session_state.chat_history = []

# ==========================================
# 4. 字典配置 (全界面翻译)
# ==========================================
D = {
    'CN': {
        'switch': "English Version",
        'title': "🎓 国际学校课程 AI 智能分析终端",
        'up_label': "请上传课程 PDF 教材 (支持多文件同时上传)",
        'clear': "🗑️ 清空所有内容",
        'analyze': "🚀 开始深度分析并生成交互报告",
        'tab1': "📖 学习理解",
        'tab2': "📝 复习备考",
        'tab3': "🃏 交互闪卡",
        'tab4': "✍️ 模拟自测",
        'tab5': "🤖 AI 助教",
        'progress': "正在处理教材 (预计 20-40 秒)...",
        'next': "下一题", 'prev': "上一题", 'reveal': "点击翻面 (查看答案)",
        'submit': "提交答案", 'analysis': "结果深度分析",
        'correct': "✅ 回答正确！", 'wrong': "❌ 回答错误！正确答案是：",
        'restart': "重新开始测试",
        'prompt_system': f"你是一名资深的国际学校教务主任。基于提供的PDF内容，生成报告。必须包含五个部分：[LEARNING]模块使用颜色区分重点内容，[REVISION]模块，[FLASHCARDS_JSON]模块和[QUIZ_JSON]模块。模型锁定为{MODEL_ID}。"
    },
    'EN': {
        'switch': "切换至中文",
        'title': "🎓 AI International Course Analytics Terminal",
        'up_label': "Upload Course PDFs (Multiple supported)",
        'clear': "🗑️ Clear and Reset",
        'analyze': "🚀 Start Deep Analysis & Generate Interactive Report",
        'tab1': "📖 Understanding",
        'tab2': "📝 Revision",
        'tab3': "🃏 Flashcards",
        'tab4': "✍️ Self-Test",
        'tab5': "🤖 AI Tutor",
        'progress': "Processing materials (Estimated 20-40s)...",
        'next': "Next", 'prev': "Previous", 'reveal': "Flip Card (See Answer)",
        'submit': "Submit Answer", 'analysis': "Depth Analysis",
        'correct': "✅ Correct!", 'wrong': "❌ Incorrect! The right answer is:",
        'restart': "Restart Test",
        'prompt_system': f"You are a senior Academic Director. Analyze PDF content. Include [LEARNING] with key highlights, [REVISION], [FLASHCARDS_JSON], and [QUIZ_JSON]. Model: {MODEL_ID}."
    }
}
ui = D[st.session_state.lang]

# ==========================================
# 5. 顶部布局 (语言按钮修正)
# ==========================================
st.markdown('<div class="header-container">', unsafe_allow_html=True)
col_t, col_l = st.columns([0.8, 0.2])
with col_t:
    st.title(ui['title'])
with col_l:
    if st.button(ui['switch'], key="lang_toggle", use_container_width=True):
        st.session_state.lang = 'EN' if st.session_state.lang == 'CN' else 'CN'
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 6. 文件上传管理
# ==========================================
pdf_files = st.file_uploader(ui['up_label'], type=['pdf'], accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")

if pdf_files:
    if st.button(ui['clear']):
        st.session_state.uploader_key += 1
        st.session_state.processed_data = None
        st.session_state.f_idx = 0
        st.session_state.q_idx = 0
        st.session_state.chat_history = []
        st.rerun()

# ==========================================
# 7. AI 核心处理 (正则表达式 + JSON 强校验)
# ==========================================
def run_ai_analysis(files):
    # 1. 提取文字
    full_text = ""
    for f in files:
        reader = PdfReader(f)
        for page in reader.pages:
            full_text += (page.extract_text() or "") + "\n"
    
    # 2. 调用 API
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel(MODEL_ID)
    
    # 构建极其详尽的 Prompt 确保输出不崩溃
    prompt = f"""
    {ui['prompt_system']}
    目标语言: {st.session_state.lang}

    请严格按照以下格式输出内容：
    
    [LEARNING_START]
    在此处总结主要内容。对于核心关键词和必考知识点，请将其包裹在 <MARK> 和 </MARK> 标签之间，以便我着色。
    [LEARNING_END]

    [REVISION_START]
    抓取重点内容。使用 💡 标注重点。
    [REVISION_END]

    [FLASHCARDS_JSON]
    [
      {{"q": "问题内容", "a": "答案内容"}},
      ... (生成 5-20 个)
    ]
    [QUIZ_JSON]
    [
      {{"question": "题目内容", "options": ["选项A", "选项B", "选项C", "选项D"], "answer": "A", "reason": "为什么选A的详细深度分析"}},
      ... (生成 10-20 个)
    ]

    教材内容：
    {full_text[:35000]}
    """
    
    response = model.generate_content(prompt)
    return response.text

if pdf_files and st.button(ui['analyze'], type="primary", use_container_width=True):
    prog_bar = st.progress(0)
    prog_status = st.empty()
    
    prog_status.info(ui['progress'])
    
    # 模拟进度条
    for p in range(1, 40):
        time.sleep(0.05)
        prog_bar.progress(p)
    
    # 获取数据
    raw_response = run_ai_analysis(pdf_files)
    
    for p in range(41, 101):
        time.sleep(0.01)
        prog_bar.progress(p)
        
    st.session_state.processed_data = raw_response
    st.session_state.f_idx = 0
    st.session_state.q_idx = 0
    st.session_state.q_submitted = False
    st.rerun()

# ==========================================
# 8. 交互式 Tabs 呈现
# ==========================================
if st.session_state.processed_data:
    data = st.session_state.processed_data
    
    # 安全提取正则函数
    def extract_section(start_tag, end_tag, text):
        try:
            pattern = f"{re.escape(start_tag)}(.*?){re.escape(end_tag)}"
            return re.findall(pattern, text, re.DOTALL)[0].strip()
        except: return ""

    tab1, tab2, tab3, tab4, tab5 = st.tabs([ui['tab1'], ui['tab2'], ui['tab3'], ui['tab4'], ui['tab5']])

    # --- TAB 1: 学习理解 (着色处理) ---
    with tab1:
        content_l = extract_section("[LEARNING_START]", "[LEARNING_END]", data)
        # 将 <MARK> 替换为 HTML 着色标签
        colored_content = content_l.replace("<MARK>", '<span class="highlight-text">').replace("</MARK>", '</span>')
        st.markdown(f'<div class="learning-box">{colored_content}</div>', unsafe_allow_html=True)

    # --- TAB 2: 复习备考 ---
    with tab2:
        content_r = extract_section("[REVISION_START]", "[REVISION_END]", data)
        st.info(content_r)

    # --- TAB 3: 交互闪卡 (一题一题显示) ---
    with tab3:
        try:
            f_json_str = data.split("[FLASHCARDS_JSON]")[1].split("[QUIZ_JSON]")[0].strip()
            flashcards = json.loads(f_json_str)
            
            curr_f = st.session_state.f_idx
            card = flashcards[curr_f]
            
            st.write(f"Card {curr_f + 1} / {len(flashcards)}")
            
            # 显示内容 (翻面逻辑)
            card_text = card['a'] if st.session_state.f_flip else card['q']
            if st.markdown(f'<div class="flashcard-box">{card_text}</div>', unsafe_allow_html=True):
                pass # 占位
            
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                if st.button(ui['prev'], key="f_prev") and curr_f > 0:
                    st.session_state.f_idx -= 1
                    st.session_state.f_flip = False
                    st.rerun()
            with col_f2:
                if st.button(ui['reveal'], key="f_reveal", use_container_width=True):
                    st.session_state.f_flip = not st.session_state.f_flip
                    st.rerun()
            with col_f3:
                if st.button(ui['next'], key="f_next") and curr_f < len(flashcards)-1:
                    st.session_state.f_idx += 1
                    st.session_state.f_flip = False
                    st.rerun()
        except: st.error("Flashcard content format error.")

    # --- TAB 4: 交互模拟考 (一题一题+解析) ---
    with tab4:
        try:
            q_json_str = data.split("[QUIZ_JSON]")[1].split("[END]")[0] if "[END]" in data else data.split("[QUIZ_JSON]")[1]
            quizzes = json.loads(q_json_str)
            
            curr_q_idx = st.session_state.q_idx
            q_data = quizzes[curr_q_idx]
            
            st.markdown(f'<div class="quiz-container">', unsafe_allow_html=True)
            st.subheader(f"Question {curr_q_idx + 1}: {q_data['question']}")
            
            # 选择题
            u_choice = st.radio("Choose one:", q_data['options'], key=f"quiz_opt_{curr_q_idx}")
            
            if not st.session_state.q_submitted:
                if st.button(ui['submit'], type="primary"):
                    st.session_state.q_submitted = True
                    st.rerun()
            else:
                # 判定对错
                is_correct = u_choice.startswith(q_data['answer'])
                if is_correct: st.success(ui['correct'])
                else: st.error(f"{ui['wrong']} {q_data['answer']}")
                
                # 显示解析
                st.info(f"💡 **{ui['analysis']}:** {q_data['reason']}")
                
                # 下一题按钮
                if st.button(ui['next'] if curr_q_idx < len(quizzes)-1 else ui['restart']):
                    if curr_q_idx < len(quizzes)-1:
                        st.session_state.q_idx += 1
                        st.session_state.q_submitted = False
                    else:
                        st.session_state.q_idx = 0
                        st.session_state.q_submitted = False
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        except: st.error("Quiz content format