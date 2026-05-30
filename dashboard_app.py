import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import os
from plotly.subplots import make_subplots

st.set_page_config(page_title="운영중심 어뷰징 대시보드", layout="wide")

st.markdown("""
<style>
.kpi-card { background: linear-gradient(145deg,#0f172a,#111827); border-radius:16px; padding:24px; border:1px solid rgba(255,255,255,0.08); box-shadow:0 10px 25px rgba(0,0,0,0.35); }
.kpi-title { font-size:14px; color:#9CA3AF; margin-bottom:10px; }
.kpi-value { font-size:36px; font-weight:700; color:white; margin-bottom:6px; }
.kpi-desc { font-size:13px; color:#9CA3AF; margin-bottom:14px; }
.kpi-badge { display:inline-block; padding:6px 12px; border-radius:20px; font-size:12px; font-weight:600; }
.badge-red { background:#3b0d0d; color:#ef4444; }
.badge-yellow { background:#3b2f0d; color:#facc15; }
.badge-blue { background:#0b2545; color:#3b82f6; }
.badge-green { background:#062e1f; color:#22c55e; }
.segment-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:4px 0 18px 0; }
.segment-card { background:linear-gradient(145deg,#0f172a,#111827); border-radius:16px; padding:20px 22px; min-height:132px; display:flex; justify-content:space-between; gap:16px; align-items:flex-start; border:1px solid rgba(255,255,255,0.08); box-shadow:0 10px 25px rgba(0,0,0,0.35); }
.segment-title { font-size:20px; font-weight:800; margin-bottom:10px; }
.segment-desc { color:#d1d5db; font-size:14px; font-weight:700; line-height:1.45; }
.segment-value { font-size:30px; font-weight:800; text-align:right; }
.segment-count { color:#9ca3af; font-size:20px; font-weight:700; text-align:right; margin-top:6px; white-space:nowrap; }
@media (max-width: 1200px) { .segment-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width: 760px) { .segment-grid { grid-template-columns:1fr; } }
</style>
""", unsafe_allow_html=True)

card_start = '<div style="background:#0b172a; padding:20px; border-radius:12px; border:1px solid rgba(255,255,255,0.05); margin-bottom:20px;">'
card_end = "</div>"

@st.cache_data
def load_data():
    base_dir = Path(__file__).resolve().parent.parent / "data"
    m_df = pd.read_csv(os.path.join(base_dir, "dashboard_media_summary.csv"), encoding='utf-8-sig') if os.path.exists(os.path.join(base_dir, "dashboard_media_summary.csv")) else pd.DataFrame()
    t_df = pd.read_csv(os.path.join(base_dir, "dashboard_daily_trend.csv"), encoding='utf-8-sig') if os.path.exists(os.path.join(base_dir, "dashboard_daily_trend.csv")) else pd.DataFrame()
    s_df = pd.read_csv(os.path.join(base_dir, "dashboard_top_suspicious.csv"), encoding='utf-8-sig') if os.path.exists(os.path.join(base_dir, "dashboard_top_suspicious.csv")) else pd.DataFrame()
    return m_df, t_df, s_df

m_df, t_df, s_df = load_data()

if m_df.empty:
    st.error("데이터가 없습니다. build_abusing_data.py를 먼저 실행해 주세요.")
    st.stop()

# 운영 기준:
# 1) 정산/환수 금액은 행 단위 어뷰징 확정 click_key의 fraud_loss만 합산한다.
# 2) 매체 등급은 금액 산정 기준이 아니라 모니터링/제재 우선순위를 정하는 운영 리스크 지표다.
risk_label_map = {
    "경고": "주의",
    "매우위험": "어뷰징 확정",
}
m_df["Risk_Label"] = m_df["Risk_Label"].replace(risk_label_map)

# 사이드바 필터
st.sidebar.title("운영 필터 설정")
unique_mda = sorted(m_df['mda_idx'].dropna().unique())
m_opt = ["전체"] + [f"mda_{int(i)}" for i in unique_mda]
sel_mda = st.sidebar.selectbox("🔎 매체 선택", m_opt)

if sel_mda != "전체":
    tid = int(sel_mda.replace("mda_", ""))
    f_m_df = m_df[m_df['mda_idx'] == tid]
    f_t_df = t_df[t_df['mda_idx'] == tid] if not t_df.empty else pd.DataFrame()
    f_s_df = s_df[s_df['mda_idx'] == tid] if not s_df.empty else pd.DataFrame()
else:
    f_m_df = m_df
    f_t_df = t_df
    f_s_df = s_df

# KPI
st.title("🛡️ 광고 어뷰징 운영 관리 대시보드")
st.info("""
💡 **운영 가이드**

정산/환수 금액: 행(Row) 단위 어뷰징 확정 데이터 기준 산출  
운영 리스크 등급: 매체 모니터링 및 제재 우선순위 결정을 위한 핵심 지표
""")

c1, c2, c3, c4, c5 = st.columns(5)
loss = f_m_df['fraud_loss'].sum()
confirmed_cnt = int(f_m_df['extreme_cnt'].sum())
ex_r = (f_m_df['extreme_cnt'].sum() / f_m_df['total_conv'].sum()) * 100 if f_m_df['total_conv'].sum() > 0 else 0
danger_cnt = len(f_m_df[f_m_df['Risk_Label'].isin(['위험', '어뷰징 확정'])])

with c1:
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">확정 환수 대상 금액</div><div class="kpi-value">{loss:,.0f}원</div><div class="kpi-desc">어뷰징 확정 행의 earn_cost 합산 금액</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">확정 어뷰징 건수</div><div class="kpi-value">{confirmed_cnt:,}건</div><div class="kpi-desc">어뷰징 확정 판정을 받은 총 click_key 수</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">평균 극단값 비중</div><div class="kpi-value">{ex_r:.1f}%</div><div class="kpi-desc">전체 전환 수 대비 극단값(이상치) 발생 비율</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">고위험 운영 매체 수</div><div class="kpi-value">{danger_cnt}개</div><div class="kpi-desc">위험 이상 운영 리스크 매체 수</div></div>', unsafe_allow_html=True)
with c5:
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">조회 대상 매체 총수</div><div class="kpi-value">{len(f_m_df)}개</div><div class="kpi-desc">현재 설정된 필터 조건 내 활성 매체 수</div></div>', unsafe_allow_html=True)

st.divider()

# 시계열 트렌드
st.subheader("📈 날짜별 어뷰징 발생 트렌드 (Time-series)")
if not f_t_df.empty:
    daily = f_t_df.groupby('click_date').agg({'fraud_loss':'sum', 'extreme_cnt':'sum', 'total_conv':'sum'}).reset_index()
    period_start = pd.to_datetime(daily['click_date']).min().strftime('%Y-%m-%d')
    period_end = pd.to_datetime(daily['click_date']).max().strftime('%Y-%m-%d')
    st.caption(f"📅 분석 기간: {period_start} ~ {period_end} (시계열 데이터 기준)")
    daily['ratio'] = (daily['extreme_cnt'] / daily['total_conv']) * 100
    
    fig_t = make_subplots(specs=[[{"secondary_y": True}]])
    fig_t.add_trace(go.Scatter(x=daily['click_date'], y=daily['fraud_loss'], name="확정 환수 대상 금액", fill='tozeroy', line=dict(color='#ef4444', width=3)), secondary_y=False)
    fig_t.add_trace(go.Scatter(x=daily['click_date'], y=daily['ratio'], name="어뷰징 확정 비율(%)", line=dict(color='#facc15', dash='dot')), secondary_y=True)
    
    fig_t.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), height=400, margin=dict(t=20, b=20))
    fig_t.update_yaxes(title_text="확정 환수 대상 금액(원)", secondary_y=False)
    fig_t.update_yaxes(title_text="어뷰징 확정 비율(%)", secondary_y=True)
    st.plotly_chart(fig_t, use_container_width=True)
else:
    st.warning("시계열 데이터를 찾을 수 없습니다.")

st.divider()

# 손실 집중 시각화
st.subheader("📊 손실 점유율 Top 10 매체")
loss_chart_df = f_m_df.copy()
loss_total = loss_chart_df['fraud_loss'].sum()
if not loss_chart_df.empty and loss_total > 0:
    loss_chart_df['매체'] = "mda_" + loss_chart_df['mda_idx'].astype(str)
    loss_chart_df['손실 점유율'] = loss_chart_df['fraud_loss'] / loss_total * 100
    loss_chart_df['확정 환수 대상 금액'] = loss_chart_df['fraud_loss']
    loss_top = loss_chart_df.sort_values('fraud_loss', ascending=False).head(10).copy()
    loss_top['운영 리스크 등급'] = loss_top['Risk_Label'].astype(str)
    loss_top['손실 점유율 표시'] = loss_top['손실 점유율'].map(lambda x: f'{x:.1f}%')
    loss_top = loss_top.sort_values('손실 점유율', ascending=False)
    risk_color_map = {"정상": "#22c55e", "주의": "#fbbf24", "위험": "#f97316", "어뷰징 확정": "#ef4444"}
    fig_loss = go.Figure(
        go.Bar(
            x=loss_top['매체'],
            y=loss_top['손실 점유율'],
            text=loss_top['손실 점유율 표시'],
            textposition='outside',
            marker_color=loss_top['운영 리스크 등급'].map(risk_color_map).fillna('#9ca3af'),
            customdata=np.stack([
                loss_top['운영 리스크 등급'],
                loss_top['확정 환수 대상 금액'],
            ], axis=-1),
            hovertemplate='매체=%{x}<br>손실 점유율=%{y:.1f}%<br>운영 리스크 등급=%{customdata[0]}<br>확정 환수 대상 금액=%{customdata[1]:,.0f}원<extra></extra>',
        )
    )
    fig_loss.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        height=360,
        margin=dict(t=10, b=20, l=20, r=50),
        xaxis_title=None,
        yaxis_title="전체 확정 환수 대상 금액 내 점유율(%)",
        showlegend=False,
    )
    fig_loss.update_traces(cliponaxis=False)
    st.plotly_chart(fig_loss, use_container_width=True)
    st.caption("⚠️ 환수 대상 금액의 매체별 집중도 및 리스크 편중 확인")
else:
    st.info("손실 점유율을 계산할 수 있는 금액 데이터가 없습니다.")

st.divider()

# 매체 순위 및 운영 리스크 분포
segment_meta = [
    ('어뷰징 확정', '#ef4444', '어뷰징 확정 비율 70% 이상<br>캠페인 차단 및 블랙리스트 후보'),
    ('위험', '#f97316', '어뷰징 확정 비율 40% 이상<br>정산 검수 및 소명 요청 대상'),
    ('주의', '#6b7280', '어뷰징 확정 비율 20% 이상<br>지속 모니터링 및 관리 대상'),
    ('정상', '#22c55e', '어뷰징 확정 비율 20% 미만<br>일반 정산 적용 대상'),
]
segment_total = len(f_m_df)
segment_cards = []
for label, color, desc in segment_meta:
    segment_rows = f_m_df[f_m_df['Risk_Label'] == label]
    media_count = len(segment_rows)
    segment_ratio = media_count / segment_total * 100 if segment_total else 0
    segment_cards.append(
        f'<div class="segment-card">'
        f'<div><div class="segment-title" style="color:{color};">{label}</div>'
        f'<div class="segment-desc">{desc}</div></div>'
        f'<div><div class="segment-value" style="color:{color};">{segment_ratio:.1f}%</div>'
        f'<div class="segment-count">{media_count:,}개 매체</div></div>'
        f'</div>'
    )
st.markdown('<div class="segment-grid">' + ''.join(segment_cards) + '</div>', unsafe_allow_html=True)

col_l, col_r = st.columns([1.5, 1])

with col_l:
    st.subheader("🎯 모니터링 대상 매체")
    st.caption("어뷰징 확정 비율 기준 내림차순 정렬. 손실액 및 점유율 매핑")

    top = f_m_df.sort_values(['extreme_ratio', 'fraud_loss'], ascending=False)
    if not top.empty:
        total_loss = f_m_df['fraud_loss'].sum()
        top['No'] = range(1, len(top)+1)
        top['mda'] = "mda_" + top['mda_idx'].astype(str)
        top['loss_share'] = np.where(total_loss > 0, top['fraud_loss'] / total_loss * 100, 0)
        top_view = top[['No', 'mda', 'Risk_Label', 'extreme_ratio', 'fraud_loss', 'loss_share', 'total_conv']].rename(columns={
            'Risk_Label': '운영 리스크 등급',
            'extreme_ratio': '어뷰징 확정 비율',
            'fraud_loss': '확정 환수 대상 금액',
            'loss_share': '손실 점유율',
            'total_conv': '전체 전환 수',
        })
        top_view['손실 점유율'] = top_view['손실 점유율'].map(lambda x: f'{x:.1f}%')
        st.dataframe(top_view, use_container_width=True, hide_index=True)
    else:
        st.success("모니터링 대상 매체가 발견되지 않았습니다.")

with col_r:
    st.subheader("📊 운영 리스크 등급 구성비")
    risk_counts = f_m_df['Risk_Label'].value_counts()
    fig_p = px.pie(values=risk_counts.values, names=risk_counts.index, color=risk_counts.index,
                   color_discrete_map={"정상": "#22c55e", "주의": "#fbbf24", "위험": "#facc15", "어뷰징 확정": "#ef4444"})
    fig_p.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), height=350, margin=dict(t=20, b=20))
    st.plotly_chart(fig_p, use_container_width=True)

# 운영 리스크 판정 근거
st.subheader("📌 운영 리스크 판정 근거")

if not f_s_df.empty:
    evidence_base = f_s_df.copy()
    confirmed_rows = evidence_base[evidence_base['row_label'] == '어뷰징 확정'].copy()
    evidence_denominator = len(evidence_base)
    confirmed_denominator = len(confirmed_rows) if not confirmed_rows.empty else evidence_denominator

    abnormal_click_ratio = len(confirmed_rows) / evidence_denominator * 100 if evidence_denominator else 0
    repeat_ip_ratio = (evidence_base['click_label'] != '정상').sum() / evidence_denominator * 100 if evidence_denominator else 0

    evidence_ratio = pd.DataFrame([
        {'항목': '이상 클릭 비율', '값': f'{abnormal_click_ratio:.1f}%'},
        {'항목': '극단값 비율', '값': f'{ex_r:.1f}%'},
        {'항목': '반복 IP 비율', '값': f'{repeat_ip_ratio:.1f}%'},
    ])

    reason_counts = pd.DataFrame([
        {'이상 유형': 'IP 반복 클릭', '건수': int((evidence_base['click_label'] != '정상').sum())},
        {'이상 유형': '동일 IP 다기기', '건수': int((evidence_base['device_label'] != '정상').sum())},
        {'이상 유형': 'CTIT 이상', '건수': int((evidence_base['ctit_label'] != '정상').sum())},
    ])
    total_reason_count = reason_counts['건수'].sum()
    reason_counts['비중'] = np.where(total_reason_count > 0, reason_counts['건수'] / total_reason_count * 100, 0)
    reason_view = reason_counts.assign(비중=reason_counts['비중'].map(lambda x: f'{x:.1f}%'))[['이상 유형', '건수', '비중']]

    top_ip = (
        confirmed_rows.groupby(['mda_idx', 'user_ip'], as_index=False)
        .agg(이상건수=('user_ip', 'count'), 손실비용=('fraud_loss', 'sum'))
        .sort_values(['이상건수', '손실비용'], ascending=False)
        .head(5)
        .rename(columns={'mda_idx': '매체', 'user_ip': 'IP'})
    )
    if not top_ip.empty:
        top_ip['매체'] = 'mda_' + top_ip['매체'].astype(str)

    ev_c1, ev_c2 = st.columns(2)
    with ev_c1:
        st.markdown("**이상 비율**")
        st.dataframe(evidence_ratio, use_container_width=True, hide_index=True)
    with ev_c2:
        st.markdown("**주요 이상 원인 비중**")
        st.dataframe(reason_view, use_container_width=True, hide_index=True)

    rule_c1, rule_c2 = st.columns(2)
    with rule_c1:
        with st.expander("🔍 이상 탐지 기준 (행 단위)", expanded=True):
            st.markdown("""
- CTIT 이상: 광고 유형별 CTIT 중앙값의 10% 미만
- 클릭형 광고(ads_type=4): CTIT가 0초인 경우
- 디바이스 밀집: 동일 IP 기준 디바이스 수 상위 0.1% 초과 (99.9% 초과)
- 클릭 과밀: 동일 IP 기준 클릭 수 상위 0.1% 초과 (99.9% 초과)
- 각 항목은 독립 지표이므로 발생 비중의 합계가 100%를 초과할 수 있습니다.
""")
    with rule_c2:
        with st.expander("🛑 매체 등급 분류 기준", expanded=True):
            st.markdown("""
- 어뷰징 확정 (≥70%): 캠페인 즉시 차단 및 블랙리스트 등록
- 위험 (40%~70%): 정산 보류 및 정식 소명 요청
- 주의 (20%~40%): 지속 모니터링 및 정밀 분석 대상
- 정상 (<20%): 일반 정산 프로세스 적용
""")
else:
    st.info("조회할 수 있는 위험 근거 데이터가 없습니다.")

st.divider()

# 운영용 드릴다운 (IP/Click 상세)
st.subheader("🔍 운영 관리용 세부 위험군 (Top Suspicious Individuals)")
st.caption("위험 IP의 이상건수와 손실비용을 기준으로 개별 의심 행을 정렬합니다.")

if not f_s_df.empty:
    detail_base = f_s_df.copy()
    confirmed_detail = detail_base[detail_base['row_label'] == '어뷰징 확정'].copy()
    ip_base = confirmed_detail if not confirmed_detail.empty else detail_base
    ip_summary = (
        ip_base.groupby(['mda_idx', 'user_ip'], as_index=False)
        .agg(IP_이상건수=('user_ip', 'count'), IP_손실비용=('fraud_loss', 'sum'))
    )
    detail_with_ip = detail_base.merge(ip_summary, on=['mda_idx', 'user_ip'], how='left')
    detail_with_ip['IP_이상건수'] = detail_with_ip['IP_이상건수'].fillna(0).astype(int)
    detail_with_ip['IP_손실비용'] = detail_with_ip['IP_손실비용'].fillna(0)
    detail_with_ip['매체'] = 'mda_' + detail_with_ip['mda_idx'].astype(str)
    detail_view = (
        detail_with_ip
        .sort_values(['IP_이상건수', 'IP_손실비용', 'row_score'], ascending=[False, False, True])
        [['매체', 'user_ip', 'IP_이상건수', 'IP_손실비용', 'click_date', 'row_score', 'row_label', 'ctit_label', 'device_label', 'click_label', 'fraud_loss']]
        .rename(columns={
            'user_ip': '위험 IP',
            'IP_이상건수': 'IP 이상건수',
            'IP_손실비용': 'IP 손실비용',
            'click_date': '발생일',
            'row_score': '품질 점수',
            'row_label': '행 판정',
            'ctit_label': 'CTIT 판정',
            'device_label': '디바이스 판정',
            'click_label': '클릭 집중 판정',
            'fraud_loss': '행 손실 비용',
        })
    )
    st.dataframe(detail_view, use_container_width=True, hide_index=True)
else:
    st.info("조회할 수 있는 상세 위험군 데이터가 없습니다.")

