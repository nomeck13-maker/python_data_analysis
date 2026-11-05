"""Interactive Delivery & Returns dashboard for the seven-table retail training dataset.

Run (Windows PowerShell):
    cd C:\\Users\\Ronn\\DataGripProjects
    python -m streamlit run dashboard.py

Place this file beside analysis.py and the outputs/ folder. If outputs are missing,
use the sidebar button to generate them from the CSVs in Downloads or data/.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

STATUS_ORDER = ["Delivered", "In Transit", "Lost", "Returned to Sender"]
COLORS = {
    "Delivered": "#21867A", "In Transit": "#E3A346",
    "Lost": "#D65458", "Returned to Sender": "#7586B1", "Unknown": "#ADB5BD",
}
PRIMARY = "#236B87"
SECONDARY = "#4A9E94"
REQUIRED_FILES = (
    "orders_clean.csv", "shipments_clean.csv", "returns_clean.csv",
    "order_items_clean.csv", "products_clean.csv",
)


def validate_outputs(output_dir: Path) -> list[str]:
    """Return list of missing cleaned files."""
    return [file for file in REQUIRED_FILES if not (output_dir / file).is_file()]


def load_cleaned(output_dir: Path) -> dict[str, pd.DataFrame]:
    """Load the same cleaned, audited files created by analysis.py."""
    missing = validate_outputs(output_dir)
    if missing:
        raise FileNotFoundError(
            "Missing cleaned datasets in " + str(output_dir) + ": " + ", ".join(missing)
        )
    tables = {
        name: pd.read_csv(output_dir / f"{name}_clean.csv", low_memory=False)
        for name in ("orders", "shipments", "returns", "order_items", "products")
    }
    for name, table in tables.items():
        if "order_id" in table.columns:
            table["order_id"] = table["order_id"].astype("string")
    s = tables["shipments"]
    s["lead_days"] = pd.to_numeric(s["lead_days"], errors="coerce")
    # Defensive check: don't count non-Delivered or negative intervals as lead time.
    s.loc[(s["shipment_status"] != "Delivered") | (s["lead_days"] < 0), "lead_days"] = float("nan")
    s["courier"] = s["courier"].fillna("Unknown")
    s["shipment_status"] = s["shipment_status"].fillna("Unknown")
    items = tables["order_items"]
    items["quantity"] = pd.to_numeric(items["quantity"], errors="coerce")
    tables["item_categories"] = (
        items.loc[items["quantity"] > 0, ["order_id", "product_id"]]
        .merge(tables["products"][["product_id", "category"]],
               on="product_id", how="inner", validate="many_to_one")
        [["order_id", "category"]]
        .drop_duplicates()
    )
    return tables


def build_view(
    tables: dict[str, pd.DataFrame],
    selected_couriers: list[str] | None = None,
    selected_categories: list[str] | None = None,
    selected_statuses: list[str] | None = None,
) -> dict:
    """Calculate every chart from the same filtered order cohort.

    - A category filter means orders containing ANY selected category.
    - Courier/status filters mean shipments matching the selected values.
    - Return rate always uses DISTINCT returned order IDs (not return-record count).
    - Category association does not establish which exact item was returned.
    """
    orders = tables["orders"]
    shipments = tables["shipments"]
    returns = tables["returns"]
    category_links = tables["item_categories"]

    selected_couriers = selected_couriers or []
    selected_categories = selected_categories or []
    selected_statuses = selected_statuses or []

    order_ids = set(orders["order_id"].dropna())
    if selected_categories:
        cat_ids = set(category_links.loc[
            category_links["category"].isin(selected_categories), "order_id"
        ].dropna())
        order_ids &= cat_ids

    shipment_mask = pd.Series(True, index=shipments.index)
    if selected_couriers:
        shipment_mask &= shipments["courier"].isin(selected_couriers)
    if selected_statuses:
        shipment_mask &= shipments["shipment_status"].isin(selected_statuses)

    if selected_couriers or selected_statuses:
        order_ids &= set(shipments.loc[shipment_mask, "order_id"].dropna())

    order_frame = orders.loc[orders["order_id"].isin(order_ids)].copy()
    shipment_frame = shipments.loc[
        shipment_mask & shipments["order_id"].isin(order_ids)
    ].copy()
    return_frame = returns.loc[returns["order_id"].isin(order_ids)].copy()
    returned_ids = set(return_frame["order_id"].dropna())

    total_orders = len(order_frame)
    total_shipments = len(shipment_frame)
    status_counts = shipment_frame["shipment_status"].value_counts()
    order_statuses = STATUS_ORDER + sorted(set(status_counts.index) - set(STATUS_ORDER))
    statuses = pd.DataFrame({"status": order_statuses})
    statuses["shipments"] = statuses["status"].map(status_counts).fillna(0).astype(int)
    statuses["pct"] = statuses["shipments"].div(total_shipments).mul(100) if total_shipments else 0.0

    leads = shipment_frame["lead_days"].dropna()
    return_rate = 100 * len(returned_ids) / total_orders if total_orders else 0.0
    reasons = (return_frame["reason"].fillna("Unspecified")
               .value_counts().rename_axis("reason").reset_index(name="returns"))

    by_courier = shipment_frame.groupby("courier", dropna=False).agg(
        shipments=("shipment_id", "size"),
        delivered=("shipment_status", lambda v: int(v.eq("Delivered").sum())),
        lost=("shipment_status", lambda v: int(v.eq("Lost").sum())),
        avg_delivery_days=("lead_days", "mean"),
        median_delivery_days=("lead_days", "median"),
    ).reset_index()
    if len(by_courier):
        by_courier["delivered_pct"] = 100 * by_courier["delivered"] / by_courier["shipments"]
        by_courier["lost_pct"] = 100 * by_courier["lost"] / by_courier["shipments"]
        courier_order = shipment_frame[["courier", "order_id"]].drop_duplicates()
        courier_order["returned"] = courier_order["order_id"].isin(returned_ids)
        courier_ret = courier_order.groupby("courier").agg(
            orders=("order_id", "nunique"), returned_orders=("returned", "sum")
        ).reset_index()
        by_courier = by_courier.merge(courier_ret, on="courier", how="left", validate="one_to_one")
        by_courier["return_rate_pct"] = (100 * by_courier["returned_orders"]
                                         / by_courier["orders"])
    else:
        for column in ("delivered_pct", "lost_pct", "orders", "returned_orders", "return_rate_pct"):
            by_courier[column] = pd.Series(dtype="float64")

    selected_links = category_links.loc[category_links["order_id"].isin(order_ids)].copy()
    if selected_categories:
        selected_links = selected_links.loc[selected_links["category"].isin(selected_categories)]
    selected_links["returned"] = selected_links["order_id"].isin(returned_ids)
    by_category = selected_links.groupby("category").agg(
        orders=("order_id", "nunique"), returned_orders=("returned", "sum")
    ).reset_index()
    by_category["return_rate_pct"] = (
        100 * by_category["returned_orders"] / by_category["orders"]
    ) if len(by_category) else pd.Series(dtype="float64")

    return {
        "orders": order_frame, "shipments": shipment_frame,
        "returns": return_frame, "status": statuses, "leads": leads,
        "couriers": by_courier, "categories": by_category, "reasons": reasons,
        "kpis": {
            "orders": total_orders,
            "shipments": total_shipments,
            "returned_orders": len(returned_ids),
            "return_records": len(return_frame),
            "return_rate_pct": return_rate,
            "delivered_pct": 100 * status_counts.get("Delivered", 0) / total_shipments if total_shipments else 0.0,
            "in_transit_pct": 100 * status_counts.get("In Transit", 0) / total_shipments if total_shipments else 0.0,
            "lost_pct": 100 * status_counts.get("Lost", 0) / total_shipments if total_shipments else 0.0,
            "rts_pct": 100 * status_counts.get("Returned to Sender", 0) / total_shipments if total_shipments else 0.0,
            "avg_delivery_days": float(leads.mean()) if len(leads) else float("nan"),
            "median_delivery_days": float(leads.median()) if len(leads) else float("nan"),
            "lead_sample_size": len(leads),
        },
    }


def styled(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=12, r=12, t=46, b=22),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial, sans-serif", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,.16)", zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    return fig


def fig_lead_time(view: dict) -> go.Figure:
    leads = view["leads"]
    fig = px.histogram(x=leads, nbins=20, labels={"x": "Delivery lead time (days)", "y": "Shipments"},
                       color_discrete_sequence=[PRIMARY])
    fig.update_traces(marker_line_width=0.5, marker_line_color="white")
    fig.update_layout(title="1. Delivery lead time distribution", showlegend=False,
                      yaxis_title="Delivered shipments", xaxis_title="Lead time (days)")
    return styled(fig)


def fig_courier(view: dict, metric: str = "Average delivery days") -> go.Figure:
    column = {
        "Average delivery days": "avg_delivery_days",
        "Delivered share (%)": "delivered_pct",
        "Lost share (%)": "lost_pct",
    }[metric]
    frame = view["couriers"].sort_values(column, ascending=True).dropna(subset=[column])
    fig = px.bar(frame, x=column, y="courier", orientation="h", color_discrete_sequence=[PRIMARY],
                 hover_data={"shipments": True, "avg_delivery_days": ":.2f",
                             "delivered_pct": ":.2f", "lost_pct": ":.2f"})
    fig.update_layout(title="2. Courier performance comparison", showlegend=False,
                      xaxis_title=metric, yaxis_title="Courier")
    return styled(fig)


def fig_reasons(view: dict) -> go.Figure:
    df = view["reasons"].sort_values("returns", ascending=True)
    fig = px.bar(df, x="returns", y="reason", orientation="h", color_discrete_sequence=[SECONDARY],
                 text="returns")
    fig.update_layout(title="3. Top reported return reasons", showlegend=False,
                      xaxis_title="Return records", yaxis_title="")
    fig.update_traces(textposition="outside", cliponaxis=False)
    return styled(fig)


def fig_category(view: dict) -> go.Figure:
    df = view["categories"].sort_values("return_rate_pct", ascending=True)
    fig = px.bar(df, x="return_rate_pct", y="category", orientation="h",
                 color_discrete_sequence=[PRIMARY], text="return_rate_pct",
                 hover_data={"orders": True, "returned_orders": True,
                             "return_rate_pct": ":.2f"})
    fig.update_layout(title="4. Return rate by product category", showlegend=False,
                      xaxis_title="Orders with return (%)", yaxis_title="")
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False)
    return styled(fig)


def fig_status(view: dict) -> go.Figure:
    df = view["status"].loc[lambda d: d["shipments"] > 0]
    fig = px.pie(df, values="shipments", names="status", hole=0.63,
                 color="status", color_discrete_map=COLORS)
    fig.update_traces(textposition="outside", textinfo="percent+label", hovertemplate="%{label}: %{value:,} (%{percent})<extra></extra>")
    fig.update_layout(title="5. Shipment status breakdown", showlegend=False,
                      annotations=[dict(text=f'{view["kpis"]["shipments"]:,}<br>shipments',
                                        x=0.5, y=0.5, showarrow=False, font=dict(size=14))])
    return styled(fig)


def fig_courier_return(view: dict) -> go.Figure:
    df = view["couriers"].sort_values("return_rate_pct", ascending=True)
    fig = px.bar(df, x="return_rate_pct", y="courier", orientation="h",
                 color_discrete_sequence=[SECONDARY], text="return_rate_pct",
                 hover_data={"orders": True, "returned_orders": True})
    fig.update_layout(title="6. Return rate by courier", showlegend=False,
                      xaxis_title="Orders with return (%)", yaxis_title="")
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False)
    return styled(fig)


def get_insights(view: dict) -> tuple[list[str], list[str]]:
    k = view["kpis"]
    insights = [
        f"{k['delivered_pct']:.2f}% of {k['shipments']:,} selected shipments are marked Delivered.",
        f"{k['in_transit_pct']:.2f}% are In Transit; this is a dataset status, not a live backlog.",
        f"{k['lost_pct']:.2f}% are Lost and {k['rts_pct']:.2f}% are Returned to Sender (distinct from customer returns).",
        (f"Completed deliveries with valid dates average {k['avg_delivery_days']:.2f} days "
         f"across {k['lead_sample_size']:,} shipments.") if k["lead_sample_size"] else
        "No valid completed delivery lead times are present under these filters.",
        (f"{k['returned_orders']:,} of {k['orders']:,} selected orders have a return record "
         f"({k['return_rate_pct']:.2f}% return rate)."),
    ]
    if len(view["reasons"]):
        top = view["reasons"].iloc[0]
        insights.append(f"Most frequently reported reason: {top['reason']} ({int(top['returns']):,} return records).")
    if len(view["categories"]):
        high = view["categories"].sort_values("return_rate_pct", ascending=False).iloc[0]
        insights.append(f"Highest category-associated return rate: {high['category']} ({high['return_rate_pct']:.2f}%).")
    if len(view["couriers"]):
        low = view["couriers"].sort_values("delivered_pct").iloc[0]
        first_reco = (f"Audit {low['courier']} shipment exceptions and delivery conditions; "
                      "compare routes and service mix before changing courier allocation.")
    else:
        first_reco = "Review shipment exceptions and missing delivery dates to identify operational bottlenecks."
    if len(view["reasons"]):
        top_reason = view["reasons"].iloc[0]["reason"]
        second_reco = (f"Investigate the leading reported return reason ({top_reason}) and review "
                       "product listings, quality checks, and packaging as applicable.")
    else:
        second_reco = "Review return records when available and verify item-level root causes before acting."
    return insights, [first_reco, second_reco]


def frame_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def main() -> None:
    try:
        import streamlit as st
    except ImportError as error:
        raise SystemExit(
            "Streamlit isn't installed. Run: python -m pip install -r requirements_dashboard.txt\n"
            "Then launch: python -m streamlit run dashboard.py"
        ) from error

    st.set_page_config(page_title="Delivery & Returns | Analyst Dashboard", page_icon="📦", layout="wide")
    st.markdown("""<style>
        .block-container {padding-top: 1.5rem; padding-bottom: 2.5rem; max-width: 1450px;}
        div[data-testid="stMetric"] {padding: 16px 18px; border-radius: 12px;
            border: 1px solid rgba(130,140,150,.24); background: rgba(130,140,150,.035);}
        div[data-testid="stMetricLabel"] {font-size: 0.94rem;}
        h1 {letter-spacing: -0.03em;}
    </style>""", unsafe_allow_html=True)
    st.title("📦 Delivery Performance & Returns")
    st.caption("How well are we delivering, and what causes returns? | Interactive analysis of synthetic e-commerce data")

    default_project = Path(os.environ.get("DELIVERY_RETURNS_PROJECT", Path(__file__).resolve().parent))
    default_downloads = Path(os.environ.get("DELIVERY_RETURNS_DATA", Path.home() / "Downloads"))
    with st.sidebar:
        st.header("Data & controls")
        project_text = st.text_input("Project folder (scripts, outputs, charts)", value=str(default_project))
        downloads_text = st.text_input("CSV source folder", value=str(default_downloads))
        project_dir = Path(project_text.strip().strip('"')).expanduser()
        data_dir = Path(downloads_text.strip().strip('"')).expanduser()
        out_dir = project_dir / "outputs"
        if st.button("🔄 Generate / refresh cleaned data", use_container_width=True,
                     help="Runs analysis.py to clean the source CSVs again."):
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            try:
                from analysis import run_analysis
                with st.spinner("Cleaning and regenerating the analyst outputs…"):
                    run_analysis(project_dir=project_dir, data_dir=data_dir)
                st.cache_data.clear()
                st.success("Cleaned data and reports regenerated.")
                st.rerun()
            except Exception as error:
                st.error(f"Couldn't regenerate the data: {error}")
                st.stop()
        st.divider()

    missing = validate_outputs(out_dir)
    if missing:
        st.warning(f"The cleaned data is missing from **{out_dir}**.")
        st.info("Click **Generate / refresh cleaned data** in the sidebar. "
                "Keep `analysis.py` beside this dashboard and place the seven CSVs together in Downloads "
                "or the project's `data` folder.")
        st.code("\n".join(missing))
        st.stop()

    @st.cache_data(show_spinner="Loading audited CSVs…")
    def cached_data(folder: str, stamps: tuple[int, ...]) -> dict[str, pd.DataFrame]:
        return load_cleaned(Path(folder))

    timestamps = tuple((out_dir / name).stat().st_mtime_ns for name in REQUIRED_FILES)
    try:
        tables = cached_data(str(out_dir), timestamps)
    except Exception as error:
        st.error(f"Unable to load cleaned data: {error}")
        st.stop()

    all_couriers = sorted(tables["shipments"]["courier"].dropna().unique().tolist())
    all_statuses = [v for v in STATUS_ORDER if v in set(tables["shipments"]["shipment_status"])]
    all_categories = sorted(tables["item_categories"]["category"].dropna().unique().tolist())
    with st.sidebar:
        st.subheader("Interactive filters")
        couriers = st.multiselect("Courier", options=all_couriers, placeholder="All couriers", key="courier_select")
        categories = st.multiselect("Product category", options=all_categories, placeholder="All categories", key="category_select")
        statuses = st.multiselect("Shipment status", options=all_statuses, placeholder="All statuses", key="status_select")
        st.caption("No selection means All. Multiple selected categories use ANY-match order membership.")
        st.caption("Status filtering changes the population for delivery and return KPIs.")
        def reset_filters() -> None:
            for widget_key in ("courier_select", "category_select", "status_select"):
                st.session_state[widget_key] = []

        st.button("Reset filters", use_container_width=True, on_click=reset_filters)

    view = build_view(tables, couriers, categories, statuses)
    k = view["kpis"]
    if not k["orders"] or not k["shipments"]:
        st.warning("No matching records for these filters. Try removing one or more selections.")
        st.stop()

    st.subheader("Delivery & returns scorecard")
    a, b, c, d, e, f = st.columns(6)
    a.metric("Shipments", f"{k['shipments']:,}")
    b.metric("Delivered", f"{k['delivered_pct']:.2f}%")
    c.metric("In transit", f"{k['in_transit_pct']:.2f}%")
    d.metric("Lost", f"{k['lost_pct']:.2f}%")
    e.metric("Avg. lead time", f"{k['avg_delivery_days']:.2f} d" if k["lead_sample_size"] else "N/A")
    f.metric("Order return rate", f"{k['return_rate_pct']:.2f}%")
    st.caption(f"Filtered population: {k['orders']:,} unique orders; "
               f"{k['returned_orders']:,} returned orders; {k['return_records']:,} return records. "
               "Delivery lead time uses valid completed shipments only.")

    left, right = st.columns(2, gap="large")
    with left:
        st.plotly_chart(fig_lead_time(view), use_container_width=True)
    with right:
        metric = st.selectbox("Courier comparison measure", [
            "Average delivery days", "Delivered share (%)", "Lost share (%)"
        ], label_visibility="visible")
        st.plotly_chart(fig_courier(view, metric), use_container_width=True)
    left, right = st.columns(2, gap="large")
    with left:
        st.plotly_chart(fig_reasons(view), use_container_width=True)
    with right:
        st.plotly_chart(fig_category(view), use_container_width=True)
    left, right = st.columns(2, gap="large")
    with left:
        st.plotly_chart(fig_status(view), use_container_width=True)
    with right:
        st.plotly_chart(fig_courier_return(view), use_container_width=True)

    st.divider()
    st.subheader("Analyst findings")
    insights, recommendations = get_insights(view)
    col_left, col_right = st.columns([1.3, 1], gap="large")
    with col_left:
        st.markdown("**Key insights**")
        for insight in insights:
            st.markdown(f"- {insight}")
    with col_right:
        st.markdown("**Recommendations**")
        for index, suggestion in enumerate(recommendations, 1):
            st.markdown(f"{index}. {suggestion}")

    with st.expander("View detailed comparison tables"):
        st.markdown("**Courier delivery and return measures**")
        st.dataframe(view["couriers"].round(2), use_container_width=True, hide_index=True)
        st.markdown("**Category-linked return rates**")
        st.dataframe(view["categories"].round(2), use_container_width=True, hide_index=True)

    with st.expander("Review cleaning and join-key audit logs"):
        for filename, label in (
            ("cleaning_audit.csv", "Duplicate and primary-key review"),
            ("orphan_audit.csv", "Orphan foreign-key checks"),
            ("date_parse_audit.csv", "Date parsing review"),
        ):
            path = out_dir / filename
            if path.is_file():
                st.markdown(f"**{label}**")
                st.dataframe(pd.read_csv(path), hide_index=True, use_container_width=True)

    st.subheader("Download your current dashboard as PDF")
    st.caption("The PDF is a print-ready, static snapshot of the current filters and "
               "selected courier comparison measure. It includes six KPIs, all six charts, "
               "analyst insights, recommendations, and methodology.")
    try:
        from pdf_export import create_dashboard_pdf

        @st.cache_data(show_spinner="Preparing PDF report…")
        def cached_pdf(folder: str, file_stamps: tuple[int, ...],
                       couriers_key: tuple[str, ...], categories_key: tuple[str, ...],
                       statuses_key: tuple[str, ...], comparison_metric: str) -> bytes:
            report_tables = cached_data(folder, file_stamps)
            report_view = build_view(report_tables, list(couriers_key),
                                     list(categories_key), list(statuses_key))
            return create_dashboard_pdf(
                report_view, couriers=list(couriers_key),
                categories=list(categories_key), statuses=list(statuses_key),
                courier_metric=comparison_metric,
            )

        pdf_bytes = cached_pdf(str(out_dir), timestamps, tuple(couriers),
                               tuple(categories), tuple(statuses), metric)
        st.download_button(
            "📄 Download Dashboard as PDF", data=pdf_bytes,
            file_name="delivery_returns_dashboard_filtered.pdf",
            mime="application/pdf", use_container_width=True,
            help="Download all six charts and the current dashboard results as a PDF report.",
        )
    except Exception as error:
        st.error(f"PDF export unavailable: {error}. "
                 "Install dependencies using: python -m pip install -r requirements_dashboard.txt")

    st.subheader("Download current filtered results")
    x, y, z = st.columns(3)
    x.download_button("Courier performance CSV", frame_csv(view["couriers"]),
                      "filtered_courier_performance.csv", "text/csv", use_container_width=True)
    y.download_button("Category return rates CSV", frame_csv(view["categories"]),
                      "filtered_category_return_rates.csv", "text/csv", use_container_width=True)
    z.download_button("Return reasons CSV", frame_csv(view["reasons"]),
                      "filtered_return_reasons.csv", "text/csv", use_container_width=True)
    with st.expander("Methodology and important cautions"):
        st.markdown("""
- **Delivery time:** `delivered_date - ship_date` in days. Only Delivered shipments with nonnegative, valid dates are included.
- **Shipment status rate:** Shipments in a given status ÷ filtered shipments. Status percentages refer to the filtered shipment population.
- **Order return rate:** Distinct filtered orders with ≥1 return ÷ distinct filtered orders (not number of return records ÷ orders).
- **Category return rate:** Distinct returned orders *containing* a category ÷ distinct orders containing that category. This is **association**, not proof of which item was returned. A multi-category order can appear in more than one category.
- **Courier return rate:** Distinct returned orders linked to a courier ÷ distinct orders linked to that courier.
- **Filters:** Categories select orders containing any selected category; courier/status filters select matching shipments, and those shipment orders define the associated returns. Empty filters mean all values. Rates therefore vary with the selection.
- **No on-time-rate claim:** There is no promised delivery date / delivery SLA in the dataset.
- **Reported reasons ≠ proven causes.** The dataset is synthetic; this dashboard provides descriptive analysis, not causal inference. "Returned to Sender" is a shipment status, not automatically a customer return request.
        """)
    st.caption(f"Cleaned source: {out_dir}")


if __name__ == "__main__":
    main()
