import streamlit as st
import json
from datetime import datetime, date
from libsql_client import create_client_sync

st.set_page_config(page_title="SSC CGL OWS Master", page_icon="📚", layout="centered")

# 30 fixed demo question IDs — same for every demo user, always
# Spread evenly across all 1173 questions so no topic is over-represented
DEMO_IDS = (1,40,79,118,157,196,235,274,313,352,391,430,469,508,547,
            586,625,664,703,742,781,820,859,898,937,976,1015,1054,1093,1132)

UPI_ID    = "your-upi-id@bank"        # ← update this
FORM_LINK = "https://forms.gle/xxxx"  # ← update this

DIFFICULTY_BADGE = {
    "easy":   "🟢 Easy",
    "medium": "🟡 Medium",
    "hard":   "🔴 Hard",
}


# ── DB ────────────────────────────────────────────────────────────────────────

def get_client():
    return create_client_sync(
        url=st.secrets["TURSO_URL"],
        auth_token=st.secrets["TURSO_TOKEN"]
    )


def check_user(email: str):
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


def get_question(paid: bool):
    """
    Paid users  → fully random from all 1173 questions
    Demo users  → random from the fixed 30 DEMO_IDS only
    """
    try:
        client = get_client()
        if paid:
            res = client.execute(
                "SELECT id, meaning, options, answer, hindi, difficulty "
                "FROM ows_master ORDER BY RANDOM() LIMIT 1"
            )
        else:
            # Pick one random ID from the fixed demo set each time
            import random
            demo_id = random.choice(DEMO_IDS)
            res = client.execute(
                "SELECT id, meaning, options, answer, hindi, difficulty "
                "FROM ows_master WHERE id = ?",
                (demo_id,)
            )
        client.close()
        if res.rows:
            row = res.rows[0]
            try:
                opts = json.loads(row[2])
            except Exception:
                opts = row[2].split(", ")
            return {
                "id":         row[0],
                "q":          row[1],
                "opts":       opts,
                "a":          row[3],
                "hindi":      row[4],
                "difficulty": row[5],
            }
    except Exception as e:
        st.error(f"DB error: {e}")
    return None


def add_user(email, paid_on_str):
    paid_on = datetime.strptime(paid_on_str, "%Y-%m-%d").date()
    month = paid_on.month - 1 + 15
    year  = paid_on.year + month // 12
    month = month % 12 + 1
    try:
        expiry = paid_on.replace(year=year, month=month)
    except ValueError:
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


# ── Screens ───────────────────────────────────────────────────────────────────

def show_login():
    st.title("SSC CGL OWS Master 📚")
    st.markdown("Master **One Word Substitution** for SSC CGL Tier 1 — 1,173 questions with Hindi meanings.")
    st.markdown("---")

    tab1, tab2 = st.tabs(["🔐 Paid Access", "🆓 Try Free Demo"])

    with tab1:
        st.markdown("#### Enter your registered email")
        email = st.text_input("Email", placeholder="yourname@gmail.com", key="paid_email")
        if st.button("▶️ Start Practice", use_container_width=True, key="paid_btn"):
            if not email.strip():
                st.warning("Please enter your email.")
            else:
                result = check_user(email)
                if result["status"] == "ok":
                    st.session_state.user = result
                    st.session_state.is_demo = False
                    st.rerun()
                elif result["status"] == "expired":
                    st.error(f"⏰ Your access expired on **{result['expiry']}**.")
                    st.info(f"Pay ₹99 to UPI `{UPI_ID}` and [fill this form]({FORM_LINK}) to renew.")
                else:
                    st.error("❌ Email not registered.")
                    st.markdown(
                        f"**Get full access — ₹99 · 15 months · 1,173 questions**\n\n"
                        f"1. Pay ₹99 to UPI: `{UPI_ID}`\n"
                        f"2. [Fill this form]({FORM_LINK}) with email + payment screenshot\n"
                        f"3. Access activated within a few hours"
                    )

    with tab2:
        st.markdown("#### Try 30 sample questions — no payment needed")
        st.caption("⚠️ Demo shows the same 30 questions to everyone. Pay ₹99 to unlock all 1,173.")
        if st.button("▶️ Start Free Demo", use_container_width=True, key="demo_btn"):
            st.session_state.user = {"email": "demo", "expiry": None}
            st.session_state.is_demo = True
            st.session_state.demo_count = 0
            st.rerun()


def show_quiz():
    is_demo = st.session_state.get("is_demo", False)
    user    = st.session_state.user

    st.title("SSC CGL OWS Master 📚")

    if is_demo:
        done = st.session_state.get("demo_count", 0)
        remaining = len(DEMO_IDS) - done
        st.info(f"🆓 Demo mode — **{remaining} questions left** out of {len(DEMO_IDS)}. "
                f"[Pay ₹99 to unlock all 1,173]({FORM_LINK})")
    else:
        expiry = datetime.strptime(user["expiry"], "%Y-%m-%d").date()
        days_left = (expiry - date.today()).days
        if days_left <= 30:
            st.warning(f"⚠️ Access expires in **{days_left} days**. Renew to avoid interruption.")
        else:
            st.caption(f"✅ Full access · {days_left} days remaining")

    if st.sidebar.button("🚪 Exit" if is_demo else "🚪 Logout"):
        st.session_state.clear()
        st.rerun()

    # Load question
    if "current_q" not in st.session_state:
        # Demo exhausted?
        if is_demo and st.session_state.get("demo_count", 0) >= len(DEMO_IDS):
            st.success("🎉 You've completed the demo!")
            st.markdown(
                f"**Enjoyed it? Get all 1,173 questions for just ₹99 (15 months access)**\n\n"
                f"Pay to UPI: `{UPI_ID}` and [fill this form]({FORM_LINK})"
            )
            if st.button("🔁 Restart Demo"):
                st.session_state.demo_count = 0
                st.rerun()
            return

        q_data = get_question(paid=not is_demo)
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

        # Upsell nudge after every 10th demo question
        if is_demo and st.session_state.get("demo_count", 0) % 10 == 9:
            st.warning(f"💡 Like this? Get all 1,173 questions for ₹99 → UPI: `{UPI_ID}`")

        next_label = "Next Question ➡️"
        if st.button(next_label, use_container_width=True):
            if is_demo:
                st.session_state.demo_count = st.session_state.get("demo_count", 0) + 1
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
                status = "✅" if date.today() <= expiry else "❌ Expired"
                st.write(f"{status} · **{row[0]}** · paid {row[1]} · expires {row[2]}")
        else:
            st.info("No paid users yet.")
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

