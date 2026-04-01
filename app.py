import streamlit as st
import datetime
import pandas as pd
import json
import os
import uuid
import time
import streamlit.components.v1 as components

# --- 設定頁面 ---
st.set_page_config(page_title="急診護佐任務系統", page_icon="🏥", layout="wide")

# --- 強制轉換為台灣時間 (UTC+8) 的小工具 ---
def get_tw_datetime():
    tw_tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(tw_tz)

def get_tw_time():
    return get_tw_datetime().strftime("%H:%M:%S")

# --- 共用筆記本 (JSON) 設定 ---
DB_FILE = "data.json"

def init_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump({"tasks": [], "online_nas": [], "online_nurses": [], "routine_tasks": []}, f, ensure_ascii=False, indent=4)

def load_data():
    init_db()
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "online_nurses" not in data: data["online_nurses"] = []
            if "routine_tasks" not in data: data["routine_tasks"] = []
            return data
    except:
        return {"tasks": [], "online_nas": [], "online_nurses": [], "routine_tasks": []}

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 🌟 自動派發常規任務邏輯
# ==========================================
def check_and_trigger_routines():
    current_db = load_data()
    now = get_tw_datetime()
    
    if now.hour % 2 != 0:
        date_hour_str = now.strftime("%Y-%m-%d-%H")
        triggered_any = False
        
        for rt in current_db.get("routine_tasks", []):
            if rt.get("last_triggered_date_hour") != date_hour_str:
                new_task = {
                    "id": str(uuid.uuid4()),
                    "time_created": now.strftime("%H:%M:%S"),
                    "location": rt["location"],
                    "items": "🔄 常規翻身 (每2H)",
                    "priority": False,
                    "status": "待處理", 
                    "assigned_to": "",
                    "est_time": "",
                    "time_completed": "",
                    "dispatched_by": f"{rt['dispatched_by']} (系統自動)"
                }
                current_db["tasks"].append(new_task)
                rt["last_triggered_date_hour"] = date_hour_str
                triggered_any = True
                
        if triggered_any:
            save_data(current_db)

check_and_trigger_routines()
db_data = load_data()

# --- 初始化個人設備記憶 ---
if 'current_user' not in st.session_state: st.session_state.current_user = None 
if 'current_nurse' not in st.session_state: st.session_state.current_nurse = None 
if 'alerted_tasks' not in st.session_state: st.session_state.alerted_tasks = set()

# --- 同步檢查 ---
if st.session_state.current_nurse and st.session_state.current_nurse not in db_data.get("online_nurses", []):
    st.session_state.current_nurse = None
if st.session_state.current_user and st.session_state.current_user not in db_data.get("online_nas", []):
    st.session_state.current_user = None

# --- 床位資料 ---
BED_DATA = {
    "留觀(OBS)": ["1", "2", "3", "5", "6", "7", "8", "9", "10", "11", "12", "13", "15", "16", "17", "18", "19", "20", "21", "22", "23", "25", "26", "27", "28", "29", "30", "31", "32", "33", "35", "36", "37", "38", "39"],
    "診間": ["5", "6", "11", "12", "13", "15", "16", "17", "18", "19", "20", "21", "22", "23", "25", "27", "28", "29", "30", "31", "32", "33", "36", "37", "38", "39"],
    "兒科": ["501", "502", "503", "505", "506", "507", "508", "509"],
    "急救區": [],
    "檢傷": [],
    "縫合室": [],
    "超音波室": []
}

# --- 側邊欄 ---
st.sidebar.title("🏥 系統導覽")
role = st.sidebar.radio("請選擇角色介面：", ["👩‍⚕️ 護理人員派發端", "🧑‍⚕️ 護佐接收端", "🖥️ 急診動態看板", "📊 歷史紀錄"])

st.sidebar.divider()

with st.sidebar.expander("⚙️ 管理線上人員 (強制下線)"):
    current_db = load_data()
    st.markdown("##### 👩‍⚕️ 護理人員")
    online_nurses = current_db.get("online_nurses", [])
    if online_nurses:
        target_nurse = st.selectbox("選擇要下線的護理師：", online_nurses)
        if st.button("強制護理師下線", use_container_width=True):
            current_db["online_nurses"].remove(target_nurse)
            save_data(current_db); st.rerun()
    else: st.caption("無護理人員上線")
        
    st.divider()
    st.markdown("##### 🧑‍⚕️ 護佐人員")
    online_nas = current_db.get("online_nas", [])
    if online_nas:
        target_na = st.selectbox("選擇要下線的護佐：", online_nas)
        if st.button("強制護佐下線", use_container_width=True):
            current_db["online_nas"].remove(target_na)
            save_data(current_db); st.rerun()
    else: st.caption("無護佐上線")

st.sidebar.divider()
auto_refresh = st.sidebar.checkbox("🔄 開啟自動更新 (10秒)", value=(role == "🖥️ 急診動態看板" or role == "🧑‍⚕️ 護佐接收端"))
if st.sidebar.button("👉 立即手動同步", type="primary", use_container_width=True): st.rerun()

st.sidebar.divider()
with st.sidebar.expander("⚠️ 系統聲明與隱私規範"):
    st.markdown("""
    **👨‍⚕️ 開發與維護：** 本系統由 花蓮慈濟急診 護理師 吳智弘 獨立開發設計。
    **🛡️ 系統版權與免責聲明：** 本系統為提升急診臨床照護效率所開發之內部輔助工具。系統架構與設計版權歸開發者所有，僅限於單位內部臨床業務交流與工作調度使用，請勿任意重製、外流或作商業用途。系統運作仰賴網路連線，若遇斷線、當機等不可抗力之突發狀況，請同仁依循常規之口頭交班模式進行作業。
    **🔒 病患隱私保密規定：** 依據《個人資料保護法》及相關醫療法規，使用本系統派發或備註任務時，**嚴禁輸入任何可直接識別病患身分之個人資訊**（例如：病患真實全名、身分證字號、完整病歷號等）。備註欄位請一律以「床號」、「病徵」或「任務代稱」代替，共同守護病患隱私與醫療資訊安全。
    """)

# ==========================================
# 畫面一：護理人員派發端
# ==========================================
if role == "👩‍⚕️ 護理人員派發端":
    st.title("👩‍⚕️ 任務派發")
    
    if not st.session_state.current_nurse:
        with st.container(border=True):
            st.info("💡 首次使用請先輸入綽號，方便護佐執行完畢後向您回報。")
            nurse_name = st.text_input("輸入您的綽號 (例如：急診瘋狗、高麗菜)：")
            if st.button("開始派發任務", type="primary"):
                if nurse_name:
                    st.session_state.current_nurse = nurse_name
                    current_db = load_data()
                    if nurse_name not in current_db.get("online_nurses", []):
                        current_db.setdefault("online_nurses", []).append(nurse_name)
                        save_data(current_db); st.rerun()
                else: st.warning("請先輸入綽號！")
    else:
        col_greet, col_logout = st.columns([4, 1])
        with col_greet: st.success(f"你好，護理師 {st.session_state.current_nurse}")
        with col_logout:
            if st.button("本人下線"):
                current_db = load_data()
                if st.session_state.current_nurse in current_db.get("online_nurses", []):
                    current_db["online_nurses"].remove(st.session_state.current_nurse)
                    save_data(current_db)
                st.session_state.current_nurse = None; st.rerun()

        online_list = db_data.get("online_nas", [])
        st.info(f"🟢 目前線上護佐：{', '.join(online_list) if online_list else '無人上線'}")
        
        with st.container(border=True):
            st.subheader("📍 步驟 1：選擇位置")
            col1, col2 = st.columns(2)
            with col1: area = st.selectbox("大區域", list(BED_DATA.keys()))
            with col2:
                beds_in_area = BED_DATA[area]
                if beds_in_area:
                    bed_options = ["(區域撥補/不需床號)"] + beds_in_area
                    bed = st.selectbox("床號", bed_options)
                else:
                    st.write("\n"); st.info("此區域不需選擇床號"); bed = ""

            st.divider()
            st.subheader("📋 步驟 2：需要協助的項目 (可多選)")
            
            col_turn, col_feed = st.columns(2)
            with col_turn:
                is_turn_over = st.checkbox("🛏️ 翻身")
                turn_over_type = None
                if is_turn_over: turn_over_type = st.radio("翻身頻率設定：", ["單次", "常規 (每兩小時奇數點自動派發)"], horizontal=True)
            with col_feed:
                is_feeding = st.checkbox("🥣 餵食 / 灌食")
                feeding_type = None
                if is_feeding: feeding_type = st.radio("進食方式：", ["由口進食", "NG 灌食"], horizontal=True)
            
            st.write("") 
            task_list = ["換尿布", "倒尿/回報", "更換全套被服", "pre OP", "pre MRI"]
            selected_checkboxes = []
            check_cols = st.columns(3)
            for i, t_name in enumerate(task_list):
                with check_cols[i % 3]:
                    if st.checkbox(t_name, key=f"chk_{t_name}"): selected_checkboxes.append(t_name)
            
            col_other1, col_other2 = st.columns(2)
            with col_other1: other_input = st.text_input("其他協助 (自行輸入)")
            with col_other2: iv_input = st.text_input("IV車/醫材撥補 (填入車號)")

            st.divider()
            is_priority = st.toggle("⭐ 優先處理 (急件請開啟)", value=False)
            
            if st.button("🚀 送出呼叫 (Submit)", type="primary", use_container_width=True):
                final_items = selected_checkboxes.copy()
                if is_feeding: final_items.append(f"餵食 ({feeding_type})")
                if is_turn_over:
                    if turn_over_type == "單次": final_items.append("翻身 (單次)")
                    else: final_items.append("翻身 (啟動常規)")
                if other_input: final_items.append(f"其他:{other_input}")
                if iv_input: final_items.append(f"撥補:{iv_input}")
                
                if not final_items: st.error("請至少選擇或輸入一個項目！")
                else:
                    current_db = load_data()
                    loc_str = f"{area}" + (f" - {bed}" if bed and bed != "(區域撥補/不需床號)" else " (全區/撥補)")
                    new_task = {
                        "id": str(uuid.uuid4()), "time_created": get_tw_time(), "location": loc_str,
                        "items": "、".join(final_items), "priority": is_priority, "status": "待處理", 
                        "assigned_to": "", "est_time": "", "time_completed": "", "dispatched_by": st.session_state.current_nurse
                    }
                    current_db["tasks"].append(new_task)
                    
                    if is_turn_over and turn_over_type != "單次":
                        now = get_tw_datetime()
                        new_routine = {
                            "id": str(uuid.uuid4()), "location": loc_str, "dispatched_by": st.session_state.current_nurse,
                            "last_triggered_date_hour": now.strftime("%Y-%m-%d-%H") if now.hour % 2 != 0 else ""
                        }
                        current_db.setdefault("routine_tasks", []).append(new_routine)

                    save_data(current_db); st.success("任務已送出！"); time.sleep(0.5); st.rerun()

        st.divider()
        st.subheader("🔁 執行中【常規翻身】管理 (停止派發)")
        routine_tasks = db_data.get("routine_tasks", [])
        if routine_tasks:
            for rt in routine_tasks:
                with st.container(border=True):
                    col_rt1, col_rt2 = st.columns([4, 1])
                    with col_rt1: st.info(f"📍 {rt['location']} / 發單：{rt['dispatched_by']} (每奇數小時自動)")
                    with col_rt2:
                        if st.button("❌ 停止常規", key=f"stop_rt_{rt['id']}"):
                            current_db = load_data()
                            current_db["routine_tasks"] = [r for r in current_db["routine_tasks"] if r["id"] != rt["id"]]
                            save_data(current_db); st.rerun()
        else: st.write("目前無設定常規翻身。")

        st.divider()
        st.subheader("🗑️ 一般進行中任務管理 (可取消單次任務)")
        active_tasks = [t for t in db_data.get("tasks", []) if t["status"] in ["待處理", "執行中"]]
        if active_tasks:
            for t in active_tasks:
                with st.expander(f"【{t['status']}】{t['location']} - {t['items']}"):
                    if st.button(f"❌ 取消此任務", key=f"cancel_nurse_{t['id']}"):
                        current_db = load_data()
                        for item in current_db["tasks"]:
                            if item["id"] == t["id"]:
                                item["status"] = "已取消"; item["time_completed"] = get_tw_time(); break
                        save_data(current_db); st.rerun()

# ==========================================
# 畫面二：護佐接收端
# ==========================================
elif role == "🧑‍⚕️ 護佐接收端":
    st.title("🧑‍⚕️ 接收端")
    
    if not st.session_state.current_user:
        with st.container(border=True):
            nickname = st.text_input("輸入綽號登入：")
            if st.button("登入"):
                if nickname:
                    st.session_state.current_user = nickname
                    current_db = load_data()
                    if nickname not in current_db.get("online_nas", []):
                        current_db.setdefault("online_nas", []).append(nickname)
                        save_data(current_db); st.rerun()
    else:
        st.success(f"你好，{st.session_state.current_user}")
        if st.button("本人下線"):
            current_db = load_data()
            if st.session_state.current_user in current_db.get("online_nas", []):
                current_db["online_nas"].remove(st.session_state.current_user)
                save_data(current_db)
            st.session_state.current_user = None; st.rerun()
        
        st.divider()
        
        # 🌟 護佐端大升級：新增自辦 / 常規任務介面
        with st.expander("➕ 新增自辦 / 常規任務 (主動巡房、口頭交辦)"):
            col_na_area, col_na_bed = st.columns(2)
            with col_na_area: na_area = st.selectbox("大區域", list(BED_DATA.keys()), key="na_area")
            with col_na_bed:
                na_beds = BED_DATA[na_area]
                if na_beds: na_bed = st.selectbox("床號", ["(區域撥補/不需床號)"] + na_beds, key="na_bed")
                else: st.info("不需選床號"); na_bed = ""
            
            na_loc_str = f"{na_area}" + (f" - {na_bed}" if na_bed and na_bed != "(區域撥補/不需床號)" else " (全區/撥補)")
            
            st.write("---")
            task_mode = st.radio("任務模式：", ["單次執行", "🔁 設定為常規任務 (每奇數小時自動派發)"], horizontal=True)
            
            if task_mode == "單次執行":
                na_task_type = st.selectbox("任務類型", ["翻身", "換尿布", "倒尿/回報", "餵食", "定時醫材/IV撥補", "其他"], key="na_type")
                na_task_other = st.text_input("備註說明", key="na_other")
                na_est_time = st.selectbox("預估時間", ["5 分鐘", "10 分鐘", "15 分鐘", "30 分鐘"], key="na_time")
                if st.button("登錄並開始執行單次任務", type="primary"):
                    current_db = load_data()
                    new_task = {
                        "id": str(uuid.uuid4()), "time_created": get_tw_time(), "location": na_loc_str,
                        "items": f"{na_task_type} - {na_task_other}" if na_task_other else na_task_type,
                        "priority": False, "status": "執行中", "assigned_to": st.session_state.current_user,
                        "est_time": na_est_time, "time_completed": "", "dispatched_by": f"{st.session_state.current_user} (護佐自建)"
                    }
                    current_db["tasks"].append(new_task)
                    save_data(current_db); st.success("任務已登錄！"); time.sleep(0.5); st.rerun()
            else:
                st.info("💡 設定後，系統會在每天的 1, 3, 5, 7, 9... 點自動將「常規翻身」發送到待處理清單。")
                if st.button("啟動常規翻身", type="primary"):
                    current_db = load_data()
                    now = get_tw_datetime()
                    new_routine = {
                        "id": str(uuid.uuid4()), "location": na_loc_str, "dispatched_by": f"{st.session_state.current_user} (護佐自建)",
                        "last_triggered_date_hour": now.strftime("%Y-%m-%d-%H") if now.hour % 2 != 0 else ""
                    }
                    current_db.setdefault("routine_tasks", []).append(new_routine)
                    save_data(current_db); st.success("已加入常規翻身清單！"); time.sleep(0.5); st.rerun()

        st.divider()
        st.subheader("🔁 執行中【常規翻身】管理 (停止派發)")
        routine_tasks = db_data.get("routine_tasks", [])
        if routine_tasks:
            for rt in routine_tasks:
                with st.container(border=True):
                    col_rt1, col_rt2 = st.columns([4, 1])
                    with col_rt1: st.info(f"📍 {rt['location']} / 發單：{rt['dispatched_by']}")
                    with col_rt2:
                        if st.button("❌ 停止", key=f"stop_rt_na_{rt['id']}"):
                            current_db = load_data()
                            current_db["routine_tasks"] = [r for r in current_db["routine_tasks"] if r["id"] != rt["id"]]
                            save_data(current_db); st.rerun()
        else: st.write("目前無設定常規翻身。")

        st.divider()
        pending = [t for t in db_data.get("tasks", []) if t["status"] == "待處理"]
        pending.sort(key=lambda x: (not x["priority"], x["time_created"]))
        
        new_priority_found = False
        for t in pending:
            if t["priority"] and t["id"] not in st.session_state.alerted_tasks:
                st.toast(f"🚨 優先任務：{t['location']} 需要協助！", icon="🚨")
                st.session_state.alerted_tasks.add(t["id"])
                new_priority_found = True
        
        if new_priority_found:
            audio_js = """<script>if (navigator.vibrate) { navigator.vibrate([500, 200, 500, 200, 500]); } var audio = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg'); audio.play().catch(function(e) { console.log("音效遭阻擋"); });</script>"""
            components.html(audio_js, height=0)

        st.subheader("🔔 待接單")
        if not pending: st.info("目前無待處理任務。")
        for t in pending:
            with st.container(border=True):
                col_t, col_b = st.columns([3, 1])
                with col_t:
                    dispatch_info = f" (發單：{t.get('dispatched_by', '未紀錄')})"
                    if t["priority"]: st.error(f"⭐ [優先] {t['location']} - {t['items']}{dispatch_info}")
                    else: st.write(f"{t['location']} - {t['items']}{dispatch_info}")
                with col_b:
                    est = st.selectbox("預估時間", ["5分", "10分", "15分"], key=f"est_{t['id']}")
                    if st.button("接單", key=f"get_{t['id']}", type="primary"):
                        current_db = load_data()
                        for item in current_db["tasks"]:
                            if item["id"] == t["id"]:
                                item["status"] = "執行中"; item["assigned_to"] = st.session_state.current_user; item["est_time"] = est
                        save_data(current_db); st.rerun()
                    if st.button("取消", key=f"cancel_na_{t['id']}"):
                        current_db = load_data()
                        for item in current_db["tasks"]:
                            if item["id"] == t["id"]: item["status"] = "已取消"; item["time_completed"] = get_tw_time()
                        save_data(current_db); st.rerun()

        st.divider()
        st.subheader("🟡 我的執行中任務")
        my_tasks = [t for t in db_data.get("tasks", []) if t["status"] == "執行中" and t["assigned_to"] == st.session_state.current_user]
        if not my_tasks: st.write("目前無執行中任務。")
        for t in my_tasks:
            with st.container(border=True):
                dispatch_info = f" (發單：{t.get('dispatched_by', '未紀錄')})"
                st.warning(f"{t['location']} - {t['items']}{dispatch_info} / 預估:{t['est_time']}")
                if st.button("✅ 完成任務", key=f"done_{t['id']}"):
                    current_db = load_data()
                    for item in current_db["tasks"]:
                        if item["id"] == t["id"]:
                            item["status"] = "已完成"; item["time_completed"] = get_tw_time()
                    save_data(current_db); st.rerun()

# ==========================================
# 畫面三：急診動態看板
# ==========================================
elif role == "🖥️ 急診動態看板":
    st.title("🖥️ 即時看板")
    all_tasks = db_data.get("tasks", [])
    pending = [t for t in all_tasks if t["status"] == "待處理"]
    doing = [t for t in all_tasks if t["status"] == "執行中"]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("🟢 線上護佐", f"{len(db_data.get('online_nas', []))}人")
    col2.metric("🟡 執行中", f"{len(doing)}件")
    col3.metric("🔴 待處理", f"{len(pending)}件")
    
    st.divider()
    st.subheader("🏃 執行中動態")
    for t in doing: st.warning(f"🧑‍⚕️ **{t['assigned_to']}** 於 **{t['location']}**：{t['items']} (發單:{t.get('dispatched_by', '未紀錄')} / 剩餘約 {t['est_time']})")
    
    st.divider()
    st.subheader("📋 待處理清單")
    pending.sort(key=lambda x: (not x["priority"], x["time_created"]))
    for t in pending:
        if t["priority"]: st.error(f"🚨 [急件] {t['location']} ➔ {t['items']} (發單:{t.get('dispatched_by', '未紀錄')} / {t['time_created']})")
        else: st.info(f"📍 {t['location']} ➔ {t['items']} (發單:{t.get('dispatched_by', '未紀錄')} / {t['time_created']})")

# ==========================================
# 畫面四：歷史紀錄
# ==========================================
elif role == "📊 歷史紀錄":
    st.title("📊 任務紀錄")
    df = pd.DataFrame(db_data.get("tasks", []))
    if not df.empty:
        cols_to_show = ["time_created", "status", "dispatched_by", "location", "items", "assigned_to", "time_completed"]
        for col in cols_to_show:
            if col not in df.columns: df[col] = "未紀錄"
        st.dataframe(df[cols_to_show], use_container_width=True)
    else: st.write("尚無資料")

# --- 自動刷新 ---
if auto_refresh:
    time.sleep(10)
    st.rerun()
