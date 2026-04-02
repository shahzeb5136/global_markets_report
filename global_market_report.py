#!/usr/bin/env python3
"""
════════════════════════════════════════════════════════════════════════════════
  GLOBAL STOCK MARKET REPORT GENERATOR
  ─────────────────────────────────────
  A standalone script you can run anytime to generate a comprehensive PDF
  report covering 30+ global indices with:
    • Return tables (1D through 5Y)
    • "If I invested N days ago" cumulative return line charts
    • Correlation heatmaps
    • Regional comparison bar charts
    • Cumulative indexed performance charts
    • Executive summary & key signals
  
  REQUIREMENTS (install once):
    pip install yfinance pandas numpy matplotlib reportlab

  USAGE:
    python global_market_report.py
    
  Output: global_market_report_YYYY-MM-DD.pdf in the current directory.
════════════════════════════════════════════════════════════════════════════════
"""

import sys, os, warnings, tempfile, copy
warnings.filterwarnings('ignore')

REQUIRED = ['yfinance', 'pandas', 'numpy', 'matplotlib', 'reportlab']
missing = [p for p in REQUIRED if not __import__('importlib').util.find_spec(p)]
if missing:
    print(f"Missing: {', '.join(missing)}\nInstall: pip install {' '.join(missing)}")
    sys.exit(1)

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import LinearSegmentedColormap
from datetime import datetime, timedelta

from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image as RLImage, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors as rl_colors


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION — Edit freely to add/remove indices
# ══════════════════════════════════════════════════════════════════════════════

INDICES = {
    # ticker: (display_name, country, region)
    # ── United States ──
    "^GSPC":      ("S&P 500",              "United States",  "Americas"),
    "^DJI":       ("Dow Jones",             "United States",  "Americas"),
    "^IXIC":      ("NASDAQ Composite",      "United States",  "Americas"),
    "^RUT":       ("Russell 2000",          "United States",  "Americas"),
    "^VIX":       ("VIX (Volatility)",      "United States",  "Americas"),
    # ── Canada ──
    "^GSPTSE":    ("S&P/TSX Composite",     "Canada",         "Americas"),
    # ── Brazil ──
    "^BVSP":      ("Bovespa",               "Brazil",         "Americas"),
    # ── Mexico ──
    "^MXX":       ("IPC Mexico",            "Mexico",         "Americas"),
    # ── United Kingdom ──
    "^FTSE":      ("FTSE 100",              "United Kingdom", "Europe"),
    # ── Germany ──
    "^GDAXI":     ("DAX 40",                "Germany",        "Europe"),
    # ── France ──
    "^FCHI":      ("CAC 40",                "France",         "Europe"),
    # ── Netherlands ──
    "^AEX":       ("AEX Amsterdam",         "Netherlands",    "Europe"),
    # ── Switzerland ──
    "^SSMI":      ("Swiss Market Index",    "Switzerland",    "Europe"),
    # ── Spain ──
    "^IBEX":      ("IBEX 35",               "Spain",          "Europe"),
    # ── Italy ──
    "FTSEMIB.MI": ("FTSE MIB",             "Italy",          "Europe"),
    # ── Euro Area ──
    "^STOXX50E":  ("EURO STOXX 50",         "Euro Area",      "Europe"),
    # ── Japan ──
    "^N225":      ("Nikkei 225",            "Japan",          "Asia-Pacific"),
    # ── China ──
    "000001.SS":  ("SSE Composite",         "China",          "Asia-Pacific"),
    "399001.SZ":  ("SZSE Component",        "China",          "Asia-Pacific"),
    # ── Hong Kong ──
    "^HSI":       ("Hang Seng",             "Hong Kong",      "Asia-Pacific"),
    # ── South Korea ──
    "^KS11":      ("KOSPI",                 "South Korea",    "Asia-Pacific"),
    "^KQ11":      ("KOSDAQ",                "South Korea",    "Asia-Pacific"),
    # ── Taiwan ──
    "^TWII":      ("TAIEX",                 "Taiwan",         "Asia-Pacific"),
    # ── India ──
    "^BSESN":     ("BSE Sensex",            "India",          "Asia-Pacific"),
    "^NSEI":      ("Nifty 50",              "India",          "Asia-Pacific"),
    # ── Australia ──
    "^AXJO":      ("S&P/ASX 200",           "Australia",      "Asia-Pacific"),
    # ── Singapore ──
    "^STI":       ("Straits Times",         "Singapore",      "Asia-Pacific"),
    # ── Indonesia ──
    "^JKSE":      ("Jakarta Composite",     "Indonesia",      "Asia-Pacific"),
    # ── New Zealand ──
    "^NZ50":      ("NZX 50",                "New Zealand",    "Asia-Pacific"),
}

RETURN_PERIODS = [
    ("1D",1), ("2D",2), ("3D",3), ("5D",5), ("10D",10),
    ("1M",21), ("2M",42), ("3M",63), ("6M",126),
    ("1Y",252), ("2Y",504), ("3Y",756), ("5Y",1260),
]

CORR_PERIODS = [("5D",5), ("10D",10), ("1M",21), ("3M",63), ("6M",126), ("1Y",252)]

COLORS = [
    '#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd',
    '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf',
    '#aec7e8','#ffbb78','#98df8a','#ff9896','#c5b0d5',
]

MAJOR_INDICES = [
    'S&P 500','Dow Jones','NASDAQ Composite','FTSE 100','DAX 40',
    'Nikkei 225','SSE Composite','Hang Seng','KOSPI','BSE Sensex',
    'S&P/ASX 200','Bovespa',
]


# ══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING & COMPUTATION
# ══════════════════════════════════════════════════════════════════════════════

def fetch_data(years=6):
    end = datetime.now()
    start = end - timedelta(days=365*years + 60)
    print(f"\n{'='*70}\n  GLOBAL STOCK MARKET REPORT GENERATOR\n{'='*70}\n")
    print(f"  Fetching data for {len(INDICES)} indices...\n")
    data = {}
    for ticker, (name, country, region) in INDICES.items():
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
            if df is not None and len(df) > 5:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                data[ticker] = df
                print(f"  ✓ {name:30s} {len(df):>5d} days")
            else:
                print(f"  ✗ {name:30s} no data")
        except Exception as e:
            print(f"  ✗ {name:30s} {str(e)[:40]}")
    print(f"\n  Fetched: {len(data)}/{len(INDICES)}")
    return data


def compute_returns(data):
    rows = []
    for ticker, df in data.items():
        name, country, region = INDICES[ticker]
        close = df['Close']
        row = {'Ticker': ticker, 'Index': name, 'Country': country,
               'Region': region, 'Last Price': float(close.iloc[-1]),
               'Last Date': df.index[-1].strftime('%Y-%m-%d')}
        for label, days in RETURN_PERIODS:
            if len(close) > days:
                row[label] = round((float(close.iloc[-1])/float(close.iloc[-days-1])-1)*100, 2)
            else:
                row[label] = None
        rows.append(row)
    return pd.DataFrame(rows)


def compute_investment_returns(data, max_days=260):
    """'If I invested N days ago, what is my return today?'"""
    result = {}
    for ticker, df in data.items():
        name = INDICES[ticker][0]
        if name == 'VIX (Volatility)':
            continue
        close = df['Close']
        today = float(close.iloc[-1])
        days_list = list(range(1, min(max_days+1, len(close))))
        returns = [(today/float(close.iloc[-d-1])-1)*100 for d in days_list]
        result[name] = pd.Series(returns, index=days_list)
    return pd.DataFrame(result)


def compute_correlations(data, period_days):
    rd = {}
    for ticker, df in data.items():
        name = INDICES[ticker][0]
        if name == 'VIX (Volatility)':
            continue
        close = df['Close']
        if len(close) > period_days:
            rd[name] = close.iloc[-period_days:].pct_change().dropna()
    if len(rd) < 3:
        return None
    return pd.DataFrame(rd).dropna(how='all').corr()


# ══════════════════════════════════════════════════════════════════════════════
# CHART GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def _setup_ax(ax, fig):
    fig.patch.set_facecolor('#1e1e2e')
    ax.set_facecolor('#1e1e2e')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#555')
    ax.spines['left'].set_color('#555')
    ax.tick_params(colors='#ccc')
    ax.xaxis.label.set_color('#ccc')
    ax.yaxis.label.set_color('#ccc')


def chart_investment_returns(inv_ret, indices, max_days, title, path):
    fig, ax = plt.subplots(figsize=(13, 5.5))
    _setup_ax(ax, fig)
    avail = [i for i in indices if i in inv_ret.columns]
    sub = inv_ret.loc[inv_ret.index <= max_days, avail]
    for i, col in enumerate(avail):
        v = sub[col].dropna()
        ax.plot(v.index, v.values, label=col, color=COLORS[i%len(COLORS)], linewidth=1.8, alpha=0.9)
    ax.axhline(0, color='#666', lw=0.8, ls='--', alpha=0.6)
    ax.set_xlabel('Days Ago I Invested', fontsize=10, fontweight='bold')
    ax.set_ylabel('Return as of Today (%)', fontsize=10, fontweight='bold')
    ax.set_title(title, fontsize=13, fontweight='bold', color='#ffffff', pad=12)
    ax.invert_xaxis()
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1f%%'))
    ax.grid(True, alpha=0.2, color='#555')
    ax.legend(loc='upper center', bbox_to_anchor=(0.5,-0.12), ncol=min(5,len(avail)),
              fontsize=8, frameon=True, facecolor='#2a2a3e', edgecolor='#555', labelcolor='#ccc')
    plt.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)


def chart_bars(returns_df, col, title, path):
    df = returns_df.dropna(subset=[col]).copy()
    df = df[df['Index'] != 'VIX (Volatility)'].sort_values(col, ascending=True)
    fig, ax = plt.subplots(figsize=(10, max(4, len(df)*0.28)))
    _setup_ax(ax, fig)
    bar_colors = ['#ff6b6b' if v<0 else '#4cdf8b' for v in df[col]]
    bars = ax.barh(range(len(df)), df[col], color=bar_colors, height=0.7, alpha=0.85)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels([f"{r['Index']} ({r['Country']})" for _,r in df.iterrows()], fontsize=7, color='#ccc')
    ax.set_xlabel('Return (%)', fontsize=9, fontweight='bold')
    ax.set_title(title, fontsize=12, fontweight='bold', color='#ffffff', pad=10)
    ax.axvline(0, color='#666', lw=0.8)
    ax.grid(True, axis='x', alpha=0.2, color='#555')
    for bar, val in zip(bars, df[col]):
        x = val + (0.15 if val>=0 else -0.15)
        ax.text(x, bar.get_y()+bar.get_height()/2, f'{val:+.2f}%',
                va='center', ha='left' if val>=0 else 'right', fontsize=6.5, color='#ccc')
    plt.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)


def chart_regional(returns_df, path):
    df = returns_df[returns_df['Index'] != 'VIX (Volatility)'].copy()
    periods = [p for p in ['1D','5D','1M','3M','6M','1Y'] if p in df.columns]
    regions = ['Americas','Europe','Asia-Pacific']
    avgs = {reg: {p: df[df['Region']==reg][p].dropna().mean() for p in periods} for reg in regions}
    fig, ax = plt.subplots(figsize=(11, 5))
    _setup_ax(ax, fig)
    x = np.arange(len(periods))
    w = 0.25
    rc = {'Americas':'#1f77b4','Europe':'#ff7f0e','Asia-Pacific':'#2ca02c'}
    for i, reg in enumerate(regions):
        vals = [avgs[reg].get(p,0) for p in periods]
        bars = ax.bar(x+i*w, vals, w, label=reg, color=rc[reg], alpha=0.85)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.1,
                    f'{val:.1f}%', ha='center', va='bottom', fontsize=7, color='#ccc')
    ax.set_xticks(x+w); ax.set_xticklabels(periods, fontsize=9, color='#ccc')
    ax.set_ylabel('Avg Return (%)', fontsize=10, fontweight='bold')
    ax.set_title('Regional Average Returns Comparison', fontsize=13, fontweight='bold', color='#ffffff', pad=12)
    ax.axhline(0, color='#666', lw=0.8, ls='--')
    ax.legend(fontsize=9, facecolor='#2a2a3e', edgecolor='#555', labelcolor='#ccc'); ax.grid(True, axis='y', alpha=0.2, color='#555')
    plt.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)


def chart_cumulative(data, indices, days, title, path):
    fig, ax = plt.subplots(figsize=(13, 5.5))
    _setup_ax(ax, fig)
    plotted = 0
    for ticker, df in data.items():
        name = INDICES[ticker][0]
        if name not in indices or name == 'VIX (Volatility)':
            continue
        close = df['Close']
        if len(close) <= days:
            continue
        seg = close.iloc[-days:]
        norm = (seg / float(seg.iloc[0])) * 100
        ax.plot(norm.index, norm.values, label=name, color=COLORS[plotted%len(COLORS)], lw=1.6, alpha=0.9)
        plotted += 1
    ax.axhline(100, color='#666', lw=0.8, ls='--', alpha=0.6)
    ax.set_ylabel('Indexed (Start=100)', fontsize=10, fontweight='bold')
    ax.set_title(title, fontsize=13, fontweight='bold', color='#ffffff', pad=12)
    ax.grid(True, alpha=0.2, color='#555')
    ax.legend(loc='upper center', bbox_to_anchor=(0.5,-0.10), ncol=min(5,plotted),
              fontsize=8, frameon=True, facecolor='#2a2a3e', edgecolor='#555', labelcolor='#ccc')
    plt.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)


def chart_corr_heatmap(corr, title, path, max_n=15):
    if corr is None:
        return False
    if len(corr) > max_n:
        priority = [c for c in MAJOR_INDICES if c in corr.columns]
        rem = [c for c in corr.columns if c not in priority]
        keep = (priority + rem)[:max_n]
        corr = corr.loc[keep, keep]
    n = len(corr)
    fig, ax = plt.subplots(figsize=(max(8, n*0.65), max(6, n*0.55)))
    fig.patch.set_facecolor('#1e1e2e')
    ax.set_facecolor('#1e1e2e')
    cmap = LinearSegmentedColormap.from_list('rg', ['#ff6b6b','#f5bf42','#4cdf8b'])
    im = ax.imshow(corr.values, cmap=cmap, vmin=-1, vmax=1, aspect='auto')
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    short = [c[:12] for c in corr.columns]
    ax.set_xticklabels(short, rotation=45, ha='right', fontsize=7, color='#ccc')
    ax.set_yticklabels(short, fontsize=7, color='#ccc')
    for i in range(n):
        for j in range(n):
            v = corr.iloc[i,j]
            ax.text(j, i, f'{v:.2f}', ha='center', va='center',
                    fontsize=6, color='white' if abs(v)>0.6 else '#1e1e2e')
    ax.set_title(title, fontsize=12, fontweight='bold', color='#ffffff', pad=12)
    cbar = plt.colorbar(im, ax=ax, shrink=0.8, label='Correlation')
    cbar.ax.yaxis.set_tick_params(color='#ccc')
    cbar.ax.yaxis.label.set_color('#ccc')
    plt.setp(plt.getp(cbar.ax, 'yticklabels'), color='#ccc')
    plt.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    return True


# ══════════════════════════════════════════════════════════════════════════════
# PDF ASSEMBLY
# ══════════════════════════════════════════════════════════════════════════════

def _cv(val, fmt="+.2f"):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "—"
    c = '#00864e' if val>0 else '#c62828' if val<0 else '#333'
    return f"<font color='{c}'>{val:{fmt}}%</font>"

def _bcv(val, fmt="+.2f"):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "—"
    c = '#00864e' if val>0 else '#c62828' if val<0 else '#333'
    return f"<font color='{c}'><b>{val:{fmt}}%</b></font>"


def build_pdf(returns_df, inv_ret, correlations, data, charts, out_path):
    doc = SimpleDocTemplate(out_path, pagesize=landscape(A4),
                            leftMargin=0.4*inch, rightMargin=0.4*inch,
                            topMargin=0.4*inch, bottomMargin=0.4*inch)
    S = getSampleStyleSheet()
    pw = landscape(A4)[0] - 0.8*inch

    ts = ParagraphStyle('T', parent=S['Title'], fontSize=24, spaceAfter=4,
                        textColor=rl_colors.HexColor("#0d1b2a"), fontName='Helvetica-Bold')
    ss = ParagraphStyle('ST', parent=S['Normal'], fontSize=11,
                        textColor=rl_colors.HexColor("#555"), spaceAfter=10)
    h1 = ParagraphStyle('H1', parent=S['Heading1'], fontSize=16, spaceAfter=6,
                        spaceBefore=10, textColor=rl_colors.HexColor("#1b263b"), fontName='Helvetica-Bold')
    h2 = ParagraphStyle('H2', parent=S['Heading2'], fontSize=13, spaceAfter=5,
                        spaceBefore=8, textColor=rl_colors.HexColor("#415a77"), fontName='Helvetica-Bold')
    bd = ParagraphStyle('B', parent=S['Normal'], fontSize=9, leading=12, spaceAfter=5)
    sm = ParagraphStyle('SM', parent=S['Normal'], fontSize=7, leading=9)
    tn = ParagraphStyle('TN', parent=S['Normal'], fontSize=6.5, leading=8)
    ds = ParagraphStyle('DS', parent=S['Normal'], fontSize=7, leading=9, textColor=rl_colors.HexColor("#888"))

    story = []

    def img(fp, w=None, h=None):
        if fp and os.path.exists(fp):
            story.append(RLImage(fp, width=w or pw, height=h or pw*0.42))

    def tbl_style():
        return [
            ('BACKGROUND', (0,0), (-1,0), rl_colors.HexColor("#1b263b")),
            ('TEXTCOLOR', (0,0), (-1,0), rl_colors.white),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('ALIGN', (2,0), (-1,-1), 'RIGHT'), ('ALIGN', (0,0), (1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.4, rl_colors.HexColor("#ccc")),
            ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('LEFTPADDING', (0,0), (-1,-1), 3), ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ]

    def alt_rows(style, n):
        for i in range(1, n):
            if i%2==0:
                style.append(('BACKGROUND', (0,i), (-1,i), rl_colors.HexColor("#f4f6f8")))

    now = datetime.now()
    mkt = returns_df[returns_df['Index'] != 'VIX (Volatility)'].copy()

    # ── TITLE ──
    story.append(Spacer(1, 1.0*inch))
    story.append(Paragraph("Global Stock Market Report", ts))
    story.append(HRFlowable(width="80%", thickness=2, color=rl_colors.HexColor("#415a77"),
                            spaceAfter=8, spaceBefore=4))
    story.append(Paragraph(f"Report Date: {now.strftime('%B %d, %Y')} | {now.strftime('%H:%M')}", ss))
    story.append(Paragraph(
        f"<b>{len(returns_df)} indices</b> across <b>{returns_df['Country'].nunique()} countries/regions</b>", ss))
    story.append(Spacer(1, 0.2*inch))

    # ── EXECUTIVE SUMMARY ──
    story.append(Paragraph("Executive Summary", h1))
    if '5D' in mkt.columns:
        v = mkt['5D'].dropna()
        if len(v):
            a = v.mean(); p = (v>0).sum()/len(v)*100
            if a<-2: rg,rc = "BROAD SELLOFF","#c62828"
            elif a<-0.5: rg,rc = "MILD BEARISH","#e65100"
            elif a<0.5: rg,rc = "NEUTRAL / MIXED","#f57f17"
            elif a<2: rg,rc = "MILD BULLISH","#2e7d32"
            else: rg,rc = "STRONG RALLY","#00864e"
            story.append(Paragraph(
                f"<b>5-Day Global Regime:</b> <font color='{rc}'><b>{rg}</b></font> — "
                f"Avg: {a:+.2f}% | {p:.0f}% positive", bd))

    vix = returns_df[returns_df['Index']=='VIX (Volatility)']
    if not vix.empty:
        vp = vix.iloc[0]['Last Price']
        vc = '#c62828' if vp>20 else '#f57f17' if vp>15 else '#00864e'
        story.append(Paragraph(
            f"<b>VIX:</b> <font color='{vc}'><b>{vp:.2f}</b></font> — "
            f"{'Elevated' if vp>20 else 'Moderate' if vp>15 else 'Low'}", bd))

    for period in ['1D','5D','10D','1M']:
        if period not in mkt.columns: continue
        vd = mkt.dropna(subset=[period])
        if vd.empty: continue
        b = vd.loc[vd[period].idxmax()]; w = vd.loc[vd[period].idxmin()]
        story.append(Paragraph(
            f"<b>{period}:</b> Avg {vd[period].mean():+.2f}% | "
            f"Best: {b['Index']} ({b[period]:+.2f}%) | "
            f"Worst: {w['Index']} ({w[period]:+.2f}%)", bd))

    for reg in ['Americas','Europe','Asia-Pacific']:
        rd = mkt[(mkt['Region']==reg) & mkt['5D'].notna()] if '5D' in mkt.columns else pd.DataFrame()
        if not rd.empty:
            story.append(Paragraph(
                f"<b>{reg} (5D):</b> Avg {rd['5D'].mean():+.2f}% — "
                f"{(rd['5D']>0).sum()} up, {(rd['5D']<=0).sum()} down", bd))

    story.append(PageBreak())

    # ── REGIONAL CHART ──
    story.append(Paragraph("Regional Performance Comparison", h1))
    img(charts.get('regional'), h=pw*0.38)
    story.append(PageBreak())

    # ── SHORT-TERM TABLE ──
    story.append(Paragraph("Short-Term Returns — 1D / 5D / 10D / 1M", h1))
    sc = '5D' if '5D' in mkt.columns else '1D'
    sm_df = mkt.sort_values(sc, ascending=False, na_position='last')
    hd = ["Country","Index","Price","1D %","5D %","10D %","1M %"]
    td = [hd]
    for _, r in sm_df.iterrows():
        td.append([Paragraph(str(r['Country']),tn), Paragraph(str(r['Index']),tn),
                   Paragraph(f"{r['Last Price']:,.2f}",tn)] +
                  [Paragraph(_bcv(r.get(p)),tn) for p in ['1D','5D','10D','1M']])
    cw = [1.3*inch,1.8*inch,0.9*inch]+[0.75*inch]*4
    t = Table(td, colWidths=cw, repeatRows=1)
    st = tbl_style(); alt_rows(st, len(td))
    t.setStyle(TableStyle(st)); story.append(t)
    story.append(PageBreak())

    # ── FULL TABLE ──
    story.append(Paragraph("Full Return Comparison — All Periods", h1))
    plabels = [l for l,_ in RETURN_PERIODS]
    hd2 = ["Country","Index","Price"] + plabels
    td2 = [hd2]
    for _, r in sm_df.iterrows():
        td2.append([Paragraph(str(r['Country']),tn), Paragraph(str(r['Index']),tn),
                    Paragraph(f"{r['Last Price']:,.0f}",tn)] +
                   [Paragraph(_cv(r.get(p)),tn) for p in plabels])
    cw2 = [0.85*inch,1.1*inch,0.55*inch]+[0.52*inch]*len(plabels)
    t2 = Table(td2, colWidths=cw2, repeatRows=1)
    st2 = tbl_style(); alt_rows(st2, len(td2))
    t2.setStyle(TableStyle(st2)); story.append(t2)
    story.append(PageBreak())

    # ── BAR CHARTS ──
    for col, lbl in [('5D','5-Day'),('1M','1-Month')]:
        k = f'bar_{col.lower()}'
        if k in charts:
            story.append(Paragraph(f"{lbl} Returns — All Indices", h1))
            img(charts[k], h=pw*0.55)
            story.append(PageBreak())

    # ── INVESTMENT RETURN CHARTS ──
    story.append(Paragraph("'If I Invested N Days Ago...' — Returns as of Today", h1))
    story.append(Paragraph(
        "These charts answer: <b>if I had put money into each index N trading days ago, "
        "what would my total return be today?</b> X-axis = how many days ago (most recent on right). "
        "Y-axis = your cumulative return percentage.", bd))
    for key, lbl in [('inv_short','Last 30 Trading Days'),
                     ('inv_medium','Last 90 Trading Days'),
                     ('inv_long','Last 252 Trading Days (~1 Year)')]:
        story.append(Paragraph(lbl, h2))
        img(charts.get(key), h=pw*0.36)
        story.append(Spacer(1, 0.08*inch))
    story.append(PageBreak())

    # ── CUMULATIVE CHARTS ──
    story.append(Paragraph("Cumulative Performance — Indexed to 100", h1))
    story.append(Paragraph("Each index is rebased to 100 at the start of the window.", bd))
    for key, lbl in [('cum_30d','Last 30 Trading Days'),('cum_1y','Last 1 Year')]:
        story.append(Paragraph(lbl, h2))
        img(charts.get(key), h=pw*0.36)
        story.append(Spacer(1, 0.08*inch))
    story.append(PageBreak())

    # ── CORRELATION HEATMAPS ──
    story.append(Paragraph("Cross-Market Correlation Analysis", h1))
    story.append(Paragraph(
        "Heatmaps of daily return correlations. Green = move together. Red = move inversely. "
        "Correlations tend to spike during crises.", bd))
    for lbl, _ in CORR_PERIODS:
        k = f'corr_{lbl}'
        if k in charts and os.path.exists(charts[k]):
            story.append(Paragraph(f"Correlation — {lbl} Period", h2))
            img(charts[k], h=pw*0.52)
            story.append(PageBreak())

    # ── LONGER-TERM TABLE ──
    story.append(Paragraph("Longer-Term Returns: 3M / 6M / 1Y / 2Y / 3Y / 5Y", h1))
    lp = [p for p in ['3M','6M','1Y','2Y','3Y','5Y'] if p in mkt.columns]
    if '1Y' in mkt.columns:
        sl = mkt.sort_values('1Y', ascending=False, na_position='last')
    else:
        sl = mkt
    hd3 = ["Country","Index","Price"] + lp
    td3 = [hd3]
    for _, r in sl.iterrows():
        td3.append([Paragraph(str(r['Country']),sm), Paragraph(str(r['Index']),sm),
                    Paragraph(f"{r['Last Price']:,.0f}",sm)] +
                   [Paragraph(_bcv(r.get(p)),sm) for p in lp])
    cw3 = [1.2*inch,1.6*inch,0.8*inch]+[0.8*inch]*len(lp)
    t3 = Table(td3, colWidths=cw3, repeatRows=1)
    st3 = tbl_style(); alt_rows(st3, len(td3))
    t3.setStyle(TableStyle(st3)); story.append(t3)

    story.append(Spacer(1, 0.3*inch))
    story.append(HRFlowable(width="100%", thickness=1, color=rl_colors.HexColor("#ccc"), spaceAfter=6))
    story.append(Paragraph(
        f"<i>Data: Yahoo Finance via yfinance. Generated {now.strftime('%B %d, %Y %H:%M')}. "
        f"Past performance ≠ future results. Informational only, not investment advice.</i>", ds))

    doc.build(story)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    data = fetch_data()
    if len(data) < 3:
        print("\nERROR: Not enough data. Check internet connection.")
        sys.exit(1)

    print("\nComputing returns...")
    returns_df = compute_returns(data)

    print("Computing investment returns...")
    inv_ret = compute_investment_returns(data, 260)

    print("Computing correlations...")
    corrs = {}
    for lbl, days in CORR_PERIODS:
        c = compute_correlations(data, days)
        if c is not None:
            corrs[lbl] = c
            print(f"  ✓ {lbl}: {c.shape[0]}x{c.shape[1]}")

    print("\nGenerating charts...")
    tmpdir = tempfile.mkdtemp(prefix='mkt_rpt_')
    charts = {}
    avail = [m for m in MAJOR_INDICES if m in inv_ret.columns]
    mkt_df = returns_df[returns_df['Index'] != 'VIX (Volatility)']

    for key, days, title in [
        ('inv_short', 30, 'If I Invested N Days Ago — Last 30 Trading Days'),
        ('inv_medium', 90, 'If I Invested N Days Ago — Last 90 Trading Days'),
        ('inv_long', 252, 'If I Invested N Days Ago — Last 1 Year'),
    ]:
        f = os.path.join(tmpdir, f'{key}.png')
        chart_investment_returns(inv_ret, avail, days, title, f)
        charts[key] = f; print(f"  ✓ {key}")

    for col, lbl in [('5D','5-Day'),('1M','1-Month')]:
        if col in mkt_df.columns:
            f = os.path.join(tmpdir, f'bar_{col.lower()}.png')
            chart_bars(mkt_df, col, f'{lbl} Returns — All Indices', f)
            charts[f'bar_{col.lower()}'] = f; print(f"  ✓ bar_{col.lower()}")

    f = os.path.join(tmpdir, 'regional.png')
    chart_regional(returns_df, f)
    charts['regional'] = f; print("  ✓ regional")

    for days, key in [(30,'cum_30d'), (252,'cum_1y')]:
        f = os.path.join(tmpdir, f'{key}.png')
        chart_cumulative(data, avail, days,
                         f"Cumulative Performance — {'30 Days' if days==30 else '1 Year'} (Indexed to 100)", f)
        charts[key] = f; print(f"  ✓ {key}")

    for lbl in ['5D','1M','3M','1Y']:
        if lbl in corrs:
            f = os.path.join(tmpdir, f'corr_{lbl}.png')
            if chart_corr_heatmap(corrs[lbl], f"Daily Return Correlations — {lbl}", f):
                charts[f'corr_{lbl}'] = f; print(f"  ✓ corr_{lbl}")

    print("\nBuilding PDF...")
    out = f"global_market_report_{datetime.now().strftime('%Y-%m-%d')}.pdf"
    build_pdf(returns_df, inv_ret, corrs, data, charts, out)

    # Cleanup
    for f in charts.values():
        try: os.remove(f)
        except: pass
    try: os.rmdir(tmpdir)
    except: pass

    print(f"\n{'='*70}")
    print(f"  ✅ REPORT SAVED: {os.path.abspath(out)}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
