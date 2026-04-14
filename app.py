import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from pathlib import Path

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Painel de Ocorrências Aeronáuticas", layout="wide")

# =========================
# STYLE
# =========================
st.markdown("""
<style>
.stApp { background-color: #0A1A2F; color: white; }
h1, h2, h3, h4, h5, h6, p, label, span { color: white !important; }

.stTabs [role="tablist"] > div {
    background: #1B3B5F !important;
    color: white !important;
    border-radius: 8px;
    padding: 6px 12px;
    border: 1px solid #2AA3D3 !important;
}

.stTabs [role="tablist"] > div[aria-selected="true"] {
    background-color: #0F4C81 !important;
}

.stButton>button {
    background-color: #1B3B5F !important;
    color: white !important;
    border-radius: 8px !important;
    border: 1px solid #2AA3D3 !important;
}
</style>
""", unsafe_allow_html=True)

# =========================
# CONSTANTS (colunas oficiais)
# =========================
COLUMNS = [
    "Operador_Padronizado","Classificacao_da_Ocorrencia","Data_da_Ocorrencia",
    "Municipio","UF","Regiao","Descricao_do_Tipo","ICAO","Latitude","Longitude",
    "Tipo_de_Aerodromo","Historico","Matricula","Categoria_da_Aeronave","Operador",
    "Tipo_de_Ocorrencia","Fase_da_Operacao","Operacao","Danos_a_Aeronave",
    "Aerodromo_de_Destino","Aerodromo_de_Origem","Modelo","CLS","Tipo_ICAO","PMD",
    "Numero_de_Assentos","Nome_do_Fabricante","PSSO"
]
TITLE_COLS = [
    "Operacao","Fase_da_Operacao","Classificacao_da_Ocorrencia",
    "Tipo_de_Ocorrencia","Danos_a_Aeronave"
]
GEOJSON_URL = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"

# =========================
# PREPROCESS
# =========================
def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    keep = [c for c in COLUMNS if c in df.columns]
    if keep:
        df = df[keep].copy()

    if "ICAO" in df.columns:
        df["ICAO"] = df["ICAO"].astype("string").str.upper().str.strip()

    for c in TITLE_COLS:
        if c in df.columns:
            df[c] = df[c].astype("string").str.title().str.strip()

    if "Data_da_Ocorrencia" in df.columns:
        df["Data_da_Ocorrencia"] = pd.to_datetime(df["Data_da_Ocorrencia"], errors="coerce")
        df["Ano"] = df["Data_da_Ocorrencia"].dt.year
        df["Mes"] = df["Data_da_Ocorrencia"].dt.month

    # garante tipos numéricos para mapa de pontos
    for c in ["Latitude", "Longitude"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df

# =========================
# HELPERS (charts)
# =========================
@st.cache_data(show_spinner=False)
def get_geojson():
    return requests.get(GEOJSON_URL, timeout=30).json()

def choropleth_uf(df: pd.DataFrame):
    if "UF" not in df.columns or df.empty:
        return None
    geojson = get_geojson()

    ocorr_uf = df["UF"].value_counts().reset_index()
    ocorr_uf.columns = ["UF", "Ocorrencias"]

    fig = px.choropleth(
        ocorr_uf,
        geojson=geojson,
        locations="UF",
        featureidkey="properties.sigla",
        color="Ocorrencias",
        color_continuous_scale="Blues"
    )
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=30, b=0)
    )
    return fig

def map_points(df: pd.DataFrame):
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        return None

    pts = df.dropna(subset=["Latitude", "Longitude"]).copy()
    if pts.empty:
        return None

    hover_cols = {}
    for col in ["UF", "ICAO", "Tipo_de_Ocorrencia", "Data_da_Ocorrencia", "Fase_da_Operacao", "Operacao"]:
        if col in pts.columns:
            hover_cols[col] = True

    fig = px.scatter_mapbox(
        pts,
        lat="Latitude",
        lon="Longitude",
        hover_name="Municipio" if "Municipio" in pts.columns else None,
        hover_data=hover_cols,
        zoom=3,
        height=650
    )
    fig.update_layout(
        mapbox_style="open-street-map",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=30, b=0)
    )
    return fig

def bar_top(df: pd.DataFrame, col: str, topn: int, title: str):
    """Barras horizontais com maior valor no topo e menor embaixo."""
    if col not in df.columns:
        return None
    vc = df[col].value_counts().head(topn)
    if vc.empty:
        return None
    fig = px.bar(vc, orientation="h", title=title, color=vc.values, color_continuous_scale="Blues")
    # ✅ garante maior em cima
    fig.update_yaxes(categoryorder="total ascending")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
    return fig

def pie_dist(df: pd.DataFrame, col: str, title: str):
    if col not in df.columns:
        return None
    vc = df[col].value_counts()
    if vc.empty:
        return None
    fig = px.pie(names=vc.index, values=vc.values, title=title, color_discrete_sequence=px.colors.sequential.Blues)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
    return fig

def line_ocorr_por_ano(df: pd.DataFrame, title: str):
    if "Ano" not in df.columns or df["Ano"].dropna().empty:
        return None
    ocorr_ano = df.groupby("Ano").size().reset_index(name="Ocorrências")
    if ocorr_ano.empty:
        return None
    fig = px.line(ocorr_ano, x="Ano", y="Ocorrências", markers=True, title=title)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig

def bar_ocorr_por_mes(df: pd.DataFrame, title: str):
    if "Mes" not in df.columns or df["Mes"].dropna().empty:
        return None
    ocorr_mes = df.groupby("Mes").size().reset_index(name="Ocorrências")
    if ocorr_mes.empty:
        return None
    fig = px.bar(ocorr_mes, x="Mes", y="Ocorrências", title=title, color="Ocorrências", color_continuous_scale="Blues")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig

def line_class_por_ano(df: pd.DataFrame, title: str):
    if "Ano" not in df.columns or "Classificacao_da_Ocorrencia" not in df.columns:
        return None
    tmp = df.dropna(subset=["Ano", "Classificacao_da_Ocorrencia"])
    if tmp.empty:
        return None
    class_ano = tmp.groupby(["Ano", "Classificacao_da_Ocorrencia"]).size().reset_index(name="Ocorrências")
    if class_ano.empty:
        return None
    fig = px.line(
        class_ano,
        x="Ano",
        y="Ocorrências",
        color="Classificacao_da_Ocorrencia",
        markers=True,
        title=title
    )
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig

# =========================
# APP TITLE
# =========================
st.markdown("# ✈️ Painel de Ocorrências Aeronáuticas")

# =========================
# LOAD LOCAL ONLY (sem upload) - UI mínima
# =========================
BASE_DIR = Path(__file__).parent
default_path = BASE_DIR / "V_OCORRENCIA_AMPLA.xlsx"

path_str = st.sidebar.text_input("", value=str(default_path), label_visibility="collapsed")
path = Path(path_str)

if not path.exists():
    st.error("Arquivo de dados não encontrado. Verifique o caminho no sidebar.")
    st.stop()

@st.cache_data(show_spinner=False)
def read_and_preprocess_excel(file_path_str: str):
    p = Path(file_path_str)
    raw_df = pd.read_excel(p)
    return preprocess(raw_df)

df = read_and_preprocess_excel(str(path))

# =========================
# FILTERS
# =========================
st.sidebar.header("🔎 Filtros")

dff = df.copy()

if "Ano" in dff.columns and dff["Ano"].dropna().size:
    ano_min = int(dff["Ano"].min())
    ano_max = int(dff["Ano"].max())
    anos = st.sidebar.slider("Período (Ano)", ano_min, ano_max, (ano_min, ano_max))
    dff = dff[dff["Ano"].between(anos[0], anos[1])]

if "UF" in dff.columns:
    ufs_all = sorted([u for u in dff["UF"].dropna().unique().tolist() if str(u).strip() != ""])
    ufs = st.sidebar.multiselect("UF", ufs_all)
    if ufs:
        dff = dff[dff["UF"].isin(ufs)]

# =========================
# TABS (8)
# =========================
tab_doc, tab_met, tab_map, tab_class, tab_ops, tab_10y, tab_table, tab_refs = st.tabs([
    "📄 Documentação",
    "🧪 Materiais & Métodos",
    "🗺️ Mapa Exploratório",
    "📊 Classificação (KPIs)",
    "🛫 Operações & Danos",
    "📆 Últimos 10 anos",
    "🔎 Tabela & Busca",
    "📚 Referências",
])

with tab_doc:
    st.markdown("""
## 📄 Documentação
                
#### Objetivo
                
O painel tem por objetivo permitir a exploração visual e analítica de registros de ocorrências aeronáuticas, com ênfase na identificação de padrões temporais, geográficos e operacionais.

#### Metodologia
                
Os dados são submetidos a procedimentos de curadoria, incluindo padronização de tipos, conversão temporal e seleção de variáveis relevantes ao método. As análises são realizadas por meio de agregações categóricas, séries temporais e visualizações espaciais.

#### Limitações
                
Os resultados dependem da qualidade e completude das notificações oficiais, não sendo indicativos de causalidade ou responsabilidade.

#### Escopo
                
O sistema destina-se a análises exploratórias e apoio à decisão.

#### Fonte dos Dados

Os dados utilizados neste painel foram obtidos a partir da base oficial de ocorrências aeronáuticas disponibilizada pela **Agência Nacional de Aviação Civil (ANAC)**.

**Título:** Ocorrências Aeronáuticas (dados abertos)  
**Origem:** ANAC – Dados Abertos  

> A base contém registros de ocorrências aeronáuticas notificadas, com variáveis referentes a localização, classificações, aeronaves, operação e demais campos relacionados à segurança operacional.

**Tratamento:** limpeza e padronização (tipos e strings)

### Observações
- Ocorrências dependem de notificação oficial
- Os dados não indicam causa ou responsabilidade
- Uso exploratório e apoio à decisão
""")

with tab_met:
    st.markdown(""" Materiais e Métodos

### Conjunto de Dados
O sistema utiliza um conjunto de dados estruturados contendo registros de ocorrências aeronáuticas, empregados como insumo para análise exploratória e visualização de padrões. A base é processada localmente, não havendo transmissão ou persistência externa dos dados durante a execução do aplicativo.

Antes da utilização, os dados foram submetidos a um processo de curadoria, com o objetivo de assegurar consistência, padronização e adequação ao método proposto.

### Tratamento e Curadoria dos Dados
O tratamento dos dados incluiu, de forma não exaustiva:
- seleção de variáveis relevantes às análises realizadas;
- padronização de campos textuais (normalização de capitalização e remoção de inconsistências);
- conversão de campos temporais para formatos apropriados;
- exclusão de variáveis e registros considerados não essenciais ao funcionamento do método;
- tratamento de valores ausentes em campos que não comprometem a validade das análises.

Os procedimentos adotados visam garantir uniformidade dos dados, sem alterar a natureza informacional das ocorrências registradas.

### Metodologia de Análise
As análises são conduzidas por meio de abordagens exploratórias, baseadas em:
- agregações categóricas (por tipo de ocorrência, operação, fase da operação, operador e características da aeronave);
- análises temporais, considerando séries anuais e mensais;
- visualizações espaciais, incluindo representação por unidades federativas e por coordenadas geográficas quando disponíveis.

Os resultados são apresentados de forma interativa, permitindo a aplicação de filtros temporais e geográficos para segmentação dos dados.

### Visualização e Interação
O sistema disponibiliza diferentes formas de visualização, tais como:
- gráficos de barras para análise comparativa de frequências;
- gráficos de linhas para avaliação de tendências temporais;
- gráficos de distribuição para avaliação de proporções;
- mapas interativos para análise espacial das ocorrências.

As visualizações são atualizadas dinamicamente de acordo com os filtros aplicados pelo usuário.

### Escopo e Limitações
O método proposto tem caráter exploratório e descritivo, destinando-se à identificação de padrões e tendências nos dados analisados. Os resultados apresentados não implicam inferência causal, atribuição de responsabilidade ou conclusões periciais.

A qualidade das análises depende da completude, consistência e precisão das informações originalmente registradas na base de dados utilizada.""")

with tab_map:
    st.subheader("🗺️ Mapa Exploratório")

    view_mode = st.radio(
        "Visualização do mapa",
        ["Pontos (Latitude / Longitude)", "Por Estado (UF)"],
        horizontal=True
    )

    if view_mode == "Pontos (Latitude / Longitude)":
        fig_pts = map_points(dff)
        if fig_pts:
            st.plotly_chart(fig_pts, use_container_width=True)
        else:
            st.info("Sem coordenadas válidas para exibir pontos.")
    else:
        fig_uf = choropleth_uf(dff)
        if fig_uf:
            st.plotly_chart(fig_uf, use_container_width=True)
        else:
            st.info("Sem dados suficientes para mapa por UF.")

with tab_class:
    st.subheader("📊 Visão Geral")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Ocorrências", len(dff))
    k2.metric("Estados (UF)", int(dff["UF"].nunique()) if "UF" in dff.columns else 0)
    k3.metric("Modelos (ICAO)", int(dff["ICAO"].nunique()) if "ICAO" in dff.columns else 0)
    if "Ano" in dff.columns and dff["Ano"].notna().any():
        k4.metric("Período", f"{int(dff['Ano'].min())}–{int(dff['Ano'].max())}")
    else:
        k4.metric("Período", "-")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        fig1 = bar_top(dff, "Fase_da_Operacao", 15, "Top Fases Envolvidas")
        if fig1: st.plotly_chart(fig1, use_container_width=True)
    with c2:
        fig2 = bar_top(dff, "Operacao", 15, "Tipos de Operação Mais Frequentes")
        if fig2: st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    c3, c4 = st.columns(2)
    with c3:
        fig3 = pie_dist(dff, "Danos_a_Aeronave", "Distribuição dos Danos")
        if fig3: st.plotly_chart(fig3, use_container_width=True)
    with c4:
        if "Aerodromo_de_Origem" in dff.columns or "Aerodromo_de_Destino" in dff.columns:
            aero = pd.concat([
                dff.get("Aerodromo_de_Origem", pd.Series(dtype="object")),
                dff.get("Aerodromo_de_Destino", pd.Series(dtype="object")),
            ]).dropna()
            if not aero.empty:
                topa = aero.value_counts().head(20)
                fig4 = px.bar(
                    topa,
                    orientation="h",
                    title="Top 20 Aeródromos Relacionados (Origem + Destino)",
                    color=topa.values,
                    color_continuous_scale="Blues"
                )
                # ✅ maior em cima
                fig4.update_yaxes(categoryorder="total ascending")
                fig4.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info("Sem aeródromos para exibir.")
        else:
            st.info("Colunas de aeródromo não encontradas.")

with tab_ops:
    st.subheader("🛫 Operações (extras)")

    c1, c2 = st.columns(2)
    with c1:
        fig = bar_top(dff, "Tipo_de_Ocorrencia", 20, "Top Tipos de Ocorrência")
        if fig: st.plotly_chart(fig, use_container_width=True)

        fig = bar_top(dff, "Classificacao_da_Ocorrencia", 20, "Top Classificações")
        if fig: st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig = bar_top(dff, "Operador_Padronizado", 20, "Top Operadores (Padronizado)")
        if fig: st.plotly_chart(fig, use_container_width=True)

        fig = bar_top(dff, "Modelo", 20, "Top Modelos")
        if fig: st.plotly_chart(fig, use_container_width=True)

with tab_10y:
    st.subheader("📆 Panorama dos Últimos 10 Anos")

    if "Ano" not in dff.columns or dff["Ano"].dropna().empty:
        st.info("Sem coluna Ano para calcular últimos 10 anos.")
    else:
        ano_max = int(dff["Ano"].max())
        ultimos_10 = ano_max - 9
        df10 = dff[dff["Ano"] >= ultimos_10]

        st.write(f"**Período analisado:** {ultimos_10}–{ano_max}")
        st.write(f"**Total de ocorrências:** {df10.shape[0]}")

        fig = line_ocorr_por_ano(df10, "Ocorrências por Ano (Últimos 10 anos)")
        if fig: st.plotly_chart(fig, use_container_width=True)

        fig = bar_ocorr_por_mes(df10, "Ocorrências por Mês (Somatório 10 anos)")
        if fig: st.plotly_chart(fig, use_container_width=True)

        fig = line_class_por_ano(df10, "Classificação das Ocorrências ao Longo dos Últimos 10 anos")
        if fig: st.plotly_chart(fig, use_container_width=True)

with tab_table:
    st.subheader("🔎 Tabela & Busca")
    q = st.text_input("Buscar (Municipio / Historico / Operador / Modelo / Matricula)")
    dd = dff.copy()

    if q.strip():
        ql = q.strip().lower()
        cols = [c for c in ["Municipio","Historico","Operador_Padronizado","Operador","Modelo","Matricula"] if c in dd.columns]
        if cols:
            mask = False
            for c in cols:
                mask = mask | dd[c].fillna("").astype(str).str.lower().str.contains(ql, na=False)
            dd = dd[mask]

    st.caption(f"Mostrando {len(dd)} registros")
    st.dataframe(dd, use_container_width=True, height=520)

with tab_refs:
    st.subheader("📚 Referências")
    st.markdown("""
    Agência Nacional de Aviação Civil (ANAC)**  
  Dados Abertos – Ocorrências Aeronáuticas  
  https://www.gov.br/anac/pt-br/acesso-a-informacao/dados-abertos/areas-de-atuacao/seguranca-operacional/ocorrencias-aeronauticas
- **GeoJSON UFs:** Click That Hood / Code for America  
- **Dataset:** (adicione a referência oficial aqui)
- **Dicionário de dados:** (adicione quando tiver)
""")