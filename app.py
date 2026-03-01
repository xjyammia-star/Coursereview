import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import time
import json
import re
import datetime

# ==========================================
# 1. 核心模型锁定 (硬性要求：gemini-2.5-flash)
# ==========================================
STR_MODEL_ID = "gemini-2.5-flash"

# ==========================================
# 2. 顶级页面配置与 CSS 视觉引擎
# ==========================================
st.set_page_config(
    page_title="AI International Academic Director", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# 强力注入 CSS：彻底抹除侧边栏，优化交互 UI，解决按钮遮挡
st.markdown("""
    <style>
        /* 1. 强制隐藏侧边栏及其所有相关元素 */
        [data-testid="stSidebar"], section[data-testid="stSidebar"], .css-nqow43 {
            display: none !important;
            width: 0px !important;
        }
        .main .block-container {
            padding-top: 1.5rem !important;
            max-width: 95% !important;
        }

        /* 2. 右上角语言切换容器布局 */
        .top-nav-area {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            padding: 10px 0;
            margin-bottom: -40px;
        }

        /* 3. 学习理解模块：学术蓝着色高亮 */
        .academic-focus-box {
            background-color: #f0f7ff;
            border-left: 8px solid #004a99;
            padding: 25px;
            border-radius: 12px;
            margin: 15px 0;
            line-height: 1.8;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }
        .term-highlight {
            background-color: #fff3bf;
            color: #d9480f;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 4px;
            border-bottom: 2px solid #fab005;
        }

        /* 4. 交互闪卡样式：3D渐变感 */
        .flashcard-display {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 60px 40px;
            border-radius: 25px;
            text-align: center;
            min-height: 350px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.8rem;
            font-weight: 700;
            box-shadow: 0 20px 40px rgba(0,0,0,0.25);
            margin: 20px 0;
            border: 5px solid rgba(255,255,255,0.1);
        }

        /* 5. 模拟考题容器 */
        .quiz-container-box {
            background-color: #ffffff;
            border: 1px solid #e1e4e8;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
            margin-bottom: 20px;
        }

        /* 6. 隐藏 Streamlit 默认元素 */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 稳健的状态管理机 (Session State)
# ==========================================
if 'lang_mode' not in st.session_state: st.session_state.lang_mode = 'CN'
if 'raw_ai_output' not in st.session_state: st.session_state.raw_ai_output = None
if 'up_key_id' not in st.session_state: st.session_state.up_key_id = 1000

# 闪卡交互状态
if 'idx_flash' not in st.session_state: st.session_state.idx_flash = 0
if 'is_flipped' not in st.session_state: st.session_state.is_flipped = False

# 自测交互状态
if 'idx_quiz' not in st.session_state: st.session_state.idx_quiz = 0
if 'is_quiz_submitted' not in st.session_state: st.session_state.is_quiz_submitted = False
if 'quiz_score_total' not in st.session_state: st.session_state.quiz_score_total = 0

# 聊天记录
if 'chat_records' not in st.session_state: st.session_state.chat_records = []

# ==========================================
# 4. 国际化字典：包含详尽的报错解释
# ==========================================
UI_MAP = {
    'CN': {
        'switch': "English UI",
        'title': "🎓 国际课程 AI 智能分析与复习终端",
        'up_hint': "请上传 PDF 课程文件 (支持多文件同时上传)",
        'up_count': "当前已成功载入 {} 个学术文件",
        'clear_btn': "🗑️ 彻底清空内容",
        'run_btn': "🚀 生成交互式复习报告",
        'wait_msg': "AI 教务主任正在深度解析内容，请稍候...",
        'eta_msg': "处理进度: {}% | 预计剩余时间: {} 秒",
        'done_msg': "报告生成成功！您可以开始复习了。",
        'tab1': "📖 学习理解", 'tab2': "📝 复习备考", 'tab3': "🃏 闪卡训练", 'tab4': "✍️ 交互自测", 'tab5': "🤖 AI 助教",
        'prev_q': "上一题", 'next_q': "下一题", 'flip_card': "翻转卡片 (查看答案)", 'submit_q': "提交并查看分析",
        'correct_label': "✅ 回答正确！", 'wrong_label': "❌ 回答错误！正确答案是：", 'anal_label': "深度解析：",
        'reset_test': "重新开始模拟考", 'chat_ph': "向 AI 助教咨询课程问题...",
        'error_429': "⚠️ 【配额限制】AI 教务主任由于访问人数过多需要稍作休息。请您在 60 秒后再次尝试点击“生成报告”。",
        'error_other': "⚠️ 【系统提示】处理过程中遇到未知干扰，请确保 PDF 文件清晰并刷新页面重试。",
        'prompt_sys': f"你是一名有30年经验的国际学校教务主任。请针对上传教材生成报告。要求：[1] 学习理解部分重点词包裹在 <MARK></MARK> 中。[2] 复习备考模块使用💡。[3] 闪卡和题目必须输出为严格 JSON。模型锁定：{STR_MODEL_ID}"
    },
    'EN': {
        'switch': "切换至中文",
        'title': "🎓 AI International Academic Review System",
        'up_hint': "Upload Course PDFs (Multiple Supported)",
        'up_count': "{} files uploaded successfully",
        'clear_btn': "🗑️ Clear & Reset",
        'run_btn': "🚀 Generate Interactive Report",
        'wait_msg': "Academic Director AI is analyzing content...",
        'eta_msg': "Progress: {}% | ETA: {}s",
        'done_msg': "Analysis complete! You may start reviewing.",
        'tab1': "📖 Learning", 'tab2': "📝 Revision", 'tab3': "🃏 Flashcards", 'tab4': "✍️ Quiz", 'tab5': "🤖 AI Tutor",
        'prev_q': "Previous", 'next_q': "Next", 'flip_card': "Flip Card (See Answer)", 'submit_q': "Submit & Analyze",
        'correct_label': "✅ Correct!", 'wrong_label': "❌ Incorrect! The right answer is:", 'anal_label': "Analysis:",
        'reset_test': "Restart Quiz", 'chat_ph': "Ask AI about the course...",
        'error_429': "⚠️ [Rate Limit] The AI Director is currently overwhelmed. Please wait about 60 seconds before clicking 'Generate' again.",
        'error_other': "⚠️ [System Notice] An error occurred. Please ensure the PDF is readable and refresh.",
        'prompt_sys': f"You are a senior Academic Director. Generate report. [1] Wrap key terms in <MARK></MARK> in Learning section. [2] Use 💡 in Revision. [3] JSON for cards and quiz. Model: {STR_MODEL_ID}"
    }
}

txt = UI_MAP[st.session_state.lang_mode]

# ==========================================
# 5. UI 头部布局与语言切换 (右上角)
# ==========================================
st.markdown('<div class="top-nav-area">', unsafe_allow_html=True)
header_col1, header_col2 = st.columns([0.8, 0.2])
with header_col1:
    st.title(txt['title'])
with header_col2:
    if st.button(txt['switch'], key="toggle_lang_btn", use_container_width=True):
        st.session_state.lang_mode = 'EN' if st.session_state.lang_mode == 'CN' else 'CN'
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 6. 文件处理区域
# ==========================================
uploaded_files = st.file_uploader(
    txt['up_hint'], 
    type=['pdf'], 
    accept_multiple_files=True, 
    key=f"file_uploader_{st.session_state.up_key_id}"
)

if uploaded_files:
    info_c, clear_c = st.columns([0.7, 0.3])
    with info_c:
        st.info(txt['up_count'].format(len(uploaded_files)))
    with clear_c:
        if st.button(txt['clear_btn'], use_container_width=True):
            st.session_state.up_key_id += 1
            st.session_state.raw_ai_output = None
            st.session_state.chat_records = []
            st.rerun()

# ==========================================
# 7. AI 分析引擎 (包含 429 拦截逻辑)
# ==========================================
def call_academic_ai(files):
    # 1. 解析文本
    full_text_stream = ""
    for f in files:
        reader = PdfReader(f)
        for page in reader.pages:
            full_text_stream += (page.extract_text() or "") + "\n"
    
    # 2. 配置并调用
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model_instance = genai.GenerativeModel(STR_MODEL_ID)
    
    # 使用 {{ }} 避开 f-string 转义大括号的 ValueError
    ai_prompt = f"""
    {txt['prompt_sys']}
    Language Mode: {st.session_state.lang_mode}

    请严格按照以下标记输出：
    [LEARN_CONTENT] 总结内容，用 <MARK>重点词</MARK> 着色 [/LEARN_CONTENT]
    [REVISION_CONTENT] 💡 复习重点... [/REVISION_CONTENT]
    [FLASHCARDS_JSON] [ {{ "q": "问题", "a": "答案" }} ] [/FLASHCARDS_JSON]
    [QUIZ_JSON] [ {{ "q": "题目", "o": ["A","B","C","D"], "a": "A", "e": "详细解析" }} ] [/QUIZ_JSON]

    教材全文内容如下：
    {full_text_stream[:33000]}
    """
    
    try:
        response = model_instance.generate_content(ai_prompt)
        return response.text, None
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "quota" in err_msg.lower() or "exhausted" in err_msg.lower():
            return None, "QUOTA_429"
        else:
            return None, "OTHER_ERR"

# ==========================================
# 8. 进度条执行器
# ==========================================
if uploaded_files and st.button(txt['run_btn'], type="primary", use_container_width=True):
    progress_bar = st.progress(0)
    msg_container = st.empty()
    eta_container = st.empty()
    
    msg_container.warning(txt['wait_msg'])
    
    # 模拟平滑进度 (35% 之前为读取和网络请求等待)
    for p in range(1, 36):
        time.sleep(0.04)
        progress_bar.progress(p)
    
    # 实际发起 AI 调用
    result_text, error_type = call_academic_ai(uploaded_files)
    
    if error_type == "QUOTA_429":
        msg_container.error(txt['error_429'])
        progress_bar.empty()
    elif error_type == "OTHER_ERR":
        msg_container.error(txt['error_other'])
        progress_bar.empty()
    else:
        # AI 返回成功，平滑走完后 65%
        for p in range(36, 101):
            time.sleep(0.01)
            progress_bar.progress(p)
            eta_container.text(txt['eta_msg'].format(p, (100-p)//10))
            
        st.session_state.raw_ai_output = result_text
        st.session_state.idx_flash = 0
        st.session_state.idx_quiz = 0
        st.session_state.is_quiz_submitted = False
        msg_container.success(txt['done_msg'])
        time.sleep(1)
        st.rerun()

# ==========================================
# 9. 交互展示区域 (五大 Tabs)
# ==========================================
if st.session_state.raw_ai_output:
    raw_res = st.session_state.raw_ai_output
    
    # 稳健的正则解析函数
    def parse_section(tag, source):
        try:
            pattern = f"\[{tag}\](.*?)\[/{tag}\]"
            finds = re.findall(pattern, source, re.DOTALL)
            return finds[0].strip() if finds else ""
        except: return ""

    tab_learn, tab_rev, tab_flash, tab_quiz, tab_chat = st.tabs([
        txt['tab1'], txt['tab2'], txt['tab3'], txt['tab4'], txt['tab5']
    ])

    # --- Tab 1: 学习理解 (着色处理) ---
    with tab_learn:
        raw_learn = parse_section("LEARN_CONTENT", raw_res)
        # 将 <MARK> 替换为 Span 并应用 academic-focus-box
        styled_learn = raw_learn.replace("<MARK>", '<span class="term-highlight">').replace("</MARK>", '</span>')
        st.markdown(f'<div class="academic-focus-box">{styled_learn}</div>', unsafe_allow_html=True)

    # --- Tab 2: 复习备考 ---
    with tab_rev:
        raw_rev = parse_section("REVISION_CONTENT", raw_res)
        st.info(raw_rev if raw_rev else "Revision content extraction failed.")

    # --- Tab 3: 交互闪卡 (一题一题切换 + 翻转) ---
    with tab_flash:
        try:
            flash_data_str = parse_section("FLASHCARDS_JSON", raw_res)
            flash_list = json.loads(flash_data_str)
            
            f_idx = st.session_state.idx_flash
            curr_card = flash_list[f_idx]
            
            st.write(f"Card {f_idx + 1} / {len(flash_list)}")
            
            # 翻转逻辑：True显示答案，False显示问题
            disp_text = curr_card['a'] if st.session_state.is_flipped else curr_card['q']
            st.markdown(f'<div class="flashcard-display">{disp_text}</div>', unsafe_allow_html=True)
            
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                if st.button(txt['prev_q'], key="btn_f_prev") and f_idx > 0:
                    st.session_state.idx_flash -= 1
                    st.session_state.is_flipped = False; st.rerun()
            with col_f2:
                if st.button(txt['flip_card'], key="btn_f_flip", use_container_width=True):
                    st.session_state.is_flipped = not st.session_state.is_flipped; st.rerun()
            with col_f3:
                if st.button(txt['next_q'], key="btn_f_next") and f_idx < len(flash_list)-1:
                    st.session_state.idx_flash += 1
                    st.session_state.is_flipped = False; st.rerun()
        except:
            st.warning("Flashcard JSON parsing error. Please re-generate.")

    # --- Tab 4: 模拟交互自测 (单题+深度分析) ---
    with tab_quiz:
        try:
            quiz_data_str = parse_section("QUIZ_JSON", raw_res)
            quiz_list = json.loads(quiz_data_str)
            
            q_idx = st.session_state.idx_quiz
            q_item = quiz_list[q_idx]
            
            st.markdown('<div class="quiz-container-box">', unsafe_allow_html=True)
            st.subheader(f"Q{q_idx + 1}: {q_item['q']}")
            
            # 单选组件
            user_ans = st.radio("Options:", q_item['o'], key=f"radio_quiz_{q_idx}")
            
            if not st.session_state.is_quiz_submitted:
                if st.button(txt['submit_q'], type="primary", use_container_width=True):
                    st.session_state.is_quiz_submitted = True; st.rerun()
            else:
                # 显示对错判定
                is_right = user_ans.startswith(q_item['a'])
                if is_right: st.success(txt['correct_label'])
                else: st.error(f"{txt['wrong_label']} {q_item['a']}")
                
                # 显示核心深度解析
                st.info(f"💡 **{txt['anal_label']}** {q_item['e']}")
                
                # 导航至下一题或重启
                if st.button(txt['next_q'] if q_idx < len(quiz_list)-1 else txt['reset_test'], use_container_width=True):
                    if q_idx < len(quiz_list)-1:
                        st.session_state.idx_quiz += 1
                        st.session_state.is_quiz_submitted = False
                    else:
                        st.session_state.idx_quiz = 0
                        st.session_state.is_quiz_submitted = False
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        except:
            st.warning("Quiz JSON parsing error. Please re-generate.")

    # --- Tab 5: AI 助教对话 ---
    with tab_chat:
        for m in st.session_state.chat_records:
            with st.chat_message(m["role"]): st.write(m["content"])
            
        if user_prompt := st.chat_input(txt['chat_ph']):
            st.session_state.chat_records.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"): st.write(user_prompt)
            
            with st.chat_message("assistant"):
                m_chat = genai.GenerativeModel(STR_MODEL_ID)
                # 提供当前分析的上下文进行对话
                context_msg = f"Based on this course report: {raw_res[:4000]}\nUser asked: {user_prompt}"
                resp = m_chat.generate_content(context_msg)
                st.write(resp.text)
                st.session_state.chat_records.append({"role": "assistant", "content": resp.text})