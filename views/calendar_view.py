import calendar as cal, streamlit as st
from datetime import date, timedelta
from database import q, ex, owned
from services import exports
import ui

def reminders(uid_):
    today = date.today()
    out = []
    for t in q("SELECT * FROM tasks WHERE user_id=? AND done=0", (uid_,)):
        d = date.fromisoformat(t["due_date"])
        if d < today: out.append(("overdue", t))
        elif (d - today).days <= (t["reminder_days"] or 0): out.append(("due soon", t))
    return out

def page():
    ui.header("Deadline calendar", "In-app reminders only. No email or push notifications are sent.")
    i = ui.uid(); today = date.today()
    t1, t2, t3 = st.tabs(["Calendar", "Add / edit", "Overdue & upcoming"])
    with t1:
        c = st.columns(3); view = c[0].radio("View", ["Month", "Week"], horizontal=True)
        y = c[1].number_input("Year", 2020, 2100, st.session_state.get("cy", today.year)); mth = c[2].selectbox("Month", range(1, 13), index=st.session_state.get("cm", today.month) - 1, format_func=lambda m: cal.month_name[m])
        kind = st.multiselect("Event types", ["task", "deadline", "event"], default=["task", "deadline", "event"]); mid = ui.matter_picker("Filter by matter", key="calm")
        evs = [e for e in q("SELECT * FROM tasks WHERE user_id=?", (i,)) if e["kind"] in kind and (not mid or e["matter_id"] == mid)]
        by = {}
        for e in evs: by.setdefault(e["due_date"], []).append(e)
        if view == "Month":
            hdr = st.columns(7)
            for k, n in enumerate(cal.day_abbr): hdr[k].markdown(f"**{n}**")
            for wk in cal.Calendar().monthdatescalendar(int(y), mth):
                cols = st.columns(7)
                for k, d in enumerate(wk):
                    items = by.get(d.isoformat(), []) if d.month == mth else []
                    cols[k].markdown(f"{'**' + str(d.day) + '**' if d == today else d.day}" if d.month == mth else "")
                    for e in items: cols[k].caption(("✅ " if e["done"] else "• ") + e["title"][:22])
        else:
            start = today - timedelta(days=today.weekday())
            for n in range(7):
                d = start + timedelta(days=n); st.markdown(f"**{d.strftime('%A %d %b')}**")
                for e in by.get(d.isoformat(), []): st.write(("✅ " if e["done"] else "• ") + e["title"] + f" ({e['kind']})")
        st.download_button("Export calendar (.ics)", exports.make_ics(evs), file_name="legal_s_india.ics")
    with t2:
        with st.form("ne"):
            tt = st.text_input("Title"); k = st.selectbox("Type", ["task", "deadline", "event"]); dd = st.date_input("Date", today); ds = st.text_area("Description"); rd = st.number_input("Remind days before", 0, 60, 1)
            mm = ui.matter_picker("Matter", key="nem")
            if st.form_submit_button("Add") and tt.strip():
                if mm and not owned("matters", mm, i): st.error("Invalid matter")
                else: ex("INSERT INTO tasks(user_id,matter_id,title,kind,due_date,description,reminder_days) VALUES(?,?,?,?,?,?,?)", (i, mm, tt.strip(), k, dd.isoformat(), ds, int(rd))); st.rerun()
        st.caption("Enter legal dates yourself. This app does not compute statutory limitation periods.")
        for e in q("SELECT * FROM tasks WHERE user_id=? ORDER BY due_date", (i,)):
            with st.expander(f"{e['due_date']} - {e['title']}"):
                nd = st.date_input("Move to", date.fromisoformat(e["due_date"]), key=f"nd{e['id']}"); c = st.columns(3)
                if c[0].button("Save date", key=f"sd{e['id']}"): ex("UPDATE tasks SET due_date=? WHERE id=? AND user_id=?", (nd.isoformat(), e["id"], i)); st.rerun()
                if c[1].button("Toggle done", key=f"td{e['id']}"): ex("UPDATE tasks SET done=1-done WHERE id=? AND user_id=?", (e["id"], i)); st.rerun()
                if c[2].button("Delete", key=f"dl{e['id']}"): ex("DELETE FROM tasks WHERE id=? AND user_id=?", (e["id"], i)); st.rerun()
    with t3:
        od = q("SELECT * FROM tasks WHERE user_id=? AND done=0 AND due_date<? ORDER BY due_date", (i, today.isoformat())); up = q("SELECT * FROM tasks WHERE user_id=? AND done=0 AND due_date>=? ORDER BY due_date LIMIT 20", (i, today.isoformat()))
        st.markdown("**Overdue**"); [st.write(f"⚠️ {e['due_date']} - {e['title']}") for e in od] or st.caption("None")
        st.markdown("**Upcoming**"); [st.write(f"{e['due_date']} - {e['title']}") for e in up] or st.caption("None")
    ui.footer()
