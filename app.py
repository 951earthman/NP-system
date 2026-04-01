import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# 設定頁面
st.set_page_config(page_title="急診專師協助派發系統", page_icon="🏥", layout="wide")

# 設定五分鐘 (300000 毫秒) 自動重新整理一次
count = st_autorefresh(interval=300000, limit=None, key="data_sync_refresh")

DATA_FILE = "task_data.json"

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

# --- 資料庫操作 (使用 JSON 模擬) ---
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
if "backend_auth" not in st.session_state:
    st.session_state.backend_auth = False 

# --- 醫師/護理師介面 (派發任務) ---
def assigner_interface():
    st.header(f"👋 醫師/護理師 {st.session_state.nickname}，您好！")
    st.markdown("---")
    
    st.subheader("📍 步驟 1：選擇位置")
    area = st.radio("【 1. 先選大區域 】", list(BED_DATA_COMPLEX.keys()), horizontal=True)
    
    final_bed = ""
    bed_note = ""
    
    if area in ["留觀(OBS)", "診間"]:
        sub_area = st.radio(f"【 2. 選擇 {area} 區域 】", list(BED_DATA_COMPLEX[area].keys()), horizontal=True)
        bed_num = st.radio(f"【 3. 選擇 {sub_area} 床號 】", BED_DATA_COMPLEX[area][sub_area], horizontal=True)
        final_bed = f"{sub_area} {bed_num}床"
        
    elif area == "兒科":
        bed_num = st.radio("【 2. 選擇床號 】", BED_DATA_COMPLEX[area]["兒科床位"], horizontal=True)
        final_bed = f"兒科 {bed_num}床"
        
    else:
        bed_note = st.text_input(f"【 2. {area} 備註 (選填) 】", placeholder="例如：等待推床、暫放走廊...")
        final_bed = area
        if bed_note:
            final_bed += f" ({bed_note})"

    st.markdown("---")
    st.subheader("📋 步驟 2：選擇協助項目")
    
    task_type = st.radio("協助項目", ["on Foley", "on NG", "Suture (縫合)", "會診", "藥物開立"], horizontal=True)
    
    st.markdown("##### 填寫詳細設定")
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

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 確認無誤，送出請求給專師", use_container_width=True, type="primary"):
        if task_type == "會診" and not consult_dept:
            st.warning("請填寫會診科別！")
        else:
            tasks = load_data()
            new_task = {
                "id": str(datetime.now().timestamp()),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bed": final_bed,
                "task_type": task_type,
                "details": details,
                "requester": st.session_state.nickname,
                "requester_role": st.session_state.role,
                "status": "待處理",
                "handler": "",
                "start_time": "",
                "complete_time": ""
            }
            tasks.append(new_task)
            save_data(tasks)
            st.success(f"✅ 已成功送出 【 {final_bed} 】 的 【 {task_type} 】 請求！")

# --- 專科護理師介面 (接收與處理任務) ---
def np_interface():
    st.header(f"👩‍⚕️ 專科護理師 {st.session_state.nickname}，您好！")
    
    tasks = load_data()
    pending_tasks = [t for t in tasks if t['status'] == '待處理']
    in_progress_tasks = [t for t in tasks if t['status'] == '執行中' and t['handler'] == st.session_state.nickname]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"🔔 待接單任務 ({len(pending_tasks)} 筆)")
        if pending_tasks:
            for t in pending_tasks:
                task_time = datetime.strptime(t['time'], "%Y-%m-%d %H:%M:%S")
                # 任務時間往後推一小時為超時門檻
                overdue_time = task_time + timedelta(hours=1)
                is_overdue = datetime.now() > overdue_time
                
                status_icon = "🔴" if is_overdue else "🟡"
                overdue_text = " ⚠️ (已超時)" if is_overdue else ""
                
                with st.container(border=True):
                    st.write(f"**{status_icon} {t['time'][11:16]} | {t['bed']} - {t['task_type']}**{overdue_text}")
                    st.write(f"內容：{t['details']}")
                    st.write(f"請求：{t['requester']} ({t['requester_role']})")
                    
                    if st.button(f"👉 點我接單", key=f"take_{t['id']}", use_container_width=True):
                        for i in range(len(tasks)):
                            if tasks[i]['id'] == t['id']:
                                tasks[i]['status'] = '執行中'
                                tasks[i]['handler'] = st.session_state.nickname
                                tasks[i]['start_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        save_data(tasks)
                        st.rerun()
        else:
            st.info("目前沒有待處理的任務。")

    with col2:
        st.subheader(f"🏃‍♂️ 我的執行中任務 ({len(in_progress_tasks)} 筆)")
        if in_progress_tasks:
            for t in in_progress_tasks:
                with st.container(border=True):
                    st.write(f"**🔵 {t['bed']} - {t['task_type']}**")
                    st.write(f"內容：{t['details']}")
                    st.write(f"接單時間：{t['start_time'][11:16]}")
                    
                    if st.button(f"✅ 標記為完成", key=f"done_{t['id']}", use_container_width=True, type="primary"):
                        for i in range(len(tasks)):
                            if tasks[i]['id'] == t['id']:
                                tasks[i]['status'] = '已完成'
                                tasks[i]['complete_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        save_data(tasks)
                        st.rerun()
        else:
            st.info("您目前沒有正在執行的任務。")

# --- 動態白板介面 ---
def whiteboard_interface():
    st.header("📊 系統動態白板")
    st.markdown("快速掌握急診現場協助派遣狀況（每5分鐘自動刷新）")
    
    tasks = load_data()
    
    pending = [t for t in tasks if t['status'] == '待處理']
    in_progress = [t for t in tasks if t['status'] == '執行中']
    active_nps = list(set([t['handler'] for t in in_progress if t['handler']]))
    
    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 待處理任務", len(pending), "未接單", delta_color="inverse")
    col2.metric("🔵 執行中任務", len(in_progress), "處理中", delta_color="off")
    col3.metric("👨‍⚕️ 前線作戰專師", len(active_nps), "上線中", delta_color="normal")
    
    st.markdown("---")
    
    w_col1, w_col2 = st.columns(2)
    
    with w_col1:
        st.subheader("🚨 未接單清單")
        if pending:
            df_pending = pd.DataFrame(pending)[['time', 'bed', 'task_type', 'requester']]
            df_pending['time'] = df_pending['time'].str[11:16]
            df_pending.columns = ['時間', '床位', '任務', '發布者']
            st.dataframe(df_pending, use_container_width=True, hide_index=True)
        else:
            st.success("目前無積壓任務！")
            
    with w_col2:
        st.subheader("⚡ 專師執行動態")
        if in_progress:
            df_prog = pd.DataFrame(in_progress)[['handler', 'bed', 'task_type', 'start_time']]
            df_prog['start_time'] = df_prog['start_time'].str[11:16]
            df_prog.columns = ['專師', '床位', '任務', '接單時間']
            st.dataframe(df_prog, use_container_width=True, hide_index=True)
        else:
            st.info("目前無正在執行的任務。")

# --- 後台紀錄介面 (需密碼) ---
def backend_interface():
    st.header("📂 後台紀錄管理")
    
    if not st.session_state.backend_auth:
        st.info("⚠️ 進入後台紀錄需要系統管理員權限，請輸入密碼解鎖。")
        pwd = st.text_input("請輸入後台密碼", type="password")
        if st.button("解鎖後台"):
            if pwd == "6155":
                st.session_state.backend_auth = True
                st.rerun()
            else:
                st.error("密碼錯誤，請重新輸入！")
    else:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("檢視所有歷史派發紀錄與完成時間。")
        with col2:
            if st.button("🔒 鎖定並離開後台", use_container_width=True):
                st.session_state.backend_auth = False
                st.rerun()
                
        tasks = load_data()
        if tasks:
            df = pd.DataFrame(tasks)
            df = df[['time', 'bed', 'task_type', 'details', 'requester', 'status', 'handler', 'start_time', 'complete_time']]
            df.columns = ['發布時間', '床位', '任務類型', '詳細內容', '發布者', '狀態', '處理專師', '接單時間', '完成時間']
            df = df.sort_values(by='發布時間', ascending=False)
            
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.write("目前系統尚無任何派發紀錄。")

# --- 主程式邏輯 ---
def main():
    # 左側欄 (Sidebar) 設計 - 直接作為全系統的導航中樞
    with st.sidebar:
        st.markdown("### 👤 使用者資訊")
        # key="nickname" 會自動將輸入框的值綁定到 st.session_state.nickname
        st.text_input("輸入您的綽號", key="nickname", placeholder="必填，例如：小明")
        
        st.markdown("---")
        st.markdown("### 📍 系統選單")
        # 直接用 radio 按鈕選擇要去的頁面
        page = st.radio("前往頁面", [
            "📟 醫師/護理師 (派發任務)", 
            "👩‍⚕️ 專科護理師 (接收任務)", 
            "📊 動態白板", 
            "📂 後台紀錄"
        ], label_visibility="collapsed")
        
        st.markdown("---")
        st.write("🔄 狀態：每 5 分鐘自動同步")

    # 根據左側欄選擇的頁面，渲染右側主畫面
    if page == "📟 醫師/護理師 (派發任務)":
        if not st.session_state.nickname.strip():
            st.warning("⚠️ 請先於左側欄「輸入您的綽號」才能開始派發任務喔！")
        else:
            st.session_state.role = "醫師/護理師"
            assigner_interface()
            
    elif page == "👩‍⚕️ 專科護理師 (接收任務)":
        if not st.session_state.nickname.strip():
            st.warning("⚠️ 請先於左側欄「輸入您的綽號」才能開始接單喔！")
        else:
            st.session_state.role = "專科護理師"
            np_interface()
            
    elif page == "📊 動態白板":
        # 白板區不強制需要綽號即可觀看
        whiteboard_interface()
        
    elif page == "📂 後台紀錄":
        # 後台紀錄區由密碼 (6155) 控管
        backend_interface()

if __name__ == "__main__":
    main()
