#!/usr/bin/env python3
"""
Simple Streamlit wrapper for the Global Stock Market Report Generator.
One button to generate, then download the PDF.
"""

import streamlit as st
import sys, os, warnings, tempfile
warnings.filterwarnings('ignore')

# ── Page config ──
st.set_page_config(
    page_title="Global Market Report",
    page_icon="📊",
    layout="centered",
)

# ── Minimal custom styling ──
st.markdown("""
<style>
    .stApp { max-width: 720px; margin: 0 auto; }
    div[data-testid="stMarkdownContainer"] h1 { text-align: center; }
    div[data-testid="stMarkdownContainer"] p.subtitle {
        text-align: center; color: #666; margin-top: -12px; font-size: 1.05rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ──
st.title("📊 Global Market Report")
st.markdown('<p class="subtitle">30+ indices · Returns · Correlations · Charts</p>', unsafe_allow_html=True)
st.divider()

# ── Import the report module ──
# We import the heavy functions only when needed (inside the button click)
# to keep the page fast on initial load.

def generate_report() -> tuple[bytes | None, str | None]:
    """Run the full report pipeline and return (pdf_bytes, filename) or (None, error)."""
    # Import everything from the original script
    from global_market_report import (
        fetch_data, compute_returns, compute_investment_returns,
        compute_correlations, chart_investment_returns, chart_bars,
        chart_regional, chart_cumulative, chart_corr_heatmap, build_pdf,
        INDICES, MAJOR_INDICES, CORR_PERIODS, RETURN_PERIODS,
    )
    from datetime import datetime

    progress = st.progress(0, text="Fetching data for 30+ indices…")

    # 1. Fetch
    data = fetch_data()
    if len(data) < 3:
        return None, "Not enough data. Check your internet connection."
    progress.progress(30, text=f"Fetched {len(data)} indices. Computing returns…")

    # 2. Compute
    returns_df = compute_returns(data)
    inv_ret = compute_investment_returns(data, 260)

    progress.progress(40, text="Computing correlations…")
    corrs = {}
    for lbl, days in CORR_PERIODS:
        c = compute_correlations(data, days)
        if c is not None:
            corrs[lbl] = c

    # 3. Charts
    progress.progress(50, text="Generating charts…")
    tmpdir = tempfile.mkdtemp(prefix='mkt_rpt_')
    charts = {}
    avail = [m for m in MAJOR_INDICES if m in inv_ret.columns]
    mkt_df = returns_df[returns_df['Index'] != 'VIX (Volatility)']

    chart_steps = []

    for key, days, title in [
        ('inv_short', 30, 'If I Invested N Days Ago — Last 30 Trading Days'),
        ('inv_medium', 90, 'If I Invested N Days Ago — Last 90 Trading Days'),
        ('inv_long', 252, 'If I Invested N Days Ago — Last 1 Year'),
    ]:
        f = os.path.join(tmpdir, f'{key}.png')
        chart_investment_returns(inv_ret, avail, days, title, f)
        charts[key] = f

    for col, lbl in [('5D', '5-Day'), ('1M', '1-Month')]:
        if col in mkt_df.columns:
            f = os.path.join(tmpdir, f'bar_{col.lower()}.png')
            chart_bars(mkt_df, col, f'{lbl} Returns — All Indices', f)
            charts[f'bar_{col.lower()}'] = f

    progress.progress(65, text="Generating regional & cumulative charts…")

    f = os.path.join(tmpdir, 'regional.png')
    chart_regional(returns_df, f)
    charts['regional'] = f

    for days, key in [(30, 'cum_30d'), (252, 'cum_1y')]:
        f = os.path.join(tmpdir, f'{key}.png')
        chart_cumulative(data, avail, days,
                         f"Cumulative Performance — {'30 Days' if days == 30 else '1 Year'} (Indexed to 100)", f)
        charts[key] = f

    progress.progress(80, text="Generating correlation heatmaps…")

    for lbl in ['5D', '1M', '3M', '1Y']:
        if lbl in corrs:
            f = os.path.join(tmpdir, f'corr_{lbl}.png')
            if chart_corr_heatmap(corrs[lbl], f"Daily Return Correlations — {lbl}", f):
                charts[f'corr_{lbl}'] = f

    # 4. Build PDF
    progress.progress(90, text="Assembling PDF…")
    filename = f"global_market_report_{datetime.now().strftime('%Y-%m-%d')}.pdf"
    out_path = os.path.join(tmpdir, filename)
    build_pdf(returns_df, inv_ret, corrs, data, charts, out_path)

    # Read PDF bytes
    with open(out_path, 'rb') as fh:
        pdf_bytes = fh.read()

    # Cleanup temp files
    for fp in charts.values():
        try: os.remove(fp)
        except: pass
    try: os.remove(out_path)
    except: pass
    try: os.rmdir(tmpdir)
    except: pass

    progress.progress(100, text="Done!")
    return pdf_bytes, filename


# ── Main UI ──
st.markdown(
    "Press the button below to fetch live data from Yahoo Finance and generate "
    "a comprehensive PDF report with return tables, charts, and correlation heatmaps."
)

if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
    st.session_state.pdf_name = None

if st.button("🚀 Generate Report", use_container_width=True, type="primary"):
    st.session_state.pdf_bytes = None
    st.session_state.pdf_name = None
    try:
        result, name_or_err = generate_report()
        if result is None:
            st.error(f"❌ {name_or_err}")
        else:
            st.session_state.pdf_bytes = result
            st.session_state.pdf_name = name_or_err
    except Exception as e:
        st.error(f"❌ Something went wrong: {e}")

if st.session_state.pdf_bytes:
    st.success("✅ Report ready!")
    st.download_button(
        label="📥 Download PDF",
        data=st.session_state.pdf_bytes,
        file_name=st.session_state.pdf_name,
        mime="application/pdf",
        use_container_width=True,
    )

st.divider()
st.caption("Data: Yahoo Finance via yfinance · Past performance ≠ future results · Not investment advice")