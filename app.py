import streamlit as st
import json
import os
from datetime import date, timedelta
import pandas as pd

st.set_page_config(
    page_title="Escala de Trabalho",
    page_icon="📅",
    layout="wide",
)

DATA_DIR = "data"
EMPLOYEES_FILE = os.path.join(DATA_DIR, "employees.json")
SCHEDULE_FILE = os.path.join(DATA_DIR, "schedule.json")

os.makedirs(DATA_DIR, exist_ok=True)

ACTIVITY_COLORS = {
    "Fila":     "#c8e6c9",
    "Chat":     "#bbdefb",
    "Backlog":  "#ffcdd2",
    "Almoço":   "#fff9c4",
    "Reunião":  "#e1bee7",
    "Atestado": "#eceff1",
    "Férias":   "#e0e0e0",
    "Fila/Chat":"#b2dfdb",
}

BLOCKS = [
    ("09:00", "10:30"),
    ("10:30", "12:00"),
    ("12:00", "13:30"),
    ("13:30", "15:00"),
    ("15:00", "16:30"),
    ("16:30", "18:00"),
    ("18:00", "18:30"),
]
BLOCK_STARTS = [b[0] for b in BLOCKS]


def load_employees():
    if not os.path.exists(EMPLOYEES_FILE):
        return []
    with open(EMPLOYEES_FILE) as f:
        return json.load(f)


def load_schedule():
    if not os.path.exists(SCHEDULE_FILE):
        return {}
    with open(SCHEDULE_FILE) as f:
        return json.load(f)


employees = load_employees()
schedule = load_schedule()
emp_map = {e["id"]: e for e in employees}

today = date.today()
today_str = today.isoformat()
today_data = schedule.get(today_str, {})

active_emps = [e for e in employees if e.get("status") == "ativo"]
ferias_emps = [e for e in employees if e.get("status") == "férias"]

st.title("📅 Dashboard — Escala de Trabalho")
st.caption(f"Hoje: {today.strftime('%A, %d de %B de %Y').capitalize()}")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Analistas ativos", len(active_emps))
with col2:
    st.metric("Em férias", len(ferias_emps))
with col3:
    dias_com_escala = sum(1 for d, v in schedule.items() if v)
    st.metric("Dias com escala", dias_com_escala)
with col4:
    coringa = next((e for e in employees if e.get("special") == "coringa"), None)
    st.metric("Coringa", coringa["name"].split()[0] if coringa else "—")

st.divider()

col_left, col_right = st.columns([1.5, 1])

with col_left:
    st.subheader(f"Escala de hoje — {today.strftime('%d/%m/%Y')}")

    if not today_data:
        st.info("Nenhuma escala gerada para hoje. Acesse a página **📅 Escala** e clique em **Auto-gerar**.")
    else:
        rows = []
        for block_start, block_end in BLOCKS:
            block = block_start
            label = f"{block_start}–{block_end}"
            acts = today_data.get(block, {})
            row = {"Bloco": label}
            for emp in sorted(active_emps, key=lambda e: e["id"]):
                act = acts.get(str(emp["id"]), "—")
                row[emp["name"].split()[0]] = act
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with col_right:
    st.subheader("Status dos analistas hoje")

    if today_data:
        # Determine each person's activity in the current/closest block
        from datetime import datetime
        now_str = datetime.now().strftime("%H:%M")
        current_block = BLOCK_STARTS[0]
        for b in BLOCK_STARTS:
            if b <= now_str:
                current_block = b

        block_now = today_data.get(current_block, {})
        for emp in employees:
            act = block_now.get(str(emp["id"]), "")
            color = emp.get("color", "#999")
            bg_act = ACTIVITY_COLORS.get(act, "#f5f5f5")
            badge = " ⭐" if emp.get("special") == "coringa" else ""
            ferias_badge = " 🏖" if emp.get("status") == "férias" else ""
            st.markdown(
                f'<div style="border-left:4px solid {color};padding:6px 12px;border-radius:4px;'
                f'background:#fafafa;margin-bottom:6px;display:flex;justify-content:space-between;">'
                f'<span><b>{emp["name"]}</b>{badge}{ferias_badge}</span>'
                f'<span style="background:{bg_act};padding:2px 10px;border-radius:12px;font-size:13px;">'
                f'{act if act else "—"}</span></div>',
                unsafe_allow_html=True,
            )
    else:
        for emp in employees:
            color = emp.get("color", "#999")
            status = "🏖 Férias" if emp.get("status") == "férias" else "Sem escala"
            badge = " ⭐" if emp.get("special") == "coringa" else ""
            st.markdown(
                f'<div style="border-left:4px solid {color};padding:6px 12px;border-radius:4px;'
                f'background:#fafafa;margin-bottom:6px;display:flex;justify-content:space-between;">'
                f'<span><b>{emp["name"]}</b>{badge}</span>'
                f'<span style="color:#999;font-size:13px;">{status}</span></div>',
                unsafe_allow_html=True,
            )

st.divider()

st.subheader("Distribuição de atividades — semana atual")

week_start = today - timedelta(days=today.weekday())
week_end = week_start + timedelta(days=6)
days_pt = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

act_totals = {}
for i in range(7):
    d = week_start + timedelta(days=i)
    d_data = schedule.get(d.isoformat(), {})
    for block_data in d_data.values():
        for act in block_data.values():
            if act and act not in ("Férias", ""):
                act_totals[act] = act_totals.get(act, 0) + 1

if act_totals:
    df_acts = pd.DataFrame(list(act_totals.items()), columns=["Atividade", "Blocos"])
    df_acts = df_acts.sort_values("Blocos", ascending=False)
    st.bar_chart(df_acts.set_index("Atividade"))
else:
    st.info("Nenhuma escala registrada para esta semana. Acesse a página **Escala** para gerar.")

if ferias_emps:
    st.divider()
    st.subheader("🏖 Em férias")
    cols = st.columns(len(ferias_emps))
    for i, emp in enumerate(ferias_emps):
        with cols[i]:
            st.markdown(
                f'<div style="border-left:4px solid {emp.get("color","#999")};'
                f'padding:8px 12px;border-radius:4px;background:#f5f5f5;">'
                f'<b>{emp["name"]}</b><br><span style="color:#888;font-size:12px;">{emp["role"]}</span></div>',
                unsafe_allow_html=True,
            )

st.caption("Use o menu lateral para gerenciar a escala, analistas e regras.")
