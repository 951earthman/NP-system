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
ONLINE_FILE = "online_users.json"

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

# --- 上線狀態管理函數 ---
def load_online_users():
    if not os.path.exists(ONLINE_FILE):
        return {}
    with open(ONLINE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_online_users(data):
    with open(ONLINE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def update_online_status(nickname, role):
    users = load_online_users()
    users[nickname] = {
        "role": role,
        "last_seen": get_tw_time().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_online_users(users)

def remove_online_status(nickname):
    users = load_online_users()
    if nickname in users:
        del users[nickname]
        save_online_users(users)

# --- 資安：身分證字號偵測 ---
def check_pii(*texts):
    for t in texts:
        if t and re.search(r'[A-Za-z][1289]\d{8}', str(t)):
            return True
    return False

# --- 初始化 Session State (加入網址記憶功能以抵抗重新整理) ---
if "is_logged_in" not in st.session_state:
    # 檢查網址參數中是否帶有登入資訊
    if "nickname" in st.query_params and "role" in st.query_params:
        st.session_state.nickname = st.query_params["nickname"]
        st.session_state.role = st.query_params["role"]
        st.session_state.is_logged_in = True
    else:
        st.session_state.nickname = ""
        st.session_state.role = ""
        st.session_state.is_logged_in = False

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

# --- 護理師專用：聯絡洗腎確認彈出視窗 ---
@st.dialog("⚠️ 聯絡洗腎 - 派發確認")
def confirm_nurse_hd_task(new_task):
    st.write(f"即將派發：**{new_task['priority']}** | **{new_task['bed']}** 的 **聯絡洗腎** 請求。")
    consent = st.radio("請問是否已完成洗腎同意書？", ["是", "否"], horizontal=True)
    reason = ""
    if consent == "否":
        reason = st.text_input("請填寫未完成原因 (必填)", placeholder="例如：家屬尚未抵達...")
    
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 確認派發任務", type="primary", use_container_width=True):
            if consent == "否" and not reason.strip():
                st.error("⚠️ 選擇「否」時，必須填寫未完成原因！")
            else:
                if consent == "否":
                    new_task['details'] += f" | 同意書: 未完成 ({reason})"
                else:
                    new_task['details'] += f" | 同意書: 已完成"
                tasks = load_data()
                tasks.append(new_task)
                save_data(tasks)
                st.session_state.success_message = f"✅ 已成功送出 【 {new_task['bed']} 】 的 【聯絡洗腎】 請求！"
                st.rerun()
    with col2:
        if st.button("❌ 返回修改", use_container_width=True):
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
            feedback_text = st.text_input("處理結果備註 (選填)", placeholder="例如：已完成採集、已處理完畢...")
            if not feedback_text: feedback_text = "已處理完畢"

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 儲存回報並結案", type="primary", use_container_width=True):
        for i in range(len(tasks)):
            if tasks[i]['id'] == task_id:
                tasks[i]['status'] = '已完成'
                tasks[i]['complete_time'] = get_tw_time().strftime("%Y-%m-%d %H:%M:%S")
                if is_doc_assisted:
                    tasks[i]['handler'] = f"{st.session_state.nickname} (註記醫師完成)"
                else:
                    tasks[i]['handler'] = st.session_state.nickname
                tasks[i]['feedback'] = feedback_text
        save_data(tasks)
        st.session_state.success_message = "✅ 任務結案與回報完成！"
        st.rerun()

# --- 後台專用：批次刪除與清空彈出視窗 ---
@st.dialog("⚠️ 警告：刪除選取的紀錄")
def delete_selected_dialog(ids_to_delete):
    st.error(f"您即將刪除選取的 {len(ids_to_delete)} 筆紀錄！此動作無法復原。")
    pwd = st.text_input("請輸入系統密碼以確認", type="password", key="pwd_del_sel")
    if st.button("🚨 確認刪除選取項目", type="primary", use_container_width=True):
        if pwd == "6155":
            tasks = load_data()
            tasks = [t for t in tasks if t['id'] not in ids_to_delete]
            save_data(tasks)
            st.session_state.known_task_ids = set([t['id'] for t in tasks])
            st.session_state.success_message = f"✅ 已成功刪除 {len(ids_to_delete)} 筆紀錄！"
            st.rerun()
        else:
            st.error("密碼錯誤，拒絕刪除！")

@st.dialog("💥 警告：清除全部紀錄")
def clear_records_dialog():
    st.error("您即將清除系統中的「所有」任務紀錄！此動作無法復原。")
    pwd = st.text_input("請輸入系統密碼以確認", type="password", key="pwd_clear_all")
    if st.button("🚨 確認清空資料庫", type="primary", use_container_width=True):
        if pwd == "6155":
            save_data([]) 
            st.session_state.known_task_ids = set()
            st.session_state.success_message = "✅ 系統內所有紀錄已成功清除！"
            st.rerun()
        else:
            st.error("密碼錯誤，拒絕清除！")

# --- 登入介面 ---
def login_interface():
    st.header("🔑 系統登入")
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
            if not final_nickname: st.error("請輸入或選擇綽號！")
            elif role_input == "請選擇...": st.error("請選擇您的身分！")
            else:
                save_user(final_nickname)
                st.session_state.nickname = final_nickname
                st.session_state.role = role_input
                st.session_state.is_logged_in = True
                
                # 寫入網址列參數，抵抗重新整理
                st.query_params["nickname"] = final_nickname
                st.query_params["role"] = role_input
                
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
    final_bed = ""; bed_note = ""; patient_name = ""
    if area in ["留觀(OBS)", "診間"]:
        sub_area = st.radio(f"【 2. 選擇 {area} 區域 】", list(BED_DATA_COMPLEX[area].keys()), horizontal=True)
        bed_num = st.radio(f"【 3. 選擇 {sub_area} 床號 】", BED_DATA_COMPLEX[area][sub_area], horizontal=True)
        final_bed = f"{sub_area} {bed_num}床"
    elif area == "兒科":
        bed_num = st.radio("【 2. 選擇床號 】", BED_DATA_COMPLEX[area]["兒科床位"], horizontal=True)
        final_bed = f"兒科 {bed_num}床"
    elif area == "病患無床位":
        patient_name = st.text_input("【 2. 填寫病患姓名 (必填) 】", placeholder="請在此貼上或輸入病患姓名...")
        if patient_name: final_bed = f"無床位 (病患: {patient_name})"
        else: final_bed = "無床位"
    else:
        bed_note = st.text_input(f"【 2. {area} 備註 (選填) 】", placeholder="例如：等待推床...")
        final_bed = area
        if bed_note: final_bed += f" ({bed_note})"

    st.markdown("---")
    st.subheader("📋 步驟 2：選擇協助項目與優先級")
    priority = st.radio("優先級別", ["🟢 一般", "🔴 緊急"], horizontal=True)
    task_type = st.radio("協助項目", ["on Foley", "on NG", "Suture (縫合)", "會診", "藥物開立", "聯絡洗腎", "檢體採集"], horizontal=True)
    
    details = ""; med_details = ""; consult_dept = ""; hd_days = []; spec_type = ""; wound_sub = []
    
    if task_type == "on Foley":
        f_type = st.radio("Foley 種類", ["一般", "矽質"], horizontal=True)
        f_sample = st.checkbox("需留取檢體")
        details = f"種類: {f_type} | 檢體: {'是' if f_sample else '否'}"
    elif task_type == "on NG":
        ng_type_choice = st.radio("NG 目的", ["Re-on", "Decompression", "IRRI (沖洗)", "其他 (自行輸入)"], horizontal=True)
        if ng_type_choice == "其他 (自行輸入)":
            custom_ng = st.text_input("請輸入自訂目的")
            actual_ng = custom_ng if custom_ng else "未填寫"
        else: actual_ng = ng_type_choice
        details = f"目的: {actual_ng}"
    elif task_type == "Suture (縫合)":
        s_part = st.selectbox("部位", ["左手", "左腳", "右手", "右腳", "胸口", "肚子", "背後", "頭皮", "臉", "脖子"])
        s_line_choice = st.selectbox("縫線選擇", ["Nylon 1-0", "Nylon 2-0", "Nylon 3-0", "Nylon 4-0", "Nylon 5-0", "Nylon 6-0", "由專科護理師自行評估", "其他 (自行輸入)"])
        if s_line_choice == "其他 (自行輸入)":
            custom_line = st.text_input("自訂縫線"); actual_line = custom_line if custom_line else "未填寫"
        else: actual_line = s_line_choice
        details = f"部位: {s_part} | 縫線: {actual_line}"
    elif task_type == "會診":
        consult_dept = st.text_input("會診科別"); details = f"科別: {consult_dept}"
    elif task_type == "藥物開立":
        med_details = st.text_input("藥物/說明"); details = f"說明: {med_details}"
    elif task_type == "聯絡洗腎":
        if st.session_state.role == "醫師": st.info("💡 醫師提醒：請務必完成「洗腎同意書」！")
        hd_days = st.multiselect("平常洗腎日", ["週一", "週二", "週三", "週四", "週五", "週六", "週日"])
        hd_location = st.radio("地點", ["本院", "外院", "不明"], horizontal=True)
        details = f"洗腎日: {','.join(hd_days)} | 地點: {hd_location}"
    elif task_type == "檢體採集":
        spec_type = st.radio("採集內容", ["鼻口腔黏膜", "傷口"], horizontal=True)
        if spec_type == "傷口":
            # 傷口培養改為複選
            wound_sub = st.multiselect("傷口培養類別 (可複選)", ["嗜氧", "厭氧", "其他 (自行備註)"])
            actual_wounds = []
            for w in wound_sub:
                if w == "其他 (自行備註)":
                    custom_w = st.text_input("請輸入其他培養類別")
                    actual_wounds.append(custom_w if custom_w else "其他(未填)")
                else:
                    actual_wounds.append(w)
            
            wound_str = " + ".join(actual_wounds) if actual_wounds else "未選擇"
            details = f"內容: 傷口 ({wound_str})"
        else:
            details = f"內容: 鼻口腔黏膜"
            if st.session_state.role == "護理師":
                st.info("💡 護理師提醒：請印好條碼貼上採檢棒，並放於待採檢區。")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.session_state.role == "護理師":
        if task_type in ["會診", "藥物開立"]: btn_text = "🚀 確認直接送出"
        elif task_type == "聯絡洗腎": btn_text = "🚀 需確認同意書"
        else: btn_text = "🚀 需確認備物"
    else: btn_text = "🚀 確認無誤送出"
    
    if st.button(btn_text, use_container_width=True, type="primary"):
        if check_pii(patient_name, details, bed_note, consult_dept, med_details):
            st.error("⚠️ 資安警告：偵測到疑似身分證字號！已攔截派發。"); st.stop()
        if area == "病患無床位" and not patient_name.strip(): st.warning("⚠️ 請填寫病患姓名！")
        elif task_type == "聯絡洗腎" and not hd_days: st.warning("⚠️ 請勾選洗腎日！")
        elif task_type == "會診" and not consult_dept: st.warning("⚠️ 請填寫科別！")
        elif task_type == "藥物開立" and not med_details: st.warning("⚠️ 請填寫藥物說明！")
        elif task_type == "檢體採集" and spec_type == "傷口" and not wound_sub: st.warning("⚠️ 請至少勾選一種傷口培養類別！")
        else:
            new_task = {"id": str(get_tw_time().timestamp()), "time": get_tw_time().strftime("%Y-%m-%d %H:%M:%S"), "priority": priority, "bed": final_bed, "task_type": task_type, "details": details, "requester": st.session_state.nickname, "requester_role": st.session_state.role, "status": "待處理", "handler": "", "start_time": "", "complete_time": "", "feedback": ""}
            if st.session_state.role == "護理師":
                if task_type in ["會診", "藥物開立"]:
                    tasks = load_data(); tasks.append(new_task); save_data(tasks); st.rerun()
                elif task_type == "聯絡洗腎": confirm_nurse_hd_task(new_task)
                else: confirm_nurse_task(new_task)
            else:
                tasks = load_data(); tasks.append(new_task); save_data(tasks); st.rerun()

# --- 專科護理師介面 (接收與處理任務) ---
def np_interface():
    st.header(f"👩‍⚕️ 專科護理師接收介面")
    check_for_new_alerts()
    tasks = load_data()
    pending = [t for t in tasks if t['status'] == '待處理']
    in_prog = [t for t in tasks if t['status'] == '執行中' and t['handler'] == st.session_state.nickname]
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader(f"🔔 待接單 ({len(pending)})")
        for t in pending:
            with st.container(border=True):
                st.markdown(f"**{t['priority']}** | **{t['time'][11:16]} | {t['bed']} - {t['task_type']}**")
                st.markdown(f"📞 **派發者：{t['requester']} ({t['requester_role']})**")
                st.write(f"📝 內容：{t['details']}")
                
                if t['task_type'] == "檢體採集" and "鼻口腔黏膜" in t['details']:
                    st.warning("🛡️ **防護提醒：** 執行鼻口腔黏膜採集，請務必配戴**護目鏡與口罩**，保護自身安全！")
                
                b1, b2 = st.columns(2)
                with b1:
                    if st.button(f"👉 點我接單", key=f"tk_{t['id']}", use_container_width=True):
                        for i in range(len(tasks)):
                            if tasks[i]['id'] == t['id']:
                                tasks[i]['status'] = '執行中'; tasks[i]['handler'] = st.session_state.nickname; tasks[i]['start_time'] = get_tw_time().strftime("%Y-%m-%d %H:%M:%S")
                        save_data(tasks); st.rerun()
                with b2:
                    if st.button(f"👨‍⚕️ 醫師已完成", key=f"dd_{t['id']}", use_container_width=True):
                        np_feedback_dialog(t['id'], is_doc_assisted=True)
    with c2:
        st.subheader(f"🏃 我的執行中 ({len(in_prog)})")
        for t in in_prog:
            with st.container(border=True):
                st.markdown(f"**{t['priority']}** | **🔵 {t['bed']} - {t['task_type']}**")
                st.write(f"📝 內容：{t['details']}")
                if t['task_type'] == "檢體採集" and "鼻口腔黏膜" in t['details']:
                    st.warning("🛡️ **防護提醒：** 請配戴護目鏡與口罩！")
                if st.button(f"✅ 標記完成", key=f"dn_{t['id']}", use_container_width=True, type="primary"):
                    np_feedback_dialog(t['id'], is_doc_assisted=False)

# --- 動態白板介面 ---
def whiteboard_interface():
    st.header("📊 系統動態白板")
    tasks = load_data(); pending = [t for t in tasks if t['status'] == '待處理']; in_prog = [t for t in tasks if t['status'] == '執行中']
    online_users = load_online_users(); active_nps = []; now = get_tw_time()
    for name, info in online_users.items():
        if info['role'] == "專科護理師":
            last_seen = datetime.strptime(info['last_seen'], "%Y-%m-%d %H:%M:%S")
            if (now - last_seen).total_seconds() < 900: active_nps.append(name)
    busy_nps = list(set([t['handler'] for t in in_prog if t['handler']]))
    idle_nps = [np for np in active_nps if np not in busy_nps]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 待處理任務", len(pending), "未接單", delta_color="inverse")
    col2.metric("🔵 執行中任務", len(in_prog), "處理中", delta_color="off")
    col3.metric("👨‍⚕️ 值班專師", len(active_nps), "上線中")
    if active_nps:
        col3.caption(f"🏃 **執行中:** {', '.join(busy_nps) if busy_nps else '無'}")
        col3.caption(f"☕ **待命中:** {', '.join(idle_nps) if idle_nps else '無'}")
    
    st.markdown("---")
    w1, w2 = st.columns(2)
    with w1:
        st.subheader("🚨 未接單清單")
        if pending:
            dfp = pd.DataFrame(pending)[['time', 'priority', 'bed', 'task_type', 'requester']]
            dfp['time'] = dfp['time'].str[11:16]; dfp.columns = ['時間', '優先級', '位置/病患', '任務', '發布者']
            st.dataframe(dfp, use_container_width=True, hide_index=True)
    with w2:
        st.subheader("⚡ 專師執行動態")
        if in_prog:
            dfg = pd.DataFrame(in_prog)[['handler', 'priority', 'bed', 'task_type', 'start_time']]
            dfg['start_time'] = dfg['start_time'].str[11:16]; dfg.columns = ['專師', '優先級', '位置/病患', '任務', '接單時間']
            st.dataframe(dfg, use_container_width=True, hide_index=True)

# --- 後台紀錄介面 ---
def backend_interface():
    st.header("📂 後台紀錄與管理")
    tasks = load_data()
    if not tasks: st.info("目前無紀錄。"); return
    df = pd.DataFrame(tasks)
    df.insert(0, "選取", False)
    st.markdown("### 📋 檢視與排序")
    sort_by = st.selectbox("🔃 排序依據", ["發布時間 (最新到最舊)", "發布時間 (最舊到最新)", "處理專師", "任務類型"])
    if "最新" in sort_by: df = df.sort_values(by='time', ascending=False)
    elif "最舊" in sort_by: df = df.sort_values(by='time', ascending=True)
    elif "專師" in sort_by: df = df.sort_values(by='handler')

    edited_df = st.data_editor(df, column_config={"選取": st.column_config.CheckboxColumn("選取", default=False), "id": None}, hide_index=True, use_container_width=True)
    sel_rows = edited_df[edited_df["選取"] == True]
    
    c1, c2, c3 = st.columns(3)
    with c1:
        if not sel_rows.empty:
            csv = sel_rows.drop(columns=["選取", "id"]).to_csv(index=False, encoding='utf-8-sig')
            st.download_button(label=f"📥 匯出選取 ({len(sel_rows)})", data=csv, file_name=f"ER_Tasks_{get_tw_time().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
    with c2:
        if st.button(f"🗑️ 刪除選取 ({len(sel_rows)})", disabled=sel_rows.empty, use_container_width=True):
            delete_selected_dialog(sel_rows['id'].tolist())
    with c3:
        if st.button("🚨 清除全部", use_container_width=True, type="primary"): clear_records_dialog()

# --- 主程式邏輯 ---
def main():
    if st.session_state.is_logged_in: update_online_status(st.session_state.nickname, st.session_state.role)
    if not st.session_state.is_logged_in:
        with st.sidebar:
            st.markdown("### 📍 系統導航")
            page = st.radio("前往頁面", ["🔑 系統登入", "📊 動態白板 (免登入)"], label_visibility="collapsed")
            st.markdown("---")
            st.caption("© 2026 護理師 吳智弘 版權所有"); st.caption("請遵守個資法，勿填真實身分證字號。")
        if page == "🔑 系統登入": login_interface()
        else: whiteboard_interface()
    else:
        with st.sidebar:
            st.markdown(f"### 👤 **{st.session_state.nickname}** ({st.session_state.role})")
            if st.button("🚪 下班登出", use_container_width=True):
                remove_online_status(st.session_state.nickname)
                # 登出時清空網址參數，避免下次不小心點進來直接登入
                if "nickname" in st.query_params: del st.query_params["nickname"]
                if "role" in st.query_params: del st.query_params["role"]
                
                tasks = load_data()
                for t in tasks:
                    if t['status'] == '執行中' and t['handler'] == st.session_state.nickname:
                        t['status'] = '待處理'; t['handler'] = ''; t['start_time'] = ''
                save_data(tasks); st.session_state.is_logged_in = False; st.rerun()
            st.markdown("""<a href="." target="_blank" style="display:block;text-align:center;padding:0.45rem;margin-top:0.5rem;background-color:transparent;color:inherit;border-radius:0.5rem;border:1px solid rgba(128,128,128,0.5);text-decoration:none;">➕ 開啟新身分</a>""", unsafe_allow_html=True)
            st.markdown("---")
            pages = ["📊 動態白板", "📂 後台紀錄"]
            if st.session_state.role == "護理師": pages.insert(0, "👩‍⚕️ 護理師派發")
            elif st.session_state.role == "醫師": pages.insert(0, "👨‍⚕️ 醫師派發")
            else: pages.insert(0, "🧑‍⚕️ 專師接收任務")
            page = st.radio("系統選單", pages, label_visibility="collapsed")
            st.markdown("---")
            st.caption("© 2026 護理師 吳智弘 版權所有")
        if "派發" in page: assigner_interface()
        elif "接收" in page: np_interface()
        elif "白板" in page: whiteboard_interface()
        else: backend_interface()

if __name__ == "__main__":
    main()
