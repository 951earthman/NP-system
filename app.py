import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# 設定頁面
st.set_page_config(page_title="專師/醫師協助派發系統", page_icon="🏥", layout="wide")

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
    st.title("🏥 臨床協助派發系統 - 登入")
    st.markdown("請輸入您的綽號與身分以進入系統。")
    
    with st.form("login_form"):
        nickname_input = st.text_input("輸入綽號 (必填)")
        role_input = st.selectbox("選擇身分", ["請選擇...", "護理師", "專科護理師/醫師"])
        submit_button = st.form_submit_button("登入")
        
        if submit_button:
            if not nickname_input.strip():
                st.error("請輸入綽號！")
            elif role_input == "請選擇...":
                st.error("請選擇身分！")
            else:
                st.session_state.nickname = nickname_input.strip()
                st.session_state.role = role_input
                st.session_state.is_logged_in = True
                st.rerun()

# --- 護理師介面 (派發任務) ---
def nurse_interface():
    st.header(f"👋 護理師 {st.session_state.nickname}，您好！")
    st.subheader("新增協助請求")
    
    with st.form("new_task_form"):
        # 床位選擇 (依急診常用床位格式，可自行擴充)
        bed_options = [f"急診 {i} 床" for i in range(1, 21)] + ["留觀區", "急救室"]
        bed = st.selectbox("選擇床位", bed_options)
        
        task_type = st.selectbox("協助項目", ["請選擇...", "on Foley", "on NG", "Suture (縫合)", "會診", "藥物開立"])
        
        # 預留子項目變數
        sub_details = {}
        
        # 根據選項動態顯示子項目 (Streamlit form 內無法動態隱藏/顯示，所以這裡改用 form 外的 UI 或將選項全部列出但標示條件)
        # 注意：為了達到根據選項變動 UI，我們不能把動態選項包在同一個 st.form 裡面。
        # 因此這部分的實作我們改用一般按鈕，而非 st.form。
        
        st.info("請於下方確認並送出詳細需求")
        submit = st.form_submit_button("確認派發") # 這邊先放一個假的，等下外面再做真正的送出邏輯
        
# 重新設計護理師介面 (不使用 form 以支援動態選單)
def nurse_interface_dynamic():
    st.header(f"👋 護理師 {st.session_state.nickname}，您好！")
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

        if st.button("🚀 送出請求", use_container_width=True):
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
                    "status": "待處理",
                    "handler": ""
                }
                tasks.append(new_task)
                save_data(tasks)
                st.success(f"已成功送出 {bed} 的 {task_type} 請求！")

# --- 專師/醫師介面 (接收與處理任務) ---
def doctor_interface():
    st.header(f"👨‍⚕️ {st.session_state.nickname} (專師/醫師)，您好！")
    
    tasks = load_data()
    pending_tasks = [t for t in tasks if t['status'] == '待處理']
    completed_tasks = [t for t in tasks if t['status'] == '已完成']
    
    st.subheader(f"🔔 待處理任務 ({len(pending_tasks)} 筆)")
    if pending_tasks:
        for idx, t in enumerate(pending_tasks):
            with st.expander(f"🔴 {t['time'][11:16]} | {t['bed']} - {t['task_type']}", expanded=True):
                st.write(f"**詳細內容：** {t['details']}")
                st.write(f"**發出請求者：** {t['requester']}")
                
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
        # 將完成的任務轉為 DataFrame 方便顯示
        df = pd.DataFrame(completed_tasks)
        df = df[['time', 'bed', 'task_type', 'details', 'requester', 'handler', 'complete_time']]
        df.columns = ['請求時間', '床位', '任務類型', '詳細內容', '護理師', '處理者', '完成時間']
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
        if st.session_state.role == "護理師":
            nurse_interface_dynamic()
        else:
            doctor_interface()

if __name__ == "__main__":
    main()
