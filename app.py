import streamlit as st
import datetime
import calendar
import json
import os
import time
import urllib.parse
import re
import html

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

def inject_css():
    """Injects all custom CSS animations (status dot glow, odometer, FLIP cards, liquid bubble, slider glow)."""
    css = """
    <style>
    /* ================= Reusable effect primitives ================= */
    @keyframes breatheGlow {
        0%, 100% { box-shadow: 0 0 4px 0 rgba(255,180,0,0.35); }
        50%      { box-shadow: 0 0 12px 3px rgba(255,180,0,0.75); }
    }
    @keyframes goldenPulse {
        0%   { box-shadow: 0 0 0 0 rgba(255,200,0,0.65); }
        100% { box-shadow: 0 0 0 12px rgba(255,200,0,0); }
    }

    /* ---- Day cells (generated with Python -> HTML) ---- */
    .cellvis {
        position: relative;
        min-height: 58px;
        border-radius: 14px;
        padding: 4px 2px 6px;
        color: #123654;
        font-weight: 700;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(220,234,255,0.92));
        border: 1.5px solid rgba(30, 94, 170, 0.24);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.8), 0 4px 12px rgba(20,72,136,0.08);
        margin-bottom: 6px;
        user-select: none;
        transition: transform .25s ease, box-shadow .3s ease, border-color .25s ease;
    }
    .cellvis.gold {
        background: linear-gradient(180deg, rgba(255,248,206,0.98), rgba(255,228,138,0.82));
        border-color: rgba(214, 159, 0, 0.65);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.8), 0 0 0 2px rgba(255,198,0,0.28), 0 6px 18px rgba(195,146,0,0.14);
        animation: goldenPulse 1.8s ease-in-out 1;
    }
    .cellvis.active {
        border-color: rgba(21, 108, 189, 0.8);
        box-shadow: 0 0 0 3px rgba(18, 83, 165, 0.24), 0 0 18px 3px rgba(33,130,255,0.45) !important;
    }
    .cellvis .dayweek {
        display: none;
        font-size: 8px;
        line-height: 1;
        letter-spacing: 0.08em;
        color: #2d5d8a;
        font-weight: 800;
        text-transform: uppercase;
        margin-bottom: 2px;
    }
    .cellvis .daynum {
        font-size: 15px;
        line-height: 1.1;
        font-weight: 800;
        color: #123654 !important;
    }
    .cellvis .droplets {
        display: flex; justify-content: center; align-items: center;
        min-height: 15px; margin-top: 2px;
    }
    .cellvis .drop {
        width: 11px; height: 11px; border-radius: 50%; display: inline-block;
        margin: 0 -2px; border: 1.5px solid rgba(255,255,255,0.9);
        box-shadow: 0 0 6px rgba(0,0,0,0.25);
        animation: breatheGlow 2.6s ease-in-out infinite;
    }

    /* ---- Turn the real St.Button into an invisible click layer over the visuals ---- */
    div[class*="st-key-b_"] {
        min-height: 58px;
        margin-top: -64px;
        z-index: 5;
    }
    div[class*="st-key-b_"] button {
        background: transparent !important;
        border: 0 transparent !important;
        box-shadow: none !important;
        min-height: 64px;
        cursor: pointer;
    }
    div[class*="st-key-b_"] button:hover { filter: brightness(1.25); }

    /* ---- Status breathing dot (used by proposal cards) ---- */
    .statusdot {
        display: inline-block; width: 12px; height: 12px; border-radius: 50%;
        vertical-align: middle; margin-right: 6px;
        animation: breatheGlow 2.4s ease-in-out infinite;
    }

    /* ============ Phase 2: Odometer Vote Counter + Auto-Sort/FLIP ============ */
    @keyframes odRoll {
        from { transform: translateY(var(--od-from, -0%)); }
        to   { transform: translateY(var(--od-to, 0%)); }
    }
    .odometer {
        display: inline-flex; gap: 2px; vertical-align: middle;
        background: linear-gradient(180deg, #fff, #eef4ff);
        border: 1px solid rgba(0,120,255,.3); border-radius: 7px;
        padding: 0 6px; box-shadow: inset 0 1px 2px rgba(0,0,0,.08);
        font-variant-numeric: tabular-nums;
    }
    .od-col { width: .78em; height: 1.3em; overflow: hidden; position: relative; }
    .od-digits {
        position: absolute; left: 0; top: 0;
        display: flex; flex-direction: column;
        transform: translateY(var(--od-to, 0%));
        animation: odRoll .8s cubic-bezier(.22,1.35,.36,1) both;
    }
    .od-digits span { height: 1.3em; line-height: 1.3em; text-align: center; font-weight: 800; color: #0a4d8e; }

    @keyframes glideIn {
        from { transform: translateY(calc(var(--flip-delta, 0) * -46px)); opacity: .55; }
        to   { transform: translateY(0); opacity: 1; }
    }
    @keyframes scatterIn {
        0%   { transform: rotate(calc(var(--rot, 3deg) * -1)) translate(-8px, -12px) scale(.55); opacity: 0; }
        70%  { transform: rotate(0) translate(0, 2px) scale(1.03); opacity: 1; }
        100% { transform: rotate(0) translate(0, 0) scale(1); opacity: 1; }
    }
    .proposal-card {
        position: relative; border-radius: 14px; padding: 10px 12px; margin-bottom: 10px;
        background: linear-gradient(135deg, rgba(255,255,255,.97), rgba(240,248,255,.93));
        border: 1px solid rgba(0,120,255,.16);
        box-shadow: 0 3px 8px rgba(0,0,0,.07);
        animation: glideIn .5s ease both;
        transition: opacity .8s ease, filter .8s ease, transform .8s ease;
        font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    }
    .proposal-card.golden {
        border: 2px solid #ffd94d;
        box-shadow: 0 0 16px 3px rgba(255,210,0,.45);
        animation: goldenPulse 1.6s ease-in-out infinite, glideIn .5s ease both;
    }
    .proposal-card.misfit { opacity: .18; filter: saturate(.2) blur(.5px); transform: scale(.96); }
    .proposal-card.scatter { animation: scatterIn .6s cubic-bezier(.34,1.56,.64,1) both; animation-delay: var(--sd, 0s); }
    .pc-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .pc-slot { font-size: 11px; background: rgba(0,120,255,.12); color: #0a5f9e; border-radius: 999px; padding: 1px 8px; }
    .pc-votes { font-size: 11px; color: #555; margin-left: auto; white-space: nowrap; }
    .pc-note { margin-top: 4px; font-size: 13px; color: #333; }
    .pc-act { margin-top: 2px; font-size: 13px; color: #1c5e8a; }
    .pc-rank { font-size: 10px; color: #b8860b; margin-left: 6px; }
    .misfit-badge { margin-left: 6px; font-size: 10px; background: rgba(180,180,180,.25); color: #666; border-radius: 999px; padding: 1px 6px; }

    /* ============ Phase 3: Liquid Cell Availability Aggregator ============ */
    @keyframes springPop {
        0%   { transform: scale(.3); opacity: 0; }
        60%  { transform: scale(1.15); }
        80%  { transform: scale(.95); }
        100% { transform: scale(1); opacity: 1; }
    }
    .liquid-cell { text-align: center; padding: 10px 0 6px; }
    .merged-orb {
        display: inline-flex; align-items: center;
        background: radial-gradient(circle at 30% 25%, rgba(255,255,255,.95), rgba(120,220,255,.4) 75%);
        border: 1.5px solid rgba(0,150,255,.45);
        border-radius: 999px; padding: 8px 20px;
        box-shadow: 0 0 20px rgba(0,170,255,.5);
        animation: springPop .65s cubic-bezier(.34,1.56,.64,1) both;
    }
    .orb-drop { width: 17px; height: 17px; border-radius: 50%; border: 2px solid #fff; display: inline-block; margin-left: -6px; box-shadow: 0 0 6px rgba(0,0,0,.25); }
    .orb-count { font-weight: 800; color: #0a5f9e; font-size: 14px; }
    .orb-sub { margin-top: 6px; font-size: 12px; color: #666; }

    /* ============ Phase 4: Magnetic Snap slider glow ============ */
    [data-testid="stSlider"] [role="slider"] { box-shadow: 0 0 8px rgba(0,150,255,.6); }

        /* ============ Responsive: same clean format on PC / iPad / phone ============
       iPad portrait & phones: stack the 2-column calendar/settings split vertically
       (col_left first, then col_right), giving each full width — same format as PC.
       The 7-column calendar grid stays in ONE row: rows with a 7th stColumn child
       are excluded via :has() so they never wrap. Selectors are keyed on testid only
       (works whether Streamlit renders columns as <section> or <div>). */
    @media (max-width: 1024px) {
        [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]:not(:has(> [data-testid="stColumn"]:nth-child(7))) {
            flex-direction: column;
        }
        [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]:not(:has(> [data-testid="stColumn"]:nth-child(7))) > [data-testid="stColumn"] {
            min-width: 100% !important;
            width: 100% !important;
            flex: 1 0 100% !important;
        }
        /* Limit panel width and center them on iPad portrait to keep identical visual ratio as PC */
        [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            max-width: 580px !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }
        .liquid-cell, .merged-orb { transform-origin: center; }
    }

    /* Phones: compact everything and center both panels to keep the elegant PC layout ratio */
    @media (max-width: 700px) {
        [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            max-width: 420px !important; /* Perfect phone portrait size, fits all elements with original PC-like aspect ratio */
        }
        h1 { font-size: 1.4rem !important; }
        h2, h3 { font-size: 1.1rem !important; }
        .cellvis {
            min-height: 58px;
            border-radius: 10px;
            padding: 4px 2px 5px;
            margin-bottom: 4px;
            border-width: 1.3px;
        }
        .cellvis .dayweek { display: block; }
        .cellvis .daynum { font-size: 14px; font-weight: 800; }
        .cellvis .drop { width: 7.5px; height: 7.5px; margin: 0 -1.5px; border-width: 1px; }
        .cellvis .droplets { min-height: 10px; margin-top: 1px; }
        div[class*="st-key-b_"] { min-height: 58px; margin-top: -63px; }
        div[class*="st-key-b_"] button { min-height: 58px; }
        .statusdot { width: 9px; height: 9px; }
        .proposal-card { padding: 8px 9px; margin-bottom: 8px; }
        .pc-slot, .pc-votes, .pc-rank, .misfit-badge { font-size: 10px; }
        .pc-note, .pc-act { font-size: 12px; }
        .odometer { transform: scale(.9); transform-origin: left center; }
        .merged-orb { padding: 6px 14px; }
        .orb-drop { width: 13px; height: 13px; border-width: 1.5px; }
        .orb-count { font-size: 12px; }
        .orb-sub { font-size: 11px; }
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def render_day_cell(day, date_str, state, current_user, is_active, weekday_label=None):
    """Builds an animated calendar cell with Heatmap Glow + individual droplets.

    - 0 people  : cool / empty cell
    - 1+ people: each available person shows as their OWN independent color droplet
                 (breathing glow), no merging bubble.
    """
    avail = state.get("availability", {}).get(date_str, {})
    members = list(avail.keys())
    cnt = len(members)
    heat = round(min(0.08 + cnt * 0.13, 0.75), 2)

    inner = ""
    if cnt:
        drops = "".join(
            f'<span class="drop" style="background:{state["members"].get(m, "#ddd")}; animation-delay:{i*0.12:.2f}s"></span>'
            for i, m in enumerate(members)
        )
        inner = f'<div class="droplets">{drops}</div>'

    weekday_html = f'<div class="dayweek">{html.escape(weekday_label)}</div>' if weekday_label else ""

    cls = "cellvis"
    if cnt >= 2: cls += " gold"          # golden-hour glow
    if is_active: cls += " active"

    return (f'<div class="{cls}" style="--heat:{heat};" title="{date_str}">'
            f'{weekday_html}<div class="daynum">{day}</div>{inner}</div>')

def fmt_min(m):
    """Convert minutes since midnight -> 'HH:MM'."""
    mh, mm = divmod(int(m), 60)
    return f"{mh:02d}:{mm:02d}"

def parse_slot_bounds(slot):
    """Parse a slot string -> (start_min, end_min). '全日得閒' => (0,1440). None if unknown."""
    if not isinstance(slot, str):
        return None
    s = slot.strip()
    if not s:
        return None
    if "全日" in s:
        return (0, 24 * 60)
    m = re.search(r"(\d{1,2}):(\d{2})\s*[-~至]\s*(\d{1,2}):(\d{2})", s)
    if m:
        return (int(m.group(1)) * 60 + int(m.group(2)), int(m.group(3)) * 60 + int(m.group(4)))
    if "上午" in s:
        return (8 * 60, 12 * 60)
    if "下午" in s:
        return (12 * 60, 18 * 60)
    if "夜" in s:
        return (18 * 60, 23 * 60)
    return None

def slots_overlap(slot, lo, hi):
    """True if 'slot' overlaps window [lo, hi] minutes."""
    b = parse_slot_bounds(slot)
    return b is not None and b[0] < hi and b[1] > lo

def render_odometer(value, prev, pid):
    """Pure-CSS odometer: digit strips roll from prev to current (like a dashboard)."""
    value = max(0, int(value)); prev = max(0, int(prev))
    t = str(value); p = str(prev)
    cols = []
    for pos, ch in enumerate(reversed(t)):
        cur_d = int(ch)
        old_d = int(p[-1 - pos]) if len(p) > pos else 0
        digits = "".join(f"<span>{i}</span>" for i in range(10))
        cols.append(
            f'<div class="od-col" style="--od-from:{-old_d * 10}%; --od-to:{-cur_d * 10}%;">'
            f'<div class="od-digits">{digits}</div></div>'
        )
    return f'<span class="odometer" id="odo_{pid}" title="票數 {prev} → {value}">{"".join(cols)}</span>'

def render_proposal_card(pid, p, data, p_c, votes, prev_votes, rank, prev_rank, misfit, scatter):
    """Feature 2 card: odometer counter + golden-border top + FLIP glide delta."""
    p_emoji = get_emoji_color(p_c)
    odo = render_odometer(votes, prev_votes, pid)
    delta = rank - prev_rank
    delay = rank * 0.06
    rot = -3 if rank % 2 else 3
    cls = "proposal-card"
    if rank == 0 and votes > 0: cls += " golden"
    if misfit: cls += " misfit"
    if scatter: cls += " scatter"

    note = html.escape((data.get("note") or "").strip() or "無留言")
    act = html.escape((data.get("activity") or "").strip() or "無提議")
    slot_txt = html.escape(data.get("time") or "全日得閒")
    name = html.escape(p)
    badge = "<span class='misfit-badge'>⏳ 唔涵蓋揀緊嘅時段</span>" if misfit else ""

    return (f'<div class="{cls}" style="--flip-delta:{delta}; --sd:{delay:.2f}s; --rot:{rot}deg;">'
            f'<div class="pc-head"><span class="statusdot" style="background:{p_c}"></span>'
            f'<b>{p_emoji} {name}</b><span class="pc-slot">🕐 {slot_txt}</span>'
            f'<span class="pc-votes">票數 {odo}{badge}</span></div>'
            f'<div class="pc-note">💬 {note}</div>'
            f'<div class="pc-act">💡 提議: {act}<span class="pc-rank">🏅 第 {rank + 1} 名</span></div></div>')

def render_aggregate_orb(count, people, colors):
    """Feature 3: merged liquid bubble (pops open into scattered cards when clicked)."""
    drops = "".join(
        f'<span class="orb-drop" style="background:{c};{"" if i == 0 else " margin-left:-6px;"}"></span>'
        for i, c in enumerate(colors)
    )
    emojis = "".join(get_emoji_color(c) for c in colors)
    names = "、".join(html.escape(n) for n in people)
    return (f'<div class="liquid-cell"><div class="merged-orb">{drops}'
            f'<span class="orb-count"> <b>{count}</b> People Free</span></div>')

st.set_page_config(page_title="共享時間表 ShareTimeTable", layout="wide")
inject_css()
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
                cell_date = datetime.date(c_year, c_month, day)
                weekday_label = ["一", "二", "三", "四", "五", "六", "日"][cell_date.weekday()]

                is_active = (st.session_state.selected_date.day == day)

                # Heatmap Glow cell visual with individual droplets (no auto-merge bubble)
                cols_d[idx].markdown(
                    render_day_cell(day, d_str, current_state, current_user, is_active, weekday_label),
                    unsafe_allow_html=True
                )

                if cols_d[idx].button(" ", key=f"b_{d_str}", use_container_width=True):
                    st.session_state.selected_date = datetime.date(c_year, c_month, day)

                    is_available = (d_str in current_state["availability"] and current_user in current_state["availability"][d_str])

                    if is_available:
                        mutate_db(_del_time, d_str, current_user)
                    else:
                        if st.session_state.get("right_all_day", True):
                            slot_label = "全日得閒"
                        else:
                            rng = st.session_state.get("right_range", (14 * 60, 18 * 60))
                            slot_label = f"{fmt_min(rng[0])}-{fmt_min(rng[1])}"
                        u_note = st.session_state.get("right_u_note", "")
                        s_act = st.session_state.get("right_s_act", "")
                        mutate_db(_save_time, d_str, current_user, {
                            "time": slot_label,
                            "note": u_note,
                            "activity": s_act,
                            "votes": 0
                        })
                    st.rerun()

with col_right:
    st.subheader(" 預設 Mark 時間設定 ")
    all_day = st.checkbox("☀️ 全日得閒 (Free all day)", value=True, key="right_all_day")
    if all_day:
        st.caption("全日得閒 —— 直接點日曆任何一格即標記")
        slot_label = "全日得閒"
        sel_lo, sel_hi = 0, 24 * 60
    else:
        rng = st.slider(
            "得閒時段",
            min_value=8 * 60, max_value=23 * 60,
            value=(14 * 60, 18 * 60), step=30,
            key="right_range",
        )
        slot_label = f"{fmt_min(rng[0])}-{fmt_min(rng[1])}"
        sel_lo, sel_hi = int(rng[0]), int(rng[1])
        st.caption(f"已選時段：**{slot_label}** —— 下方只保留覆蓋此段嘅朋友")

    u_note = st.text_input("留言 / 備註:", key="right_u_note")
    s_act = st.text_input("想做咩活動？", key="right_s_act")

    st.divider()

    active_d_str = st.session_state.selected_date.strftime("%Y-%m-%d")
    st.subheader(f" {active_d_str} 得閒嘅人 / 投票")

    people = list(current_state["availability"].get(active_d_str, {}).keys())
    if not people:
        st.info("呢一日暫時未有人 Mark 得閒。")
    else:
        # Feature 3 ---- Liquid Cell Aggregator (merge bubble when 2+ people free)
        agg_open = st.session_state.get("agg_open", False)
        replay_anim = False
        if len(people) >= 2:
            btn_txt = (
                f"點擊彈開"
                if not agg_open else "點擊合併"
            )
            if st.button(btn_txt, key="toggle_agg", use_container_width=True):
                st.session_state["agg_open"] = not agg_open
                st.session_state["agg_anim"] = True
                st.rerun()
            agg_open = st.session_state.get("agg_open", False)
            replay_anim = bool(st.session_state.get("agg_anim", False))
            if replay_anim:
                del st.session_state["agg_anim"]

        # Feature 2 ---- Auto-sort by votes (highest first, golden top)
        items = list(current_state["availability"][active_d_str].items())
        items.sort(key=lambda kv: kv[1].get("votes", 0), reverse=True)

        prev_v = dict(st.session_state.get("prev_votes", {}))
        prev_r = dict(st.session_state.get("prev_rank", {}))
        cur_v, cur_r = {}, {}

        show_cards = agg_open or len(people) < 2
        if not show_cards:
            colors = [current_state["members"].get(pp, "#888") for pp in people]
            st.markdown(render_aggregate_orb(len(people), people, colors), unsafe_allow_html=True)
        else:
            for rank, (p, data) in enumerate(items):
                pid = f"{p}|{active_d_str}"
                votes = data.get("votes", 0)
                old_v = prev_v.get(pid, votes)
                old_r = prev_r.get(pid, rank)
                cur_v[pid], cur_r[pid] = votes, rank

                # Feature 4 ---- magnetic-slot filter: non-overlapping friends dissolve
                misfit = (not all_day) and (not slots_overlap(data.get("time", ""), sel_lo, sel_hi))
                scatter = replay_anim and len(people) >= 2

                p_c = current_state["members"].get(p, "#888")
                st.markdown(
                    render_proposal_card(pid, p, data, p_c, votes, old_v, rank, old_r, misfit, scatter),
                    unsafe_allow_html=True,
                )
                if st.button(f"👍 投 {p}", key=f"v_{pid}"):
                    mutate_db(_add_vote, active_d_str, p)
                    st.rerun()

        st.session_state["prev_votes"] = cur_v
        st.session_state["prev_rank"] = cur_r
