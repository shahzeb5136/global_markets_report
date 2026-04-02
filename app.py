#!/usr/bin/env python3
"""
════════════════════════════════════════════════════════════════════════════════
  Global Stock Market Report — Streamlit In-App Viewer
  ────────────────────────────────────────────────────
  Displays the full report (tables, charts, heatmaps, summary) directly
  inside the Streamlit page.  No PDF download — designed for website embedding.
════════════════════════════════════════════════════════════════════════════════
"""

import streamlit as st
import sys, os, warnings, tempfile, io, base64
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Page config ──
st.set_page_config(
    page_title="Global Market Report",
    page_icon="📊",
    layout="wide",
)

# ── Custom styling ──
st.markdown("""
<style>
    /* Main container */
    .block-container { max-width: 1100px; padding-top: 2rem; }

    /* Title area */
    div[data-testid="stMarkdownContainer"] h1 { text-align: center; color: #ffffff; }
    div[data-testid="stMarkdownContainer"] p.subtitle {
        text-align: center; color: #aab4c0; margin-top: -12px; font-size: 1.05rem;
    }

    /* Return value colouring — brighter for dark bg */
    .ret-pos { color: #4cdf8b; font-weight: 600; }
    .ret-neg { color: #ff6b6b; font-weight: 600; }
    .ret-zero { color: #ccc; }

    /* Section headers — white text */
    .section-hdr {
        font-size: 1.35rem; font-weight: 700; color: #ffffff;
        border-bottom: 2px solid #5a7a9a; padding-bottom: 4px;
        margin-top: 2.5rem; margin-bottom: 0.8rem;
    }
    .sub-hdr {
        font-size: 1.1rem; font-weight: 600; color: #a0b8d0;
        margin-top: 1.2rem; margin-bottom: 0.5rem;
    }

    /* Metric cards — dark surface */
    .metric-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
    .metric-card {
        background: rgba(255,255,255,0.06); border-radius: 8px; padding: 14px 18px;
        flex: 1; min-width: 200px; border-left: 4px solid #5a7a9a;
    }
    .metric-card.bullish  { border-left-color: #4cdf8b; }
    .metric-card.bearish  { border-left-color: #ff6b6b; }
    .metric-card.neutral  { border-left-color: #f5bf42; }
    .metric-label { font-size: 0.78rem; color: #8a96a6; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { font-size: 1.3rem; font-weight: 700; margin-top: 2px; }

    /* Disclaimer */
    .disclaimer {
        font-size: 0.75rem; color: #6b7785; text-align: center;
        margin-top: 3rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.1);
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# HELPER: colour-format return values
# ═══════════════════════════════════════════════════════════════════════

def _fmt(val, bold=False):
    """Return an HTML-styled return value string."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "—"
    cls = "ret-pos" if val > 0 else ("ret-neg" if val < 0 else "ret-zero")
    txt = f"{val:+.2f}%"
    if bold:
        return f'<span class="{cls}" style="font-weight:700">{txt}</span>'
    return f'<span class="{cls}">{txt}</span>'


def _styled_df(df, value_cols):
    """Return a Pandas Styler that colours return columns green/red."""
    def _color(v):
        if pd.isna(v):
            return ""
        if v > 0:
            return "color: #4cdf8b; font-weight: 600"
        elif v < 0:
            return "color: #ff6b6b; font-weight: 600"
        return ""

    fmt = {c: "{:+.2f}%" for c in value_cols if c in df.columns}
    return (
        df.style
        .format(fmt, na_rep="—")
        .map(_color, subset=[c for c in value_cols if c in df.columns])
    )


# ═══════════════════════════════════════════════════════════════════════
# MAIN GENERATION + DISPLAY
# ═══════════════════════════════════════════════════════════════════════

def generate_and_display():
    """Fetch data, compute everything, and render the full report in-page."""
    from global_market_report import (
        fetch_data, compute_returns, compute_investment_returns,
        compute_correlations, chart_investment_returns, chart_bars,
        chart_regional, chart_cumulative, chart_corr_heatmap,
        INDICES, MAJOR_INDICES, CORR_PERIODS, RETURN_PERIODS,
    )
    from datetime import datetime

    progress = st.progress(0, text="Fetching data for 30+ indices…")

    # 1 ── Fetch ──
    data = fetch_data()
    if len(data) < 3:
        st.error("❌ Not enough data.  Check your internet connection.")
        return
    progress.progress(25, text=f"Fetched {len(data)} indices.  Computing returns…")

    # 2 ── Compute ──
    returns_df = compute_returns(data)
    inv_ret = compute_investment_returns(data, 260)

    progress.progress(35, text="Computing correlations…")
    corrs = {}
    for lbl, days in CORR_PERIODS:
        c = compute_correlations(data, days)
        if c is not None:
            corrs[lbl] = c

    # 3 ── Generate chart images into temp dir ──
    progress.progress(50, text="Generating charts…")
    tmpdir = tempfile.mkdtemp(prefix="mkt_rpt_")
    charts = {}
    avail = [m for m in MAJOR_INDICES if m in inv_ret.columns]
    mkt_df = returns_df[returns_df["Index"] != "VIX (Volatility)"]

    for key, days, title in [
        ("inv_short", 30, "If I Invested N Days Ago — Last 30 Trading Days"),
        ("inv_medium", 90, "If I Invested N Days Ago — Last 90 Trading Days"),
        ("inv_long", 252, "If I Invested N Days Ago — Last 1 Year"),
    ]:
        f = os.path.join(tmpdir, f"{key}.png")
        chart_investment_returns(inv_ret, avail, days, title, f)
        charts[key] = f

    for col, lbl in [("5D", "5-Day"), ("1M", "1-Month")]:
        if col in mkt_df.columns:
            f = os.path.join(tmpdir, f"bar_{col.lower()}.png")
            chart_bars(mkt_df, col, f"{lbl} Returns — All Indices", f)
            charts[f"bar_{col.lower()}"] = f

    progress.progress(65, text="Regional & cumulative charts…")

    f = os.path.join(tmpdir, "regional.png")
    chart_regional(returns_df, f)
    charts["regional"] = f

    for days, key in [(30, "cum_30d"), (252, "cum_1y")]:
        f = os.path.join(tmpdir, f"{key}.png")
        chart_cumulative(
            data, avail, days,
            f"Cumulative Performance — {'30 Days' if days == 30 else '1 Year'} (Indexed to 100)",
            f,
        )
        charts[key] = f

    progress.progress(80, text="Correlation heatmaps…")

    for lbl in ["5D", "1M", "3M", "1Y"]:
        if lbl in corrs:
            f = os.path.join(tmpdir, f"corr_{lbl}.png")
            if chart_corr_heatmap(corrs[lbl], f"Daily Return Correlations — {lbl}", f):
                charts[f"corr_{lbl}"] = f

    progress.progress(100, text="Done!")

    # ── Store everything in session state so it survives reruns ──
    st.session_state.report = {
        "returns_df": returns_df,
        "inv_ret": inv_ret,
        "corrs": corrs,
        "charts": {},         # will hold base64 encoded PNGs
        "generated": datetime.now(),
    }
    # Encode chart PNGs as base64 so we don't depend on temp files later
    for key, path in charts.items():
        if os.path.exists(path):
            with open(path, "rb") as fh:
                st.session_state.report["charts"][key] = base64.b64encode(fh.read()).decode()

    # Cleanup temp files
    for fp in charts.values():
        try:
            os.remove(fp)
        except OSError:
            pass
    try:
        os.rmdir(tmpdir)
    except OSError:
        pass


def display_report():
    """Render the stored report data inside the Streamlit page."""
    rpt = st.session_state.report
    returns_df = rpt["returns_df"]
    inv_ret = rpt["inv_ret"]
    corrs = rpt["corrs"]
    charts = rpt["charts"]      # dict of key → base64 PNG
    generated = rpt["generated"]

    mkt = returns_df[returns_df["Index"] != "VIX (Volatility)"].copy()

    def show_chart(key, caption=None, use_column_width=True):
        b64 = charts.get(key)
        if b64:
            img_bytes = base64.b64decode(b64)
            st.image(img_bytes, caption=caption, use_container_width=use_column_width)

    # ── HEADER ──
    st.markdown(
        f'<p style="text-align:center;color:#8a96a6;font-size:0.95rem;">'
        f'Report generated {generated.strftime("%B %d, %Y at %H:%M")} · '
        f'{len(returns_df)} indices across {returns_df["Country"].nunique()} countries</p>',
        unsafe_allow_html=True,
    )

    # ──────────────────────────────────────────────────────
    # EXECUTIVE SUMMARY
    # ──────────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">Executive Summary</div>', unsafe_allow_html=True)

    # Global regime card
    if "5D" in mkt.columns:
        v = mkt["5D"].dropna()
        if len(v):
            a = v.mean()
            p = (v > 0).sum() / len(v) * 100
            if a < -2:
                rg, rc, cls = "BROAD SELLOFF", "#ff6b6b", "bearish"
            elif a < -0.5:
                rg, rc, cls = "MILD BEARISH", "#ff9a5c", "bearish"
            elif a < 0.5:
                rg, rc, cls = "NEUTRAL / MIXED", "#f5bf42", "neutral"
            elif a < 2:
                rg, rc, cls = "MILD BULLISH", "#4cdf8b", "bullish"
            else:
                rg, rc, cls = "STRONG RALLY", "#4cdf8b", "bullish"

            st.markdown(
                f'<div class="metric-row">'
                f'<div class="metric-card {cls}">'
                f'<div class="metric-label">5-Day Global Regime</div>'
                f'<div class="metric-value" style="color:{rc}">{rg}</div>'
                f'<div style="font-size:0.85rem;color:#8a96a6;margin-top:4px">'
                f'Avg: {a:+.2f}%  ·  {p:.0f}% positive</div></div>',
                unsafe_allow_html=True,
            )

            # VIX card
            vix_row = returns_df[returns_df["Index"] == "VIX (Volatility)"]
            vix_html = ""
            if not vix_row.empty:
                vp = vix_row.iloc[0]["Last Price"]
                vc = "#ff6b6b" if vp > 20 else "#f5bf42" if vp > 15 else "#4cdf8b"
                vix_cls = "bearish" if vp > 20 else "neutral" if vp > 15 else "bullish"
                vlabel = "Elevated" if vp > 20 else "Moderate" if vp > 15 else "Low"
                vix_html = (
                    f'<div class="metric-card {vix_cls}">'
                    f'<div class="metric-label">VIX (Volatility)</div>'
                    f'<div class="metric-value" style="color:{vc}">{vp:.2f}</div>'
                    f'<div style="font-size:0.85rem;color:#8a96a6;margin-top:4px">{vlabel}</div></div>'
                )
            st.markdown(vix_html + "</div>", unsafe_allow_html=True)

    # Period summaries
    for period in ["1D", "5D", "10D", "1M"]:
        if period not in mkt.columns:
            continue
        vd = mkt.dropna(subset=[period])
        if vd.empty:
            continue
        b = vd.loc[vd[period].idxmax()]
        w = vd.loc[vd[period].idxmin()]
        st.markdown(
            f"**{period}:** Avg {_fmt(vd[period].mean())} · "
            f"Best: {b['Index']} ({_fmt(b[period])}) · "
            f"Worst: {w['Index']} ({_fmt(w[period])})",
            unsafe_allow_html=True,
        )

    # Regional quick stats
    for reg in ["Americas", "Europe", "Asia-Pacific"]:
        rd = mkt[(mkt["Region"] == reg) & mkt["5D"].notna()] if "5D" in mkt.columns else pd.DataFrame()
        if not rd.empty:
            st.markdown(
                f"**{reg} (5D):** Avg {_fmt(rd['5D'].mean())} — "
                f"{(rd['5D'] > 0).sum()} up, {(rd['5D'] <= 0).sum()} down",
                unsafe_allow_html=True,
            )

    # ──────────────────────────────────────────────────────
    # REGIONAL CHART
    # ──────────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">Regional Performance Comparison</div>', unsafe_allow_html=True)
    show_chart("regional")

    # ──────────────────────────────────────────────────────
    # SHORT-TERM TABLE
    # ──────────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">Short-Term Returns — 1D / 5D / 10D / 1M</div>', unsafe_allow_html=True)
    sc = "5D" if "5D" in mkt.columns else "1D"
    sm_df = mkt.sort_values(sc, ascending=False, na_position="last")
    short_cols = ["Country", "Index", "Last Price", "1D", "5D", "10D", "1M"]
    short_show = [c for c in short_cols if c in sm_df.columns]
    val_cols = [c for c in ["1D", "5D", "10D", "1M"] if c in sm_df.columns]
    st.dataframe(
        _styled_df(sm_df[short_show].reset_index(drop=True), val_cols),
        use_container_width=True,
        hide_index=True,
        height=min(800, 36 * len(sm_df) + 38),
    )

    # ──────────────────────────────────────────────────────
    # FULL RETURN TABLE
    # ──────────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">Full Return Comparison — All Periods</div>', unsafe_allow_html=True)
    from global_market_report import RETURN_PERIODS
    plabels = [l for l, _ in RETURN_PERIODS]
    full_cols = ["Country", "Index", "Last Price"] + [p for p in plabels if p in sm_df.columns]
    full_val = [p for p in plabels if p in sm_df.columns]
    st.dataframe(
        _styled_df(sm_df[full_cols].reset_index(drop=True), full_val),
        use_container_width=True,
        hide_index=True,
        height=min(800, 36 * len(sm_df) + 38),
    )

    # ──────────────────────────────────────────────────────
    # BAR CHARTS (5D & 1M)
    # ──────────────────────────────────────────────────────
    for col, lbl in [("5D", "5-Day"), ("1M", "1-Month")]:
        k = f"bar_{col.lower()}"
        if k in charts:
            st.markdown(f'<div class="section-hdr">{lbl} Returns — All Indices</div>', unsafe_allow_html=True)
            show_chart(k)

    # ──────────────────────────────────────────────────────
    # INVESTMENT RETURN CHARTS
    # ──────────────────────────────────────────────────────
    st.markdown(
        '<div class="section-hdr">"If I Invested N Days Ago…" — Returns as of Today</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "These charts answer: **if I had put money into each index N trading days ago, "
        "what would my total return be today?** X-axis = how many days ago · Y-axis = cumulative return %."
    )
    for key, lbl in [
        ("inv_short", "Last 30 Trading Days"),
        ("inv_medium", "Last 90 Trading Days"),
        ("inv_long", "Last 252 Trading Days (~1 Year)"),
    ]:
        st.markdown(f'<div class="sub-hdr">{lbl}</div>', unsafe_allow_html=True)
        show_chart(key)

    # ──────────────────────────────────────────────────────
    # CUMULATIVE PERFORMANCE
    # ──────────────────────────────────────────────────────
    st.markdown(
        '<div class="section-hdr">Cumulative Performance — Indexed to 100</div>',
        unsafe_allow_html=True,
    )
    st.markdown("Each index is rebased to 100 at the start of the window.")
    for key, lbl in [("cum_30d", "Last 30 Trading Days"), ("cum_1y", "Last 1 Year")]:
        st.markdown(f'<div class="sub-hdr">{lbl}</div>', unsafe_allow_html=True)
        show_chart(key)

    # ──────────────────────────────────────────────────────
    # CORRELATION HEATMAPS
    # ──────────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">Cross-Market Correlation Analysis</div>', unsafe_allow_html=True)
    st.markdown(
        "Heatmaps of daily return correlations.  Green = move together · "
        "Red = move inversely.  Correlations tend to spike during crises."
    )
    from global_market_report import CORR_PERIODS as _CP
    for lbl, _ in _CP:
        k = f"corr_{lbl}"
        if k in charts:
            st.markdown(f'<div class="sub-hdr">Correlation — {lbl} Period</div>', unsafe_allow_html=True)
            show_chart(k)

    # ──────────────────────────────────────────────────────
    # LONGER-TERM TABLE
    # ──────────────────────────────────────────────────────
    st.markdown(
        '<div class="section-hdr">Longer-Term Returns: 3M / 6M / 1Y / 2Y / 3Y / 5Y</div>',
        unsafe_allow_html=True,
    )
    lp = [p for p in ["3M", "6M", "1Y", "2Y", "3Y", "5Y"] if p in mkt.columns]
    if "1Y" in mkt.columns:
        sl = mkt.sort_values("1Y", ascending=False, na_position="last")
    else:
        sl = mkt
    long_cols = ["Country", "Index", "Last Price"] + lp
    st.dataframe(
        _styled_df(sl[long_cols].reset_index(drop=True), lp),
        use_container_width=True,
        hide_index=True,
        height=min(800, 36 * len(sl) + 38),
    )

    # ── Disclaimer ──
    st.markdown(
        f'<div class="disclaimer">'
        f'Data: Yahoo Finance via yfinance · Generated {generated.strftime("%B %d, %Y %H:%M")} · '
        f'Past performance ≠ future results · Not investment advice</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ═══════════════════════════════════════════════════════════════════════

st.title("📊 Global Market Report")
st.markdown(
    '<p class="subtitle">30+ indices · Returns · Correlations · Charts</p>',
    unsafe_allow_html=True,
)
st.divider()

st.markdown(
    "Press the button below to fetch live data from Yahoo Finance and generate "
    "a comprehensive market report with return tables, charts, and correlation heatmaps."
)

if "report" not in st.session_state:
    st.session_state.report = None

if st.button("🚀 Generate Report", use_container_width=True, type="primary"):
    st.session_state.report = None
    try:
        generate_and_display()
    except Exception as e:
        st.error(f"❌ Something went wrong: {e}")

if st.session_state.report is not None:
    display_report()

st.divider()
st.caption("Data: Yahoo Finance via yfinance · Past performance ≠ future results · Not investment advice")
