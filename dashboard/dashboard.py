import time
from typing import Any, Dict, List

import streamlit as st

from config import (
    ENABLE_AUTO_REFRESH,
    ENABLE_SIGNAL_CARDS,
    ENABLE_TABLE_VIEW,
    PAGE_ICON,
    PAGE_TITLE,
    REFRESH_INTERVAL,
)

from data_loader import get_latest_articles, get_latest_signals
from app.backtester import load_tracked_performance, summarize_tracked_performance
from components import (
    render_articles_table,
    render_sidebar_filters,
    render_signal_card,
    render_signals_table,
)


st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")


# ---------------------------
# DATA HELPERS
# ---------------------------


def _extract_filter_values(signals: List[Dict[str, Any]]):
    actions = set()
    assets = set()
    themes = set()

    for s in signals:
        if s.get("action"):
            actions.add(str(s.get("action")))
        if s.get("theme"):
            themes.add(str(s.get("theme")))

        for asset in s.get("assets", []) or []:
            assets.add(str(asset))

    return actions, assets, themes



def _apply_filters(signals: List[Dict[str, Any]], filters: Dict[str, Any]):
    result = []

    for s in signals:
        if filters["actions"] and s.get("action") not in filters["actions"]:
            continue

        if filters["themes"] and s.get("theme") not in filters["themes"]:
            continue

        if filters["assets"]:
            signal_assets = s.get("assets", []) or []
            if not any(asset in filters["assets"] for asset in signal_assets):
                continue

        if s.get("confidence", 0) < filters["min_confidence"]:
            continue

        result.append(s)

    return result[: filters["max_rows"]]


# ---------------------------
# SIGNAL PRIORITY & METRICS HELPERS
# ---------------------------

def _signal_priority(signal: Dict[str, Any]) -> tuple:
    """Ranking key for signals: confidence first, then asset breadth, then BUY/SELL over HOLD."""
    action = str(signal.get("action") or "").upper()
    action_weight = 0
    if action == "BUY":
        action_weight = 2
    elif action == "SELL":
        action_weight = 1

    confidence = int(signal.get("confidence") or 0)
    assets_count = len(signal.get("assets", []) or [])
    return (confidence, action_weight, assets_count)


def _count_actions(signals: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
    for signal in signals:
        action = str(signal.get("action") or "").upper()
        if action in counts:
            counts[action] += 1
    return counts


def _average_confidence(signals: List[Dict[str, Any]]) -> float:
    if not signals:
        return 0.0
    values = [int(signal.get("confidence") or 0) for signal in signals]
    return round(sum(values) / len(values), 2)


def _top_assets(signals: List[Dict[str, Any]], limit: int = 3) -> str:
    asset_counts: Dict[str, int] = {}
    for signal in signals:
        for asset in signal.get("assets", []) or []:
            key = str(asset)
            asset_counts[key] = asset_counts.get(key, 0) + 1

    if not asset_counts:
        return "-"

    ranked = sorted(asset_counts.items(), key=lambda item: item[1], reverse=True)
    return ", ".join(asset for asset, _ in ranked[:limit])


def _resolve_position_size(signal: Dict[str, Any]) -> float:
    """Fallback position sizing when DB does not store it yet."""
    raw_value = signal.get("position_size")
    if raw_value not in (None, ""):
        try:
            return round(float(raw_value), 2)
        except (TypeError, ValueError):
            pass

    confidence = int(signal.get("confidence") or 0)
    action = str(signal.get("action") or "").upper()

    if action == "HOLD" or confidence <= 1:
        return 0.0
    if confidence >= 5:
        return 1.0
    if confidence == 4:
        return 0.7
    if confidence == 3:
        return 0.4
    if confidence == 2:
        return 0.2
    return 0.0


def _apply_quick_filters(signals: List[Dict[str, Any]], mode: str) -> List[Dict[str, Any]]:
    """Apply high-level quick filters shown at the top of the dashboard."""
    if mode == "strong":
        return [signal for signal in signals if int(signal.get("confidence") or 0) >= 4]
    if mode == "buy":
        return [signal for signal in signals if str(signal.get("action") or "").upper() == "BUY"]
    if mode == "sell":
        return [signal for signal in signals if str(signal.get("action") or "").upper() == "SELL"]
    if mode == "hold":
        return [signal for signal in signals if str(signal.get("action") or "").upper() == "HOLD"]
    return signals


def _render_quick_filter_control() -> str:
    """Render a quick filter control compatible with older Streamlit versions."""
    options = ["all", "strong", "buy", "sell", "hold"]

    if hasattr(st, "segmented_control"):
        value = st.segmented_control(
            "Quick View",
            options=options,
            default="all",
            selection_mode="single",
        )
        return str(value or "all")

    return str(
        st.radio(
            "Quick View",
            options=options,
            index=0,
            horizontal=True,
        )
    )


def _high_conviction_signals(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return only the strongest actionable signals."""
    return [
        signal
        for signal in signals
        if str(signal.get("action") or "").upper() != "HOLD"
        and int(signal.get("confidence") or 0) >= 4
    ]




def _other_signals(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return the remaining lower-priority signals."""
    return [signal for signal in signals if signal not in _high_conviction_signals(signals)]


# ---------------------------
# NEWS PRIORITY HELPERS
# ---------------------------

def _article_priority(article: Dict[str, Any]) -> tuple:
    """Rank news by impact first, then by whether assets were identified."""
    impact = int(article.get("impact_score") or 0)
    assets_count = len(article.get("assets", []) or [])
    return (impact, assets_count)


def _top_market_news(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return the strongest market-moving articles for the News tab."""
    ranked = sorted(articles, key=_article_priority, reverse=True)
    return [article for article in ranked if int(article.get("impact_score") or 0) >= 4][:8]


def _performance_priority(row: Dict[str, Any]) -> tuple:
    """Rank tracked trades by recency and weighted return magnitude."""
    created_at = str(row.get("created_at") or "")
    weighted = abs(float(row.get("weighted_return_pct") or 0.0))
    return (created_at, weighted)



def _format_pct(value: Any) -> str:
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "-"


# ---------------------------
# MAIN APP
# ---------------------------

st.title("📊 Trading Signals Dashboard")

signals = get_latest_signals()
for signal in signals:
    signal["position_size"] = _resolve_position_size(signal)

signals = sorted(signals, key=_signal_priority, reverse=True)
articles = get_latest_articles()
articles = sorted(articles, key=_article_priority, reverse=True)

performance_rows = load_tracked_performance(limit=200)
performance_rows = sorted(performance_rows, key=_performance_priority, reverse=True)
performance_summary = summarize_tracked_performance(limit=500)

# ---------------------------
# TOP METRICS
# ---------------------------

action_counts = _count_actions(signals)
avg_confidence = _average_confidence(signals)
top_assets = _top_assets(signals)
high_conviction_count = len(_high_conviction_signals(signals))

metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
metric_col1.metric("Total Signals", len(signals))
metric_col2.metric("High Conviction", high_conviction_count)
metric_col3.metric("BUY / SELL / HOLD", f"{action_counts['BUY']} / {action_counts['SELL']} / {action_counts['HOLD']}")
metric_col4.metric("Avg Confidence", avg_confidence)
metric_col5.metric("Top Assets", top_assets)

st.markdown("---")

actions, assets, themes = _extract_filter_values(signals)
filters = render_sidebar_filters(actions, assets, themes)
filtered_signals = _apply_filters(signals, filters)

# ---------------------------
# QUICK FILTERS
# ---------------------------

quick_filter = _render_quick_filter_control()
filtered_signals = _apply_quick_filters(filtered_signals, quick_filter)


# ---------------------------
# MAIN CONTENT TABS
# ---------------------------

signals_tab, news_tab, performance_tab = st.tabs(["Signals", "News", "Performance"])

with signals_tab:
    st.subheader("Top Ranked Signals")

    if not filtered_signals:
        st.info("No signals match current filters.")
    else:
        high_conviction = _high_conviction_signals(filtered_signals)
        remaining_signals = _other_signals(filtered_signals)

        if high_conviction:
            st.markdown("## 🔥 High Conviction Trades")
            st.caption("Only signals with confidence ≥ 4 and action different from HOLD.")
            for signal in high_conviction:
                assets = signal.get("assets") or []
                decision = signal.get("portfolio_decision")

                if assets and decision:
                    if len(assets) == 1:
                        st.caption(f"Portfolio: {decision}")
                    else:
                        st.markdown("**Portfolio Decisions:**")
                        for asset in assets:
                            st.caption(f"{asset} → {decision}")
                render_signal_card(signal)

        if remaining_signals and ENABLE_SIGNAL_CARDS:
            st.markdown("## Other Signals")
            for signal in remaining_signals:
                assets = signal.get("assets") or []
                decision = signal.get("portfolio_decision")

                if assets and decision:
                    if len(assets) == 1:
                        st.caption(f"Portfolio: {decision}")
                    else:
                        st.markdown("**Portfolio Decisions:**")
                        for asset in assets:
                            st.caption(f"{asset} → {decision}")
                render_signal_card(signal)

        if ENABLE_TABLE_VIEW:
            st.markdown("---")
            st.subheader("Signals Table")
            render_signals_table(filtered_signals)

with news_tab:
    st.subheader("Top Market News")
    st.caption("Highest-impact tradable news after filtering and enrichment.")

    top_news = _top_market_news(articles)
    if top_news:
        for article in top_news:
            with st.container(border=True):
                st.markdown(f"### {article.get('title', '')}")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Impact", article.get("impact_score") or "-")
                col2.metric("Theme", article.get("theme") or "-")
                col3.metric("Sentiment", article.get("sentiment") or "-")
                col4.metric("Assets", ", ".join(article.get("assets") or []) or "-")

                source = str(article.get("source") or "")
                published_at = str(article.get("published_at") or "")
                summary = str(article.get("summary") or "")

                if source or published_at:
                    st.caption(" • ".join(part for part in [source, published_at] if part))

                if summary:
                    st.write(summary)
    else:
        st.info("No high-impact market news available.")

    st.markdown("---")
    with st.expander("All Filtered News", expanded=False):
        render_articles_table(articles)



# ---------------------------
# PERFORMANCE TAB
# ---------------------------

with performance_tab:
    st.subheader("Tracked Performance")
    st.caption("Backtested trades persisted in SQLite after signals are generated.")

    perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
    perf_col1.metric("Tracked Trades", performance_summary.get("trades", 0))
    perf_col2.metric("Win Rate", _format_pct(performance_summary.get("win_rate", 0.0)))
    perf_col3.metric("Avg Return", _format_pct(performance_summary.get("avg_return_pct", 0.0)))
    perf_col4.metric("Total Weighted Return", _format_pct(performance_summary.get("total_weighted_return_pct", 0.0)))

    if not performance_rows:
        st.info("No tracked performance rows yet. Recent signals may still be waiting for enough market data to close the holding window.")
    else:
        for row in performance_rows[:20]:
            with st.container(border=True):
                title = str(row.get("title") or "")
                asset = str(row.get("asset") or "")
                action = str(row.get("action") or "")
                outcome = str(row.get("outcome") or "")

                st.markdown(f"### {title}")

                row_col1, row_col2, row_col3, row_col4 = st.columns(4)
                row_col1.metric("Asset", asset or "-")
                row_col2.metric("Action", action or "-")
                row_col3.metric("Return", _format_pct(row.get("return_pct")))
                row_col4.metric("Weighted", _format_pct(row.get("weighted_return_pct")))

                meta_line = " • ".join(
                    part
                    for part in [
                        f"Confidence: {row.get('confidence', '-')}",
                        f"Size: {row.get('position_size', '-')}",
                        f"Outcome: {outcome or '-'}",
                        f"Created: {row.get('created_at', '-')}",
                    ]
                    if part
                )
                if meta_line:
                    st.caption(meta_line)

        st.markdown("---")
        st.subheader("Performance Table")
        st.dataframe(performance_rows, use_container_width=True, hide_index=True)


# ---------------------------
# AUTO REFRESH
# ---------------------------

if ENABLE_AUTO_REFRESH:
    st.markdown(f"⏳ Auto-refresh every {REFRESH_INTERVAL}s")
    time.sleep(REFRESH_INTERVAL)
    st.rerun()