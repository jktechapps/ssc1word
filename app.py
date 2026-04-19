import streamlit as st
import json
from datetime import datetime, date
from libsql_client import create_client_sync

st.set_page_config(page_title="SSC CGL OWS Master", page_icon="📚", layout="centered")


# ── DB ────────────────────────────────────────────────────────────────────────

def get_client():
    return create_client_sync(
        url=st.secrets["TURSO_URL"],
        auth_token=st.secrets["TURSO_TOKEN"]
    )


def check_user(email: str):
    """
    Returns dict with status:
      'ok'      → valid paid user, access granted
      'expired' → was a user, subscription ended
      'not_found' → email not in DB
    """
    try:
        client = get_client()
        res = client.execute(
            "SELECT email, paid_on, expiry FROM paid_users WHERE email = ?",
            (email.strip().lower(),)
        )
        client.close()
        if not res.rows:
            return {"status": "not_found"}
        row = res.rows[0]
        expiry = datetime.strptime(row[2], "%Y-%m-%d").date()
        if date.today() > expiry:
            return {"status": "expired", "expiry": row[2]}
        return {"status": "ok", "email": row[0], "expiry": row[2]}
    except Exception as e:
        st.error(f"DB error: {e}")
        return {"status": "not_found"}


def get_random_question():
    try:
        client = get_client()
        res = client.execute(
            "SELECT meaning, options, answer, hindi, difficulty "
            "FROM ows_master ORDER BY RANDOM() LIMIT 1"
        )
        client.close()
        if res.rows:
            row = res.rows[0]
            try:
                opts = json.loads(row[1])
            except Exception:
                opts = row[1].split(", ")
            return {
                "q":          row[0],
                "opts":       opts,
                "a":          row[2],
                "hindi":      row[3],
                "difficulty": row[4],
            }
    except Exception as e:
        st.error(f"DB error: {e}")
    return None


# ── Admin helpers ─────────────────────────────────────────────────────────────

def add_user(email, paid_on_str):
    """Adds user with 15-month expiry from paid_on date."""
    from datetime import timedelta
    paid_on = datetime.strptime(paid_on_str, "%Y-%m-%d").date()
    # 15 months = ~456 days (no monthsadd in stdlib, so we do it properly)
    month = paid_on.month - 1 + 15
    year  = paid_on.year + month // 12
    month = month % 12 + 1
    try:
        expiry = paid_on.replace(year=year, month=month)
    except ValueError:
        # handles edge case like Jan 31 + 15 months
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        expiry = paid_on.replace(year=year, month=month, day=last_day)

    client = get_client()
    client.execute(
        "INSERT OR REPLACE INTO paid_users (email, paid_on, expiry) VALUES (?, ?, ?)",
        (email.strip().lower(), paid_on_str, expiry.strftime("%Y-%m-%d"))
    )
    client.close()
    return expiry.strftime("%Y-%m-%d")


# ── UI constants ──────────────────────────────────────────────────────────────

DIFFICULTY_BADGE = {
    "easy":   "🟢 Easy",
    "medium": "🟡 Medium",
    "hard":   "🔴 Hard",
}

UPI_ID    = "your-upi-id@bank"        # ← update this
FORM_LINK = "https://forms.gle/xxxx"  # ← update this


# ── Screens ───────────────────────────────────────────────────────────────────

def show_login():
    st.title("SSC CGL OWS Master 📚")
    st.markdown("Practice 1,173 One Word Substitution questions for SSC CGL Tier 1.")
    st.markdown("---")

    st.markdown("### 🔐 Enter your registered email")
    email = st.text_input("Email address", placeholder="yourname@gmail.com")

    if st.button("▶️ Start Practice", use_container_width=True):
        if not email.strip():
            st.warning("Please enter your email.")
            return

        result = check_user(email)

        if result["status"] == "ok":
            st.session_state.user = result
            st.rerun()

        elif result["status"] == "expired":
            st.error(f"⏰ Your access expired on **{result['expiry']}**.")
            st.info("Pay ₹99 again to renew for another 15 months.")
            st.markdown(f"UPI: `{UPI_ID}`  |  [Fill renewal form]({FORM_LINK})")

        else:
            st.error("❌ Email not registered. Please complete payment first.")
            st.markdown(
                f"**How to get access (₹99 · 15 months):**\n\n"
                f"1. Pay ₹99 to UPI: `{UPI_ID}`\n"
                f"2. [Fill this form]({FORM_LINK}) with your email + payment screenshot\n"
                f"3. Access activated within a few hours"
            )


def show_quiz():
    user = st.session_state.user

    st.title("SSC CGL OWS Master 📚")

    # Show expiry as a soft reminder
    expiry = datetime.strptime(user["expiry"], "%Y-%m-%d").date()
    days_left = (expiry - date.today()).days
    if days_left <= 30:
        st.warning(f"⚠️ Your access expires in **{days_left} days** ({user['expiry']}). Renew early to avoid interruption.")
    else:
        st.caption(f"Access valid until **{user['expiry']}** · {days_left} days left")

    if st.sidebar.button("🚪 Logout"):
        st.session_state.clear()
        st.rerun()

    # Load question
    if "current_q" not in st.session_state:
        q_data = get_random_question()
        if q_data is None:
            st.error("Could not load a question. Try refreshing.")
            return
        st.session_state.current_q = q_data
        st.session_state.answered  = False
        st.session_state.selected  = None

    q = st.session_state.current_q

    badge = DIFFICULTY_BADGE.get((q["difficulty"] or "").lower(), "")
    if badge:
        st.caption(badge)

    st.markdown(f"### {q['q']}")
    st.markdown("---")

    # Phase 1 — options
    if not st.session_state.answered:
        for opt in q['opts']:
            if st.button(opt, use_container_width=True, key=f"opt_{opt}"):
                st.session_state.selected = opt
                st.session_state.answered = True
                st.rerun()

    # Phase 2 — result
    else:
        selected = st.session_state.selected
        correct  = q['a']

        for opt in q['opts']:
            if opt == correct:
                st.success(f"✅ {opt}")
            elif opt == selected:
                st.error(f"❌ {opt}  ← your answer")
            else:
                st.write(f"　{opt}")

        st.markdown("---")
        if selected == correct:
            st.success("🎉 Correct!")
        else:
            st.error(f"Correct answer: **{correct}**")

        if q.get("hindi"):
            st.info(f"🇮🇳 Hindi: {q['hindi']}")

        if st.button("Next Question ➡️", use_container_width=True):
            for key in ["current_q", "answered", "selected"]:
                st.session_state.pop(key, None)
            st.rerun()


def show_admin():
    st.title("🛠️ Admin Panel")

    st.markdown("#### ➕ Register a new paid user")
    email   = st.text_input("Email")
    paid_on = st.text_input("Payment date (YYYY-MM-DD)", value=date.today().strftime("%Y-%m-%d"))

    if st.button("Add User", use_container_width=True):
        if not email.strip():
            st.warning("Email required.")
        else:
            try:
                expiry = add_user(email, paid_on)
                st.success(f"✅ {email} added. Access until **{expiry}**.")
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")
    st.markdown("#### 👥 All users")

    try:
        client = get_client()
        res = client.execute(
            "SELECT email, paid_on, expiry FROM paid_users ORDER BY expiry DESC"
        )
        client.close()
        if res.rows:
            for row in res.rows:
                expiry = datetime.strptime(row[2], "%Y-%m-%d").date()
                status = "✅ Active" if date.today() <= expiry else "❌ Expired"
                st.write(f"{status} · **{row[0]}** · paid {row[1]} · expires {row[2]}")
        else:
            st.info("No users yet.")
    except Exception as e:
        st.error(f"Error: {e}")

    if st.button("🚪 Exit Admin"):
        st.session_state.pop("admin", None)
        st.rerun()


# ── Router ────────────────────────────────────────────────────────────────────

if st.query_params.get("admin") == "1" or st.session_state.get("admin"):
    if not st.session_state.get("admin"):
        pwd = st.text_input("Admin password", type="password")
        if st.button("Login"):
            if pwd == st.secrets.get("ADMIN_PASSWORD", "changeme"):
                st.session_state.admin = True
                st.rerun()
            else:
                st.error("Wrong password.")
    else:
        show_admin()

elif "user" in st.session_state:
    show_quiz()

else:
    show_login()
