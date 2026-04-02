import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import os
import re
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# 設定頁面
st.set_page_config(page_title="急診專師協助派發系統", page_icon="🏥", layout="wide")

# 設定五分鐘 (300000 毫秒) 自動重新整理一次
count = st_autorefresh(interval=300000, limit=None, key="data_sync_refresh")

DATA_FILE = "task_data.json"
USERS_FILE = "users_data.json"

# --- 台灣時間轉換函數 ---
def get_tw_time():
    return datetime.utcnow() + timedelta(hours=8)

# --- 全新分層床位資料庫 ---
BED_DATA_COMPLEX = {
    "留觀(OBS)": {
        "OBS 1": ["1", "2", "3", "5", "6", "7", "8", "9", "10", "35", "36", "37", "38"],
        "OBS 2": ["11", "12", "13", "15", "16", "17", "18", "19", "20", "21", "22", "23"],
        "OBS 3": ["25", "26", "27", "28", "29", "30", "31", "32", "33", "39"]
    },
    "診間": {
        "第一診間": ["11", "12", "13", "15", "21", "22", "23", "25"],
        "第二診間": ["16", "17", "18", "19", "20", "36", "37", "38"],
        "第三診間": ["5", "6", "27", "28", "29", "30", "31", "32", "33", "39"]
    },
    "兒科": {
        "兒科床位": ["501", "502", "503", "505", "506", "507", "508", "509"]
    },
    "急救區": {},
    "檢傷": {},
    "縫合室": {},
    "超音波室": {}
}

# --- 資料庫操作 ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            for t in data:
                if 'priority' not in t: t['priority'] = '🟢 一般'
            return data
        except json.JSONDecodeError:
            return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_user(nickname):
    users = load_users()
    if nickname not in users:
        users.append(nickname)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)

# --- 資安：身分證字號偵測 ---
def check_pii(*texts):
    # 判斷是否符合台灣身分證格式 (1英文字母 + 1或2或8或9 + 8個數字)
    for t in texts:
        if t and re.search(r'[A-Za-z][1289]\d{8}', str(t)):
            return True
    return False

# --- 初始化 Session State ---
if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False
if "nickname" not in st.session_state:
    st.session_state.nickname = ""
if "role" not in st.session_state:
    st.session_state.role = ""
if "success_message" not in st.session_state:
    st.session_state.success_message = ""
if "known_task_ids" not in st.session_state:
    st.session_state.known_task_ids = set([t['id'] for t in load_data()])

# --- 新任務偵測與警報音系統 ---
def check_for_new_alerts():
    tasks = load_data()
    current_ids = set([t['id'] for t in tasks])
    new_ids = current_ids - st.session_state.known_task_ids
    
    if new_ids:
        st.toast("🚨 系統有新的協助任務派發！請查看列表。", icon="🔔")
        components.html(
            """
            <audio autoplay>
                <source src="https://actions.google.com/sounds/v1/alarms/beep_short.ogg" type="audio/ogg">
            </audio>
            """,
            width=0, height=0
        )
    st.session_state.known_task_ids = current_ids

# --- 護理師專用：備物確認彈出視窗 ---
@st.dialog("⚠️ 護理師派發確認")
def confirm_nurse_task(new_task):
    st.write(f"即將派發：**{new_task['priority']}** | **{new_task['bed']}** 的 **{new_task['task_type']}** 請求。")
    st.warning("請問是否已完成相關備物？")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 已完成備物，確認派發", type="primary", use_container_width=True):
            tasks = load_data()
            tasks.append(new_task)
            save_data(tasks)
            st.session_state.success_message = f"✅ 已成功送出 【 {new_task['bed']} 】 的 【 {new_task['task_type']} 】 請求！"
            st.rerun() 
    with col2:
        if st.button("❌ 尚未完成，返回修改", use_container_width=True):
            st.rerun() 

# --- 專科護理師專用：任務回報彈出視窗 ---
@st.dialog("📝 執行任務回報與結案")
def np_feedback_dialog(task_id, is_doc_assisted=False):
    tasks = load_data()
    task = next((t for t in tasks if t['id'] == task_id), None)
    
    if not task:
        st.error("找不到該任務資料！")
        return

    st.write(f"**位置/病患：** {task['bed']} | **任務：** {task['task_type']}")
    st.write(f"**派發者：** {task['requester']} ({task['requester_role']})")
    st.markdown("---")
    
    feedback_text = ""
    
    if is_doc_assisted:
        st.info("💡 目前為「醫師已協助完成」模式")
        feedback_text = st.text_input("處理結果備註", value="醫師已於現場協助處理完畢")
    else:
        if task['task_type'] == "Suture (縫合)":
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                thread_choice = st.selectbox("實際使用縫線", ["Nylon 1-0", "Nylon 2-0", "Nylon 3-0", "Nylon 4-0", "Nylon 5-0", "Nylon 6-0", "其他 (自行輸入)"])
                if thread_choice == "其他 (自行輸入)":
                    thread = st.text_input("請輸入自訂縫線", placeholder="例如: Prolene 4-0")
                    if not thread: thread = "未填寫"
                else:
                    thread = thread_choice
            with col_s2:
                stitches = st.number_input("縫合針數", min_value=1, max_value=50, value=3, step=1)
            feedback_text = f"縫線: {thread} | 針數: {stitches} 針"
            
        elif task['task_type'] == "on Foley":
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                material = st.radio("材質", ["一般 (Latex)", "矽質 (Silicone)"])
            with col_f2:
                size = st.selectbox("尺寸 (Fr)", ["14", "16", "18", "20", "22"])
            feedback_text = f"材質: {material} | 尺寸: {size} Fr"
            
        elif task['task_type'] == "on NG":
            col_n1, col_n2 = st.columns(2)
            with col_n1:
                nostril = st.radio("固定鼻孔", ["左鼻孔", "右鼻孔"])
                material = st.radio("材質", ["一般 (PVC)", "矽質 (Silicone)"])
            with col_n2:
                fix_cm = st.number_input("固定刻度 (公分數)", min_value=10, max_value=100, value=55, step=1)
            feedback_text = f"鼻孔: {nostril} | 材質: {material} | 固定刻度: {fix_cm} cm"
            
        else:
            feedback_text = st.text_input("處理結果備註 (選填)", placeholder="例如：已聯絡骨科醫師、點滴已開立...")
            if not feedback_text: feedback_text = "已處理完畢"

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 儲存回報並結案", type="primary", use_container_width=True):
        for i in range(len(tasks)):
            if tasks[i]['id'] == task_id:
                tasks[i]['status'] = '已完成'
                tasks[i]['complete_time'] = get_tw_time().strftime("%Y-%m-%d %H:%M:%S")
                # 若為醫師協助，將紀錄者標示為代轉
                if is_doc_assisted:
                    tasks[i]['handler'] = f"{st.session_state.nickname} (註記醫師完成)"
                tasks[i]['feedback'] = feedback_text
        save_data(tasks)
        st.session_state.success_message = "✅ 任務結案與回報完成！"
        st.rerun()

# --- 登入介面 ---
def login_interface():
    st.header("🔑 系統登入")
    st.markdown("歡迎使用急診專師協助派發系統，請先登入以解鎖功能。")
    
    users_list = load_users()
    
    with st.container(border=True):
        user_choice = st.selectbox("選擇曾使用的綽號", ["(新增綽號...)"] + users_list)
        if user_choice == "(新增綽號...)":
            nickname_input = st.text_input("輸入新綽號 (必填)")
        else:
            nickname_input = user_choice
            
        role_input = st.selectbox("選擇身分", ["請選擇...", "護理師", "醫師", "專科護理師"])
        
        if st.button("🚀 登入系統", use_container_width=True, type="primary"):
            final_nickname = nickname_input.strip()
            if not final_nickname:
                st.error("請輸入或選擇綽號！")
            elif role_input == "請選擇...":
                st.error("請選擇您的身分！")
            else:
                save_user(final_nickname)
                st.session_state.nickname = final_nickname
                st.session_state.role = role_input
                st.session_state.is_logged_in = True
                st.rerun()

# --- 醫師/護理師共用介面 (派發任務) ---
def assigner_interface():
    st.header(f"👋 {st.session_state.role} 派發介面")
    
    if st.session_state.success_message:
        st.success(st.session_state.success_message)
        st.session_state.success_message = "" 
        
    st.markdown("---")
    st.subheader("📍 步驟 1：選擇位置")
    
    area_options = list(BED_DATA_COMPLEX.keys()) + ["病患無床位"]
    area = st.radio("【 1. 先選大區域 】", area_options, horizontal=True)
    
    final_bed = ""
    bed_note = ""
    patient_name = ""
    
    if area in ["留觀(OBS)", "診間"]:
        sub_area = st.radio(f"【 2. 選擇 {area} 區域 】", list(BED_DATA_COMPLEX[area].keys()), horizontal=True)
        bed_num = st.radio(f"【 3. 選擇 {sub_area} 床號 】", BED_DATA_COMPLEX[area][sub_area], horizontal=True)
        final_bed = f"{sub_area} {bed_num}床"
        
    elif area == "兒科":
        bed_num = st.radio("【 2. 選擇床號 】", BED_DATA_COMPLEX[area]["兒科床位"], horizontal=True)
        final_bed = f"兒科 {bed_num}床"
        
    elif area == "病患無床位":
        patient_name = st.text_input("【 2. 填寫病患姓名 (必填) 】", placeholder="請在此貼上或輸入病患姓名...")
        if patient_name:
            final_bed = f"無床位 (病患: {patient_name})"
        else:
            final_bed = "無床位"
            
    else:
        bed_note = st.text_input(f"【 2. {area} 備註 (選填) 】", placeholder="例如：等待推床、暫放走廊...")
        final_bed = area
        if bed_note:
            final_bed += f" ({bed_note})"

    st.markdown("---")
    st.subheader("📋 步驟 2：選擇協助項目與優先級")
    
    priority = st.radio("優先級別", ["🟢 一般", "🔴 緊急"], horizontal=True)
    task_type = st.radio("協助項目", ["on Foley", "on NG", "Suture (縫合)", "會診", "藥物開立"], horizontal=True)
    
    st.markdown("##### 填寫詳細設定")
    details = ""
    med_details = "" 
    consult_dept = "" 
    
    if task_type == "on Foley":
        f_type = st.radio("Foley 種類", ["一般", "矽質"], horizontal=True)
        f_sample = st.checkbox("需留取檢體")
        details = f"種類: {f_type} | 檢體: {'是' if f_sample else '否'}"
        
    elif task_type == "on NG":
        ng_type_choice = st.radio("NG 目的", ["Re-on", "Decompression", "IRRI (沖洗)", "其他 (自行輸入)"], horizontal=True)
        if ng_type_choice == "其他 (自行輸入)":
            custom_ng = st.text_input("請輸入自訂 NG 目的/處置", placeholder="例如: 檢查反抽物...")
            actual_ng = custom_ng if custom_ng else "未填寫"
        else:
            actual_ng = ng_type_choice
        details = f"目的: {actual_ng}"
        
    elif task_type == "Suture (縫合)":
        s_part = st.selectbox("部位", ["左手", "左腳", "右手", "右腳", "胸口", "肚子", "背後", "頭皮", "臉", "脖子"])
        s_line_choice = st.selectbox("縫線選擇", [
            "Nylon 1-0", "Nylon 2-0", "Nylon 3-0", "Nylon 4-0", "Nylon 5-0", "Nylon 6-0", 
            "由專科護理師自行評估", 
            "其他 (自行輸入)"
        ])
        
        if s_line_choice == "其他 (自行輸入)":
            custom_line = st.text_input("請輸入所需縫線", placeholder="例如: Prolene 4-0, Vicryl...")
            actual_line = custom_line if custom_line else "未填寫"
        else:
            actual_line = s_line_choice
            
        details = f"部位: {s_part} | 縫線: {actual_line}"
        
    elif task_type == "會診":
        consult_dept = st.text_input("請輸入會診科別 (必填)", placeholder="例如：骨科, 外科")
        details = f"科別: {consult_dept}"
        
    elif task_type == "藥物開立":
        med_details = st.text_input("請輸入藥物名稱或處置說明 (必填)", placeholder="例如：Keto 1 amp IV stat")
        details = f"說明: {med_details}"

    st.markdown("<br>", unsafe_allow_html=True)
    btn_text = "🚀 準備派發任務 (需確認備物)" if st.session_state.role == "護理師" else "🚀 確認無誤，送出請求給專師"
    
    if st.button(btn_text, use_container_width=True, type="primary"):
        # 1. 執行資安攔截 (身分證字號判定)
        if check_pii(patient_name, details, bed_note, consult_dept, med_details):
            st.error("⚠️ 資安警告：偵測到疑似身分證字號！系統已攔截此派發。請勿在系統內填寫病患真實身分證字號以保護個資。")
            st.stop()
            
        # 2. 執行常規防呆
        if area == "病患無床位" and not patient_name.strip():
            st.warning("⚠️ 選擇無床位時，請務必填寫或貼上病患姓名！")
        elif task_type == "會診" and not consult_dept.strip():
            st.warning("⚠️ 請填寫會診科別！")
        elif task_type == "藥物開立" and not med_details.strip():
            st.warning("⚠️ 請填寫需開立的藥物名稱或說明！")
        else:
            new_task = {
                "id": str(get_tw_time().timestamp()),
                "time": get_tw_time().strftime("%Y-%m-%d %H:%M:%S"), 
                "priority": priority, 
                "bed": final_bed,
                "task_type": task_type,
                "details": details,
                "requester": st.session_state.nickname,
                "requester_role": st.session_state.role,
                "status": "待處理",
                "handler": "",
                "start_time": "",
                "complete_time": "",
                "feedback": "" 
            }
            
            if st.session_state.role == "護理師":
                confirm_nurse_task(new_task)
            else:
                tasks = load_data()
                tasks.append(new_task)
                save_data(tasks)
                st.session_state.success_message = f"✅ 已成功送出 【 {final_bed} 】 的 【 {task_type} 】 請求！"
                st.rerun()

# --- 專科護理師介面 (接收與處理任務) ---
def np_interface():
    st.header(f"👩‍⚕️ 專科護理師接收介面")
    
    if st.session_state.success_message:
        st.success(st.session_state.success_message)
        st.session_state.success_message = ""
    
    tasks = load_data()
    pending_tasks = [t for t in tasks if t['status'] == '待處理']
    in_progress_tasks = [t for t in tasks if t['status'] == '執行中' and t['handler'] == st.session_state.nickname]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"🔔 待接單任務 ({len(pending_tasks)} 筆)")
        if pending_tasks:
            for t in pending_tasks:
                task_time = datetime.strptime(t['time'], "%Y-%m-%d %H:%M:%S")
                overdue_time = task_time + timedelta(hours=1)
                is_overdue = get_tw_time() > overdue_time
                
                status_icon = "🔴" if is_overdue else "🟡"
                overdue_text = " ⚠️ (已超時)" if is_overdue else ""
                
                with st.container(border=True):
                    st.markdown(f"**{t['priority']}** | **{status_icon} {t['time'][11:16]} | {t['bed']} - {t['task_type']}**{overdue_text}")
                    st.markdown(f"📞 **派發者：{t['requester']} ({t['requester_role']})**")
                    st.write(f"📝 內容：{t['details']}")
                    
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button(f"👉 點我接單", key=f"take_{t['id']}", use_container_width=True):
                            for i in range(len(tasks)):
                                if tasks[i]['id'] == t['id']:
                                    tasks[i]['status'] = '執行中'
                                    tasks[i]['handler'] = st.session_state.nickname
                                    tasks[i]['start_time'] = get_tw_time().strftime("%Y-%m-%d %H:%M:%S")
                            save_data(tasks)
                            st.rerun()
                    with btn_col2:
                        # 點擊醫師協助，呼叫帶有 is_doc_assisted=True 的回報視窗
                        if st.button(f"👨‍⚕️ 醫師已協助完成", key=f"doc_done_{t['id']}", use_container_width=True):
                            np_feedback_dialog(t['id'], is_doc_assisted=True)
        else:
            st.info("目前沒有待處理的任務。")

    with col2:
        st.subheader(f"🏃‍♂️ 我的執行中任務 ({len(in_progress_tasks)} 筆)")
        if in_progress_tasks:
            for t in in_progress_tasks:
                with st.container(border=True):
                    st.markdown(f"**{t['priority']}** | **🔵 {t['bed']} - {t['task_type']}**")
                    st.markdown(f"📞 **派發者：{t['requester']} ({t['requester_role']})**")
                    st.write(f"📝 內容：{t['details']}")
                    st.write(f"⏱️ 接單時間：{t['start_time'][11:16]}")
                    
                    # 點擊完成回報
                    if st.button(f"✅ 標記為完成 (填寫回報)", key=f"done_btn_{t['id']}", use_container_width=True, type="primary"):
                        np_feedback_dialog(t['id'], is_doc_assisted=False)
        else:
            st.info("您目前沒有正在執行的任務。")

# --- 動態白板介面 ---
def whiteboard_interface():
    st.header("📊 系統動態白板")
    st.markdown("快速掌握急診現場協助派遣狀況（每5分鐘自動刷新）")
    
    tasks = load_data()
    pending = [t for t in tasks if t['status'] == '待處理']
    in_progress = [t for t in tasks if t['status'] == '執行中']
    
    # 擷取活躍專師名稱
    active_nps = list(set([t['handler'] for t in in_progress if t['handler']]))
    
    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 待處理任務", len(pending), "未接單", delta_color="inverse")
    col2.metric("🔵 執行中任務", len(in_progress), "處理中", delta_color="off")
    col3.metric("👨‍⚕️ 前線作戰專師", len(active_nps), "上線中", delta_color="normal")
    
    # 在卡片下方顯示實際名字
    if active_nps:
        col3.caption(f"📍 執行中: {', '.join(active_nps)}")
    else:
        col3.caption("📍 目前無專師執行任務中")
    
    st.markdown("---")
    
    w_col1, w_col2 = st.columns(2)
    
    with w_col1:
        st.subheader("🚨 未接單清單")
        if pending:
            df_pending = pd.DataFrame(pending)[['time', 'priority', 'bed', 'task_type', 'requester']]
            df_pending['time'] = df_pending['time'].str[11:16]
            df_pending.columns = ['時間', '優先級', '位置/病患', '任務', '發布者']
            st.dataframe(df_pending, use_container_width=True, hide_index=True)
        else:
            st.success("目前無積壓任務！")
            
    with w_col2:
        st.subheader("⚡ 專師執行動態")
        if in_progress:
            df_prog = pd.DataFrame(in_progress)[['handler', 'priority', 'bed', 'task_type', 'start_time']]
            df_prog['start_time'] = df_prog['start_time'].str[11:16]
            df_prog.columns = ['專師', '優先級', '位置/病患', '任務', '接單時間']
            st.dataframe(df_prog, use_container_width=True, hide_index=True)
        else:
            st.info("目前無正在執行的任務。")

# --- 後台紀錄介面 ---
def backend_interface():
    st.header("📂 後台紀錄管理")
    
    if st.session_state.success_message:
        st.success(st.session_state.success_message)
        st.session_state.success_message = ""
    
    tasks = load_data()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("檢視與管理所有歷史派發、執行回報紀錄。")
    with col2:
        if tasks:
            # 匯出資料功能
            df_export = pd.DataFrame(tasks)
            if 'feedback' not in df_export.columns: df_export['feedback'] = ""
            df_export = df_export[['id', 'time', 'priority', 'bed', 'task_type', 'details', 'feedback', 'requester', 'status', 'handler', 'start_time', 'complete_time']]
            df_export.columns = ['任務ID', '發布時間', '優先級', '位置/病患', '任務類型', '派發細節', '執行回報', '發布者', '狀態', '處理專師', '接單時間', '完成時間']
            df_export = df_export.sort_values(by='發布時間', ascending=False)
            
            csv_data = df_export.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(label="📥 匯出 Excel (CSV)", data=csv_data, file_name=f"ER_Tasks_Record_{get_tw_time().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)

    st.markdown("---")
    
    # 增加單筆刪除功能區塊
    with st.expander("🗑️ 管理員功能：刪除特定紀錄", expanded=False):
        if tasks:
            # 建立選單選項，格式為: [時間] 床位 - 任務
            task_options = {f"[{t['time'][5:16]}] {t['bed']} - {t['task_type']} (ID:{t['id']})": t['id'] for t in reversed(tasks)}
            del_choice = st.selectbox("選擇要刪除的紀錄", list(task_options.keys()))
            del_pwd = st.text_input("輸入最高權限密碼以執行刪除", type="password", key="single_del_pwd")
            
            if st.button("🚫 確認刪除此筆紀錄", type="primary"):
                if del_pwd == "6155":
                    # 濾除被選中的任務 ID
                    tasks = [t for t in tasks if t['id'] != task_options[del_choice]]
                    save_data(tasks)
                    st.session_state.success_message = "✅ 該筆紀錄已成功刪除！"
                    st.rerun()
                else:
                    st.error("密碼錯誤，刪除失敗！")
        else:
            st.info("無紀錄可刪除。")
            
    st.markdown("---")

    if tasks:
        # 顯示時將欄位重新整理得漂亮一點
        df_display = pd.DataFrame(tasks)
        if 'feedback' not in df_display.columns: df_display['feedback'] = ""
        df_display = df_display[['time', 'priority', 'bed', 'task_type', 'feedback', 'status', 'handler']]
        df_display.columns = ['發布時間', '優先級', '床位', '任務', '執行回報', '狀態', '處理者']
        df_display = df_display.sort_values(by='發布時間', ascending=False)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("目前系統尚無任何派發紀錄。")

# --- 主程式邏輯 ---
def main():
    check_for_new_alerts()
    
    # 判斷登入狀態以決定顯示介面
    if not st.session_state.is_logged_in:
        with st.sidebar:
            st.markdown("### 📍 系統導航")
            page = st.radio("前往頁面", ["🔑 系統登入", "📊 動態白板 (免登入)"], label_visibility="collapsed")
            st.markdown("---")
            st.caption("© 2026 護理師 吳智弘 版權所有")
            st.caption("請遵守相關資安與隱私規範，勿輸入真實病患個資。")
            
        if page == "🔑 系統登入":
            login_interface()
        elif page == "📊 動態白板 (免登入)":
            whiteboard_interface()
            
    else:
        # 已登入狀態
        with st.sidebar:
            st.markdown(f"### 👤 登入者：**{st.session_state.nickname}**")
            st.markdown(f"**身分：** {st.session_state.role}")
            
            # 下班登出按鈕
            if st.button("🚪 下班登出", use_container_width=True):
                # 登出時，若該人員有未完成的「執行中」任務，自動退回「待處理」狀態，讓名字從白板上消失
                tasks = load_data()
                for t in tasks:
                    if t['status'] == '執行中' and t['handler'] == st.session_state.nickname:
                        t['status'] = '待處理'
                        t['handler'] = ''
                        t['start_time'] = ''
                save_data(tasks)
                
                st.session_state.is_logged_in = False
                st.session_state.nickname = ""
                st.session_state.role = ""
                st.rerun()
                
            st.markdown("---")
            st.markdown("### 📍 系統選單")
            
            # 根據身分動態過濾可用頁面
            if st.session_state.role == "護理師":
                pages = ["👩‍⚕️ 護理師派發", "📊 動態白板", "📂 後台紀錄"]
            elif st.session_state.role == "醫師":
                pages = ["👨‍⚕️ 醫師派發", "📊 動態白板", "📂 後台紀錄"]
            else: # 專科護理師
                pages = ["🧑‍⚕️ 專師接收任務", "📊 動態白板", "📂 後台紀錄"]
                
            page = st.radio("前往頁面", pages, label_visibility="collapsed")
            
            st.markdown("---")
            st.write("🔄 狀態：每 5 分鐘自動同步")
            st.caption("© 2026 護理師 吳智弘 版權所有")
            st.caption("請遵守相關資安與隱私規範，勿輸入真實病患個資。")

        # 根據側邊欄的選擇渲染對應的畫面
        if page == "👩‍⚕️ 護理師派發" or page == "👨‍⚕️ 醫師派發":
            assigner_interface()
        elif page == "🧑‍⚕️ 專師接收任務":
            np_interface()
        elif page == "📊 動態白板":
            whiteboard_interface()
        elif page == "📂 後台紀錄":
            backend_interface()

if __name__ == "__main__":
    main()
