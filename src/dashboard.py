"""CodeBouncer Security Dashboard — Local Streamlit app."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import altair as alt
from dotenv import load_dotenv

load_dotenv()

from bouncer_logic import config

@st.cache_resource
def get_connection():
    return config.get_snowflake_connection()

conn = get_connection()

st.set_page_config(page_title="CodeBouncer", layout="wide")

# -- Minimal custom styling ---------------------------------------------------
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] {background: #1a1c24;}
    .severity-crit {color:#cf3838; font-weight:700}
    .severity-high {color:#e07930; font-weight:600}
    .severity-med  {color:#c9a825}
    .severity-low  {color:#2d8a4e}
    </style>
    """,
    unsafe_allow_html=True,
)

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
SEVERITY_COLORS = ["#cf3838", "#e07930", "#c9a825", "#2d8a4e"]
SEVERITY_ICONS = {"CRITICAL": "\u25cf", "HIGH": "\u25cf", "MEDIUM": "\u25cf", "LOW": "\u25cf"}


def run_query(sql, params=None):
    """Execute a query and return a pandas DataFrame."""
    cur = conn.cursor()
    try:
        cur.execute(sql, params or ())
        columns = [desc[0] for desc in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=columns)
    finally:
        cur.close()


# -- Sidebar ------------------------------------------------------------------
st.sidebar.title("CodeBouncer")
st.sidebar.caption("Security Audit Dashboard")

repos_df = run_query(
    "SELECT REPO_NAME FROM CODEBOUNCER.CORE.REPOSITORY_CONFIG WHERE IS_ACTIVE = TRUE"
)
repo_names = repos_df["REPO_NAME"].tolist() if not repos_df.empty else []
selected_repo = st.sidebar.selectbox(
    "Repository",
    repo_names if repo_names else ["No repos configured"],
)

scans_df = run_query(
    """SELECT SCAN_ID, COMMIT_HASH, STARTED_AT, FINDINGS_COUNT
       FROM CODEBOUNCER.CORE.SCAN_HISTORY
       WHERE STATUS = 'COMPLETED'
       ORDER BY STARTED_AT DESC
       LIMIT 20"""
)

selected_scan = None
if not scans_df.empty:
    scan_labels = {}
    for _, row in scans_df.iterrows():
        commit = str(row["COMMIT_HASH"] or "")[:7] or "full"
        label = f"{commit} \u2014 {row['STARTED_AT']}"
        scan_labels[label] = row["SCAN_ID"]
    selected_label = st.sidebar.selectbox("Scan", list(scan_labels.keys()))
    selected_scan = scan_labels[selected_label]
else:
    st.sidebar.warning("No completed scans yet.")

severity_filter = st.sidebar.multiselect(
    "Severity",
    SEVERITY_ORDER,
    default=["CRITICAL", "HIGH", "MEDIUM"],
)

# -- Main content -------------------------------------------------------------
st.title("Security Findings")

if not selected_scan:
    st.info(
        "No scan selected. Run a scan first:\n\n"
        "```\npython src/scan.py https://github.com/user/repo\n```"
    )
    st.stop()

# Metrics
metrics_df = run_query(
    "SELECT * FROM CODEBOUNCER.CORE.SCAN_RESULTS WHERE SCAN_ID = %s",
    (selected_scan,),
)
total = len(metrics_df)
counts = {s: int((metrics_df["SEVERITY"] == s).sum()) for s in SEVERITY_ORDER}

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total", total)
col2.metric("Critical", counts.get("CRITICAL", 0))
col3.metric("High", counts.get("HIGH", 0))
col4.metric("Medium", counts.get("MEDIUM", 0))
col5.metric("Low", counts.get("LOW", 0))

st.divider()

# -- Heatmap ------------------------------------------------------------------
st.subheader("File Risk Heatmap")

heatmap_df = (
    metrics_df.groupby(["FILE_PATH", "SEVERITY"])
    .size()
    .reset_index(name="FINDING_COUNT")
)

if heatmap_df.empty:
    st.success("No findings for this scan.")
    st.stop()

heatmap_df["SHORT_PATH"] = heatmap_df["FILE_PATH"].apply(
    lambda p: "/".join(str(p).rsplit("/", 3)[-3:])
)

heatmap = (
    alt.Chart(heatmap_df)
    .mark_rect(stroke="#2a2d37", strokeWidth=1)
    .encode(
        x=alt.X("SEVERITY:N", sort=SEVERITY_ORDER, title=None),
        y=alt.Y("SHORT_PATH:N", title=None, sort="-x"),
        color=alt.Color(
            "FINDING_COUNT:Q",
            scale=alt.Scale(scheme="reds"),
            title="Count",
        ),
        tooltip=["FILE_PATH", "SEVERITY", "FINDING_COUNT"],
    )
    .properties(height=max(260, len(heatmap_df["FILE_PATH"].unique()) * 28))
)
st.altair_chart(heatmap, use_container_width=True)

st.divider()

# -- Findings detail ----------------------------------------------------------
st.subheader("Findings")

if severity_filter:
    filtered = metrics_df[metrics_df["SEVERITY"].isin(severity_filter)].copy()
else:
    filtered = metrics_df.copy()

if filtered.empty:
    st.info("No findings match the selected severity filter.")
    st.stop()

for _, row in filtered.iterrows():
    sev = row["SEVERITY"]
    color = dict(zip(SEVERITY_ORDER, SEVERITY_COLORS)).get(sev, "#888")
    label = (
        f":{color}[{SEVERITY_ICONS.get(sev, '')}] **{sev}** | "
        f"{row['VULN_TYPE']} \u2014 `{row['FILE_PATH']}"
        f":{row['LINE_NUMBER'] or '?'}`"
    )
    with st.expander(label):
        st.markdown(f"**Description:** {row['DESCRIPTION']}")
        if row["CODE_SNIPPET"]:
            st.code(row["CODE_SNIPPET"])
        if row["FIX_SUGGESTION"]:
            st.markdown("**Suggested fix:**")
            st.code(row["FIX_SUGGESTION"])
        st.caption(
            f"Model: {row['MODEL_USED']}  \u00b7  "
            f"Confidence: {row['CONFIDENCE']:.0%}"
        )
