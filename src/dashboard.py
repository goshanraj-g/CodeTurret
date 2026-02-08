"""CodeBouncer Security Dashboard — Streamlit in Snowflake."""

import streamlit as st
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import col
import altair as alt

session = get_active_session()

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

# -- Sidebar ------------------------------------------------------------------
st.sidebar.title("CodeBouncer")
st.sidebar.caption("Security Audit Dashboard")

repos_df = (
    session.table("CODEBOUNCER.CORE.REPOSITORY_CONFIG")
    .filter(col("IS_ACTIVE") == True)
    .select("REPO_NAME")
    .to_pandas()
)
repo_names = repos_df["REPO_NAME"].tolist() if not repos_df.empty else []
selected_repo = st.sidebar.selectbox(
    "Repository",
    repo_names if repo_names else ["No repos configured"],
)

scans_df = (
    session.table("CODEBOUNCER.CORE.SCAN_HISTORY")
    .filter(col("STATUS") == "COMPLETED")
    .sort(col("STARTED_AT").desc())
    .limit(20)
    .select("SCAN_ID", "COMMIT_HASH", "STARTED_AT", "FINDINGS_COUNT")
    .to_pandas()
)

selected_scan = None
if not scans_df.empty:
    scan_labels = {
        f"{row['COMMIT_HASH'][:7]} — {row['STARTED_AT']}": row["SCAN_ID"]
        for _, row in scans_df.iterrows()
    }
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
        "No scan selected. Configure a repository in "
        "`REPOSITORY_CONFIG` then run `CALL RUN_SECURITY_SCAN();`."
    )
    st.stop()

# Metrics
results_table = session.table("CODEBOUNCER.CORE.SCAN_RESULTS").filter(
    col("SCAN_ID") == selected_scan
)
metrics_df = results_table.to_pandas()
total = len(metrics_df)
counts = {s: int((metrics_df["SEVERITY"] == s).sum()) for s in SEVERITY_ORDER}

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total", total)
col2.metric("Critical", counts["CRITICAL"])
col3.metric("High", counts["HIGH"])
col4.metric("Medium", counts["MEDIUM"])
col5.metric("Low", counts["LOW"])

st.divider()

# -- Heatmap ------------------------------------------------------------------
st.subheader("File Risk Heatmap")

heatmap_df = (
    results_table.group_by("FILE_PATH", "SEVERITY")
    .count()
    .to_pandas()
    .rename(columns={"COUNT": "FINDING_COUNT"})
)

if heatmap_df.empty:
    st.success("No findings for this scan.")
    st.stop()

heatmap_df["SHORT_PATH"] = heatmap_df["FILE_PATH"].apply(
    lambda p: "/".join(p.rsplit("/", 3)[-3:])
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

filtered = (
    results_table.filter(col("SEVERITY").isin(severity_filter))
    .sort(
        col("SEVERITY").asc()  # CRITICAL sorts first alphabetically
    )
    .to_pandas()
)

if filtered.empty:
    st.info("No findings match the selected severity filter.")
    st.stop()

for _, row in filtered.iterrows():
    sev = row["SEVERITY"]
    color = dict(zip(SEVERITY_ORDER, SEVERITY_COLORS)).get(sev, "#888")
    label = (
        f":{color}[{SEVERITY_ICONS.get(sev, '')}] **{sev}** | "
        f"{row['VULN_TYPE']} — `{row['FILE_PATH']}"
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
