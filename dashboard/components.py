

from typing import Any, Dict, Iterable, List

import pandas as pd
import streamlit as st


ACTION_EMOJI = {
    "BUY": "🟢",
    "SELL": "🔴",
    "HOLD": "🟡",
}



def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)



def _format_assets(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(asset) for asset in value)
    return str(value)



def _signal_badge(action: str) -> str:
    normalized = _safe_str(action).upper()
    return f"{ACTION_EMOJI.get(normalized, '⚪')} {normalized or 'UNKNOWN'}"



def render_signal_card(signal_row: Dict[str, Any]) -> None:
    """Render a single signal as a compact Streamlit card."""
    title = _safe_str(signal_row.get("title"))
    action = _safe_str(signal_row.get("action") or signal_row.get("final_action"))
    assets = _format_assets(signal_row.get("assets"))
    confidence = signal_row.get("confidence", "")
    position_size = signal_row.get("position_size", "")
    reason = _safe_str(signal_row.get("reason"))
    theme = _safe_str(signal_row.get("theme"))
    sentiment = _safe_str(signal_row.get("sentiment"))
    technical_bias = _safe_str(signal_row.get("technical_bias"))
    risk_reason = _safe_str(signal_row.get("risk_reason"))
    published_at = _safe_str(signal_row.get("published_at"))

    with st.container(border=True):
        st.markdown(f"### {_signal_badge(action)}  {title}")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Confidence", confidence)
        col2.metric("Position Size", position_size)
        col3.metric("Theme", theme or "-")
        col4.metric("Sentiment", sentiment or "-")

        if assets:
            st.markdown(f"**Assets:** {assets}")

        if published_at:
            st.caption(f"Published: {published_at}")

        if reason:
            st.write(reason)

        meta_parts: List[str] = []
        if technical_bias:
            meta_parts.append(f"Technicals: {technical_bias}")
        if risk_reason:
            meta_parts.append(f"Risk: {risk_reason}")

        if meta_parts:
            st.caption(" • ".join(meta_parts))



def render_signals_table(signals: Iterable[Dict[str, Any]]) -> None:
    """Render a dataframe view for signal rows."""
    rows = list(signals)
    if not rows:
        st.info("No signals available.")
        return

    normalized_rows = []
    for row in rows:
        normalized_rows.append(
            {
                "Title": _safe_str(row.get("title")),
                "Action": _safe_str(row.get("action") or row.get("final_action")),
                "Assets": _format_assets(row.get("assets")),
                "Confidence": row.get("confidence"),
                "Position Size": row.get("position_size"),
                "Theme": _safe_str(row.get("theme")),
                "Sentiment": _safe_str(row.get("sentiment")),
                "Technical Bias": _safe_str(row.get("technical_bias")),
                "Published": _safe_str(row.get("published_at")),
                "Reason": _safe_str(row.get("reason")),
            }
        )

    df = pd.DataFrame(normalized_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)



def render_articles_table(articles: Iterable[Dict[str, Any]]) -> None:
    """Render latest raw/enriched articles as a dataframe."""
    rows = list(articles)
    if not rows:
        st.info("No articles available.")
        return

    normalized_rows = []
    for row in rows:
        normalized_rows.append(
            {
                "Title": _safe_str(row.get("title")),
                "Source": _safe_str(row.get("source")),
                "Theme": _safe_str(row.get("theme")),
                "Sentiment": _safe_str(row.get("sentiment")),
                "Impact": row.get("impact_score"),
                "Assets": _format_assets(row.get("assets")),
                "Published": _safe_str(row.get("published_at")),
                "Summary": _safe_str(row.get("summary")),
            }
        )

    df = pd.DataFrame(normalized_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)



def render_sidebar_filters(
    available_actions: Iterable[str],
    available_assets: Iterable[str],
    available_themes: Iterable[str],
) -> Dict[str, Any]:
    """Render common sidebar filters and return their selected values."""
    with st.sidebar:
        st.header("Filters")

        action_options = [option for option in available_actions if option]
        asset_options = [option for option in available_assets if option]
        theme_options = [option for option in available_themes if option]

        selected_actions = st.multiselect(
            "Action",
            options=sorted(set(action_options)),
            default=[],
        )
        selected_assets = st.multiselect(
            "Assets",
            options=sorted(set(asset_options)),
            default=[],
        )
        selected_themes = st.multiselect(
            "Theme",
            options=sorted(set(theme_options)),
            default=[],
        )
        min_confidence = st.slider(
            "Minimum confidence",
            min_value=1,
            max_value=5,
            value=1,
        )
        max_rows = st.slider(
            "Rows to display",
            min_value=5,
            max_value=100,
            value=25,
            step=5,
        )

    return {
        "actions": selected_actions,
        "assets": selected_assets,
        "themes": selected_themes,
        "min_confidence": min_confidence,
        "max_rows": max_rows,
    }