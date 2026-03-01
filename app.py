import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import time
import random

# ==========================================
# 1. 核心模型锁定 (强制硬编码)
# ==========================================
TARGET_MODEL = "gemini-2.5-flash"

# ==========================================
# 2. 页面与视觉架构 (极致隐藏侧边栏)
# ==========================================
st.set_page_config(
    page_title="AI International Course System",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 强力 CSS 注入：隐藏侧边栏、美化界面、定制高亮
st.markdown("""
    <style>
        /* 彻底消除侧边栏及其占位 */
        [data-testid="stSidebar"], [data-testid="stSidebarNav"], section[data-testid="stSidebar"] {
            display: none !important;
            width: 0px !important;
        }
        /* 移除顶部多余空白 */
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 1rem !important;
        }
        /* 右上角按钮美化 */
        .stButton button {
            border-radius: 12px;
            font-weight: 600;
        }
        /* 复习重点块 - 橙色警示风格 */
        .revision-highlight {
            background-color: #fff9db;
            border-left: 5px solid #fcc419;
            padding: 1.5rem;
            border-radius: 8px;
            color: #444;
            margin: 10px 0;
        }
        /* 闪卡卡片风格 */
        .flashcard {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 0.5rem;
            border-bottom: 3px solid #339af0;
        }
        /* 隐藏 Streamlit 默认页脚 */
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 多语言支持系统 (Session State)
# ==========================================
if 'lang' not in st.session_state:
    st.session_state.lang = 'CN'
if 'result_raw' not in st.session_state:
    st.session_state.result_raw = None
if 'file_key' not in st.session_state:
    st.session_state.file_key = 0
if 'chat_msgs' not in st.session_state:
    st.session_state.chat_msgs = []

# 定义全量文本映射
DIC = {
    'CN': {
        'toggle': "English Version",
        'title': "🎓 国际学校课程 AI 智能分析终端",
        'up_label': "请上传课程 PDF 教材 (支持多个文件同时上传)",
        'up_success': "✅ 成功载入 {} 个学术文件",
        'clear': "🗑️ 一键清除所有文件",
        'analyze': "开始深度分析课程 (AI 发起)",
        'step_read': "正在读取 PDF 文本内容...",
        'step_ai': "正在调用 Gemini 2.5 Flash 进行学术归纳...",
        'eta': "预计进度: {}% | 剩余约 {} 秒",
        'finish': "分析任务圆满完成！",
        'tab1': "📖 学习理解",
        'tab2': "📝 复习备考",
        'tab3': "🃏 闪卡训练",
        'tab4': "✍️ 自测题目",
        'tab5': "🤖 AI 助教",
        'chat_input': "输入问题，咨询您的 AI 助教...",
        'error_api': "API 调用失败，请检查密钥或网络状态。",
        'prompt_role': f"你是一名拥有30年经验的国际学校教务主任，精通 IB, A-Level, AP, IGCSE 等课程。你的任务是基于上传的教材，生成一份极其专业的学习复习报告。必须使用中文。模型锁定：{TARGET_MODEL}"
    },
    'EN': {
        'toggle': "切换至中文",
        'title': "🎓 AI International Course Analytics Terminal",
        'up_label': "Upload Course PDF Materials (Multiple files supported)",
        'up_success': "✅ {} academic files loaded successfully",
        'clear': "🗑️ Clear and Restart",
        'analyze': "Start Deep Analysis (AI Trigger)",
        'step_read': "Reading PDF text content...",
        'step_ai': "Analyzing with Gemini 2.5 Flash...",
        'eta': "Progress: {}% | ETA: {}s",
        'finish': "Analysis Task Completed!",
        'tab1': "📖 Understanding",
        'tab2': "📝 Revision",
        'tab3': "🃏 Flashcards",
        'tab4': "✍️ Self-Test",
        'tab5': "🤖 AI Assistant",
        'chat_input': "Ask your AI tutor anything...",
        'error_api': "API call failed. Please check your credentials.",
        'prompt_role': f"You are a senior Academic Director with 30 years of experience in IB, A-Level, AP, etc. Your task is to generate a highly professional review report based on the provided materials. MUST BE IN ENGLISH. Model: {TARGET_MODEL}"
    }
}

ui = DIC[st.session_state.lang]

# ==========================================
# 4. 头部导航 (右上角切换语言)
# ==========================================
h_col1, h_col2 = st.columns([0.8, 0.2])
with h_col1:
    st.title(ui['title'])
with h_col2:
    if st.button(ui['toggle'], use_container_width=True):
        st.session_state.lang = 'EN' if st.session_state.lang == 'CN' else 'CN'
        st.rerun()

st.divider()

# ==========================================
# 5. 上传管理区
# ==========================================
pdf_inputs = st.file_uploader(
    ui['up_label'],
    type=['pdf'],
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.file_key}"
)

if pdf_inputs:
    info_c, ctrl_c = st.columns([0.7, 0.3])
    with info_c:
        st.success(ui['up_success'].format(len(pdf_inputs)))
    with ctrl_c:
        if st.button(ui['clear'], use_container_width=True):
            st.session_state.file_key += 1
            st.session_state.result_raw = None
            st.session_state.chat_msgs = []
            st.rerun()

# ==========================================
# 6. 学术分析引擎 (PDF 处理 + API 调用)
# ==========================================
def perform_academic_analysis(files):
    # 提取文本
    combined_text = ""
    for f in files:
        reader = PdfReader(f)
        for page in reader.pages:
            combined_text += (page.extract_text() or "") + "\n"
    
    # 准备 API
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel(TARGET_MODEL)
        
        # 精心设计的系统 Prompt，确保五个模块被标记，方便切分
        sys_prompt = f"""
        {ui['prompt_role']}
        
        请严格按以下格式输出，不要包含多余的开场白：
        ---SECTION_1---
        (此处为学习理解模块：简洁归纳核心内容，多使用层级符号)
        ---SECTION_2---
        (此处为复习备考模块：抓取重难点。对最关键的知识点请用 💡 标注并加粗。关键术语必须突出。)
        ---SECTION_3---
        (此处为闪卡部分：5-20个闪卡。格式：Q: [问题] | A: [答案])
        ---SECTION_4---
        (此处为自测部分：10-20题，包含各种题型，最后附上答案)
        ---END---
        
        待分析教材内容：
        {combined_text[:35000]}
        """
        
        response = model.generate_content(sys_prompt)
        return response.text
    except Exception as e:
        st.error(f"{ui['error_api']} : {str(e)}")
        return None

# ==========================================
# 7. 进度反馈与执行逻辑
# ==========================================
if pdf_inputs and st.button(ui['analyze'], type="primary", use_container_width=True):
    bar = st.progress(0)
    msg_slot = st.empty()
    eta_slot = st.empty()
    
    # 步骤 1: 读取
    msg_slot.info(ui['step_read'])
    time.sleep(1) # 增加物理读取感
    bar.progress(10)
    
    # 步骤 2: 调用 AI
    msg_slot.info(ui['step_ai'])
    
    # 开启模拟倒计时
    start_time = time.time()
    total_expected = 25 # 预估处理时间
    
    # 真实 API 请求
    raw_output = perform_academic_analysis(pdf_inputs)
    
    # 模拟平滑进度条
    for i in range(11, 101):
        elapsed = time.time() - start_time
        remain = max(1, total_expected - int(elapsed))
        bar.progress(i)
        eta_slot.write(ui['eta'].format(i, remain))
        time.sleep(0.05) if i < 90 else time.sleep(0.01)
        
    if raw_output:
        st.session_state.result_raw = raw_output
        msg_slot.success(ui['finish'])
        eta_slot.empty()
        time.sleep(1)
        st.rerun()

# ==========================================
# 8. 成果展示区 (学术报告 Tabs)
# ==========================================
if st.session_state.result_raw:
    raw = st.session_state.result_raw
    
    # 稳健的切分逻辑
    try:
        s1 = raw.split("---SECTION_1---")[1].split("---SECTION_2---")[0]
        s2 = raw.split("---SECTION_2---")[1].split("---SECTION_3---")[0]
        s3 = raw.split("---SECTION_3---")[1].split("---SECTION_4---")[0]
        s4 = raw.split("---SECTION_4---")[1].split("---END---")[0]
    except:
        s1, s2, s3, s4 = raw, "Error", "Error", "Error"

    tab1, tab2, tab3, tab4, tab5 = st.tabs([ui['tab1'], ui['tab2'], ui['tab3'], ui['tab4'], ui['tab5']])
    
    with tab1:
        st.markdown(s1)
    
    with tab2:
        # 使用自定义 CSS 类来美化复习重点
        st.markdown(f'<div class="revision-highlight">{s2}</div>', unsafe_allow_html=True)
        
    with tab3:
        # 闪卡部分美化
        cards = s3.strip().split("\n")
        for card in cards:
            if "|" in card:
                st.markdown(f'<div class="flashcard">{card}</div>', unsafe_allow_html=True)
            else:
                st.write(card)
                
    with tab4:
        st.markdown(s4)
        
    with tab5:
        st.subheader(ui['tab5'])
        # 对话容器
        for m in st.session_state.chat_msgs:
            with st.chat_message(m["role"]):
                st.write(m["content"])
        
        if q := st.chat_input(ui['chat_input']):
            st.session_state.chat_msgs.append({"role": "user", "content": q})
            with st.chat_message("user"):
                st.write(q)
            
            with st.chat_message("assistant"):
                m_chat = genai.GenerativeModel(TARGET_MODEL)
                # 注入上下文进行对话
                context = f"Context Material: {s1[:3000]}\nUser Question: {q}"
                resp = m_chat.generate_content(context)
                st.write(resp.text)
                st.session_state.chat_msgs.append({"role": "assistant", "content": resp.text})