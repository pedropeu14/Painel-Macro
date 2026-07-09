"""Painel Macro US — SocInvest / Central de Ferramentas.

Indicadores: ISM (Manufacturing e Services + subíndices), Inflação (CPI,
Core PCE, PPI), Juros (curva de Treasuries, breakeven), GDP, Payroll
(desemprego, salários, claims, revisões) e JOLTS (vagas, quits, layoffs).
Fontes: FRED (CSV público) e DBnomics (ISM). Híbrido: upload de CSV/Excel
pode complementar ou sobrescrever qualquer série (mesmo nome de coluna).

Rodar: streamlit run app.py
"""
import glob
import io
import os
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="Painel Macro US | SocInvest", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")

PRIMARY, ACCENT, GRID = "#4f8cff", "#22c07a", "#dde3ee"
NEG = "#ef5561"

st.markdown(f"""<style>
.main .block-container {{ padding-top:1.2rem; max-width:1450px; }}
h1,h2,h3 {{ color:{PRIMARY}; }}
[data-testid="stMetricValue"] {{ color:{PRIMARY}; }}
.soc-header {{ display:flex; align-items:center; gap:14px;
  border-bottom:3px solid {ACCENT}; padding-bottom:12px; margin-bottom:8px; }}
.soc-badge {{ background:{PRIMARY}; color:#fff; border-radius:8px;
  padding:6px 12px; font-weight:700; font-size:20px; }}
.soc-sub {{ color:#5b6678; font-size:14px; }}
</style>
<div class="soc-header"><span class="soc-badge">SocInvest</span><div>
<div style="font-size:26px;font-weight:800;color:{PRIMARY};">Painel Macro — EUA</div>
<div class="soc-sub">Central de Ferramentas · ISM · Inflação · Juros · GDP · Payroll · JOLTS</div>
</div></div>""", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Catálogo de séries
# ----------------------------------------------------------------------------
FRED = {  # label -> series_id
    "CPI (índice)": "CPIAUCSL",
    "Core CPI (índice)": "CPILFESL",
    "CPI Moradia/Shelter (índice)": "CUSR0000SAH1",
    "CPI Serviços ex-energia (índice)": "CUSR0000SASLE",
    "CPI Serviços ex-shelter (índice)": "CUSR0000SASL2RS",
    "CPI Bens núcleo (índice)": "CUSR0000SACL1E",
    "CPI Energia (índice)": "CPIENGSL",
    "CPI Alimentos (índice)": "CPIUFDSL",
    "GDP real (nível, US$ bi 2017)": "GDPC1",
    "GDP QoQ anualizado (%)": "A191RL1Q225SBEA",
    "GDP YoY (%)": "A191RO1Q156NBEA",
    "Payroll — emprego total (mil)": "PAYEMS",
    "Taxa de desemprego (%)": "UNRATE",
    "Salário médio/hora (US$)": "CES0500000003",
    "Participação na força de trabalho (%)": "CIVPART",
    "PCE (índice)": "PCEPI",
    "Core PCE (índice)": "PCEPILFE",
    "PPI Final Demand (índice)": "PPIFIS",
    "Initial Claims (semanal)": "ICSA",
    "Fed Funds efetiva (%)": "FEDFUNDS",
    "UST 2 anos (%)": "DGS2",
    "UST 10 anos (%)": "DGS10",
    "Spread 10a−2a (p.p.)": "T10Y2Y",
    "Breakeven 10 anos (%)": "T10YIE",
    "JOLTS — Vagas abertas (mil)": "JTSJOL",
    "JOLTS — Hires (mil)": "JTSHIL",
    "JOLTS — Taxa de vagas (%)": "JTSJOR",
    "JOLTS — Hires rate (%)": "JTSHIR",
    "JOLTS — Quits rate (%)": "JTSQUR",
    "JOLTS — Layoffs rate (%)": "JTSLDR",
    "Desempregados (mil)": "UNEMPLOY",
}
ISM_DB = {  # label -> (dataset, series_code)
    "ISM Manufacturing PMI": ("pmi", "pm"),
    "ISM Mfg — New Orders": ("neword", "in"),
    "ISM Mfg — Production": ("production", "in"),
    "ISM Mfg — Employment": ("employment", "in"),
    "ISM Mfg — Prices Paid": ("prices", "in"),
    "ISM Services PMI": ("nm-pmi", "pm"),
    "ISM Serv — Business Activity": ("nm-busact", "in"),
    "ISM Serv — New Orders": ("nm-neword", "in"),
    "ISM Serv — Employment": ("nm-employment", "in"),
    "ISM Serv — Prices Paid": ("nm-prices", "in"),
}
ISM_MFG = ["ISM Manufacturing PMI", "ISM Mfg — New Orders", "ISM Mfg — Production",
           "ISM Mfg — Employment", "ISM Mfg — Prices Paid"]
ISM_SRV = ["ISM Services PMI", "ISM Serv — Business Activity", "ISM Serv — New Orders",
           "ISM Serv — Employment", "ISM Serv — Prices Paid"]

# ----------------------------------------------------------------------------
# Camada de dados
# ----------------------------------------------------------------------------
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fred_series(series_id: str, start: str = "1990-01-01") -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["date"]).set_index("date")["value"]


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def dbnomics_series(dataset: str, code: str) -> pd.Series:
    url = (f"https://api.db.nomics.world/v22/series/ISM/{dataset}/{code}"
           f"?observations=1&format=json")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    doc = r.json()["series"]["docs"][0]
    s = pd.Series(doc["value"], index=pd.PeriodIndex(doc["period"], freq="M")
                  .to_timestamp(), name=code)
    s = pd.to_numeric(s, errors="coerce")
    return s[(s >= 25) & (s <= 95)]  # descarta valores corrompidos (índice de difusão)


# --- ISM direto do ismworld.org (último release) -----------------------------
MONTHS_EN = ["january", "february", "march", "april", "may", "june", "july",
             "august", "september", "october", "november", "december"]
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/126.0.0.0 Safari/537.36"),
      "Accept-Language": "en-US,en;q=0.9"}
ISM_SUB = {  # nome no release -> sufixo do label
    "pmi": {"New Orders": "ISM Mfg — New Orders",
            "Production": "ISM Mfg — Production",
            "Employment": "ISM Mfg — Employment",
            "Prices": "ISM Mfg — Prices Paid"},
    "services": {"Business Activity": "ISM Serv — Business Activity",
                 "New Orders": "ISM Serv — New Orders",
                 "Employment": "ISM Serv — Employment",
                 "Prices": "ISM Serv — Prices Paid"},
}
ISM_HEAD = {"pmi": "ISM Manufacturing PMI", "services": "ISM Services PMI"}


def _month_str(x):
    try:
        return pd.to_datetime(str(x).strip(), format="%b %Y")
    except Exception:
        return pd.NaT


def _parse_ism_html(kind: str, html: str) -> dict:
    """Extrai séries das tabelas do release (12m de PMI + 4m de cada subíndice)."""
    out = {}
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        return out
    subs = ISM_SUB[kind]
    for t in tables:
        t = t.copy()
        t.columns = [" ".join(str(x) for x in col).strip() if isinstance(col, tuple)
                     else str(col).strip() for col in t.columns]
        cols = list(t.columns)
        # tabela "THE LAST 12 MONTHS": pares de colunas Month / PMI
        month_cols = [i for i, c in enumerate(cols) if c.lower().startswith("month")]
        if month_cols and any("pmi" in c.lower() for c in cols):
            pts = {}
            for i in month_cols:
                if i + 1 >= len(cols):
                    continue
                for m, v in zip(t.iloc[:, i], t.iloc[:, i + 1]):
                    d = _month_str(m)
                    v = pd.to_numeric(v, errors="coerce")
                    if pd.notna(d) and pd.notna(v):
                        pts[d] = v
            if pts:
                s = pd.Series(pts).sort_index()
                out[ISM_HEAD[kind]] = s.combine_first(out.get(ISM_HEAD[kind],
                                                              pd.Series(dtype=float)))
        # tabelas de subíndice: 1ª coluna = nome, colunas %Higher/.../Index
        first = cols[0].replace("®", "").strip()
        if first in subs and any(c.lower() == "index" for c in cols):
            icol = [c for c in cols if c.lower() == "index"][0]
            pts = {}
            for m, v in zip(t.iloc[:, 0], t[icol]):
                d = _month_str(m)
                v = pd.to_numeric(v, errors="coerce")
                if pd.notna(d) and pd.notna(v):
                    pts[d] = v
            if pts:
                s = pd.Series(pts).sort_index()
                out[subs[first]] = s.combine_first(out.get(subs[first],
                                                           pd.Series(dtype=float)))
    return out


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def ism_from_site(kind: str, n_reports: int = 4) -> dict:
    """Busca os últimos releases no ismworld.org e monta as séries."""
    merged, got = {}, 0
    now = pd.Timestamp.today()
    for back in range(1, 8):
        if got >= n_reports:
            break
        ref = now - pd.DateOffset(months=back)
        url = ("https://www.ismworld.org/supply-management-news-and-reports/"
               f"reports/ism-report-on-business/{kind}/{MONTHS_EN[ref.month - 1]}/")
        try:
            r = requests.get(url, timeout=30, headers=UA)
            r.raise_for_status()
            html = r.text
        except Exception:
            continue
        if f"{MONTHS_EN[ref.month - 1].capitalize()} {ref.year}" not in html:
            continue  # página de outro ano
        part = _parse_ism_html(kind, html)
        for k, s in part.items():
            merged[k] = s.combine_first(merged.get(k, pd.Series(dtype=float)))
        got += 1
    return merged


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def ism_all_site() -> dict:
    out = {}
    for kind in ["pmi", "services"]:
        try:
            out.update(ism_from_site(kind))
        except Exception:
            pass
    return out


def try_load(label: str) -> pd.Series:
    try:
        if label in FRED:
            return fred_series(FRED[label])
        site = ism_all_site().get(label, pd.Series(dtype=float))
        ds, code = ISM_DB[label]
        try:
            db = dbnomics_series(ds, code)
        except Exception:
            db = pd.Series(dtype=float)
        return site.combine_first(db).sort_index()  # site tem prioridade
    except Exception:
        return pd.Series(dtype=float)


# --- upload (override/complemento) ------------------------------------------
def find_header_row(raw):
    best_rate, first_row = 0.0, 0
    for c in raw.columns:
        parsed = pd.to_datetime(raw[c], errors="coerce", dayfirst=True)
        rate = parsed.notna().mean()
        if rate > best_rate:
            best_rate = rate
            first_row = raw.index.get_loc(parsed.notna().idxmax())
    return max(first_row - 1, 0) if best_rate >= 0.5 else 0


@st.cache_data(show_spinner=False)
def load_upload(file_bytes, filename):
    if filename.lower().endswith((".xlsx", ".xls")):
        raw = pd.read_excel(io.BytesIO(file_bytes), header=None)
    else:
        raw = None
        for sep in [",", ";", "\t"]:
            try:
                tmp = pd.read_csv(io.BytesIO(file_bytes), sep=sep, header=None, dtype=str)
                if tmp.shape[1] > 1:
                    raw = tmp
                    break
            except Exception:
                continue
        if raw is None:
            raw = pd.read_csv(io.BytesIO(file_bytes), header=None, dtype=str)
    hdr = find_header_row(raw)
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(x).strip() for x in raw.iloc[hdr].tolist()]
    df = df.reset_index(drop=True).dropna(axis=1, how="all")
    date_col = None
    for c in df.columns:
        if pd.to_datetime(df[c], errors="coerce", dayfirst=True).notna().mean() > 0.7:
            date_col = c
            break
    if date_col is None:
        return {}
    idx = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    out = {}
    for c in df.columns:
        if c == date_col:
            continue
        v = df[c]
        if not pd.api.types.is_numeric_dtype(v):
            v = smart_numeric(v)
        s = pd.Series(pd.to_numeric(v, errors="coerce").values, index=idx)
        s = s.dropna().sort_index()
        if not s.empty:
            out[str(c).strip()] = s
    return out


def smart_numeric(sr: pd.Series) -> pd.Series:
    """Detecta o formato decimal por coluna: US (53.3) ou PT-BR (53,3 / 1.234,5)."""
    sr = sr.astype(str).str.replace("%", "", regex=False).str.strip()
    has_c, has_d = sr.str.contains(",", na=False), sr.str.contains(r"\.", na=False)
    if has_c.any() and has_d.any():
        samp = sr[has_c & has_d].iloc[0]
        if samp.rfind(",") > samp.rfind("."):          # 1.234,5 -> PT-BR
            sr = (sr.str.replace(".", "", regex=False)
                    .str.replace(",", ".", regex=False))
        else:                                          # 1,234.5 -> US c/ milhar
            sr = sr.str.replace(",", "", regex=False)
    elif has_c.any():                                  # 53,3 -> PT-BR
        sr = sr.str.replace(",", ".", regex=False)
    return pd.to_numeric(sr, errors="coerce")          # 53.3 -> US puro


ALIASES = {  # nomes comuns (ex.: export Bloomberg) -> séries do painel
    "ism manufacturing": "ISM Manufacturing PMI",
    "ism manufacturing pmi": "ISM Manufacturing PMI",
    "ism services": "ISM Services PMI",
    "ism services pmi": "ISM Services PMI",
    "ism manufacturing new orders": "ISM Mfg — New Orders",
    "ism manufacturing production": "ISM Mfg — Production",
    "ism manufacturing employment": "ISM Mfg — Employment",
    "ism manufacturing prices paid": "ISM Mfg — Prices Paid",
    "ism services business activity": "ISM Serv — Business Activity",
    "ism services new orders": "ISM Serv — New Orders",
    "ism services employment": "ISM Serv — Employment",
    "ism services prices paid": "ISM Serv — Prices Paid",
}


def canon(name: str) -> str:
    return ALIASES.get(name.strip().lower(), name.strip())


def merged(label: str) -> pd.Series:
    """API + dados locais/upload: planilha sobrescreve e estende o histórico."""
    api = try_load(label)
    up = st.session_state.get("uploads", {})
    key = next((k for k in up
                if canon(k).lower() == label.strip().lower()), None)
    if key is None:
        return api
    s = up[key].copy()
    s.index = s.index.to_period("M").to_timestamp()  # normaliza p/ início do mês
    s = s.groupby(s.index).last()
    return s.combine_first(api).sort_index() if not api.empty else s


# --- comentários por data (anotações pós-divulgação) -------------------------
COMMENTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "dados", "comentarios.csv")
COMMENTS_COLS = ["Date", "Aba", "Comentário"]
COMMENT_TABS = ["Geral", "ISM", "Inflação", "Juros", "GDP", "Payroll", "JOLTS"]


def load_comments() -> pd.DataFrame:
    try:
        df = pd.read_csv(COMMENTS_PATH)
    except Exception:
        return pd.DataFrame(columns=COMMENTS_COLS)
    df.columns = COMMENTS_COLS[:len(df.columns)]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df["Aba"] = df.get("Aba", "Geral").fillna("Geral")
    df["Comentário"] = df.get("Comentário", "").fillna("")
    return df[COMMENTS_COLS].sort_values("Date", ascending=False)


def show_comments(aba: str):
    """Expander com os comentários da aba (mais recentes primeiro)."""
    df = st.session_state.get("comments", pd.DataFrame())
    if df.empty:
        return
    sub = df[df["Aba"] == aba].dropna(subset=["Date"])
    if sub.empty:
        return
    with st.expander(f"🗒️ Comentários — {aba} ({len(sub)})"):
        for _, r in sub.sort_values("Date", ascending=False).iterrows():
            st.markdown(f"**{pd.Timestamp(r['Date']):%d/%m/%Y}** — {r['Comentário']}")


# ----------------------------------------------------------------------------
# Helpers de UI
# ----------------------------------------------------------------------------
def fmt(v, dec=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    s = f"{v:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


PERIODS = {"1a": 1, "2a": 2, "5a": 5, "10a": 10, "20a": 20, "Máx": None}


def period_picker(key, default="5a"):
    """Seletor de período dentro da aba. Retorna a data de corte (ou None=tudo)."""
    choice = st.radio("Período", list(PERIODS), horizontal=True,
                      index=list(PERIODS).index(default), key=f"per_{key}")
    n = PERIODS[choice]
    return None if n is None else pd.Timestamp(datetime.now()) - pd.DateOffset(years=n)


def kpi_row(items):
    """items: lista de (label, série, decimais). Mostra último valor + delta."""
    cols = st.columns(len(items))
    for col, (label, s, dec) in zip(cols, items):
        with col:
            s = s.dropna()
            if s.empty:
                st.metric(label, "—")
                continue
            last, prev = s.iloc[-1], (s.iloc[-2] if len(s) > 1 else np.nan)
            st.metric(label, fmt(last, dec),
                      delta=None if pd.isna(prev) else fmt(last - prev, dec))
            st.caption(f"{s.index[-1]:%b/%Y}")


def line_chart(series_map, ref=None, height=460, yfmt=None, cut=None, secondary=()):
    """secondary: rótulos plotados no eixo direito (para escalas diferentes)."""
    fig = go.Figure()
    for label, s in series_map.items():
        s = s.dropna()
        if cut is not None:
            s = s[s.index >= cut]
        if s.empty:
            continue
        fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines",
                                 name=label + (" (dir.)" if label in secondary else ""),
                                 yaxis="y2" if label in secondary else "y"))
    if ref is not None:
        fig.add_hline(y=ref, line_dash="dash", line_color="#8a8f94",
                      annotation_text=f"{ref:g}")
    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=height, hovermode="x unified",
                      legend=dict(orientation="h", y=1.02, x=0),
                      margin=dict(l=10, r=10, t=30, b=10))
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(gridcolor=GRID, ticksuffix=yfmt or "")
    if secondary:
        fig.update_layout(yaxis2=dict(overlaying="y", side="right",
                                      ticksuffix=yfmt or "", showgrid=False))
    st.plotly_chart(fig, use_container_width=True)


def bar_chart(s, name, height=380, suffix="", cut=None, avg=None, ymin=None):
    """avg: (janela, rótulo) sobrepõe média móvel em linha — ex.: (4, "Média 4 semanas").
    ymin: piso do eixo Y (recorta a base das barras para dar zoom na variação)."""
    s = s.dropna()
    if avg:
        n, lbl = avg
        m = s.rolling(n).mean()
    if cut is not None:
        s = s[s.index >= cut]
    if s.empty:
        st.info("Sem dados no período.")
        return
    colors = [ACCENT if v >= 0 else NEG for v in s.values]
    fig = go.Figure(go.Bar(x=s.index, y=s.values, name=name, marker_color=colors))
    if avg:
        if cut is not None:
            m = m[m.index >= cut]
        fig.add_trace(go.Scatter(x=m.index, y=m.values, mode="lines",
                                 name=lbl, line=dict(color=PRIMARY, width=2)))
    if ymin is not None:
        top = max([s.max()] + ([m.max()] if avg and not m.dropna().empty else []))
        fig.update_yaxes(range=[ymin, float(top) * 1.03])
    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=height, hovermode="x unified",
                      legend=dict(orientation="h", y=1.02, x=0),
                      margin=dict(l=10, r=10, t=30, b=10))
    fig.update_yaxes(gridcolor=GRID, ticksuffix=suffix)
    st.plotly_chart(fig, use_container_width=True)


def line_bar_chart(line_s, line_name, bar_s, bar_name, height=380, cut=None,
                   suffix="%", y2_zoom=False):
    """Linha no eixo esquerdo, barras no direito. y2_zoom: eixo das barras
    ajustado à faixa dos dados (para série de nível, ex.: participação)."""
    a, b = line_s.dropna(), bar_s.dropna()
    if cut is not None:
        a, b = a[a.index >= cut], b[b.index >= cut]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=b.index, y=b.values, name=f"{bar_name} (dir.)",
                         yaxis="y2", marker_color=ACCENT, opacity=0.55))
    fig.add_trace(go.Scatter(x=a.index, y=a.values, name=line_name,
                             line=dict(color=PRIMARY, width=2)))
    y2 = dict(overlaying="y", side="right", ticksuffix=suffix, showgrid=False)
    if y2_zoom and not b.empty:
        pad = (b.max() - b.min()) * 0.15 or 0.5
        y2["range"] = [float(b.min() - pad), float(b.max() + pad)]
    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", height=height,
                      hovermode="x unified",
                      legend=dict(orientation="h", y=1.02, x=0),
                      margin=dict(l=10, r=10, t=30, b=10),
                      yaxis=dict(ticksuffix=suffix, gridcolor=GRID), yaxis2=y2)
    st.plotly_chart(fig, use_container_width=True)


def table_download(series_map, fname, cut=None):
    df = pd.DataFrame(series_map).sort_index()
    if cut is not None:
        df = df[df.index >= cut]
    df = df.dropna(how="all")
    df.index.name = "Date"
    show = df.reset_index()
    show["Date"] = pd.to_datetime(show["Date"]).dt.strftime("%Y-%m-%d")
    st.dataframe(show, use_container_width=True, hide_index=True, height=320)
    st.download_button("⬇️ Baixar CSV", show.to_csv(index=False).encode("utf-8"),
                       fname, "text/csv", key=fname)


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
with st.sidebar:
    st.header("📂 Dados locais / upload")
    st.caption("Arquivos CSV/Excel na pasta **dados/** do app são carregados "
               "automaticamente (ex.: ISM da Bloomberg). Upload abaixo vale só "
               "nesta sessão e tem prioridade. Colunas casam com as séries pelo "
               "nome; outros nomes viram séries extras na Visão Geral.")
    local_files = sorted(
        p for p in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "dados", "*"))
        if p.lower().endswith((".csv", ".xlsx", ".xls"))
        and os.path.basename(p).lower() != "comentarios.csv")
    local = {}
    for p in local_files:
        try:
            with open(p, "rb") as fh:
                local.update(load_upload(fh.read(), os.path.basename(p)))
        except Exception:
            st.warning(f"Falha ao ler {os.path.basename(p)}")
    upfile = st.file_uploader("CSV ou Excel", type=["csv", "xlsx", "xls"])
    session_up = load_upload(upfile.getvalue(), upfile.name) if upfile else {}
    st.session_state["uploads"] = {**local, **session_up}
    if st.session_state["uploads"]:
        st.success(f"{len(st.session_state['uploads'])} série(s) de "
                   f"{len(local_files) + (1 if upfile else 0)} arquivo(s).")
    st.divider()
    if st.button("🔄 Atualizar dados (limpar cache)"):
        st.cache_data.clear()
        st.rerun()
    st.caption("Fontes: FRED (St. Louis Fed) · ismworld.org + DBnomics (ISM). "
               "Histórico curto do ISM? Estenda via upload (ex.: export Bloomberg).")

# ----------------------------------------------------------------------------
# Carrega tudo
# ----------------------------------------------------------------------------
if "comments" not in st.session_state:
    st.session_state["comments"] = load_comments()

with st.spinner("Carregando dados..."):
    S = {label: merged(label) for label in list(ISM_DB) + list(FRED)}

failed = [k for k, v in S.items() if v.dropna().empty]
if failed:
    st.warning("Sem dados para: " + ", ".join(failed) +
               ". Verifique a conexão ou carregue via upload (coluna com o mesmo nome).")

# derivadas
def yoy(s):  return (s / s.shift(12) - 1) * 100
def mom(s):  return (s / s.shift(1) - 1) * 100

cpi_yoy = {k.replace(" (índice)", " YoY"): yoy(S[k]) for k in FRED if k.endswith("(índice)")}
cpi_mom = {k.replace(" (índice)", " MoM"): mom(S[k]) for k in FRED if k.endswith("(índice)")}
payroll_chg = S["Payroll — emprego total (mil)"].diff()
ahe_yoy = yoy(S["Salário médio/hora (US$)"])
ahe_mom = mom(S["Salário médio/hora (US$)"])
claims = S["Initial Claims (semanal)"] / 1000          # mil, semanal
jolts_mi = S["JOLTS — Vagas abertas (mil)"] / 1000     # milhões
hires_mi = S["JOLTS — Hires (mil)"] / 1000             # milhões
vac_per_unemp = (S["JOLTS — Vagas abertas (mil)"]
                 / S["Desempregados (mil)"])           # vagas por desempregado

# ----------------------------------------------------------------------------
# Abas
# ----------------------------------------------------------------------------
tab_ov, tab_ism, tab_cpi, tab_juros, tab_gdp, tab_pay, tab_jolts = st.tabs(
    ["📊 Visão Geral", "🏭 ISM", "💵 Inflação", "🏦 Juros", "📈 GDP",
     "👷 Payroll", "🔄 JOLTS"])

with tab_ov:
    st.subheader("Últimos dados")
    kpi_row([("ISM Manufacturing", S["ISM Manufacturing PMI"], 1),
             ("ISM Services", S["ISM Services PMI"], 1),
             ("CPI YoY (%)", cpi_yoy["CPI YoY"], 1),
             ("Core CPI YoY (%)", cpi_yoy["Core CPI YoY"], 1)])
    kpi_row([("Payroll MoM (mil)", payroll_chg, 0),
             ("Desemprego (%)", S["Taxa de desemprego (%)"], 1),
             ("AHE YoY (%)", ahe_yoy, 1),
             ("GDP QoQ anualizado (%)", S["GDP QoQ anualizado (%)"], 1)])
    kpi_row([("Core PCE YoY (%)", cpi_yoy["Core PCE YoY"], 1),
             ("Initial Claims (mil)", claims, 0),
             ("UST 10 anos (%)", S["UST 10 anos (%)"], 2),
             ("Vagas JOLTS (mi)", jolts_mi, 2)])
    extras = {k: v for k, v in st.session_state.get("uploads", {}).items()
              if canon(k).lower() not in {x.lower() for x in S}}
    if extras:
        st.divider()
        st.subheader("Séries extras (upload)")
        line_chart(extras, cut=period_picker("ov"))
    st.divider()
    st.subheader("🗒️ Comentários por data")
    st.caption("Anotações feitas após cada divulgação — aparecem na aba "
               "correspondente. Edite abaixo (linhas novas no +). Para "
               "persistir no Streamlit Cloud, baixe o CSV e commite em "
               "`dados/comentarios.csv`; o 💾 grava direto no arquivo "
               "quando rodando localmente.")
    edited = st.data_editor(
        st.session_state["comments"], num_rows="dynamic",
        use_container_width=True, key="comments_editor",
        column_config={
            "Date": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Aba": st.column_config.SelectboxColumn("Aba", options=COMMENT_TABS,
                                                    default="Geral"),
            "Comentário": st.column_config.TextColumn("Comentário", width="large"),
        })
    st.session_state["comments"] = edited
    csv_out = edited.dropna(subset=["Date"]).copy()
    if not csv_out.empty:
        csv_out["Date"] = pd.to_datetime(csv_out["Date"]).dt.strftime("%Y-%m-%d")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Salvar em dados/comentarios.csv"):
            csv_out.to_csv(COMMENTS_PATH, index=False)
            st.success(f"{len(csv_out)} comentário(s) salvos.")
    with c2:
        st.download_button("⬇️ Baixar comentarios.csv",
                           csv_out.to_csv(index=False).encode("utf-8"),
                           "comentarios.csv", "text/csv")

with tab_ism:
    st.subheader("ISM — Manufacturing")
    kpi_row([(k.replace("ISM Mfg — ", "").replace("ISM ", ""), S[k], 1)
             for k in ISM_MFG])
    st.subheader("ISM — Services")
    kpi_row([(k.replace("ISM Serv — ", "").replace("ISM ", ""), S[k], 1)
             for k in ISM_SRV])
    st.divider()
    cut = period_picker("ism")
    sel_ism = st.multiselect("Séries no gráfico", ISM_MFG + ISM_SRV,
                             default=["ISM Manufacturing PMI", "ISM Services PMI"])
    if sel_ism:
        line_chart({k: S[k] for k in sel_ism}, ref=50, cut=cut)
    with st.expander("📋 Tabela e download"):
        table_download({k: S[k] for k in ISM_MFG + ISM_SRV}, "ism.csv", cut=cut)
    show_comments("ISM")
    st.caption("Acima de 50 = expansão; abaixo = contração. "
               "Fonte: ismworld.org (últimos releases) + DBnomics (histórico).")

with tab_cpi:
    st.subheader("Inflação — CPI, PCE e PPI")
    kpi_row([("CPI YoY (%)", cpi_yoy["CPI YoY"], 1),
             ("Core CPI YoY (%)", cpi_yoy["Core CPI YoY"], 1),
             ("Core PCE YoY (%)", cpi_yoy["Core PCE YoY"], 1),
             ("Serviços ex-shelter YoY (%)", cpi_yoy["CPI Serviços ex-shelter YoY"], 1),
             ("Shelter YoY (%)", cpi_yoy["CPI Moradia/Shelter YoY"], 1)])
    cut = period_picker("cpi")
    mode = st.radio("Métrica", ["YoY (%)", "MoM (%)"], horizontal=True)
    src = cpi_yoy if mode.startswith("YoY") else cpi_mom
    default = [c for c in ["CPI YoY", "Core CPI YoY", "Core PCE YoY",
                           "CPI Serviços ex-shelter YoY"]]
    default = [d.replace("YoY", "MoM") for d in default] if mode.startswith("MoM") else default
    sel = st.multiselect("Séries", list(src), default=[d for d in default if d in src])
    if sel:
        line_chart({k: src[k] for k in sel},
                   ref=2 if mode.startswith("YoY") else None, yfmt="%", cut=cut)
    with st.expander("📋 Tabela e download"):
        table_download(src, "inflacao.csv", cut=cut)
    show_comments("Inflação")
    st.caption("Variações calculadas sobre índices dessazonalizados (SA). "
               "'Serviços ex-shelter' = CPI Services less rent of shelter "
               "(proxy do supercore). Core PCE é a métrica-alvo do Fed "
               "(linha de 2%). Fonte: BLS e BEA via FRED.")

with tab_juros:
    st.subheader("Juros — curva de Treasuries e expectativa de inflação")
    kpi_row([("Fed Funds efetiva (%)", S["Fed Funds efetiva (%)"], 2),
             ("UST 2 anos (%)", S["UST 2 anos (%)"], 2),
             ("UST 10 anos (%)", S["UST 10 anos (%)"], 2),
             ("Spread 10a−2a (p.p.)", S["Spread 10a−2a (p.p.)"], 2),
             ("Breakeven 10a (%)", S["Breakeven 10 anos (%)"], 2)])
    cut = period_picker("juros")
    st.markdown("**Fed Funds × UST 2 anos × UST 10 anos (%)**")
    line_chart({"Fed Funds": S["Fed Funds efetiva (%)"],
                "UST 2 anos": S["UST 2 anos (%)"],
                "UST 10 anos": S["UST 10 anos (%)"]}, yfmt="%", cut=cut)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Spread 10a−2a (p.p.) — abaixo de 0 = curva invertida**")
        line_chart({"10a−2a": S["Spread 10a−2a (p.p.)"]}, ref=0,
                   height=380, cut=cut)
    with c2:
        st.markdown("**Breakeven 10 anos (%) — inflação implícita no mercado**")
        line_chart({"Breakeven 10a": S["Breakeven 10 anos (%)"]}, ref=2,
                   yfmt="%", height=380, cut=cut)
    with st.expander("📋 Tabela e download"):
        table_download({"Fed Funds (%)": S["Fed Funds efetiva (%)"],
                        "UST 2a (%)": S["UST 2 anos (%)"],
                        "UST 10a (%)": S["UST 10 anos (%)"],
                        "Spread 10a−2a": S["Spread 10a−2a (p.p.)"],
                        "Breakeven 10a (%)": S["Breakeven 10 anos (%)"]},
                       "juros.csv", cut=cut)
    show_comments("Juros")
    st.caption("Treasuries e breakeven são diários; Fed Funds efetiva é média "
               "mensal. Inversão da curva (spread < 0) historicamente antecede "
               "recessões. Fonte: Fed/Treasury via FRED.")

with tab_gdp:
    st.subheader("Atividade — PIB real")
    kpi_row([("QoQ anualizado (%)", S["GDP QoQ anualizado (%)"], 1),
             ("YoY (%)", S["GDP YoY (%)"], 1),
             ("Nível (US$ bi 2017)", S["GDP real (nível, US$ bi 2017)"], 0)])
    cut = period_picker("gdp")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Crescimento QoQ anualizado (%)**")
        bar_chart(S["GDP QoQ anualizado (%)"], "QoQ SAAR", suffix="%", cut=cut)
    with c2:
        st.markdown("**Crescimento YoY (%)**")
        line_chart({"GDP YoY": S["GDP YoY (%)"]}, yfmt="%", height=380, cut=cut)
    with st.expander("📋 Tabela e download"):
        table_download({"QoQ SAAR (%)": S["GDP QoQ anualizado (%)"],
                        "YoY (%)": S["GDP YoY (%)"],
                        "Nível": S["GDP real (nível, US$ bi 2017)"]}, "gdp.csv", cut=cut)
    show_comments("GDP")
    st.caption("Fonte: BEA via FRED. Dados trimestrais.")

with tab_pay:
    st.subheader("Mercado de trabalho")
    rev2m = st.session_state.get("uploads", {}).get("Revisão 2M (mil)", pd.Series(dtype=float))
    kpis = [("Payroll MoM (mil)", payroll_chg, 0),
            ("Initial Claims (mil)", claims, 0),
            ("Desemprego (%)", S["Taxa de desemprego (%)"], 1),
            ("AHE MoM (%)", ahe_mom, 1),
            ("AHE YoY (%)", ahe_yoy, 1),
            ("Participação (%)", S["Participação na força de trabalho (%)"], 1)]
    if not rev2m.dropna().empty:
        kpis.insert(1, ("Revisão 2M (mil)", rev2m, 0))
    kpi_row(kpis[:6])
    cut = period_picker("pay")
    st.markdown("**Criação de vagas — Nonfarm Payrolls (mil/mês)**")
    bar_chart(payroll_chg, "Payroll MoM", suffix="", cut=cut, avg=(3, "Média 3m"))
    st.markdown("**Initial Claims — pedidos de seguro-desemprego (mil, semanal)**")
    bar_chart(claims, "Claims", cut=cut, avg=(4, "Média 4 semanas"), ymin=150)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Desemprego linha (esq.) × Participação barras (dir.), %**")
        line_bar_chart(S["Taxa de desemprego (%)"], "Desemprego",
                       S["Participação na força de trabalho (%)"], "Participação",
                       cut=cut, y2_zoom=True)
    with c2:
        st.markdown("**AHE — YoY linha (esq.) × MoM barras (dir.), %**")
        line_bar_chart(ahe_yoy, "AHE YoY", ahe_mom, "AHE MoM", cut=cut)
    if not rev2m.dropna().empty:
        st.markdown("**Revisão líquida de 2 meses (mil)**")
        bar_chart(rev2m, "Revisão 2M", cut=cut)
    else:
        st.info("**Revisão líquida de 2 meses:** o FRED só traz o dado revisado. "
                "Para exibir, carregue no upload um CSV com colunas `Date` e "
                "`Revisão 2M (mil)` (valores do release do BLS).")
    with st.expander("📋 Tabela e download"):
        table_download({"Payroll MoM (mil)": payroll_chg,
                        "Initial Claims (mil)": claims,
                        "Desemprego (%)": S["Taxa de desemprego (%)"],
                        "AHE MoM (%)": ahe_mom, "AHE YoY (%)": ahe_yoy},
                       "payroll.csv", cut=cut)
    show_comments("Payroll")
    st.caption("Fonte: BLS e DOL via FRED. Dados dessazonalizados. "
               "Claims é semanal — o termômetro mais tempestivo do emprego.")

with tab_jolts:
    st.subheader("JOLTS — vagas, contratações e desligamentos")
    kpi_row([("Vagas abertas (mi)", jolts_mi, 2),
             ("Vagas por desempregado", vac_per_unemp, 2),
             ("Taxa de vagas (%)", S["JOLTS — Taxa de vagas (%)"], 1),
             ("Quits rate (%)", S["JOLTS — Quits rate (%)"], 1),
             ("Layoffs rate (%)", S["JOLTS — Layoffs rate (%)"], 1)])
    cut = period_picker("jolts")
    st.markdown("**Vagas abertas (esq.) × Contratações (dir.) — milhões de pessoas**")
    line_chart({"Vagas abertas": jolts_mi, "Contratações": hires_mi},
               height=380, cut=cut, secondary={"Contratações"})
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Contratações × Quits × Layoffs (taxa, %)**")
        line_chart({"Contratações": S["JOLTS — Hires rate (%)"],
                    "Quits": S["JOLTS — Quits rate (%)"],
                    "Layoffs": S["JOLTS — Layoffs rate (%)"]},
                   yfmt="%", height=380, cut=cut)
    with c2:
        st.markdown("**Vagas por desempregado — acima de 1 = mercado apertado**")
        line_chart({"Vagas/desempregado": vac_per_unemp}, ref=1,
                   height=380, cut=cut)
    with st.expander("📋 Tabela e download"):
        table_download({"Vagas abertas (mi)": jolts_mi,
                        "Contratações (mi)": hires_mi,
                        "Vagas por desempregado": vac_per_unemp,
                        "Taxa de vagas (%)": S["JOLTS — Taxa de vagas (%)"],
                        "Hires rate (%)": S["JOLTS — Hires rate (%)"],
                        "Quits rate (%)": S["JOLTS — Quits rate (%)"],
                        "Layoffs rate (%)": S["JOLTS — Layoffs rate (%)"]},
                       "jolts.csv", cut=cut)
    show_comments("JOLTS")
    st.caption("Vagas abertas é estoque no fim do mês; contratações é fluxo do "
               "mês (eixo direito). Quits alto = trabalhador "
               "confiante (pede demissão por opção); layoffs baixo = empresas "
               "segurando gente. JOLTS sai com ~1 mês de defasagem vs. payroll. "
               "Fonte: BLS via FRED.")

st.divider()
st.caption(f"SocInvest · Painel Macro US · FRED + DBnomics (cache 6h) · "
           f"Gerado em {datetime.now():%d/%m/%Y %H:%M}")
