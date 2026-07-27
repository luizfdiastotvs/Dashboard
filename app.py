# -*- coding: utf-8 -*-
"""
Dashboard de Escala Automática (Streamlit)
===========================================
Grade em blocos de 1h30 (subdivididos em linhas de 30 min), regras de
alocação com Coringa dinâmico, categorias protegidas, rotação diária por
seed de data, salvamento de histórico e exportação/compartilhamento em HTML.
"""

import streamlit as st
import random
import json
import os
from datetime import date, datetime

# ---------------------------------------------------------------------------
# Configuração geral
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Escala Automática", layout="wide")

HIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historico_escalas.json")

# Blocos de 1h30 (rowspan = 3 sub-linhas de 30 min)
BLOCOS = [
    ("09:00", "10:30"),
    ("10:30", "12:00"),
    ("12:00", "13:30"),
    ("13:30", "15:00"),
    ("15:00", "16:30"),
    ("16:30", "18:00"),
]
# Bloco final: exceção, linha única de 30 min (rowspan = 1)
BLOCO_FINAL = ("18:00", "18:30")

def sub_horarios(inicio, fim, passo_min=30):
    """Gera os rótulos de 30 em 30 minutos dentro de um bloco."""
    h, m = map(int, inicio.split(":"))
    fh, fm = map(int, fim.split(":"))
    horarios = []
    total_ini = h * 60 + m
    total_fim = fh * 60 + fm
    t = total_ini
    while t < total_fim:
        horarios.append(f"{t // 60:02d}:{t % 60:02d}")
        t += passo_min
    return horarios

# ---------------------------------------------------------------------------
# Atividades e cores
# ---------------------------------------------------------------------------

# Atividades "rotativas" normais, usadas na geração automática
ATIVIDADES_ROTATIVAS = {
    "Chat": "#43A047",
    "Ligação": "#1E88E5",
    "Backoffice": "#8E24AA",
    "Pausa": "#FDD835",
    "Almoço": "#FB8C00",
}

# Atividades protegidas: preservam o estado do analista durante a geração
# automática (mesma categoria da regra de "Reunião").
ATIVIDADES_PROTEGIDAS = {
    "Reunião": "#607D8B",
    "Treinamento": "#3F51B5",
    "Reset Day": "#00897B",
    "Consulta médica": "#D81B60",
    "Folga": "#6D4C41",
    "Prioridade": "#E53935",
    "S/ Luz": "#212121",
    "S/ Internet": "#455A64",
    "S/ Acesso": "#757575",
    "Apoio Fiscal": "#7CB342",
    "Banco de Horas": "#00ACC1",
    "Projeto": "#5E35B1",
}

COR_LIVRE = "#B0BEC5"
CORES = {**ATIVIDADES_ROTATIVAS, **ATIVIDADES_PROTEGIDAS, "Livre": COR_LIVRE}

MIN_REGULARES_PARA_CORINGA_FOLGAR = 4  # abaixo disso, Coringa vai pro Chat

# ---------------------------------------------------------------------------
# Estado da sessão
# ---------------------------------------------------------------------------

def init_state():
    if "analistas" not in st.session_state:
        st.session_state.analistas = [
            "Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gabriela",
        ]
    if "coringa" not in st.session_state:
        st.session_state.coringa = "Coringa"
    if "locks" not in st.session_state:
        # { (analista, bloco_inicio): atividade_protegida }
        st.session_state.locks = {}
    if "schedule" not in st.session_state:
        # { (analista, bloco_inicio): atividade }
        st.session_state.schedule = {}
    if "data_escala" not in st.session_state:
        st.session_state.data_escala = date.today()

init_state()

def todos_blocos():
    return BLOCOS + [BLOCO_FINAL]

def rotulo_bloco(bloco):
    return f"{bloco[0]}–{bloco[1]}"

# ---------------------------------------------------------------------------
# Geração automática da escala
# ---------------------------------------------------------------------------

def montar_pool(qtd):
    """Monta um conjunto balanceado de atividades rotativas para `qtd` analistas."""
    base = ["Chat", "Chat", "Ligação", "Backoffice", "Pausa", "Almoço"]
    pool = []
    while len(pool) < qtd:
        pool.extend(base)
    return pool[:qtd]

def gerar_escala(analistas, coringa, locks, data_escala):
    """
    Gera a escala do dia.
    - Usa a data como seed, então muda a cada dia (mas é reproduzível no mesmo dia).
    - Analistas com trava em atividade protegida mantêm o estado (não são sobrescritos).
    - Coringa é escalado dinamicamente para o Chat sempre que houver menos de
      MIN_REGULARES_PARA_CORINGA_FOLGAR analistas regulares disponíveis no bloco.
    """
    seed_base = data_escala.isoformat()
    nova_escala = {}

    for bloco in todos_blocos():
        rnd = random.Random(f"{seed_base}-{bloco[0]}")

        disponiveis = [
            a for a in analistas if (a, bloco[0]) not in locks
        ]
        indisponiveis = [a for a in analistas if a not in disponiveis]

        pool = montar_pool(len(disponiveis))
        rnd.shuffle(pool)
        for analista, atividade in zip(disponiveis, pool):
            nova_escala[(analista, bloco[0])] = atividade

        for analista in indisponiveis:
            nova_escala[(analista, bloco[0])] = locks[(analista, bloco[0])]

        # Regra do Coringa dinâmico
        if (coringa, bloco[0]) in locks:
            nova_escala[(coringa, bloco[0])] = locks[(coringa, bloco[0])]
        elif len(disponiveis) < MIN_REGULARES_PARA_CORINGA_FOLGAR:
            nova_escala[(coringa, bloco[0])] = "Chat"
        else:
            nova_escala[(coringa, bloco[0])] = "Backoffice"

    return nova_escala

# ---------------------------------------------------------------------------
# Renderização da grade em HTML
# ---------------------------------------------------------------------------

def gerar_grid_html(schedule, analistas, coringa):
    colunas = analistas + [coringa]

    css = """
    <style>
      .escala-wrap { overflow-x:auto; font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; }
      table.escala { border-collapse: collapse; width:100%; min-width:900px; }
      table.escala th, table.escala td {
          border: 1px solid #E0E0E0; padding: 4px 6px; text-align:center; font-size: 13px;
      }
      table.escala th { background:#263238; color:#fff; position: sticky; top:0; }
      td.bloco-label { background:#ECEFF1; font-weight:700; color:#37474F; white-space:nowrap; }
      td.sub-hora { background:#FAFAFA; color:#607D8B; font-weight:600; width:56px; }
      td.card {
          font-weight:600; color:#fff; border-radius:6px; padding:6px 4px;
          box-shadow: inset 0 0 0 2px rgba(255,255,255,0.15);
      }
      .legenda-wrap { margin-top:18px; font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; }
      .legenda-titulo { font-weight:700; margin-bottom:8px; color:#37474F; }
      .pill {
          display:inline-block; padding:5px 12px; border-radius:999px; color:#fff;
          font-size:12px; font-weight:600; margin:3px 6px 3px 0;
      }
    </style>
    """

    linhas = []
    linhas.append('<div class="escala-wrap"><table class="escala">')
    linhas.append("<thead><tr>")
    linhas.append('<th>Bloco</th><th>Horário</th>')
    for col in analistas:
        linhas.append(f"<th>{col}</th>")
    linhas.append(f'<th>{coringa} 🃏</th>')
    linhas.append("</tr></thead><tbody>")

    for bloco in BLOCOS:
        subs = sub_horarios(bloco[0], bloco[1])  # 3 sub-horários de 30 min
        span = len(subs)
        for i, sub in enumerate(subs):
            linhas.append("<tr>")
            if i == 0:
                linhas.append(f'<td class="bloco-label" rowspan="{span}">{rotulo_bloco(bloco)}</td>')
            linhas.append(f'<td class="sub-hora">{sub}</td>')
            if i == 0:
                for col in colunas:
                    atividade = schedule.get((col, bloco[0]), "Livre")
                    cor = CORES.get(atividade, COR_LIVRE)
                    linhas.append(
                        f'<td class="card" rowspan="{span}" style="background:{cor}">{atividade}</td>'
                    )
            linhas.append("</tr>")

    # Bloco final — exceção: linha única de 30 min, sem rowspan
    sub_final = sub_horarios(BLOCO_FINAL[0], BLOCO_FINAL[1])
    linhas.append("<tr>")
    linhas.append(f'<td class="bloco-label">{rotulo_bloco(BLOCO_FINAL)}</td>')
    linhas.append(f'<td class="sub-hora">{sub_final[0]}</td>')
    for col in colunas:
        atividade = schedule.get((col, BLOCO_FINAL[0]), "Livre")
        cor = CORES.get(atividade, COR_LIVRE)
        linhas.append(f'<td class="card" style="background:{cor}">{atividade}</td>')
    linhas.append("</tr>")

    linhas.append("</tbody></table></div>")

    tabela_html = "".join(linhas)

    legenda = ['<div class="legenda-wrap"><div class="legenda-titulo">Legenda de atividades</div>']
    for nome, cor in {**ATIVIDADES_ROTATIVAS, **ATIVIDADES_PROTEGIDAS}.items():
        legenda.append(f'<span class="pill" style="background:{cor}">{nome}</span>')
    legenda.append("</div>")
    legenda_html = "".join(legenda)

    return css + tabela_html + legenda_html

def gerar_html_completo(schedule, analistas, coringa, data_escala):
    grid = gerar_grid_html(schedule, analistas, coringa)
    return f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Escala {data_escala.isoformat()}</title>
<style>
  body {{ margin:24px; background:#fff; }}
  h1 {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; color:#263238; font-size:20px; }}
  #btn-imprimir {{
      background:#263238; color:#fff; border:none; padding:10px 18px; border-radius:6px;
      font-size:14px; cursor:pointer; margin-bottom:16px; font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif;
  }}
  #btn-imprimir:hover {{ background:#37474F; }}
  @media print {{
      #btn-imprimir {{ display:none; }}
  }}
</style>
</head>
<body>
  <button id="btn-imprimir" onclick="window.print()">🖨️ Imprimir / Salvar como PDF</button>
  <h1>Escala do dia {data_escala.strftime('%d/%m/%Y')}</h1>
  {grid}
</body>
</html>"""

# ---------------------------------------------------------------------------
# Persistência de histórico
# ---------------------------------------------------------------------------

def carregar_historico():
    if os.path.exists(HIST_PATH):
        try:
            with open(HIST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def salvar_escala_do_dia(schedule, analistas, coringa, data_escala):
    historico = carregar_historico()
    registro = {
        "data": data_escala.isoformat(),
        "salvo_em": datetime.now().isoformat(timespec="seconds"),
        "coringa": coringa,
        "escala": {
            f"{analista}|{bloco[0]}": schedule.get((analista, bloco[0]), "Livre")
            for analista in (analistas + [coringa])
            for bloco in todos_blocos()
        },
    }
    # Substitui um registro já existente para a mesma data, se houver
    historico = [h for h in historico if h.get("data") != registro["data"]]
    historico.append(registro)
    with open(HIST_PATH, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)
    return registro

# ---------------------------------------------------------------------------
# Sidebar — configuração, travas e ações
# ---------------------------------------------------------------------------

st.sidebar.header("⚙️ Configuração")

st.session_state.data_escala = st.sidebar.date_input("Data da escala", value=st.session_state.data_escala)

nomes_txt = st.sidebar.text_area(
    "Analistas regulares (um por linha)",
    value="\n".join(st.session_state.analistas),
    height=150,
)
st.session_state.analistas = [n.strip() for n in nomes_txt.splitlines() if n.strip()]

st.session_state.coringa = st.sidebar.text_input("Nome do Coringa", value=st.session_state.coringa)

st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Travar atividade protegida")
st.sidebar.caption(
    "Analistas travados numa atividade protegida mantêm esse estado ao gerar a escala automática."
)

with st.sidebar.form("form_trava", clear_on_submit=True):
    todos_colaboradores = st.session_state.analistas + [st.session_state.coringa]
    analista_sel = st.selectbox("Analista", todos_colaboradores)
    bloco_sel = st.selectbox("Bloco", todos_blocos(), format_func=rotulo_bloco)
    atividade_sel = st.selectbox("Atividade protegida", list(ATIVIDADES_PROTEGIDAS.keys()))
    adicionar = st.form_submit_button("Adicionar trava")
    if adicionar:
        st.session_state.locks[(analista_sel, bloco_sel[0])] = atividade_sel
        st.sidebar.success(f"{analista_sel} travado em '{atividade_sel}' no bloco {rotulo_bloco(bloco_sel)}")

if st.session_state.locks:
    st.sidebar.caption("Travas ativas:")
    for chave in list(st.session_state.locks.keys()):
        analista, bloco_inicio = chave
        bloco_lbl = next((rotulo_bloco(b) for b in todos_blocos() if b[0] == bloco_inicio), bloco_inicio)
        col1, col2 = st.sidebar.columns([4, 1])
        col1.write(f"{analista} · {bloco_lbl} · {st.session_state.locks[chave]}")
        if col2.button("✖", key=f"rm-{analista}-{bloco_inicio}"):
            del st.session_state.locks[chave]
            st.rerun()

st.sidebar.markdown("---")

# ---------------------------------------------------------------------------
# Corpo principal
# ---------------------------------------------------------------------------

st.title("📋 Dashboard de Escala Automática")
st.caption(
    "Grade em blocos de 1h30, Coringa dinâmico no Chat quando faltam analistas, "
    "categorias protegidas e rotação diária por data."
)

col_a, col_b, col_c = st.columns([1, 1, 2])

with col_a:
    if st.button("🎲 Gerar Escala Automática", use_container_width=True):
        st.session_state.schedule = gerar_escala(
            st.session_state.analistas,
            st.session_state.coringa,
            st.session_state.locks,
            st.session_state.data_escala,
        )
        st.success("Escala gerada com sucesso.")

with col_b:
    if st.button("💾 Salvar Escala do Dia", use_container_width=True):
        if not st.session_state.schedule:
            st.warning("Gere a escala antes de salvar.")
        else:
            registro = salvar_escala_do_dia(
                st.session_state.schedule,
                st.session_state.analistas,
                st.session_state.coringa,
                st.session_state.data_escala,
            )
            st.success(f"Escala de {registro['data']} salva no histórico.")

with col_c:
    if st.session_state.schedule:
        html_export = gerar_html_completo(
            st.session_state.schedule,
            st.session_state.analistas,
            st.session_state.coringa,
            st.session_state.data_escala,
        )
        st.download_button(
            "📤 Compartilhar (baixar HTML)",
            data=html_export.encode("utf-8"),
            file_name=f"escala_{st.session_state.data_escala.isoformat()}.html",
            mime="text/html",
            use_container_width=True,
        )
    else:
        st.button("📤 Compartilhar (baixar HTML)", disabled=True, use_container_width=True)

st.markdown("---")

if not st.session_state.schedule:
    st.info("Nenhuma escala gerada ainda. Clique em '🎲 Gerar Escala Automática'.")
else:
    # Aviso de blocos onde o Coringa foi ativado no Chat por falta de analistas
    ativacoes = []
    for bloco in todos_blocos():
        disponiveis_no_bloco = [
            a for a in st.session_state.analistas
            if (a, bloco[0]) not in st.session_state.locks
        ]
        if (
            st.session_state.schedule.get((st.session_state.coringa, bloco[0])) == "Chat"
            and len(disponiveis_no_bloco) < MIN_REGULARES_PARA_CORINGA_FOLGAR
        ):
            ativacoes.append(rotulo_bloco(bloco))
    if ativacoes:
        st.caption(f"🃏 Coringa ativado no Chat nos blocos: {', '.join(ativacoes)} (menos de {MIN_REGULARES_PARA_CORINGA_FOLGAR} analistas regulares disponíveis).")

    grid_html = gerar_grid_html(
        st.session_state.schedule, st.session_state.analistas, st.session_state.coringa
    )
    st.markdown(grid_html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Histórico
# ---------------------------------------------------------------------------

with st.expander("📜 Histórico de escalas salvas"):
    hist = carregar_historico()
    if not hist:
        st.write("Nenhuma escala salva ainda.")
    else:
        for h in sorted(hist, key=lambda x: x["data"], reverse=True):
            st.write(f"**{h['data']}** — salvo em {h['salvo_em']}")
