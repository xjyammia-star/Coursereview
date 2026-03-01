import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import time
import json
import re

# ==========================================
# 1. 核心锁定：模型名称 (绝对禁止修改)
# ==========================================
TARGET_MODEL = "gemini-2.5-flash"

# ==========================================
# 2. 页面配置与顶级 CSS (UI 布局与美化)
# ==========================================
st.set_page_config(page_title="AI Academic Terminal", layout="wide", initial_sidebar_state="collapsed")

# 强力 CSS：隐藏侧边栏、美化交互卡片、解决按钮遮挡
st.markdown("""
    <style>
        /* 彻底消除侧边栏 */
        [data-testid="stSidebar"], [data-testid="stSidebarNav"] { display: none !important; }
        .main .block-container { padding-top: 2rem !important; }

        /* 右上角语言切换容器 */
        .header-wrapper {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
        }

        /* 学习理解重点块 (Tab 1) */
        .learning-container {
            background-color: #f8fbff;
            border-left: 8px solid #0056b3;
            padding: 25px;
            border-radius: 12px;
            margin: 15px 0;
            line-height: 1.8;
            font-size: 1.1rem;
        }
        
        /* 重点内容着色 */
        .highlight-blue {
            background-color: #d1ecf1;
            color: #0c5460;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 4px;
            border: 1px solid #bee5eb;
        }

        /* 交互闪卡样式 (Tab 3) */
        .flashcard-main {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 50px;
            border-radius: 25px;
            text-align: center;
            min-height: 350px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.8rem;
            font-weight: 600;
            box-shadow: 0 15px 35px rgba(0,0,0,0.3);
            margin: 20px 0;
            border: 4px solid rgba(255,255,255,0.1);
        }

        /* 自测题容器 (Tab 4) */
        .quiz-wrapper {
            background-color: #ffffff;
            border: 1px solid #e9ecef;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 10px 20px rgba(0,0,0,0.05);
        }
        
        /* 隐藏 Streamlit 默认页脚 */
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 复杂 Session State 状态机 (确保交互不重置)
# ==========================================
if 'lang' not in st.session_state: st.session_state.lang = 'CN'
if 'processed_data' not in st.session_state: st.session_state.processed_data = None
if 'up_key' not in st.session_state: st.session_state.up_key = 0

# 交互组件状态
if 'f_idx' not in st.session_state: st.session_state.f_idx = 0
if 'f_flipped' not in st.session_state: st.session_state.f_flipped = False
if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'q_submitted' not in st.session_state: st.session_state.q_submitted = False
if 'chat_history' not in st.session_state: st.session_state.chat_history = []

# ==========================================
# 4. 国际化字典 (全界面翻译)
# ==========================================
D = {
    'CN': {
        'switch': "English Version",
        'title': "🎓 国际学校 AI 智能课程分析系统",
        'up_label': "请上传 PDF 教材 (支持多个文件同时上传)",
        'up_done': "✅ 已成功载入 {} 个学术文件",
        'clear': "🗑️ 一键清空",
        'analyze': "🚀 开始生成深度交互报告",
        'wait': "AI 教务主任分析中 (预计需要 20-40 秒)...",
        'eta': "分析进度: {}% | 预计还需 {} 秒",
        'tab1': "📖 学习理解", 'tab2': "📝 复习备考", 'tab3': "🃏 交互闪卡", 'tab4': "✍️ 模拟自测", 'tab5': "🤖 AI 助教",
        'next': "下一题", 'prev': "上一题", 'flip': "翻转卡片", 'submit': "提交答案",
        'correct': "✅ 正确！", 'wrong': "❌ 错误！", 'ans': "正确答案：", 'reason': "深度解析",
        'restart': "重新开始测试", 'chat_hit': "询问关于课程的任何问题...",
        'prompt_sys': f"你是一名有30年经验的国际学校教务主任。请针对教材生成报告。要求：[1] 学习理解模块核心词包裹在 <MARK></MARK> 中。[2] 复习备考模块使用💡。[3] 闪卡和题目必须是严格 JSON。模型锁定：{TARGET_MODEL}"
    },
    'EN': {
        'switch': "切换至中文",
        'title': "🎓 AI International Course Terminal",
        'up_label': "Upload PDF Materials (Multiple)",
        'up_done': "✅ {} academic files loaded",
        'clear': "🗑️ Clear All",
        'analyze': "🚀 Generate Interactive Report",
        'wait': "Analyzing content, please wait...",
        'eta': "Progress: {}% | ETA: {}s",
        'tab1': "📖 Learning", 'tab2': "📝 Revision", 'tab3': "🃏 Flashcards", 'tab4': "✍️ Self-Test", 'tab5': "🤖 AI Tutor",
        'next': "Next", 'prev': "Previous", 'flip': "Flip Card", 'submit': "Submit",
        'correct': "✅ Correct!", 'wrong': "❌ Wrong!", 'ans': "Correct Answer:", 'reason': "Analysis",
        'restart': "Restart Test", 'chat_hit': "Ask AI about the course...",
        'prompt_sys': f"You are a senior Academic Director. Generate report. [1] Wrap key terms in <MARK></MARK> in Learning section. [2] Use 💡 in Revision. [3] JSON for cards and quiz. Model: {TARGET_MODEL}"
    }
}
ui = D[st.session_state.lang]

# ==========================================
# 5. UI 头部布局
# ==========================================
st.markdown('<div class="header-wrapper">', unsafe_allow_html=True)
c_title, c_lang = st.columns([0.8, 0.2])
with c_title:
    st.title(ui['title'])
with c_lang:
    if st.button(ui['switch'], key="lang_btn", use_container_width=True):
        st.session_state.lang = 'EN' if st.session_state.lang == 'CN' else 'CN'
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 6. 文件上传管理
# ==========================================
uploaded_pdfs = st.file_uploader(ui['up_label'], type=['pdf'], accept_multiple_files=True, key=f"up_{st.session_state.up_key}")

if uploaded_pdfs:
    col_info, col_clear = st.columns([0.7, 0.3])
    with col_info:
        st.info(ui['up_done'].format(len(uploaded_pdfs)))
    with col_clear:
        if st.button(ui['clear'], use_container_width=True):
            st.session_state.up_key += 1
            st.session_state.processed_data = None
            st.rerun()

# ==========================================
# 7. AI 引擎 (修复 F-string 大括号转义)
# ==========================================
def run_academic_analysis(files):
    # 提取 PDF
    text = ""
    for f in files:
        reader = PdfReader(f)
        for page in reader.pages: text += (page.extract_text() or "") + "\n"
    
    # 配置 API
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel(TARGET_MODEL)
    
    # 核心修复：JSON 示例中的大括号必须双写 {{ }} 以防 ValueError
    prompt = f"""
    {ui['prompt_sys']}
    Language: {st.session_state.lang}

    请严格按照以下标记输出内容：
    [L_SECTION]
    总结内容。核心概念必须包裹在 <MARK>核心词</MARK> 中。
    [/L_SECTION]

    [R_SECTION]
    复习备考重点。多用 💡。
    [/R_SECTION]

    [FLASH_JSON]
    [ {{"q": "问题内容", "a": "答案内容"}} ]
    [/FLASH_JSON]

    [QUIZ_JSON]
    [ {{"q": "题目", "o": ["A","B","C","D"], "a": "A", "e": "深度解析内容"}} ]
    [/QUIZ_JSON]

    教材原始内容：
    {text[:35000]}
    """
    response = model.generate_content(prompt)
    return response.text

if uploaded_pdfs and st.button(ui['analyze'], type="primary", use_container_width=True):
    bar = st.progress(0)
    msg = st.empty()
    msg.warning(ui['wait'])
    
    # 模拟平滑进度
    for p in range(1, 35):
        time.sleep(0.05); bar.progress(p)
    
    # 调用真实 AI
    try:
        raw_result = run_academic_analysis(uploaded_pdfs)
        
        for p in range(36, 101):
            time.sleep(0.01); bar.progress(p)
        
        st.session_state.processed_data = raw_result
        # 重置所有交互索引
        st.session_state.f_idx = 0
        st.session_state.f_flipped = False
        st.session_state.q_idx = 0
        st.session_state.q_submitted = False
        st.rerun()
    except Exception as e:
        st.error(f"Error: {str(e)}")

# ==========================================
# 8. 交互展示区域 (五大 Tabs)
# ==========================================
if st.session_state.processed_data:
    raw = st.session_state.processed_data
    
    # 安全提取正则函数
    def extract_tag(tag, text):
        try:
            pattern = f"\[{tag}\](.*?)\[/{tag}\]"
            return re.findall(pattern, text, re.DOTALL)[0].strip()
        except: return ""

    tabs = st.tabs([ui['tab1'], ui['tab2'], ui['tab3'], ui['tab4'], ui['tab5']])

    # --- Tab 1: 学习理解 (着色处理) ---
    with tabs[0]:
        c1 = extract_tag("L_SECTION", raw)
        # 重点词转换成 HTML Span
        c1 = c1.replace("<MARK>", '<span class="highlight-blue">').replace("</MARK>", '</span>')
        st.markdown(f'<div class="learning-container">{c1}</div>', unsafe_allow_html=True)

    # --- Tab 2: 复习备考 ---
    with tabs[1]:
        c2 = extract_tag("R_SECTION", raw)
        st.info(c2)

    # --- Tab 3: 交互闪卡 (一题一题) ---
    with tabs[2]:
        try:
            f_data = json.loads(extract_tag("FLASH_JSON", raw))
            f_idx = st.session_state.f_idx
            card = f_data[f_idx]
            
            st.write(f"Card {f_idx + 1} / {len(f_data)}")
            # 翻转逻辑
            disp = card['a'] if st.session_state.f_flipped else card['q']
            st.markdown(f'<div class="flashcard-main">{disp}</div>', unsafe_allow_html=True)
            
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                if st.button(ui['prev'], key="f_p") and f_idx > 0:
                    st.session_state.f_idx -= 1
                    st.session_state.f_flipped = False
                    st.rerun()
            with col_b2:
                if st.button(ui['flip'], key="f_flip", use_container_width=True):
                    st.session_state.f_flipped = not st.session_state.f_flipped
                    st.rerun()
            with col_b3:
                if st.button(ui['next'], key="f_n") and f_idx < len(f_data)-1:
                    st.session_state.f_idx += 1
                    st.session_state.f_flipped = False
                    st.rerun()
        except: st.warning("Flashcard parsing error.")

    # --- Tab 4: 交互自测 (答题+深度分析) ---
    with tabs[3]:
        try:
            q_data = json.loads(extract_tag("QUIZ_JSON", raw))
            q_idx = st.session_state.q_idx
            q_item = q_data[q_idx]
            
            st.markdown('<div class="quiz-wrapper">', unsafe_allow_html=True)
            st.subheader(f"Q{q_idx + 1}: {q_item['q']}")
            
            # 单选组件
            ans_choice = st.radio("Options:", q_item['o'], key=f"q_radio_{q_idx}")
            
            if not st.session_state.q_submitted:
                if st.button(ui['submit'], type="primary"):
                    st.session_state.q_submitted = True
                    st.rerun()
            else:
                # 判定逻辑
                correct = ans_choice.startswith(q_item['a'])
                if correct: st.success(ui['correct'])
                else: st.error(f"{ui['wrong']} {ui['ans']} {q_item['a']}")
                
                # 深度解析
                st.info(f"💡 **{ui['reason']}:** {q_item['e']}")
                
                # 导航
                if st.button(ui['next'] if q_idx < len(q_data)-1 else ui['restart']):
                    if q_idx < len(q_data)-1:
                        st.session_state.q_idx += 1
                        st.session_state.q_submitted = False
                    else:
                        st.session_state.q_idx = 0
                        st.session_state.q_submitted = False
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        except: st.warning("Quiz parsing error.")

    # --- Tab 5: AI 助教 ---
    with tabs[4]:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.write(msg["content"])
        
        if prompt := st.chat_input(ui['chat_hit']):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)
            
            with st.chat_message("assistant"):
                m_chat = genai.GenerativeModel(TARGET_MODEL)
                resp = m_chat.generate_content(f"Context: {raw[:5000]}\nQuestion: {prompt}")
                st.write(resp.text)
                st.session_state.chat_history.append({"role": "assistant", "content": resp.text})