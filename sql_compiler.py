"""
SQL Notebook — Streamlit + SQLite
A Jupyter-notebook-style SQL compiler: write queries in independent cells,
run them one at a time (or all at once), and see each cell's own output
persist right below it — just like In[]/Out[] in Jupyter.
"""

import streamlit as st
import pandas as pd
import sqlite3
import io
import time
import uuid

st.set_page_config(page_title="SQL Notebook", page_icon="📓", layout="wide")

# ----------------------------------------------------------------------------
# Session state setup
# ----------------------------------------------------------------------------
if "conn" not in st.session_state:
    st.session_state.conn = sqlite3.connect(":memory:", check_same_thread=False)
if "cells" not in st.session_state:
    st.session_state.cells = []
if "exec_counter" not in st.session_state:
    st.session_state.exec_counter = 0

conn = st.session_state.conn


def get_tables():
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    return [r[0] for r in cur.fetchall()]


def load_sample_data():
    """Load a couple of sample tables so users have something to query immediately."""
    employees = pd.DataFrame({
        "id": range(1, 11),
        "name": ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun",
                 "Sai", "Reyansh", "Krishna", "Ishaan", "Rohan"],
        "department": ["Engineering", "Sales", "Engineering", "Marketing", "Sales",
                        "Engineering", "HR", "Marketing", "Engineering", "Sales"],
        "salary": [85000, 62000, 91000, 58000, 64000, 88000, 55000, 60000, 95000, 67000],
        "hire_year": [2019, 2021, 2018, 2022, 2020, 2017, 2023, 2021, 2016, 2022],
    })
    departments = pd.DataFrame({
        "department": ["Engineering", "Sales", "Marketing", "HR"],
        "head": ["Priya Sharma", "Karan Mehta", "Neha Gupta", "Ravi Iyer"],
        "budget": [500000, 300000, 200000, 100000],
    })
    matches = pd.DataFrame({
        "match_id": range(1, 9),
        "home_team": ["Mumbai City", "Bengaluru FC", "ATK Mohun Bagan", "Kerala Blasters",
                      "Mumbai City", "Odisha FC", "Bengaluru FC", "Kerala Blasters"],
        "away_team": ["Bengaluru FC", "Odisha FC", "Kerala Blasters", "Mumbai City",
                      "ATK Mohun Bagan", "Kerala Blasters", "Mumbai City", "Odisha FC"],
        "home_goals": [2, 1, 3, 0, 1, 2, 2, 1],
        "away_goals": [1, 1, 1, 0, 1, 2, 0, 3],
        "season": ["2024-25"] * 8,
    })

    employees.to_sql("employees", conn, if_exists="replace", index=False)
    departments.to_sql("departments", conn, if_exists="replace", index=False)
    matches.to_sql("matches", conn, if_exists="replace", index=False)
    conn.commit()


if not get_tables():
    load_sample_data()


def new_cell(query=""):
    return {
        "id": uuid.uuid4().hex,
        "query": query,
        "status": None,       # None | "success" | "error"
        "message": "",
        "result_df": None,
        "exec_count": None,
        "elapsed": None,
    }


if not st.session_state.cells:
    st.session_state.cells.append(new_cell("SELECT * FROM employees LIMIT 10;"))


def run_cell(cell):
    sql = (cell["query"] or "").strip()
    if not sql:
        cell["status"] = None
        cell["message"] = "Cell is empty."
        cell["result_df"] = None
        cell["exec_count"] = None
        cell["elapsed"] = None
        return
    start = time.time()
    try:
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        result_df = None
        for stmt in statements:
            lower = stmt.lower().lstrip()
            if lower.startswith(("select", "pragma", "with")):
                result_df = pd.read_sql_query(stmt, conn)
            else:
                conn.execute(stmt)
        conn.commit()
        elapsed = time.time() - start

        st.session_state.exec_counter += 1
        cell["exec_count"] = st.session_state.exec_counter
        cell["status"] = "success"
        cell["elapsed"] = elapsed
        cell["result_df"] = result_df
        cell["message"] = (
            f"{len(result_df)} row(s) returned in {elapsed:.3f}s"
            if result_df is not None
            else f"Executed successfully in {elapsed:.3f}s (no rows returned)"
        )
    except Exception as e:
        st.session_state.exec_counter += 1
        cell["exec_count"] = st.session_state.exec_counter
        cell["status"] = "error"
        cell["message"] = str(e)
        cell["result_df"] = None
        cell["elapsed"] = None


def add_cell_after(cell_id, query=""):
    cells = st.session_state.cells
    idx = next(i for i, c in enumerate(cells) if c["id"] == cell_id)
    cells.insert(idx + 1, new_cell(query))


def delete_cell(cell_id):
    cells = st.session_state.cells
    st.session_state.cells = [c for c in cells if c["id"] != cell_id]
    if not st.session_state.cells:
        st.session_state.cells.append(new_cell())


def move_cell(cell_id, direction):
    cells = st.session_state.cells
    idx = next(i for i, c in enumerate(cells) if c["id"] == cell_id)
    new_idx = idx + direction
    if 0 <= new_idx < len(cells):
        cells[idx], cells[new_idx] = cells[new_idx], cells[idx]


# ----------------------------------------------------------------------------
# Sidebar — schema browser + CSV upload + reset
# ----------------------------------------------------------------------------
with st.sidebar:
    st.header("🗄️ Database")

    st.subheader("Upload CSV as table")
    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])
    if uploaded_file is not None:
        default_name = uploaded_file.name.rsplit(".", 1)[0].replace(" ", "_").lower()
        table_name = st.text_input("Table name", value=default_name, key="upload_table_name")
        if st.button("Load into database", use_container_width=True):
            try:
                df_upload = pd.read_csv(uploaded_file)
                df_upload.to_sql(table_name, conn, if_exists="replace", index=False)
                conn.commit()
                st.success(f"Loaded '{table_name}' ({len(df_upload)} rows)")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to load CSV: {e}")

    st.divider()
    st.subheader("Tables & Schema")
    tables = get_tables()
    if not tables:
        st.info("No tables yet. Upload a CSV to get started.")
    for t in tables:
        with st.expander(f"📋 {t}"):
            schema = pd.read_sql_query(f"PRAGMA table_info('{t}');", conn)
            st.dataframe(schema[["name", "type"]], hide_index=True, use_container_width=True)
            count = conn.execute(f"SELECT COUNT(*) FROM '{t}'").fetchone()[0]
            st.caption(f"{count} rows")

    st.divider()
    st.subheader("Quick examples")
    st.caption("Adds a new cell with the query — doesn't run it.")
    examples = {
        "Select all employees": "SELECT * FROM employees;",
        "Avg salary by dept": "SELECT department, AVG(salary) AS avg_salary\nFROM employees\nGROUP BY department\nORDER BY avg_salary DESC;",
        "Join employees + departments": "SELECT e.name, e.salary, d.head\nFROM employees e\nJOIN departments d ON e.department = d.department;",
        "Top scoring matches": "SELECT home_team, away_team, (home_goals + away_goals) AS total_goals\nFROM matches\nORDER BY total_goals DESC\nLIMIT 5;",
    }
    for label, q in examples.items():
        if st.button(label, use_container_width=True, key=f"ex_{label}"):
            st.session_state.cells.append(new_cell(q))
            st.rerun()

    st.divider()
    if st.button("🔄 Reset database (reload samples)", use_container_width=True):
        for t in get_tables():
            conn.execute(f"DROP TABLE IF EXISTS '{t}'")
        conn.commit()
        load_sample_data()
        st.session_state.cells = [new_cell("SELECT * FROM employees LIMIT 10;")]
        st.session_state.exec_counter = 0
        st.rerun()

# ----------------------------------------------------------------------------
# Main area — notebook toolbar
# ----------------------------------------------------------------------------
st.title("📓 SQL Notebook")
st.caption("Write SQL in cells, run them independently, and keep every result on screen. Powered by SQLite.")

tb1, tb2, tb3, tb4 = st.columns([1.3, 1.3, 1.6, 5.8])
with tb1:
    run_all_clicked = st.button("▶▶ Run all", use_container_width=True)
with tb2:
    add_bottom_clicked = st.button("➕ Add cell", use_container_width=True)
with tb3:
    clear_outputs_clicked = st.button("🧹 Clear outputs", use_container_width=True)

if run_all_clicked:
    for c in st.session_state.cells:
        run_cell(c)
    st.rerun()

if add_bottom_clicked:
    st.session_state.cells.append(new_cell())
    st.rerun()

if clear_outputs_clicked:
    for c in st.session_state.cells:
        c["status"] = None
        c["message"] = ""
        c["result_df"] = None
        c["exec_count"] = None
        c["elapsed"] = None
    st.rerun()

st.divider()

# ----------------------------------------------------------------------------
# Notebook cells
# ----------------------------------------------------------------------------
for i, cell in enumerate(st.session_state.cells):
    cid = cell["id"]

    label_col, body_col = st.columns([0.7, 11.3])

    with label_col:
        if cell["exec_count"] is not None:
            st.markdown(f"**In [{cell['exec_count']}]:**")
        else:
            st.markdown("**In [ ]:**")

    with body_col:
        with st.container(border=True):
            new_query = st.text_area(
                "SQL query",
                value=cell["query"],
                height=120,
                key=f"code_{cid}",
                label_visibility="collapsed",
                placeholder="Type your SQL query here...",
            )
            cell["query"] = new_query

            bcol1, bcol2, bcol3, bcol4, bcol5, bcol6 = st.columns([1.4, 1, 1, 1, 1, 6.6])
            with bcol1:
                if st.button("▶ Run", key=f"run_{cid}", type="primary", use_container_width=True):
                    run_cell(cell)
                    st.rerun()
            with bcol2:
                if st.button("⬆", key=f"up_{cid}", use_container_width=True, help="Move cell up"):
                    move_cell(cid, -1)
                    st.rerun()
            with bcol3:
                if st.button("⬇", key=f"down_{cid}", use_container_width=True, help="Move cell down"):
                    move_cell(cid, 1)
                    st.rerun()
            with bcol4:
                if st.button("➕", key=f"addbelow_{cid}", use_container_width=True, help="Insert cell below"):
                    add_cell_after(cid, "")
                    st.rerun()
            with bcol5:
                if st.button("🗑", key=f"del_{cid}", use_container_width=True, help="Delete cell"):
                    delete_cell(cid)
                    st.rerun()

            # Output area
            if cell["status"] == "success":
                st.success(cell["message"])
                if cell["result_df"] is not None:
                    st.dataframe(cell["result_df"], use_container_width=True)
                    csv_buffer = io.StringIO()
                    cell["result_df"].to_csv(csv_buffer, index=False)
                    st.download_button(
                        "⬇ Download results as CSV",
                        data=csv_buffer.getvalue(),
                        file_name=f"cell_{i + 1}_results.csv",
                        mime="text/csv",
                        key=f"dl_{cid}",
                    )
            elif cell["status"] == "error":
                st.error(f"❌ SQL Error: {cell['message']}")
            elif cell["message"]:
                st.info(cell["message"])

    st.write("")  # small vertical gap between cells

st.divider()
if st.button("➕ Add cell at end", use_container_width=False):
    st.session_state.cells.append(new_cell())
    st.rerun()