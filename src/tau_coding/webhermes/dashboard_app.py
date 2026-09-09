"""WebHermes web dashboard (Phase 11). Thin Streamlit views over queries.py.

Run: streamlit run src/tau_coding/webhermes/dashboard_app.py
All data access lives in queries.py (tested); this file only renders.
"""

from __future__ import annotations


def main() -> None:
    import streamlit as st

    from tau_coding.webhermes import queries

    st.title("WebHermes")

    stats = queries.home_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Components", stats["components"])
    c2.metric("Healthy", stats["healthy"])
    c3.metric("Executions", stats["executions"])
    c4.metric("Recoveries", stats["recoveries"])

    st.header("Components")
    st.table(queries.list_components())

    st.header("Workflows")
    for w in queries.list_workflows():
        st.write(f"**{w['name']}** [{w['created_by']}]: {w['chain']}")

    st.header("Executions")
    for e in queries.list_executions():
        mode = "deterministic" if e["deterministic"] else f"ai-assisted ({e['llm_calls']})"
        st.write(f"#{e['id']} {e['status']} — {mode}")
        for comp, method, ok in e["steps"]:
            st.write(f"{'✅' if ok else '❌'} {comp} [{method}]")

    st.header("Failures")
    for f in queries.list_failures():
        st.write(f"#{f['id']} {f['component']}: {f['error']}")
        st.write(f"_{f['narrative']}_")
        if f["screenshot"]:
            st.image(f["screenshot"])
            st.write(f"DOM: {f['dom']}")


if __name__ == "__main__":
    main()
