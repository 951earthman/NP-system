import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# 設定頁面
st.set_page_config(page_title="專師協助派發系統", page_icon="🏥", layout="wide")

# 設定五分鐘 (300000 毫秒) 自動重新整理一次，達到同步效果
count = st_autorefresh(interval=300000, limit=None, key="data_sync_refresh")

DATA_FILE = "task_data.json"

# --- 資料庫操作 (使用 JSON 模擬資料庫以利跨裝置同步) ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- 初始化 Session State ---
if "nickname" not in st.session_state:
    st.session_state.nickname = ""
if "role" not in st.session_state:
    st.session_state.role = ""
if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False

# --- 登入介面 ---
def login_page():
    st.title("🏥 專師協助派發系統 - 登入")
    st.markdown("請輸入您的綽號與身分以進入系統。")
    
    with st.form("login_form"):
        nickname_input = st.text_input("輸入綽號 (必填)")
        role_input = st.selectbox("選擇身分", ["請選擇...", "醫師/護理師 (派發任務)", "專科護理師 (執行任務)"])
        submit_button = st.form_submit_button("登入")
        
        if submit_button:
            if not nickname_input.strip():
                st.error("請輸入綽號！")
            elif role_input == "請選擇...":
                st.error("請選擇身分！")
            else:
                st.session_state.nickname = nickname_input.strip()
                st.session_state.role = "醫師/護理師" if "派發" in role_input else "專科護理師"
                st.session_state.is_logged_in = True
                st.rerun()

# --- 醫師/護理師介面 (派發任務) ---
def assigner_interface():
    st.header(f"👋 {st.session_state.role} {st.session_state.nickname}，您好！")
    st.markdown("---")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("1. 選擇床位與項目")
        bed = st.selectbox("選擇床位", [f"急診 {i} 床" for i in range(1, 31)] + ["留觀區", "急救室"])
        task_type = st.radio("協助項目", ["on Foley", "on NG", "Suture (縫合)", "會診", "藥物開立"])
        
    with col2:
        st.subheader("2. 填寫詳細設定")
        details = ""
        
        if task_type == "on Foley":
            f_type = st.radio("Foley 種類", ["一般", "矽質"], horizontal=True)
            f_sample = st.checkbox("需留取檢體")
            details = f"種類: {f_type} | 檢體: {'是' if f_sample else '否'}"
            
        elif task_type == "on NG":
            ng_type = st.radio("NG 目的", ["Re-on", "Decompression"], horizontal=True)
            details = f"目的: {ng_type}"
            
        elif task_type == "Suture (縫合)":
            s_part = st.selectbox("部位", ["四肢", "頭部", "臉部"])
            s_line = st.selectbox("縫線選擇", ["Nylon 1-0", "Nylon 2-0", "Nylon 3-0", "Nylon 4-0", "Nylon 5-0", "Nylon 6-0"])
            details = f"部位: {s_part} | 縫線: {s_line}"
            
        elif task_type == "會診":
            consult_dept = st.text_input("請輸入會診科別 (例如：骨科, 外科)")
            details = f"科別: {consult_dept}"
            
        elif task_type == "藥物開立":
            med_type = st.radio("藥物類別", ["續開", "大量點滴"], horizontal=True)
            details = f"類別: {med_type}"

        if st.button("🚀 送出請求給專師", use_container_width=True):
            if task_type == "會診" and not consult_dept:
                st.warning("請填寫會診科別！")
            else:
                tasks = load_data()
                new_task = {
                    "id": str(datetime.now().timestamp()),
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "bed": bed,
                    "task_type": task_type,
                    "details": details,
                    "requester": st.session_state.nickname,
                    "requester_role": st.session_state.role,
                    "status": "待處理",
                    "handler": ""
                }
                tasks.append(new_task)
                save_data(tasks)
                st.success(f"已成功送出 {bed} 的 {task_type} 請求給專師！")

# --- 專科護理師介面 (接收與處理任務) ---
def np_interface():
    st.header(f"👩‍⚕️ 專科護理師 {st.session_state.nickname}，您好！")
    
    tasks = load_data()
    pending_tasks = [t for t in tasks if t['status'] == '待處理']
    completed_tasks = [t for t in tasks if t['status'] == '已完成']
    
    st.subheader(f"🔔 待處理任務 ({len(pending_tasks)} 筆)")
    if pending_tasks:
        for t in pending_tasks:
            # 判斷是否超過一小時 (3600秒)
            task_time = datetime.strptime(t['time'], "%Y-%m-%d %H:%M:%S")
            time_diff = (datetime.now() - task_time).total_seconds()
            is_overdue = time_diff > 3600
            
            # 超時加上警告標示
            status_icon = "🔴" if is_overdue else "🟡"
            overdue_text = " ⚠️ (已超時)" if is_overdue else ""
            
            with st.expander(f"{status_icon} {t['time'][11:16]} | {t['bed']} - {t['task_type']}{overdue_text}", expanded=True):
                st.write(f"**詳細內容：** {t['details']}")
                st.write(f"**發出請求者：** {t['requester']} ({t['requester_role']})")
                
                if st.button(f"✅ 標記為完成", key=f"done_{t['id']}"):
                    # 更新狀態
                    for i in range(len(tasks)):
                        if tasks[i]['id'] == t['id']:
                            tasks[i]['status'] = '已完成'
                            tasks[i]['handler'] = st.session_state.nickname
                            tasks[i]['complete_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    save_data(tasks)
                    st.rerun()
    else:
        st.info("目前沒有待處理的任務，辛苦了！")

    st.markdown("---")
    st.subheader(f"✅ 今日已完成紀錄 ({len(completed_tasks)} 筆)")
    if completed_tasks:
        df = pd.DataFrame(completed_tasks)
        df = df[['time', 'bed', 'task_type', 'details', 'requester', 'handler', 'complete_time']]
        df.columns = ['請求時間', '床位', '任務類型', '詳細內容', '發送者', '處理專師', '完成時間']
        st.dataframe(df, use_container_width=True)

# --- 主程式邏輯 ---
def main():
    if not st.session_state.is_logged_in:
        login_page()
    else:
        # 側邊欄：顯示登入資訊與登出按鈕
        with st.sidebar:
            st.write(f"👤 登入身分：**{st.session_state.nickname}**")
            st.write(f"🏷️ 權限：{st.session_state.role}")
            st.write(f"🔄 系統狀態：每 5 分鐘自動同步")
            if st.button("登出"):
                st.session_state.is_logged_in = False
                st.session_state.nickname = ""
                st.session_state.role = ""
                st.rerun()
        
        # 根據身分顯示對應介面
        if st.session_state.role == "醫師/護理師":
            assigner_interface()
        else:
            np_interface()

if __name__ == "__main__":
    main()
