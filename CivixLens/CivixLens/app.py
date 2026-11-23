import os
import io
import hashlib
import sqlite3
import datetime
from pathlib import Path

import streamlit as st
from PIL import Image

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "database" / "civixlens.db"
DB_PATH.parent.mkdir(exist_ok=True)

st.set_page_config(page_title="CivixLens", page_icon="🏙️", layout="wide")

# ---------- Database ----------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Citizen'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending Approval',
                points_awarded INTEGER NOT NULL DEFAULT 0,
                image_blob BLOB NOT NULL,
                image_hash TEXT NOT NULL UNIQUE,
                ai_notes TEXT DEFAULT ''
            )
        """)
        # Create an admin account from environment variables if configured.
        admin_user = os.getenv("CIVIXLENS_ADMIN_USER", "admin")
        admin_password = os.getenv("CIVIXLENS_ADMIN_PASSWORD", "")
        if admin_password:
            conn.execute(
                "INSERT OR IGNORE INTO users(username, password_hash, role) VALUES (?, ?, 'Admin')",
                (admin_user, hashlib.sha256(admin_password.encode()).hexdigest())
            )

def password_hash(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def authenticate(username, password):
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT username, role FROM users WHERE username=? AND password_hash=?",
            (username.strip(), password_hash(password))
        ).fetchone()
    return dict(row) if row else None

def register_user(username, password):
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO users(username, password_hash, role) VALUES (?, ?, 'Citizen')",
                (username.strip(), password_hash(password))
            )
        return True
    except sqlite3.IntegrityError:
        return False

def status_badge(status):
    colors = {
        "Pending Approval": "#D97706",
        "In Progress": "#2563EB",
        "Resolved": "#16A34A",
        "Rejected": "#DC2626",
    }
    color = colors.get(status, "#64748B")
    return f'<span style="background:{color};color:white;padding:4px 10px;border-radius:20px;font-size:12px">{status}</span>'

def classify_image_with_gemini(image_bytes):
    """Optional Gemini Vision check. Without an API key, reports are flagged for manual review."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return True, "Civic issue submitted. AI verification is not configured; authority review is required.", "Needs Manual Review"
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        prompt = (
            "Inspect this image for a visible civic infrastructure issue such as pothole, "
            "garbage dumping, water leakage, drainage, or broken streetlight. "
            "If it is clearly unsafe, abusive, or unrelated, set safe=false. "
            "Return concise JSON with keys safe (boolean), category (string), note (string)."
        )
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        import json
        result = json.loads(response.text)
        return bool(result.get("safe", True)), str(result.get("note", "AI inspection completed.")), str(result.get("category", "Other Civic Issue"))
    except Exception as exc:
        return True, f"AI verification unavailable; sent for authority review ({type(exc).__name__}).", "Needs Manual Review"

init_db()

# ---------- Styling ----------
st.markdown("""
<style>
.block-container {padding-top: 1.6rem; max-width: 1400px;}
.hero {padding: 25px 28px; border-radius: 18px; color: white;
       background: linear-gradient(120deg,#0f2747,#176b87);}
.hero h1 {margin:0;font-size:2.1rem;}
.hero p {margin:8px 0 0 0;color:#e2f2f7;}
.kpi-card {background:var(--secondary-background-color);padding:18px;border-radius:13px;
           border-top:4px solid #0D9488;min-height:112px;}
.kpi-label {font-size:.85rem;opacity:.8;}
.kpi-value {font-size:1.8rem;font-weight:750;margin:5px 0;}
.kpi-sub {font-size:.78rem;opacity:.7;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>🏙️ CivixLens</h1>
  <p>Smart Civic Issue Reporting & Resolution Platform</p>
</div>
""", unsafe_allow_html=True)

# ---------- Session / Authentication ----------
if "user" not in st.session_state:
    st.session_state.user = None
if "role" not in st.session_state:
    st.session_state.role = None

def logout():
    st.session_state.user = None
    st.session_state.role = None
    st.rerun()

if not st.session_state.user:
    login_tab, signup_tab = st.tabs(["🔐 Login", "📝 Create Citizen Account"])
    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state.user = user["username"]
                st.session_state.role = user["role"]
                st.rerun()
            else:
                st.error("Invalid username or password.")
        st.caption("Admin login is created when CIVIXLENS_ADMIN_PASSWORD is configured.")
    with signup_tab:
        with st.form("signup_form"):
            new_username = st.text_input("Choose a username")
            new_password = st.text_input("Choose a password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            create = st.form_submit_button("Create Account", use_container_width=True)
        if create:
            if len(new_username.strip()) < 3:
                st.error("Username must contain at least 3 characters.")
            elif len(new_password) < 8:
                st.error("Use a password with at least 8 characters.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            elif register_user(new_username, new_password):
                st.success("Account created. Please log in.")
            else:
                st.error("That username is already taken.")
    st.stop()

# ---------- Citizen Dashboard ----------
if st.session_state.role == "Citizen":
    top_l, top_r = st.columns([4, 1])
    with top_l:
        st.subheader(f"Welcome, {st.session_state.user} 👋")
        st.caption("Report local civic problems and follow their resolution.")
    with top_r:
        if st.button("🚪 Logout", use_container_width=True):
            logout()

    with get_db_connection() as conn:
        my_records = conn.execute(
            "SELECT * FROM complaints WHERE user_id=? ORDER BY id DESC",
            (st.session_state.user,)
        ).fetchall()
    my_total = len(my_records)
    my_pending = sum(r["status"] in ("Pending Approval", "In Progress") for r in my_records)
    my_resolved = sum(r["status"] == "Resolved" for r in my_records)
    my_points = sum(r["points_awarded"] or 0 for r in my_records)

    k1, k2, k3, k4 = st.columns(4)
    for col, label, value, sub, border in [
        (k1, "Total Submitted", my_total, "All reports submitted", "#0D9488"),
        (k2, "Active / Pending", my_pending, "Under authority review", "#D97706"),
        (k3, "Resolved Issues", my_resolved, "Verified and fixed", "#16A34A"),
        (k4, "Reward Points", f"{my_points} ⭐", "+50 points per standard resolution", "#2563EB"),
    ]:
        with col:
            st.markdown(f"""<div class="kpi-card" style="border-top-color:{border}">
            <div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>
            <div class="kpi-sub">{sub}</div></div>""", unsafe_allow_html=True)

    report_tab, history_tab = st.tabs(["📸 Report a New Civic Issue", f"📋 My Submitted Reports ({my_total})"])
    with report_tab:
        with st.container(border=True):
            st.markdown("### Submit a Civic Issue")
            st.caption("Add the location, describe the problem, and attach a photo for review.")
            with st.form("report_form"):
                zone = st.selectbox("Municipal Zone / Area", [
                    "Zone 1 — Central Civic Ward",
                    "Zone 2 — University & Institutional Road",
                    "Zone 3 — Residential Sector A/B",
                    "Zone 4 — Industrial & Highway Corridor",
                    "Zone 5 — Commercial Market District",
                    "Other / Custom Location"
                ])
                location = st.text_input("Specific Landmark / Street Address *",
                                         placeholder="e.g., Near Gate No. 2, Main Crossing")
                description = st.text_area("Brief Issue Description *",
                                           placeholder="Describe the severity, hazard, or duration...")
                photo = st.file_uploader("Upload Photo Evidence (JPG, JPEG, PNG) *",
                                         type=["jpg", "jpeg", "png"])
                submit = st.form_submit_button("🚀 Verify & Submit Complaint", use_container_width=True)
            if photo:
                st.image(photo, caption="Uploaded photographic evidence", width=420)
            if submit:
                if not photo or not location.strip() or not description.strip():
                    st.error("Please provide a photo, location, and issue description.")
                else:
                    image_bytes = photo.getvalue()
                    digest = hashlib.sha256(image_bytes).hexdigest()
                    with get_db_connection() as conn:
                        duplicate = conn.execute(
                            "SELECT id, category, status FROM complaints WHERE image_hash=?", (digest,)
                        ).fetchone()
                    if duplicate:
                        st.warning(f"This exact image was already submitted as Report #{duplicate['id']} "
                                   f"({duplicate['category']} — {duplicate['status']}).")
                    else:
                        with st.spinner("Checking image and registering your report..."):
                            safe, ai_note, category = classify_image_with_gemini(image_bytes)
                        if not safe:
                            st.error(f"Submission blocked by the image safety check: {ai_note}")
                        else:
                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            with get_db_connection() as conn:
                                cur = conn.execute("""
                                    INSERT INTO complaints
                                    (user_id,timestamp,category,location,description,status,points_awarded,
                                     image_blob,image_hash,ai_notes)
                                    VALUES (?,?,?,?,?,'Pending Approval',0,?,?,?)
                                """, (st.session_state.user, timestamp, category,
                                      f"{zone} — {location.strip()}", description.strip(),
                                      image_bytes, digest, ai_note))
                                report_id = cur.lastrowid
                            st.success(f"Report #{report_id} submitted successfully!")
                            st.info(f"Category: {category}  \nAI note: {ai_note}")
                            st.rerun()

    with history_tab:
        if not my_records:
            st.info("You have not submitted any civic complaints yet.")
        for rec in my_records:
            with st.container(border=True):
                left, right = st.columns([3, 1])
                with left:
                    st.markdown(f"#### Report #{rec['id']} — {rec['category']} {status_badge(rec['status'])}",
                                unsafe_allow_html=True)
                    st.write(f"**Submitted:** {rec['timestamp']}  |  **Points:** {rec['points_awarded']}")
                    st.write(f"**Location:** {rec['location']}")
                    st.write(f"**Description:** {rec['description']}")
                    if rec["ai_notes"]:
                        st.caption(f"AI review: {rec['ai_notes']}")
                with right:
                    st.image(rec["image_blob"], use_container_width=True)

# ---------- Municipal Admin Dashboard ----------
elif st.session_state.role == "Admin":
    left, right = st.columns([4, 1])
    with left:
        st.subheader("🏛️ Municipal Authority Dashboard")
        st.caption("Review reports, update resolution status, and award contributor points.")
    with right:
        if st.button("🚪 Logout Admin", use_container_width=True):
            logout()

    with get_db_connection() as conn:
        all_records = conn.execute("SELECT * FROM complaints ORDER BY id DESC").fetchall()

    total = len(all_records)
    pending = sum(r["status"] == "Pending Approval" for r in all_records)
    progress = sum(r["status"] == "In Progress" for r in all_records)
    resolved = sum(r["status"] == "Resolved" for r in all_records)
    rejected = sum(r["status"] == "Rejected" for r in all_records)
    points = sum(r["points_awarded"] or 0 for r in all_records)

    metrics = st.columns(5)
    metric_data = [
        ("Total Complaints", total, "All submitted reports", "#0D9488"),
        ("Pending Approval", pending, "Awaiting action", "#D97706"),
        ("In Progress", progress, "Field team dispatched", "#2563EB"),
        ("Resolved", resolved, "Completed reports", "#16A34A"),
        ("Points Awarded", points, f"{rejected} rejected", "#0D9488")
    ]
    for col, (label, value, sub, color) in zip(metrics, metric_data):
        with col:
            st.markdown(f"""<div class="kpi-card" style="border-top-color:{color}">
            <div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>
            <div class="kpi-sub">{sub}</div></div>""", unsafe_allow_html=True)

    queue_tab, analytics_tab = st.tabs(["📋 Complaint Review & Resolution Queue", "📊 Municipal Analytics & Export"])
    with queue_tab:
        f1, f2, f3 = st.columns([1, 1, 2])
        with f1:
            status_filter = st.selectbox("Filter by Status",
                ["All", "Pending Approval", "In Progress", "Resolved", "Rejected"])
        with f2:
            categories = sorted({r["category"] for r in all_records if r["category"]})
            category_filter = st.selectbox("Filter by Category", ["All Categories"] + categories)
        with f3:
            search = st.text_input("Search by ID, username, or location")
        filtered = list(all_records)
        if status_filter != "All":
            filtered = [r for r in filtered if r["status"] == status_filter]
        if category_filter != "All Categories":
            filtered = [r for r in filtered if r["category"] == category_filter]
        if search.strip():
            term = search.strip().lower()
            filtered = [r for r in filtered if term in str(r["id"]).lower()
                        or term in (r["user_id"] or "").lower()
                        or term in (r["location"] or "").lower()
                        or term in (r["description"] or "").lower()]
        if not filtered:
            st.info("No complaints match the selected filters.")
        for rec in filtered:
            with st.expander(f"Report #{rec['id']} | {rec['category']} | {rec['status']} | Citizen: {rec['user_id']}"):
                info, photo_col = st.columns([2, 1])
                with info:
                    st.markdown(f"### {rec['category']} — Report #{rec['id']}")
                    st.markdown(status_badge(rec["status"]), unsafe_allow_html=True)
                    st.write(f"**Citizen:** {rec['user_id']}  |  **Logged:** {rec['timestamp']}")
                    st.write(f"**Location:** {rec['location']}")
                    st.write(f"**Description:** {rec['description']}")
                    st.write(f"**AI note:** {rec['ai_notes']}")
                    st.write(f"**Current points:** {rec['points_awarded']}")
                    pts = st.selectbox("Reward points", [0, 25, 50, 75, 100, 150, 200],
                                       index=2 if rec["points_awarded"] == 0 else
                                       ([0,25,50,75,100,150,200].index(rec["points_awarded"])
                                        if rec["points_awarded"] in [0,25,50,75,100,150,200] else 2),
                                       key=f"points_{rec['id']}")
                    b1, b2, b3, b4 = st.columns(4)
                    if b1.button("✅ Resolve", key=f"resolve_{rec['id']}", use_container_width=True):
                        with get_db_connection() as conn:
                            conn.execute("UPDATE complaints SET status='Resolved', points_awarded=? WHERE id=?",
                                         (pts, rec["id"]))
                        st.rerun()
                    if b2.button("🚧 Under Work", key=f"work_{rec['id']}", use_container_width=True):
                        with get_db_connection() as conn:
                            conn.execute("UPDATE complaints SET status='In Progress' WHERE id=?", (rec["id"],))
                        st.rerun()
                    if b3.button("❌ Reject", key=f"reject_{rec['id']}", use_container_width=True):
                        with get_db_connection() as conn:
                            conn.execute("UPDATE complaints SET status='Rejected', points_awarded=0 WHERE id=?",
                                         (rec["id"],))
                        st.rerun()
                    if b4.button("🗑️ Delete", key=f"delete_{rec['id']}", use_container_width=True):
                        with get_db_connection() as conn:
                            conn.execute("DELETE FROM complaints WHERE id=?", (rec["id"],))
                        st.rerun()
                with photo_col:
                    st.image(rec["image_blob"], caption=f"Report #{rec['id']}", use_container_width=True)

    with analytics_tab:
        st.write("### Complaint Summary")
        st.dataframe([{
            "Report ID": r["id"], "Citizen": r["user_id"], "Category": r["category"],
            "Status": r["status"], "Location": r["location"], "Points": r["points_awarded"],
            "Submitted": r["timestamp"]
        } for r in all_records], use_container_width=True, hide_index=True)
        if all_records:
            import csv
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=[
                "Report ID", "Citizen", "Category", "Status", "Location", "Points", "Submitted"
            ])
            writer.writeheader()
            for r in all_records:
                writer.writerow({
                    "Report ID": r["id"], "Citizen": r["user_id"], "Category": r["category"],
                    "Status": r["status"], "Location": r["location"],
                    "Points": r["points_awarded"], "Submitted": r["timestamp"]
                })
            st.download_button("⬇️ Download CSV Report", output.getvalue(),
                               file_name="civixlens_complaints.csv", mime="text/csv")
