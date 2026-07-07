# Painel Macro US — SocInvest

Painel em Streamlit com os principais indicadores da economia americana, para a Central de Ferramentas da SocInvest.

## Abas e indicadores

- **📊 Visão Geral** — KPIs dos últimos dados de todos os blocos
- **🏭 ISM** — Manufacturing e Services PMI + subíndices (New Orders, Production/Business Activity, Employment, Prices Paid), com linha de 50 (expansão × contração)
- **💵 CPI** — Headline, Core, Shelter, Serviços ex-energia, Serviços ex-shelter (proxy supercore), Bens núcleo, Energia, Alimentos — em YoY ou MoM
- **📈 GDP** — QoQ anualizado (SAAR), YoY e nível real
- **👷 Payroll** — criação de vagas MoM (+ média 3m), desemprego, participação, salário médio/hora (MoM e YoY), revisão de 2 meses (via upload)

## Fontes de dados (automáticas)

| Bloco | Fonte | Como |
|---|---|---|
| CPI, GDP, Payroll | FRED (St. Louis Fed) | CSV público `fredgraph.csv` — **não precisa de API key** |
| ISM | DBnomics (`ISM/...`) | API JSON gratuita |

Cache de 6 horas; botão **Atualizar dados** na barra lateral força recarga.

> ⚠️ O ISM no DBnomics tem histórico curto (começa em ~2020/21). Para histórico longo, use o upload.

## Modo híbrido (upload)

Carregue CSV/Excel na barra lateral com uma coluna de data + colunas de valores:

- Coluna com o **mesmo nome** de uma série do painel (ex.: `ISM Manufacturing PMI`) → sobrescreve datas coincidentes e **estende o histórico**
- `Revisão 2M (mil)` → habilita o gráfico de revisão do payroll (dado não disponível no FRED)
- Outros nomes → aparecem como séries extras na Visão Geral

Aceita decimal PT-BR (vírgula), `%` e exports tipo Bloomberg (preâmbulo de metadados é ignorado).

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`.

## Deploy no Streamlit Community Cloud

1. Suba a pasta para um repositório no GitHub
2. [share.streamlit.io](https://share.streamlit.io) → **New app** → selecione o repo e `app.py`
3. Use o link `https://<app>.streamlit.app` na Central de Ferramentas da SocInvest

## Séries usadas (FRED)

`CPIAUCSL`, `CPILFESL`, `CUSR0000SAH1`, `CUSR0000SASLE`, `CUSR0000SASL2RS`, `CUSR0000SACL1E`, `CPIENGSL`, `CPIUFDSL`, `GDPC1`, `A191RL1Q225SBEA`, `A191RO1Q156NBEA`, `PAYEMS`, `UNRATE`, `CES0500000003`, `CIVPART`

DBnomics (ISM): `pmi`, `neword`, `production`, `employment`, `prices`, `nm-pmi`, `nm-busact`, `nm-neword`, `nm-employment`, `nm-prices` (série `in`/`pm`).
