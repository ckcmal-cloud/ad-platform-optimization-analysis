from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="광고 전략 추천 대시보드",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_CANDIDATES = [
    BASE_DIR / "data",
    BASE_DIR.parent / "data",
]

MASTER_FILE = "advertiser_strategy_master.csv"
LIFECYCLE_FILE = "ad_lifecycle_summary.csv"
RECOMMENDATION_FILE = "domain_recommendation.csv"

DOMAIN_ORDER = ["엔터", "커머스", "금융", "라이프", "기타"]
WEEKDAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"]
PRICE_ORDER = ["저단가(1~50)", "중단가(51~200)", "고단가(201~500)", "프리미엄(501+)", "미상", "미분류"]
TYPE_ORDER = ["설치형", "실행형", "참여형", "클릭형", "페이스북", "트위터", "인스타그램", "퀘스트", "유튜브", "네이버", "CPS(구매)"]
BUDGET_STRATEGY = {
    "소규모(~10만)": "참여형 테스트로 반응 확인",
    "중규모(10~50만)": "설치형/실행형 검증 운영",
    "대규모(50~200만)": "실행형 중심 전환 확대",
    "초대형(200만+)": "CPA 중심 대량 확보",
}

CARD_STYLE = """
<style>
.block-container {padding-top: 2rem; max-width: 1280px;}
.metric-card {
    border: 1px solid #243247;
    background: linear-gradient(180deg, #162234 0%, #101722 100%);
    border-radius: 8px;
    padding: 16px 18px;
    min-height: 138px;
}
.metric-card h4 {margin: 0 0 12px 0; font-size: 18px; color: #f8fafc;}
.metric-card .sub {font-size: 13px; color: #cbd5e1; line-height: 1.45;}
.metric-card .score {font-size: 18px; color: #facc15; font-weight: 700; margin-top: 10px;}
.metric-card .cycle {font-size: 13px; color: #bfdbfe; margin-top: 6px;}
.small-note {color: #94a3b8; font-size: 13px;}
</style>
"""
st.markdown(CARD_STYLE, unsafe_allow_html=True)


def normalize_price_label(value):
    text = str(value)
    if text in {"nan", "None", ""}:
        return "미상"
    return text


def load_csv(filename: str) -> pd.DataFrame:
    checked_paths = [data_dir / filename for data_dir in DATA_CANDIDATES]
    path = next((candidate for candidate in checked_paths if candidate.exists()), None)
    if path is None:
        locations = "\n".join(str(candidate) for candidate in checked_paths)
        raise FileNotFoundError(f"{filename} 파일을 찾을 수 없습니다. 확인한 위치:\n{locations}")
    return pd.read_csv(path, encoding="utf-8-sig")


def safe_div(num, den, scale=1.0):
    if isinstance(num, (pd.Series, np.ndarray)) or isinstance(den, (pd.Series, np.ndarray)):
        return np.where((pd.notna(den)) & (den != 0), num / den * scale, 0)
    if den is None or pd.isna(den) or den == 0:
        return 0.0
    return num / den * scale


def fmt_int(value):
    return f"{float(value):,.0f}"


def fmt_money(value):
    return f"{float(value):,.0f}원"


def fmt_pct(value):
    return f"{float(value):,.2f}%"


def sort_order(df, col, order):
    order_map = {name: idx for idx, name in enumerate(order)}
    out = df.copy()
    out["_order"] = out[col].map(order_map).fillna(len(order_map))
    return out.sort_values(["_order", col]).drop(columns="_order")


def spend_band(value):
    if value <= 100_000:
        return "소규모(~10만)"
    if value <= 500_000:
        return "중규모(10~50만)"
    if value <= 2_000_000:
        return "대규모(50~200만)"
    return "초대형(200만+)"


def recommended_cycle(p80_day):
    if pd.isna(p80_day):
        return "점검 필요"
    if p80_day <= 14:
        return "1~2주 교체"
    if p80_day <= 21:
        return "2~3주 점검"
    return "3주 이상 유지"


def load_data():
    master = load_csv(MASTER_FILE)
    lifecycle = load_csv(LIFECYCLE_FILE)
    recommendation = load_csv(RECOMMENDATION_FILE)

    required_master = ["ad_id", "ads_name", "domain", "ads_type_name", "date", "weekday", "price_segment", "total_cost", "click_cnt", "conv_cnt", "non_conv_cnt"]
    required_life = ["domain", "p80_day"]
    required_rec = ["domain", "rank", "recommended_type", "recommended_price_segment", "strategy_message"]
    for label, frame, cols in [(MASTER_FILE, master, required_master), (LIFECYCLE_FILE, lifecycle, required_life), (RECOMMENDATION_FILE, recommendation, required_rec)]:
        missing = [col for col in cols if col not in frame.columns]
        if missing:
            st.error(f"{label} 필수 컬럼 누락: {', '.join(missing)}")
            st.stop()

    master["date"] = pd.to_datetime(master["date"], errors="coerce")
    master = master.dropna(subset=["date"]).copy()
    for col in ["total_cost", "click_cnt", "conv_cnt", "non_conv_cnt", "ads_type", "kpi_click_cnt", "kpi_conv_cnt", "kpi_non_conv_cnt"]:
        if col in master.columns:
            master[col] = pd.to_numeric(master[col], errors="coerce")
    for col in ["total_cost", "click_cnt", "conv_cnt", "non_conv_cnt"]:
        master[col] = master[col].fillna(0)
    master["price_segment"] = master["price_segment"].map(normalize_price_label)
    lifecycle["p80_day"] = pd.to_numeric(lifecycle["p80_day"], errors="coerce")
    recommendation["rank"] = pd.to_numeric(recommendation["rank"], errors="coerce").fillna(0).astype(int)
    recommendation["recommended_price_segment"] = recommendation["recommended_price_segment"].map(normalize_price_label)
    return master, lifecycle, recommendation


def aggregate(df, by):
    out = df.groupby(by, dropna=False).agg(
        unique_ads=("ad_id", "nunique"),
        total_cost=("total_cost", "sum"),
        click_cnt=("click_cnt", "sum"),
        conv_cnt=("conv_cnt", "sum"),
        non_conv_cnt=("non_conv_cnt", "sum"),
    ).reset_index()
    out["cvr"] = safe_div(out["conv_cnt"], out["click_cnt"], 100)
    out["cpa"] = safe_div(out["total_cost"], out["conv_cnt"])
    out["conv_per_ad"] = safe_div(out["conv_cnt"], out["unique_ads"])
    out["dropout_rate"] = safe_div(out["non_conv_cnt"], out["click_cnt"], 100)
    return out


def strategy_score_table(df):
    base = aggregate(df, ["domain", "ads_type_name"])
    domain_conv = base.groupby("domain")["conv_cnt"].transform("sum")
    domain_cost = base.groupby("domain")["total_cost"].transform("sum")
    base["conv_share"] = safe_div(base["conv_cnt"], domain_conv, 100)
    base["cost_share"] = safe_div(base["total_cost"], domain_cost, 100)
    base["score"] = np.sqrt(base["conv_share"] * base["cost_share"])
    return base


def representative_ad(df, domain, ad_type):
    sample = df[(df["domain"] == domain) & (df["ads_type_name"] == ad_type)].copy()
    if sample.empty or "ads_name" not in sample.columns:
        return "-"
    ad = sample.groupby(["ad_id", "ads_name"], as_index=False).agg(conv_cnt=("conv_cnt", "sum"), click_cnt=("click_cnt", "sum"))
    ad["cvr"] = safe_div(ad["conv_cnt"], ad["click_cnt"], 100)
    ad = ad.sort_values(["conv_cnt", "cvr"], ascending=False)
    return "-" if ad.empty else str(ad.iloc[0]["ads_name"])


def caution_type(df, domain):
    part = aggregate(df[df["domain"] == domain], ["ads_type_name"])
    if part.empty:
        return "-"
    return str(part.sort_values(["non_conv_cnt", "dropout_rate"], ascending=False).iloc[0]["ads_type_name"])


def domain_priority_table(df):
    score = strategy_score_table(df)
    rows = []
    for domain, part in score.groupby("domain"):
        top = part.sort_values(["score", "conv_cnt"], ascending=False).head(3)
        cells = top["ads_type_name"].astype(str).tolist()
        while len(cells) < 3:
            cells.append("-")
        top1 = top.iloc[0] if not top.empty else None
        rows.append({
            "도메인": domain,
            "우선유형 1": cells[0],
            "우선유형 2": cells[1],
            "우선유형 3": cells[2],
            "주의유형": caution_type(df, domain),
            "대표 광고": representative_ad(df, domain, cells[0]),
            "전략 근거": "-" if top1 is None else f"{cells[0]}: 전략 중요도 {top1['score']:.1f}점 / 전환 {fmt_int(top1['conv_cnt'])}",
        })
    return sort_order(pd.DataFrame(rows), "도메인", DOMAIN_ORDER)


def price_rank_table(df):
    base = aggregate(df, ["domain", "price_segment"])
    rows = []
    for domain, part in base.groupby("domain"):
        ranked = part.sort_values(["conv_per_ad", "conv_cnt"], ascending=False)
        top = ranked["price_segment"].astype(str).tolist()
        while len(top) < 3:
            top.append("-")
        rows.append({
            "도메인": domain,
            "1순위": top[0],
            "2순위": top[1],
            "주의구간": top[-1],
            "전략 근거": f"{top[0]}에서 광고당 전환 기여가 가장 큼",
        })
    return sort_order(pd.DataFrame(rows), "도메인", DOMAIN_ORDER)


def render_kpis(df, kpi_source=None):
    source = kpi_source if kpi_source is not None else df
    if {"kpi_click_cnt", "kpi_conv_cnt"}.issubset(source.columns):
        total_click = float(source["kpi_click_cnt"].dropna().max())
        total_conv = float(source["kpi_conv_cnt"].dropna().max())
    else:
        total_click = df["click_cnt"].sum()
        total_conv = df["conv_cnt"].sum()
    total_cost = df["total_cost"].sum()
    unique_ads = df["ad_id"].nunique()
    cols = st.columns(5)
    cols[0].metric("광고 수", fmt_int(unique_ads))
    cols[1].metric("클릭", fmt_int(total_click))
    cols[2].metric("전환", fmt_int(total_conv))
    cols[3].metric("CVR", fmt_pct(safe_div(total_conv, total_click, 100)))
    cols[4].metric("CPA", fmt_money(safe_div(total_cost, total_conv)))


def render_strategy_cards(df, lifecycle):
    score = strategy_score_table(df)
    life_map = lifecycle.set_index("domain")["p80_day"].to_dict()
    card_cols = st.columns(5)
    for idx, domain in enumerate(DOMAIN_ORDER):
        part = score[score["domain"] == domain].sort_values(["score", "conv_cnt"], ascending=False)
        if part.empty:
            continue
        top = part.iloc[0]
        price = df[(df["domain"] == domain) & (df["ads_type_name"] == top["ads_type_name"])]
        price_label = price.groupby("price_segment")["conv_cnt"].sum().sort_values(ascending=False).index[0] if not price.empty else "-"
        p80 = life_map.get(domain, np.nan)
        html = f"""
        <div class="metric-card">
            <h4>{domain}</h4>
            <div class="sub">운영 중심 유형 {top['ads_type_name']} / {price_label}</div>
            <div class="score">전략 중요도 {top['score']:.1f}점</div>
            <div class="sub">{top['conv_cnt']:,.0f}건 전환 기여</div>
            <div class="cycle">교체주기 {recommended_cycle(p80)}</div>
        </div>
        """
        card_cols[idx].markdown(html, unsafe_allow_html=True)


def bar_chart(df, x, y, title, color="#2563eb", horizontal=False):
    if horizontal:
        fig = go.Figure(go.Bar(x=df[y], y=df[x], orientation="h", text=df[y], marker_color=color, cliponaxis=False))
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
    else:
        fig = go.Figure(go.Bar(x=df[x], y=df[y], text=df[y], marker_color=color, cliponaxis=False))
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(title=title, height=360, margin=dict(l=20, r=20, t=55, b=45), showlegend=False)
    return fig


def heatmap(df, row, col, value, title, colorscale="YlGnBu", height=420):
    pivot = df.pivot_table(index=row, columns=col, values=value, aggfunc="sum", fill_value=0)
    if row == "domain":
        pivot = pivot.reindex([d for d in DOMAIN_ORDER if d in pivot.index])
    if col in {"ads_type_name", "weekday"}:
        order = TYPE_ORDER if col == "ads_type_name" else WEEKDAY_ORDER
        pivot = pivot.reindex(columns=[v for v in order if v in pivot.columns])
    fig = go.Figure(go.Heatmap(z=pivot.values, x=pivot.columns.astype(str), y=pivot.index.astype(str), text=np.round(pivot.values, 1), texttemplate="%{text}", colorscale=colorscale, colorbar={"title": value}))
    fig.update_layout(title=title, height=height, margin=dict(l=20, r=20, t=55, b=45))
    return fig


def render_strategy_summary(df, lifecycle):
    st.subheader("도메인별 전략 우선유형")
    render_strategy_cards(df, lifecycle)
    domain = sort_order(aggregate(df, ["domain"]), "domain", DOMAIN_ORDER)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(bar_chart(domain, "domain", "conv_cnt", "도메인별 총 전환"), use_container_width=True)
    with c2:
        fig = go.Figure(go.Scatter(x=domain["cpa"], y=domain["cvr"], text=domain["domain"], mode="markers+text", textposition="top center", marker={"size": 15, "color": "#38bdf8"}))
        fig.update_layout(title="도메인별 CPA x CVR 포지션", xaxis_title="CPA", yaxis_title="CVR(%)", height=360)
        st.plotly_chart(fig, use_container_width=True)
    st.subheader("도메인별 광고유형 전략 우선순위")
    st.dataframe(domain_priority_table(df), use_container_width=True, hide_index=True)


def render_efficiency(df):
    st.subheader("효율 분석")
    c1, c2 = st.columns(2)
    with c1:
        selected_types = st.multiselect(
            "광고유형",
            sorted(df["ads_type_name"].dropna().unique().tolist()),
            default=sorted(df["ads_type_name"].dropna().unique().tolist()),
            key="efficiency_type_filter",
        )
    with c2:
        selected_prices = st.multiselect(
            "단가구간",
            sorted(df["price_segment"].dropna().unique().tolist()),
            default=sorted(df["price_segment"].dropna().unique().tolist()),
            key="efficiency_price_filter",
        )
    view = df[df["ads_type_name"].isin(selected_types) & df["price_segment"].isin(selected_prices)].copy()
    type_domain = aggregate(view, ["domain", "ads_type_name"])
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(heatmap(type_domain, "domain", "ads_type_name", "cvr", "도메인 x 광고유형 CVR 히트맵"), use_container_width=True)
    with c2:
        type_cost = aggregate(view, ["ads_type_name"]).sort_values("cpa")
        st.plotly_chart(bar_chart(type_cost, "ads_type_name", "cpa", "광고유형(1~12)별 전환당 비용(CPA)", "#f97316"), use_container_width=True)
    c1, c2 = st.columns([1, 1.2])
    with c1:
        price = sort_order(aggregate(view, ["price_segment"]), "price_segment", PRICE_ORDER)
        st.plotly_chart(bar_chart(price, "price_segment", "conv_per_ad", "단가구간별 광고당 전환", "#22c55e"), use_container_width=True)
    with c2:
        type_sum = aggregate(view, ["ads_type_name"]).sort_values("conv_cnt", ascending=False)
        fig = go.Figure()
        fig.add_bar(x=type_sum["ads_type_name"], y=type_sum["conv_cnt"], name="전환수", marker_color="#22c55e")
        fig.add_bar(x=type_sum["ads_type_name"], y=type_sum["total_cost"], name="누적비용", marker_color="#f97316", yaxis="y2")
        fig.update_layout(title="광고유형별 전환수 및 누적비용", height=360, yaxis2={"overlaying": "y", "side": "right"}, barmode="group")
        st.plotly_chart(fig, use_container_width=True)
    st.subheader("도메인별 단가 전략 랭킹")
    st.dataframe(price_rank_table(view), use_container_width=True, hide_index=True)


def render_operation(df, lifecycle, kpi_source=None):
    selected_domain = st.selectbox("전환 구조 도메인 필터", ["전체"] + DOMAIN_ORDER, key="operation_domain_filter")
    view = df.copy() if selected_domain == "전체" else df[df["domain"] == selected_domain].copy()
    st.subheader("도메인별 운영 점검주기")
    cols = st.columns(5)
    life_map = lifecycle.set_index("domain")["p80_day"].to_dict()
    for idx, domain in enumerate(DOMAIN_ORDER):
        cols[idx].metric(domain, recommended_cycle(life_map.get(domain, np.nan)))
    c1, c2 = st.columns(2)
    if selected_domain == "전체" and kpi_source is not None and {"kpi_click_cnt", "kpi_conv_cnt", "kpi_non_conv_cnt"}.issubset(kpi_source.columns):
        total_click = float(kpi_source["kpi_click_cnt"].dropna().max())
        total_conv = float(kpi_source["kpi_conv_cnt"].dropna().max())
        total_non_conv = float(kpi_source["kpi_non_conv_cnt"].dropna().max())
    else:
        total_click = view["click_cnt"].sum()
        total_conv = view["conv_cnt"].sum()
        total_non_conv = view["non_conv_cnt"].sum()
    with c1:
        funnel = pd.DataFrame({"단계": ["전체 클릭", "전환", "이탈"], "수치": [total_click, total_conv, total_non_conv]})
        st.plotly_chart(bar_chart(funnel, "단계", "수치", "전체/전환/이탈 규모", "#64748b", horizontal=True), use_container_width=True)
    with c2:
        summary = pd.DataFrame({"지표": ["평균 CVR", "평균 CPA", "반응 광고 비율"], "수치": [fmt_pct(safe_div(total_conv, total_click, 100)), fmt_money(safe_div(view["total_cost"].sum(), total_conv)), fmt_pct(safe_div((view["click_cnt"] > 0).sum(), view["ad_id"].nunique(), 100))]})
        st.subheader("전환구조 요약")
        st.dataframe(summary, use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    with c1:
        risk = aggregate(view, ["ads_type_name"]).sort_values(["dropout_rate", "non_conv_cnt"], ascending=False).head(5)
        risk_table = risk.rename(columns={"ads_type_name": "광고유형", "dropout_rate": "이탈률", "click_cnt": "클릭", "non_conv_cnt": "이탈"})[["광고유형", "이탈률", "클릭", "이탈"]]
        st.subheader("이탈 취약 광고유형")
        st.dataframe(risk_table.style.format({"이탈률": "{:.2f}%", "클릭": "{:,.0f}", "이탈": "{:,.0f}"}), use_container_width=True, hide_index=True)
    with c2:
        weekday_type = aggregate(view, ["weekday", "ads_type_name"])
        st.plotly_chart(heatmap(weekday_type, "weekday", "ads_type_name", "conv_cnt", "요일 x 광고유형 전환수 히트맵", "YlGnBu"), use_container_width=True)
    st.subheader("예산별 운영 방식")
    bcols = st.columns(4)
    for idx, (band, message) in enumerate(BUDGET_STRATEGY.items()):
        bcols[idx].markdown(f"<div class='metric-card'><h4>{band}</h4><div class='sub'>{message}</div></div>", unsafe_allow_html=True)


master, lifecycle, recommendation = load_data()

with st.sidebar:
    st.header("필터")
    min_date = master["date"].min().date()
    max_date = master["date"].max().date()
    date_range = st.date_input("전체 날짜", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="sidebar_date_filter")
    domain_options = [d for d in DOMAIN_ORDER if d in master["domain"].dropna().unique()]
    selected_domains = st.multiselect("도메인", domain_options, default=domain_options, key="sidebar_domain_filter")
    with st.expander("고급 필터"):
        type_options = sorted(master["ads_type_name"].dropna().unique().tolist())
        selected_types = st.multiselect("광고유형", type_options, default=type_options, key="sidebar_type_filter")
        price_options = sorted(master["price_segment"].dropna().unique().tolist())
        selected_prices = st.multiselect("단가구간", price_options, default=price_options, key="sidebar_price_filter")

is_full_filter = (
    len(date_range) == 2
    and date_range[0] == min_date
    and date_range[1] == max_date
    and set(selected_domains) == set(domain_options)
    and set(selected_types) == set(type_options)
    and set(selected_prices) == set(price_options)
)

filtered = master.copy()
if len(date_range) == 2:
    filtered = filtered[(filtered["date"].dt.date >= date_range[0]) & (filtered["date"].dt.date <= date_range[1])]
filtered = filtered[filtered["domain"].isin(selected_domains)]
filtered = filtered[filtered["ads_type_name"].isin(selected_types)]
filtered = filtered[filtered["price_segment"].isin(selected_prices)]

st.title("광고 전략 추천 대시보드")
st.caption("도메인별 광고유형 구조와 운영 중심 유형을 한눈에 확인하는 대시보드")
if filtered.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()
render_kpis(filtered, master if is_full_filter else None)
st.caption("상단 KPI는 현재 필터 기준입니다. 전략 상세 분석은 도메인·광고유형 매칭 가능 데이터 기준입니다.")
strategy_tab, efficiency_tab, operation_tab = st.tabs(["전략 요약", "효율 분석", "운영 전략"])
with strategy_tab:
    render_strategy_summary(filtered, lifecycle)
with efficiency_tab:
    render_efficiency(filtered)
with operation_tab:
    render_operation(filtered, lifecycle, master if is_full_filter else None)
