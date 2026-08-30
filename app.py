import streamlit as st
import datetime
import calendar
import json
import os
import time
import urllib.parse

DB_FILE = "share_timetable_db.json"

def init_db():
    default_state = {
        "members": {"永康": "#FF4B4B", "子希": "#00C49F", "余俊": "#0088FE"},
        "availability": {},  
        "meta": {"last_update": 0}
    }
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(default_state, f, ensure_ascii=False, indent=4)
    else:
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(default_state, f, ensure_ascii=False, indent=4)

def mutate_db(action_fn, *args, **kwargs):
    init_db()
    lock_file = DB_FILE + ".lock"
    for _ in range(10):  
        if not os.path.exists(lock_file):
            try:
                with open(lock_file, "w") as lf: lf.write("LOCKED")
                with open(DB_FILE, "r", encoding="utf-8") as f: data = json.load(f)
                data = action_fn(data, *args, **kwargs)
                data["meta"]["last_update"] = time.time()
                with open(DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                os.remove(lock_file)
                return True
            except:
                if os.path.exists(lock_file): os.remove(lock_file)
        time.sleep(0.05)
    return False

def get_emoji_color(hex_str):
    hex_str = hex_str.lstrip('#').lower()
    if not hex_str:
        return "⚪"
    try:
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
    except ValueError:
        return "⚫"
    
    # Standard colors in RGB
    colors = {
        "🔴": (255, 75, 75),   # Red
        "🟢": (0, 196, 159),   # Teal / Green
        "🔵": (0, 136, 254),   # Blue
        "🟡": (255, 187, 40),   # Yellow
        "🟠": (255, 127, 80),  # Coral / Orange
        "🟣": (128, 0, 128),   # Purple
        "⚫": (0, 0, 0),       # Black
    }
    
    closest_emoji = "⚫"
    min_dist = float('inf')
    for emoji, rgb in colors.items():
        dist = (r - rgb[0])**2 + (g - rgb[1])**2 + (b - rgb[2])**2
        if dist < min_dist:
            min_dist = dist
            closest_emoji = emoji
    return closest_emoji

def _add_mem(d, name, color): d["members"][name] = color; return d
def _save_time(d, date_str, user, slot):
    if date_str not in d["availability"]: d["availability"][date_str] = {}
    d["availability"][date_str][user] = slot; return d
def _del_time(d, date_str, user):
    if date_str in d["availability"] and user in d["availability"][date_str]:
        del d["availability"][date_str][user]
        if not d["availability"][date_str]:
            del d["availability"][date_str]
    return d
def _add_vote(d, date_str, user):
    if date_str in d["availability"] and user in d["availability"][date_str]:
        d["availability"][date_str][user]["votes"] += 1; return d

st.set_page_config(page_title="共享時間表 ShareTimeTable", layout="wide")
init_db()

with open(DB_FILE, "r", encoding="utf-8") as f:
    current_state = json.load(f)

if "selected_date" not in st.session_state:
    st.session_state.selected_date = datetime.date.today()

st.title("📅 共享時間表 (ShareTimeTable)")

with st.sidebar:
    st.header("👤 身份與成員")
    current_user = st.selectbox("選擇你嘅身份開始 Mark 時間:", list(current_state["members"].keys()))
    user_color = current_state["members"][current_user]
    st.markdown(f"你目前的專屬顏色: <span style='color:{user_color};font-weight:bold;'>■</span>", unsafe_allow_html=True)
    st.divider()
    st.subheader("➕ 加新成員")
    new_name = st.text_input("輸入新朋友名:")
    new_color = st.color_picker("揀一隻專屬顏色:", "#FFBB28")
    if st.button("確認加入"):
        if new_name and new_name not in current_state["members"]:
            mutate_db(_add_mem, new_name, new_color); st.rerun()
            
    st.divider()
    with st.sidebar.expander(" "):
        st.markdown(""" """)

col_left, col_right = st.columns([5, 4])

with col_left:
    # Month jumping
    col_y, col_m, col_btn = st.columns([3, 3, 2])
    with col_y:
        t_year = st.number_input("年份", min_value=2000, max_value=2100, value=st.session_state.selected_date.year)
    with col_m:
        t_month = st.number_input("月份", min_value=1, max_value=12, value=st.session_state.selected_date.month)
    with col_btn:
        st.write("##")
        if st.button("跳轉", use_container_width=True):
            max_days = calendar.monthrange(t_year, t_month)[1]
            target_day = min(st.session_state.selected_date.day, max_days)
            st.session_state.selected_date = datetime.date(t_year, t_month, target_day)
            st.rerun()

    c_year, c_month = st.session_state.selected_date.year, st.session_state.selected_date.month
    st.write(f"### 📅 {c_year} 年 {c_month} 月")
    cal = calendar.monthcalendar(c_year, c_month)

    cols_h = st.columns(7)
    for idx, h in enumerate(["一", "二", "三", "四", "五", "六", "日"]): 
        cols_h[idx].markdown(f"<div style='text-align:center;'><b>{h}</b></div>", unsafe_allow_html=True)

    for week in cal:
        cols_d = st.columns(7)
        for idx, day in enumerate(week):
            if day == 0: 
                cols_d[idx].write("")
            else:
                d_str = f"{c_year}-{c_month:02d}-{day:02d}"
                
                # Gather emojis of members who are available on this day
                emojis = ""
                if d_str in current_state["availability"]:
                    for person in current_state["availability"][d_str].keys():
                        p_col = current_state["members"].get(person, "#ddd")
                        emojis += get_emoji_color(p_col)
                
                btn_label = f"{day}\n{emojis}" if emojis else f"{day}"
                is_active = (st.session_state.selected_date.day == day)
                
                if cols_d[idx].button(
                    btn_label, 
                    key=f"b_{d_str}", 
                    type="primary" if is_active else "secondary",
                    use_container_width=True
                ):
                    st.session_state.selected_date = datetime.date(c_year, c_month, day)
                    
                    is_available = (d_str in current_state["availability"] and current_user in current_state["availability"][d_str])
                    
                    if is_available:
                        mutate_db(_del_time, d_str, current_user)
                    else:
                        t_slot = st.session_state.get("right_t_slot", "全日得閒")
                        u_note = st.session_state.get("right_u_note", "")
                        s_act = st.session_state.get("right_s_act", "")
                        mutate_db(_save_time, d_str, current_user, {
                            "time": t_slot, 
                            "note": u_note, 
                            "activity": s_act, 
                            "votes": 0
                        })
                    st.rerun()

with col_right:
    st.subheader("✍️ 預設 Mark 時間設定")
    t_slot = st.selectbox(
        "邊段時間有空？", 
        ["全日得閒", "上午 (08:00-12:00)", "下午 (12:00-18:00)", "夜晚 (18:00-23:00)"],
        key="right_t_slot"
    )
    u_note = st.text_input("留言 / 備註:", key="right_u_note")
    s_act = st.text_input("想做咩活動？", key="right_s_act")
    
    st.divider()
    
    active_d_str = st.session_state.selected_date.strftime("%Y-%m-%d")
    st.subheader(f"👀 {active_d_str} 得閒嘅人 / 投票")
    
    if active_d_str not in current_state["availability"] or not current_state["availability"][active_d_str]:
        st.info("呢一日暫時未有人 Mark 得閒。")
    else:
        for p, data in current_state["availability"][active_d_str].items():
            p_c = current_state["members"].get(p, "#000")
            p_emoji = get_emoji_color(p_c)
            st.markdown(
                f"<div style='border-left:5px solid {p_c}; padding-left:10px; margin-bottom:12px; background-color: rgba(120,120,120,0.05); padding-top: 5px; padding-bottom: 5px; border-radius: 0 8px 8px 0;'>"
                f"<b>{p_emoji} {p}</b> - {data['time']}<br/>"
                f"💬 {data['note'] if data['note'] else '無留言'}<br/>"
                f"💡 提議: {data['activity'] if data['activity'] else '無提議'} (票數: {data['votes']})"
                f"</div>", 
                unsafe_allow_html=True
            )
            if st.button(f"👍 投 {p}", key=f"v_{p}_{active_d_str}"):
                mutate_db(_add_vote, active_d_str, p)
                st.rerun()
