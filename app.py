import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import time
import json
import re

# ==========================================
# 1. 核心锁定：模型名称 (绝对禁止修改)
# ==========================================
STR_MODEL_ID = "gemini-2.5-flash"

# ==========================================
# 2. 页面配置与 CSS 深度定制
# ==========================================
st.set_page_config(page_title="AI Academic Terminal", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
        /* 彻底消除侧边栏 */
        [data-testid="stSidebar"], [data-testid="stSidebarNav"] { display: none !important; }
        .main .block-container { padding-top: 2rem !important; }

        /* 顶部语言按钮布局：放置在右上角并防止遮挡 */
        .top-nav {
            display: flex;
            justify-content: flex-end;
            padding: 10px 0;
            margin-bottom: -30px;
        }

        /* 学习理解重点块样式 */
        .learning-card {
            background-color: #f8faff;
            border-left: 6px solid #007bff;
            padding: 20px;
            border-radius: 10px;
            margin: 15px 0;
        }

        /* 重点高亮（Span着色） */
        .key-concept {
            background-color: #fff3bf;
            color: #d9480f;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 4px;
        }

        /* 交互闪卡样式 */
        .card-inner {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 60px 40px;
            border-radius: 20px;
            text-align: center;
            min-height: 300px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.6rem;
            font-weight: 700;
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
            margin: 20px 0;
        }

        /* 自测题容器 */
        .quiz-box {
            background-color: white;
            border: 1px solid #e1e4e8;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. Session State 状态管理 (交互核心)
# ==========================================
if 'lang' not in st.session_state: st.session_state.lang = 'CN'
if 'analysis_data' not in st.session_state: st.session_state.analysis_data = None
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0

# 交互组件专用状态
if 'f_idx' not in st.session_state: st.session_state.f_idx = 0
if 'f_reveal' not in st.session_state: st.session_state.f_reveal = False
if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'q_submitted' not in st.session_state: st.session_state.q_submitted = False
if 'chat_history' not in st.session_state: st.session_state.chat_history = []

# ==========================================
# 4. 语言字典定义
# ==========================================
D = {
    'CN': {
        'switch': "English Version",
        'title': "🎓 国际课程 AI 智能分析系统",
        'up_label': "上传课程 PDF 教材 (支持多个文件)",
        'up_count': "已成功上传 {} 个文件",
        'clear': "🗑️ 一键清空",
        'start': "🚀 开始分析并生成交互式报告",
        'progress': "AI 教务主任分析中 (预计 20-30 秒)...",
        'tab1': "📖 学习理解", 'tab2': "📝 复习备考", 'tab3': "🃏 闪卡训练", 'tab4': "✍️ 模拟自测", 'tab5': "🤖 AI 助教",
        'prev': "上一题", 'next': "下一题", 'flip': "翻转 (查看答案)", 'submit': "提交答案",
        'correct': "✅ 正确！", 'wrong': "❌ 错误！", 'ans_label': "正确答案是：", 'explain': "结果分析",
        'restart': "重新开始", 'chat_hit': "输入课程问题...",
        'prompt': f"你是一名有30年经验的国际学校教务主任。请针对教材生成报告。要求：[1] 学习理解部分重点词汇用 <KEY>词汇</KEY> 包裹。[2] 复习备考重点使用 💡。[3] 生成 JSON 格式的闪卡和自测题。模型锁定：{STR_MODEL_ID}"
    },
    'EN': {
        'switch': "切换至中文",
        'title': "🎓 AI International Course Analytics",
        'up_label': "Upload Course PDFs (Multiple)",
        'up_count': "{} files uploaded",
        'clear': "🗑️ Clear All",
        'start': "🚀 Start Analysis & Interactive Report",
        'progress': "Analyzing Content (Estimated 20-30s)...",
        'tab1': "📖 Learning", 'tab2': "📝 Revision", 'tab3': "🃏 Flashcards", 'tab4': "✍️ Self-Test", 'tab5': "🤖 AI Tutor",
        'prev': "Previous", 'next': "Next", 'flip': "Flip (See Answer)", 'submit': "Submit",
        'correct': "✅ Correct!", 'wrong': "❌ Incorrect!", 'ans_label': "Correct Answer:", 'explain': "Analysis",
        'restart': "Restart", 'chat_hit': "Ask about the course...",
        'prompt': f"You are an Academic Director with 30 years experience. Generate report. [1] Wrap key terms in <KEY>term</KEY> in Learning section. [2] Use 💡 in Revision. [3] JSON for flashcards and quiz. Model: {STR_MODEL_ID}"
    }
}
ui = D[st.session_state.lang]

# ==========================================
# 5. UI 顶部导航 (语言切换按钮置顶)
# ==========================================
st.markdown('<div class="top-nav">', unsafe_allow_html=True)
col_title, col_lang = st.columns([0.8, 0.2])
with col_title:
    st.title(ui['title'])
with col_lang:
    if st.button(ui['switch'], key="lang_btn", use_container_width=True):
        st.session_state.lang = 'EN' if st.session_state.lang == 'CN' else 'CN'
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 6. 文件上传处理
# ==========================================
pdf_files = st.file_uploader(ui['up_label'], type=['pdf'], accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")

if pdf_files:
    c1, c2 = st.columns([0.7, 0.3])
    with c1:
        st.success(ui['up_count'].format(len(pdf_files)))
    with c2:
        if st.button(ui['clear'], use_container_width=True):
            st.session_state.uploader_key += 1
            st.session_state.analysis_data = None
            st.rerun()

# ==========================================
# 7. AI 分析引擎 (强力正则提取)
# ==========================================
def get_ai_report(files):
    # 提取 PDF
    text = ""
    for f in files:
        reader = PdfReader(f)
        for page in reader.pages: text += (page.extract_text() or "") + "\n"
    
    # 调用 Gemini
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel(STR_MODEL_ID)
    
    prompt = f"""
    {ui['prompt']}
    Language: {st.session_state.lang}

    Output markers:
    [LEARN] 内容... [/LEARN]
    [REVISION] 内容... [/REVISION]
    [FLASH_JSON] [{"q": "...", "a": "..."}] [/FLASH_JSON]
    [QUIZ_JSON] [{"q": "...", "o": ["A","B","C","D"], "a": "A", "e": "..."}] [/QUIZ_JSON]

    Content:
    {text[:35000]}
    """
    response = model.generate_content(prompt)
    return response.text

if pdf_files and st.button(ui['start'], type="primary", use_container_width=True):
    with st.status(ui['progress']) as status:
        res = get_ai_report(pdf_files)
        st.session_state.analysis_data = res
        # 重置交互状态
        st.session_state.f_idx = 0
        st.session_state.q_idx = 0
        st.session_state.q_submitted = False
        status.update(label="Complete!", state="complete")
        st.rerun()

# ==========================================
# 8. 交互展示区域
# ==========================================
if st.session_state.analysis_data:
    raw = st.session_state.analysis_data
    
    # 正则提取器
    def extract(tag, source):
        try:
            pattern = f"\[{tag}\](.*?)\[/{tag}\]"
            return re.findall(pattern, source, re.DOTALL)[0].strip()
        except: return ""

    tabs = st.tabs([ui['tab1'], ui['tab2'], ui['tab3'], ui['tab4'], ui['tab5']])

    # --- Tab 1: 学习理解 (着色处理) ---
    with tabs[0]:
        c = extract("LEARN", raw)
        # 高亮转换
        c = c.replace("<KEY>", '<span class="key-concept">').replace("</KEY>", '</span>')
        st.markdown(f'<div class="learning-card">{c}</div>', unsafe_allow_html=True)

    # --- Tab 2: 复习备考 ---
    with tabs[1]:
        st.info(extract("REVISION", raw))

    # --- Tab 3: 交互闪卡 (一题一题) ---
    with tabs[2]:
        try:
            f_list = json.loads(extract("FLASH_JSON", raw))
            f_idx = st.session_state.f_idx
            card = f_list[f_idx]
            
            st.write(f"Card {f_idx + 1} / {len(f_list)}")
            content = card['a'] if st.session_state.f_reveal else card['q']
            st.markdown(f'<div class="card-inner">{content}</div>', unsafe_allow_html=True)
            
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button(ui['prev'], key="f_p") and f_idx > 0:
                    st.session_state.f_idx -= 1
                    st.session_state.f_reveal = False
                    st.rerun()
            with b2:
                if st.button(ui['flip'], key="f_f", use_container_width=True):
                    st.session_state.f_reveal = not st.session_state.f_reveal
                    st.rerun()
            with b3:
                if st.button(ui['next'], key="f_n") and f_idx < len(f_list)-1:
                    st.session_state.f_idx += 1
                    st.session_state.f_reveal = False
                    st.rerun()
        except: st.warning("Flashcard format error.")

    # --- Tab 4: 模拟自测 (答题+分析) ---
    with tabs[3]:
        try:
            q_list = json.loads(extract("QUIZ_JSON", raw))
            q_idx = st.session_state.q_idx
            q = q_list[q_idx]
            
            st.markdown('<div class="quiz-box">', unsafe_allow_html=True)
            st.subheader(f"Q{q_idx + 1}: {q['q']}")
            
            choice = st.radio("Options:", q['o'], key=f"q_choice_{q_idx}")
            
            if not st.session_state.q_submitted:
                if st.button(ui['submit'], type="primary"):
                    st.session_state.q_submitted = True
                    st.rerun()
            else:
                is_correct = choice.startswith(q['a'])
                if is_correct: st.success(ui['correct'])
                else: st.error(f"{ui['wrong']} {ui['ans_label']} {q['a']}")
                
                st.info(f"💡 **{ui['explain']}:** {q['e']}")
                
                if st.button(ui['next'] if q_idx < len(q_list)-1 else ui['restart']):
                    if q_idx < len(q_list)-1:
                        st.session_state.q_idx += 1
                        st.session_state.q_submitted = False
                    else:
                        st.session_state.q_idx = 0
                        st.session_state.q_submitted = False
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        except: st.warning("Quiz format error.")

    # --- Tab 5: AI 助教 ---
    with tabs[4]:
        for m in st.session_state.chat_history:
            with st.chat_message(m["role"]): st.write(m["content"])
        
        if prompt := st.chat_input(ui['chat_hit']):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)
            
            with st.chat_message("assistant"):
                m_bot = genai.GenerativeModel(STR_MODEL_ID)
                resp = m_bot.generate_content(f"Context: {raw[:5000]}\nQuestion: {prompt}")
                st.write(resp.text)
                st.session_state.chat_history.append({"role": "assistant", "content": resp.text})