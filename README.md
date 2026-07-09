# Painel Macro US — SocInvest

Painel em Streamlit com os principais indicadores da economia americana, para a Central de Ferramentas da SocInvest.

## Abas e indicadores

- **📊 Visão Geral** — KPIs dos últimos dados de todos os blocos
- **🏭 ISM** — Manufacturing e Services PMI + subíndices (New Orders, Production/Business Activity, Employment, Prices Paid), com linha de 50 (expansão × contração)
- **💵 Inflação** — CPI (Headline, Core, Shelter, Serviços ex-energia, Serviços ex-shelter/supercore, Bens núcleo, Energia, Alimentos), **Core PCE** (métrica-alvo do Fed, linha de 2%) e PPI Final Demand — em YoY ou MoM
- **🏦 Juros** — Fed Funds, Treasuries 2 e 10 anos, spread 10a−2a (inversão da curva) e breakeven de inflação 10 anos
- **📈 GDP** — QoQ anualizado (SAAR), YoY e nível real
- **👷 Payroll** — criação de vagas MoM (+ média 3m), initial claims semanais em barras (+ média 4 semanas em linha), desemprego, participação, salário médio/hora (MoM e YoY), revisão de 2 meses (via upload)
- **🔄 JOLTS** — vagas abertas × hires (milhões, eixo único), vagas por desempregado, taxas de vagas/hires/quits/layoffs

## Repercussão na imprensa

Cada aba tem um expander **📰 Repercussão na imprensa** com as manchetes recentes que casam com o tema (payroll → notícias de emprego, Inflação → CPI/PCE, etc.). Fontes via RSS público, sem API key: CNBC Economy, Investing.com (indicadores econômicos), MarketWatch e press releases do Federal Reserve. Cache de 30 minutos. A Visão Geral mostra o feed completo sem filtro.

## Comentários por data

Anotações pós-divulgação vivem em `dados/comentarios.csv` (colunas `Date, Aba, Comentário`) e aparecem num expander na aba correspondente. Edite na tabela da **Visão Geral**:

- **💾 Salvar** grava direto no arquivo (rodando localmente)
- **⬇️ Baixar** exporta o CSV — no Streamlit Cloud o filesystem é efêmero, então para persistir é preciso commitar o arquivo baixado no repositório

## Fontes de dados (automáticas)

| Bloco | Fonte | Como |
|---|---|---|
| Inflação, Juros, GDP, Payroll, JOLTS | FRED (St. Louis Fed) | CSV público `fredgraph.csv` — **não precisa de API key** |
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

`CPIAUCSL`, `CPILFESL`, `CUSR0000SAH1`, `CUSR0000SASLE`, `CUSR0000SASL2RS`, `CUSR0000SACL1E`, `CPIENGSL`, `CPIUFDSL`, `PCEPI`, `PCEPILFE`, `PPIFIS`, `GDPC1`, `A191RL1Q225SBEA`, `A191RO1Q156NBEA`, `PAYEMS`, `UNRATE`, `CES0500000003`, `CIVPART`, `ICSA`, `FEDFUNDS`, `DGS2`, `DGS10`, `T10Y2Y`, `T10YIE`, `JTSJOL`, `JTSHIL`, `JTSJOR`, `JTSHIR`, `JTSQUR`, `JTSLDR`, `UNEMPLOY`

DBnomics (ISM): `pmi`, `neword`, `production`, `employment`, `prices`, `nm-pmi`, `nm-busact`, `nm-neword`, `nm-employment`, `nm-prices` (série `in`/`pm`).
