import streamlit as st
import streamlit.components.v1 as components
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
        time.sleep(0.0001)
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
    """Injects custom CSS ensuring the main settings/voting panel stacks underneath the calendar table on mobile while keeping the 7-column grid intact."""
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

    /* ---- Pointer Events Tunneling for Full-Box Clicks ---- */
    div[data-testid="stMarkdownContainer"]:has(.cellvis) {
        position: relative;
        z-index: 10;
        pointer-events: none; 
    }

    /* ---- Day cells (Desktop & Tablet Base) ---- */
    .cellvis {
        pointer-events: none;
        position: relative;
        height: 85px;
        min-height: 85px;
        border-radius: 14px;
        padding: 6px 4px;
        color: #123654;
        font-weight: 700;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
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
        display: none; font-size: 8px; line-height: 1; letter-spacing: 0.08em;
        color: #2d5d8a; font-weight: 800; text-transform: uppercase; margin-bottom: 2px;
    }
    .cellvis .daynum { font-size: 15px; line-height: 1.1; font-weight: 800; color: #123654 !important; pointer-events: none; }

    /* ---- Scrollable Member Badges Container ---- */
    .user-scroll-box {
        display: flex;
        flex-direction: column;
        gap: 2px;
        width: 100%;
        margin-top: 4px;
        overflow-y: auto;
        pointer-events: auto;
        cursor: pointer;
        max-height: 48px;
        scrollbar-width: none; 
        -ms-overflow-style: none; 
        -webkit-overflow-scrolling: touch;
    }
    .user-scroll-box::-webkit-scrollbar { display: none; }

    .member-badge {
        font-size: 11px;
        color: #ffffff;
        text-shadow: 0 1px 2px rgba(0,0,0,0.6);
        border-radius: 4px;
        padding: 2px 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis; 
        width: 100%;
        box-sizing: border-box;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.15);
        flex-shrink: 0;
    }

    /* ---- Synced Transparent Button Layer (Full-Box Clickable) ---- */
    div[class*="st-key-b_"] {
        position: relative;
        z-index: 5;
        height: 85px;
        min-height: 85px;
        margin-top: -91px;
    }
    div[class*="st-key-b_"] button {
        background: transparent !important;
        border: 0 transparent !important;
        box-shadow: none !important;
        width: 100% !important;
        height: 100% !important;
        min-height: 85px;
        cursor: pointer;
        pointer-events: auto;
    }
    div[class*="st-key-b_"] button:hover { filter: brightness(1.15); }

    /* ---- Status breathing dot ---- */
    .statusdot {
        display: inline-block; width: 12px; height: 12px; border-radius: 50%;
        vertical-align: middle; margin-right: 6px;
        animation: breatheGlow 2.4s ease-in-out infinite;
    }

    /* ============ Phase 2 & 3: Odometer, Voting Cards & Liquid Orbs ============ */
    @keyframes odRoll { from { transform: translateY(var(--od-from, -0%)); } to { transform: translateY(var(--od-to, 0%)); } }
    .odometer { display: inline-flex; gap: 2px; vertical-align: middle; background: linear-gradient(180deg, #fff, #eef4ff); border: 1px solid rgba(0,120,255,.3); border-radius: 7px; padding: 0 6px; box-shadow: inset 0 1px 2px rgba(0,0,0,.08); font-variant-numeric: tabular-nums; }
    .od-col { width: .78em; height: 1.3em; overflow: hidden; position: relative; }
    .od-digits { position: absolute; left: 0; top: 0; display: flex; flex-direction: column; transform: translateY(var(--od-to, 0%)); animation: odRoll .8s cubic-bezier(.22,1.35,.36,1) both; }
    .od-digits span { height: 1.3em; line-height: 1.3em; text-align: center; font-weight: 800; color: #0a4d8e; }

    @keyframes glideIn { from { transform: translateY(calc(var(--flip-delta, 0) * -46px)); opacity: .55; } to { transform: translateY(0); opacity: 1; } }
    @keyframes scatterIn { 0% { transform: rotate(calc(var(--rot, 3deg) * -1)) translate(-8px, -12px) scale(.55); opacity: 0; } 70% { transform: rotate(0) translate(0, 2px) scale(1.03); opacity: 1; } 100% { transform: rotate(0) translate(0, 0) scale(1); opacity: 1; } }
    .proposal-card { position: relative; border-radius: 14px; padding: 10px 12px; margin-bottom: 10px; background: linear-gradient(135deg, rgba(255,255,255,.97), rgba(240,248,255,.93)); border: 1px solid rgba(0,120,255,.16); box-shadow: 0 3px 8px rgba(0,0,0,.07); animation: glideIn .5s ease both; transition: opacity .8s ease, filter .8s ease, transform .8s ease; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; }
    .proposal-card.golden { border: 2px solid #ffd94d; box-shadow: 0 0 16px 3px rgba(255,210,0,.45); animation: goldenPulse 1.6s ease-in-out infinite, glideIn .5s ease both; }
    .proposal-card.misfit { opacity: .18; filter: saturate(.2) blur(.5px); transform: scale(.96); }
    .proposal-card.scatter { animation: scatterIn .6s cubic-bezier(.34,1.56,.64,1) both; animation-delay: var(--sd, 0s); }
    .pc-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .pc-slot { font-size: 11px; background: rgba(0,120,255,.12); color: #0a5f9e; border-radius: 999px; padding: 1px 8px; }
    .pc-votes { font-size: 11px; color: #555; margin-left: auto; white-space: nowrap; }
    .pc-note { margin-top: 4px; font-size: 13px; color: #333; }
    .pc-act { margin-top: 2px; font-size: 13px; color: #1c5e8a; }
    .pc-rank { font-size: 10px; color: #b8860b; margin-left: 6px; }
    .misfit-badge { margin-left: 6px; font-size: 10px; background: rgba(180,180,180,.25); color: #666; border-radius: 999px; padding: 1px 6px; }

    @keyframes springPop { 0% { transform: scale(.3); opacity: 0; } 60% { transform: scale(1.15); } 80% { transform: scale(.95); } 100% { transform: scale(1); opacity: 1; } }
    .liquid-cell { text-align: center; padding: 10px 0 6px; }
    .merged-orb { display: inline-flex; align-items: center; background: radial-gradient(circle at 30% 25%, rgba(255,255,255,.95), rgba(120,220,255,.4) 75%); border: 1.5px solid rgba(0,150,255,.45); border-radius: 999px; padding: 8px 20px; box-shadow: 0 0 20px rgba(0,170,255,.5); animation: springPop .65s cubic-bezier(.34,1.56,.64,1) both; }
    .orb-drop { width: 17px; height: 17px; border-radius: 50%; border: 2px solid #fff; display: inline-block; margin-left: -6px; box-shadow: 0 0 6px rgba(0,0,0,.25); }
    .orb-count { font-weight: 800; color: #0a5f9e; font-size: 14px; }
    .orb-sub { margin-top: 6px; font-size: 12px; color: #666; }

    /* ============ RESPONSIVE MOBILE LAYOUT ============ */
    @media (max-width: 700px) {
        /* 1. Stack the main columns vertically so settings/voting appear UNDER the calendar table */
        [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]:not(:has(> [data-testid="stColumn"]:nth-child(7))) {
            flex-direction: column !important;
        }
        [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]:not(:has(> [data-testid="stColumn"]:nth-child(7))) > [data-testid="stColumn"] {
            width: 100% !important;
            min-width: 100% !important;
            flex: 1 0 100% !important;
        }

        /* 2. Keep calendar rows strictly as a 7-column grid matching Picture 1 */
        [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)) {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 2px !important;
        }
        [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)) > [data-testid="stColumn"] {
            flex: 1 1 calc(100% / 7) !important;
            min-width: 0 !important;
            width: calc(100% / 7) !important;
            padding: 0 !important;
        }

        .cellvis {
            height: 58px;
            min-height: 58px;
            border-radius: 6px;
            padding: 3px 2px;
            margin-bottom: 2px;
        }
        .cellvis .daynum { font-size: 11px; font-weight: 800; line-height: 1.1; }
        .user-scroll-box { max-height: 34px; margin-top: 2px; gap: 1px; }
        .member-badge { font-size: 7.5px; padding: 1px 2px; border-radius: 2px; }

        div[class*="st-key-b_"] {
            height: 58px;
            min-height: 58px;
            margin-top: -63px;
        }
        div[class*="st-key-b_"] button {
            height: 58px;
            min-height: 58px;
        }
    }
    /* ============ DARK MODE OVERRIDES FOR VOTE BOX ============ */
    @media (prefers-color-scheme: dark) {
        /* Changes the box background to a sleek dark theme */
        .proposal-card {
            background: linear-gradient(135deg, #2b303b, #1a1e24) !important;
            border: 1px solid rgba(100, 150, 255, 0.2) !important;
            box-shadow: 0 3px 8px rgba(0,0,0,0.4) !important;
        }
        
        /* If you make the box dark, the text needs to be white/light instead of black */
        .pc-head b { color: #ffffff !important; text-shadow: none !important; }
        .pc-note { color: #cccccc !important; }
        .pc-act { color: #8ab4f8 !important; }
        .pc-votes { color: #aaaaaa !important; }
        .pc-slot { background: rgba(100,150,255,.2) !important; color: #8ab4f8 !important; }
    }
    </style>
        """
    st.markdown(css, unsafe_allow_html=True)

def inject_js():
    """Injects JavaScript that differentiates tap vs. scroll inside .user-scroll-box.

    Uses st.components.v1.html() (an iframe) because st.markdown does NOT
    execute <script> tags (React dangerouslySetInnerHTML strips them).
    The iframe script accesses window.parent.document so event listeners
    are attached to the Streamlit app page itself.

    On touch devices a quick tap (movement < 10px) forwards a synthetic click
    to the corresponding Streamlit date-selection button.  Vertical dragging
    beyond the threshold is left to the browser's native scroll.  On desktop
    a standard mouse click is forwarded directly.  A short suppression window
    prevents the synthetic mouse-click that mobile browsers emit after
    touchend from firing twice.
    """
    js = """
    <script>
    (function() {
        try {
            var p = window.parent;
            var d = p.document;

            if (p.__stScrollBoxTapInit) return;
            p.__stScrollBoxTapInit = true;

            var TAP_THRESHOLD = 10;           // px — below = tap
            var CLICK_SUPPRESS_MS = 300;      // ms — suppress synthetic click after touch
            var lastTouchTime = 0;

            function findDateButtonFromBox(box) {
                var cellvis = box.closest('.cellvis');
                if (!cellvis) return null;

                // Method 1 — button lives in the same Streamlit column as the cell
                var col = cellvis.closest('[data-testid="stColumn"]');
                if (col) {
                    var btnDiv = col.querySelector('div[class*="st-key-b_"]');
                    if (btnDiv) {
                        var b = btnDiv.querySelector('button');
                        if (b) return b;
                    }
                }

                // Method 2 — match by date string in the cell title ↔ button key class
                var dateStr = cellvis.getAttribute('title');
                if (dateStr) {
                    var key = 'b_' + dateStr;
                    var divs = d.querySelectorAll('div[class*="st-key-b_"]');
                    for (var i = 0; i < divs.length; i++) {
                        if ((divs[i].className || '').indexOf(key) !== -1) {
                            var b2 = divs[i].querySelector('button');
                            if (b2) return b2;
                        }
                    }
                }
                return null;
            }

            function triggerSelect(box) {
                var btn = findDateButtonFromBox(box);
                if (btn) {
                    btn.click();
                }
            }

            /* ---- Touch: differentiate tap from scroll ---- */
            d.addEventListener('touchstart', function(e) {
                var box = e.target.closest('.user-scroll-box');
                if (!box) return;
                var t = e.touches[0];
                box.__tapX = t.clientX;
                box.__tapY = t.clientY;
                box.__scrolling = false;
            }, { passive: true });

            d.addEventListener('touchmove', function(e) {
                var box = e.target.closest('.user-scroll-box');
                if (!box) return;
                if (!box.__tapX || e.touches.length === 0) return;
                var dx = e.touches[0].clientX - box.__tapX;
                var dy = e.touches[0].clientY - box.__tapY;
                if (Math.sqrt(dx * dx + dy * dy) > TAP_THRESHOLD) {
                    box.__scrolling = true;
                }
            }, { passive: true });

            d.addEventListener('touchend', function(e) {
                var box = e.target.closest('.user-scroll-box');
                if (!box) return;
                if (!box.__scrolling) {
                    lastTouchTime = Date.now();
                    triggerSelect(box);
                }
                box.__tapX = null;
                box.__tapY = null;
                box.__scrolling = false;
            });

            d.addEventListener('touchcancel', function(e) {
                var box = e.target.closest('.user-scroll-box');
                if (!box) return;
                box.__tapX = null;
                box.__tapY = null;
                box.__scrolling = false;
            }, { passive: true });

            /* ---- Mouse: forward click to date button on desktop ---- */
            d.addEventListener('click', function(e) {
                var box = e.target.closest('.user-scroll-box');
                if (!box) return;
                // Suppress the synthetic click that mobile emits after touchend
                if (Date.now() - lastTouchTime < CLICK_SUPPRESS_MS) return;
                triggerSelect(box);
            });
        } catch (err) {
            if (typeof console !== 'undefined' && console.error) {
                console.error('Streamlit tap handler error:', err);
            }
        }
    })();
    </script>
    """
    components.html(js, width=0, height=0)

def render_day_cell(day, date_str, state, current_user, is_active, weekday_label=None):
    """Builds an animated calendar cell with scrollable member name badges and full-box clickability."""
    avail = state.get("availability", {}).get(date_str, {})
    members = list(avail.keys())
    cnt = len(members)
    heat = round(min(0.08 + cnt * 0.13, 0.75), 2)

    inner = ""
    if cnt:
        tags = "".join(
            f'<div class="member-badge" style="background-color:{state["members"].get(m, "#ddd")};">{html.escape(m)}</div>'
            for m in members
        )
        inner = f'<div class="user-scroll-box">{tags}</div>'

    weekday_html = f'<div class="dayweek">{html.escape(weekday_label)}</div>' if weekday_label else ""

    cls = "cellvis"
    if cnt >= 2: cls += " gold"
    if is_active: cls += " active"

    return (f'<div class="{cls}" style="--heat:{heat};" title="{date_str}">'
            f'{weekday_html}<div class="daynum">{day}</div>{inner}</div>')
    
def fmt_min(m):
    """Convert minutes since midnight -> 'HH:MM'."""
    mh, mm = divmod(int(m), 60)
    return f"{mh:02d}:{mm:02d}"

def parse_slot_bounds(slot):
    """Parse a slot string -> (start_min, end_min)."""
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
    """Pure-CSS odometer: digit strips roll from prev to current."""
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
    """Proposal card: odometer counter + golden-border top + FLIP glide delta."""
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
    badge = "<span class='misfit-badge'> 唔涵蓋揀緊嘅時段</span>" if misfit else ""

    return (f'<div class="{cls}" style="--flip-delta:{delta}; --sd:{delay:.2f}s; --rot:{rot}deg;">'
            f'<div class="pc-head"><span class="statusdot" style="background:{p_c}"></span>'
            f'<b>{p_emoji} {name}</b><span class="pc-slot">🕐 {slot_txt}</span>'
            f'<span class="pc-votes">票數 {odo}{badge}</span></div>'
            f'<div class="pc-note">💬 {note}</div>'
            f'<div class="pc-act">💡 提議: {act}<span class="pc-rank">🏅 第 {rank + 1} 名</span></div></div>')

def render_aggregate_orb(count, people, colors):
    """Merged liquid bubble."""
    drops = "".join(
        f'<span class="orb-drop" style="background:{c};{"" if i == 0 else " margin-left:-6px;"}"></span>'
        for i, c in enumerate(colors)
    )
    return (f'<div class="liquid-cell"><div class="merged-orb">{drops}'
            f'<span class="orb-count"> <b>{count}</b> People Free</span></div>')

st.set_page_config(page_title="共享時間表 ShareTimeTable", layout="wide")
inject_css()
inject_js()
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
    col_y, col_m, col_btn, col_today = st.columns([3, 3, 2, 2])
    with col_y:
        t_year = st.number_input("年份", min_value=2000, max_value=2100, key="t_year", value=st.session_state.selected_date.year)
    with col_m:
        t_month = st.number_input("月份", min_value=1, max_value=12, key="t_month", value=st.session_state.selected_date.month)
    with col_btn:
        st.write("##")
        if st.button("跳轉", use_container_width=True):
            max_days = calendar.monthrange(t_year, t_month)[1]
            target_day = min(st.session_state.selected_date.day, max_days)
            st.session_state.selected_date = datetime.date(t_year, t_month, target_day)
            st.rerun()
    with col_today:
        st.write("##")
        if st.button("📅 回到今天", use_container_width=True):
            st.session_state.selected_date = datetime.date.today()
            st.session_state.pop("t_year", None)
            st.session_state.pop("t_month", None)
            st.rerun()

    c_year, c_month = st.session_state.selected_date.year, st.session_state.selected_date.month
    st.write(f"### 📅 {c_year} 年 {c_month} 月")
    cal = calendar.monthcalendar(c_year, c_month)

    cols_h = st.columns(7)
    for idx, h in enumerate(["一", "二", "三", "四", "五", "六", "日"]): 
        # ADDED: .cal-header class to hide the Mon-Sun header row on mobile
        cols_h[idx].markdown(f"<div class='cal-header' style='text-align:center;'><b>{h}</b></div>", unsafe_allow_html=True)

    for week in cal:
        cols_d = st.columns(7)
        for idx, day in enumerate(week):
            if day == 0: 
                # ADDED: .empty-day class so mobile view skips rendering blank gaps
                cols_d[idx].markdown("<div class='empty-day'></div>", unsafe_allow_html=True)
            else:
                d_str = f"{c_year}-{c_month:02d}-{day:02d}"
                cell_date = datetime.date(c_year, c_month, day)
                weekday_label = ["一", "二", "三", "四", "五", "六", "日"][cell_date.weekday()]

                is_active = (st.session_state.selected_date.day == day)

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
            min_value=0 * 60, max_value=24 * 60,
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
        agg_open = st.session_state.get("agg_open", False)
        replay_anim = False
        if len(people) >= 2:
            btn_txt = "點擊彈開" if not agg_open else "點擊合併"
            if st.button(btn_txt, key="toggle_agg", use_container_width=True):
                st.session_state["agg_open"] = not agg_open
                st.session_state["agg_anim"] = True
                st.rerun()
            agg_open = st.session_state.get("agg_open", False)
            replay_anim = bool(st.session_state.get("agg_anim", False))
            if replay_anim:
                del st.session_state["agg_anim"]

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
