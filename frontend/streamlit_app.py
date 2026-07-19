from __future__ import annotations

import os
from pathlib import Path

import requests
import streamlit as st


BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def fetch_projects() -> list[dict]:
    response = requests.get(f"{BACKEND_URL}/projects", timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_report(project_id: int) -> dict | None:
    response = requests.get(f"{BACKEND_URL}/report/{project_id}", timeout=60)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def fetch_architecture(project_id: int) -> dict | None:
    response = requests.get(f"{BACKEND_URL}/architecture/{project_id}", timeout=60)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def trigger_analysis(project_id: int) -> dict:
    response = requests.get(f"{BACKEND_URL}/analysis/{project_id}", timeout=300)
    response.raise_for_status()
    return response.json()


def send_chat(project_id: int, question: str) -> dict:
    response = requests.post(
        f"{BACKEND_URL}/chat/{project_id}",
        json={"question": question},
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def upload_zip(file_path: Path) -> dict:
    with file_path.open("rb") as handle:
        files = {"file": (file_path.name, handle.read(), "application/zip")}
        response = requests.post(f"{BACKEND_URL}/upload-project", files=files, timeout=300)
    response.raise_for_status()
    return response.json()


st.set_page_config(page_title="AI Codebase Architect", layout="wide")
st.title("🏗️ AI Codebase Architect & Engineering Reviewer")

if "messages" not in st.session_state:
    st.session_state.messages = {}
if "selected_file" not in st.session_state:
    st.session_state.selected_file = None
if "selected_function" not in st.session_state:
    st.session_state.selected_function = None

sidebar_projects = []
try:
    sidebar_projects = fetch_projects()
except Exception:
    st.sidebar.warning("Backend is not reachable yet.")

st.sidebar.header("📂 Project List")
project_labels = [f"{project['id']}: {project['project_name']}" for project in sidebar_projects]
selected_label = st.sidebar.selectbox("Project Selection", [""] + project_labels)

selected_project = None
if selected_label:
    selected_id = int(selected_label.split(":")[0])
    selected_project = next((project for project in sidebar_projects if project["id"] == selected_id), None)

tab_analysis, tab_architect, tab_report, tab_chat, tab_upload = st.tabs([
    "📊 Analysis",
    "🏗️ Architecture Explorer",
    "📋 Stored Report",
    "💬 Chat With Codebase",
    "📦 Upload ZIP"
])

with tab_upload:
    st.subheader("Upload a Project")
    uploaded_file = st.file_uploader("Upload a ZIP project", type=["zip"])
    if uploaded_file and st.button("📤 Send ZIP to Backend"):
        try:
            response = requests.post(
                f"{BACKEND_URL}/upload-project",
                files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/zip")},
                timeout=300,
            )
            response.raise_for_status()
            result = response.json()
            st.success(f"✅ Project uploaded with ID {result['project_id']}")
        except Exception as e:
            st.error(f"Upload failed: {e}")

with tab_analysis:
    if selected_project is None:
        st.info("📌 Select a project to run analysis.")
    elif st.button("🚀 Run Analysis"):
        try:
            with st.spinner("Analyzing..."):
                analysis = trigger_analysis(selected_project["id"])
            st.json(analysis)
        except Exception as e:
            st.error(f"Analysis failed: {e}")

with tab_architect:
    if selected_project is None:
        st.info("📌 Select a project to explore its architecture.")
    else:
        try:
            with st.spinner("Loading architecture data..."):
                arch_data = fetch_architecture(selected_project["id"])
            
            if arch_data is None:
                st.error("Architecture data not available. Run analysis first.")
            else:
                # ============================================================
                # SECTION 1: PROJECT OVERVIEW DASHBOARD
                # ============================================================
                st.header("📊 Project Overview")
                metrics = arch_data["project_metrics"]
                col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
                with col1:
                    st.metric("📄 Files", metrics["total_files"])
                with col2:
                    st.metric("📁 Folders", metrics["total_folders"])
                with col3:
                    st.metric("🐍 Python", metrics["python_files"])
                with col4:
                    st.metric("⚙️ Functions", metrics["functions"])
                with col5:
                    st.metric("🔧 Classes", metrics["classes"])
                with col6:
                    st.metric("🌐 Routes", metrics["api_routes"])

                # ============================================================
                # SECTION 2 & 3: PROJECT TREE & FILE DEPENDENCY EXPLORER
                # ============================================================
                col_tree, col_deps = st.columns(2)

                with col_tree:
                    st.subheader("🌳 Project Structure")
                    python_files = arch_data.get("python_files", [])
                    selected_file = st.selectbox(
                        "Select a file to inspect",
                        python_files,
                        key="file_selector"
                    )
                    if selected_file:
                        st.session_state.selected_file = selected_file

                with col_deps:
                    st.subheader("📚 File Dependencies")
                    dep_graph = arch_data.get("dependency_graph", {})
                    if selected_file and selected_file in dep_graph.get("files", {}):
                        deps = dep_graph["files"].get(selected_file, [])
                        if deps:
                            for dep in deps[:10]:
                                st.write(f"→ {dep}")
                        else:
                            st.write(f"No dependencies")
                    else:
                        st.write("Select a file to see dependencies")

                # ============================================================
                # SECTION 4: FILE INSPECTOR
                # ============================================================
                if st.session_state.selected_file:
                    st.subheader(f"📝 File Inspector: {st.session_state.selected_file}")
                    inspector_tabs = st.tabs(["Details", "Functions", "Classes", "Imports", "Routes", "Database"])

                    # Get file details via API if available
                    try:
                        file_details = requests.get(
                            f"{BACKEND_URL}/architecture/{selected_project['id']}/file/{st.session_state.selected_file}",
                            timeout=30
                        ).json()

                        with inspector_tabs[0]:  # Details
                            st.write(f"**File**: {file_details.get('file')}")
                            if file_details.get('imported_by'):
                                st.write("**Imported by:**")
                                for importer in file_details['imported_by']:
                                    st.write(f"  ← {importer}")

                        with inspector_tabs[1]:  # Functions
                            if file_details.get('functions'):
                                for func in file_details['functions']:
                                    st.write(f"🔧 **{func['name']}** (line {func['line']})")
                            else:
                                st.write("No functions")

                        with inspector_tabs[2]:  # Classes
                            if file_details.get('classes'):
                                for cls in file_details['classes']:
                                    st.write(f"📦 **{cls['name']}** (line {cls['line']})")
                                    if cls['methods']:
                                        for method in cls['methods']:
                                            st.write(f"  → {method}")
                            else:
                                st.write("No classes")

                        with inspector_tabs[3]:  # Imports
                            if file_details.get('imports'):
                                for imp in file_details['imports']:
                                    st.write(f"📌 {imp.get('name')}")
                            else:
                                st.write("No imports")

                        with inspector_tabs[4]:  # Routes
                            if file_details.get('api_routes'):
                                for route in file_details['api_routes']:
                                    st.write(f"🌐 {', '.join(route['methods'])} {route['path']}")
                            else:
                                st.write("No API routes")

                        with inspector_tabs[5]:  # Database
                            if file_details.get('database_usage'):
                                db_usage = file_details['database_usage']
                                if db_usage.get('imports'):
                                    st.write("**DB Imports:**")
                                    for imp in db_usage['imports']:
                                        st.write(f"  → {imp}")
                                if db_usage.get('operations'):
                                    st.write("**DB Operations:**")
                                    for op in db_usage['operations']:
                                        st.write(f"  → {op['name']} (line {op['line']})")
                            else:
                                st.write("No database usage")

                    except Exception as e:
                        st.write(f"Could not load file details: {e}")

                # ============================================================
                # SECTION 5 & 6: FUNCTION EXPLORER & FLOW VIEWER
                # ============================================================
                col_func, col_flow = st.columns(2)

                with col_func:
                    st.subheader("⚙️ Function Explorer")
                    functions = arch_data.get("functions", [])
                    func_names = [f["name"] for f in functions]
                    selected_func = st.selectbox(
                        "Select a function",
                        func_names,
                        key="func_selector"
                    )

                    if selected_func:
                        st.session_state.selected_function = selected_func
                        try:
                            func_details = requests.get(
                                f"{BACKEND_URL}/architecture/{selected_project['id']}/function/{selected_func}",
                                timeout=30
                            ).json()

                            st.write(f"**File**: {func_details.get('file')}")
                            st.write(f"**Line**: {func_details.get('line')}")
                            if func_details.get('is_async'):
                                st.write("🔄 **Async Function**")
                            if func_details.get('parameters'):
                                st.write(f"**Parameters**: {', '.join(func_details['parameters'])}")

                        except Exception as e:
                            st.write(f"Could not load function details: {e}")

                with col_flow:
                    st.subheader("🔄 Function Flow")
                    if st.session_state.selected_function:
                        func_graph = arch_data.get("function_graph", {})
                        calls = func_graph.get("function_calls", {}).get(st.session_state.selected_function, [])
                        if calls:
                            st.write(f"**{st.session_state.selected_function}** calls:")
                            for called_func in calls[:5]:
                                st.write(f"  ↓ {called_func}")
                        else:
                            st.write(f"**{st.session_state.selected_function}** has no function calls")

                # ============================================================
                # SECTION 7: API FLOW EXPLORER
                # ============================================================
                st.subheader("🌐 API Flow")
                execution_flows = arch_data.get("execution_flow", [])
                if execution_flows:
                    for flow in execution_flows[:5]:
                        with st.expander(f"{' | '.join(flow['methods'])} {flow['route']}"):
                            st.write(f"**Handler**: {flow['handler']}")
                            if flow['calls']:
                                st.write("**Calls:**")
                                for called in flow['calls'][:5]:
                                    st.write(f"  → {called}")
                else:
                    st.write("No API routes found")

                # ============================================================
                # SECTION 8: DATABASE FLOW
                # ============================================================
                st.subheader("🗄️ Database Flow")
                db_flow = arch_data.get("database_flow", {})
                st.write("**Tables:**")
                for table in db_flow.get("tables", []):
                    st.write(f"  📊 {table}")

                # ============================================================
                # SECTION 9: MERMAID ARCHITECTURE
                # ============================================================
                st.subheader("📐 Architecture Diagram")
                mermaid_arch = arch_data.get("mermaid_architecture")
                if mermaid_arch:
                    st.code(mermaid_arch, language="mermaid")

                # ============================================================
                # SECTION 10: CRITICAL FILES
                # ============================================================
                st.subheader("⭐ Critical Files")
                critical = arch_data.get("critical_files", {})
                col_crit1, col_crit2, col_crit3 = st.columns(3)
                with col_crit1:
                    st.write("**Entry Point:**")
                    for f in critical.get("entry_point", []):
                        st.write(f"  🚀 {f}")
                    st.write("**API Layer:**")
                    for f in critical.get("api_layer", []):
                        st.write(f"  🌐 {f}")
                with col_crit2:
                    st.write("**Database Layer:**")
                    for f in critical.get("database_layer", []):
                        st.write(f"  🗄️ {f}")
                    st.write("**AI Layer:**")
                    for f in critical.get("ai_layer", []):
                        st.write(f"  🤖 {f}")
                with col_crit3:
                    st.write("**Analysis Layer:**")
                    for f in critical.get("analysis_layer", []):
                        st.write(f"  📊 {f}")

                # ============================================================
                # SECTION 11: EXECUTION PATH EXPLORER
                # ============================================================
                st.subheader("🎯 Execution Paths")
                st.write("**Analysis Flow:**")
                st.write("""
                User Clicks Analyze
                        ↓
                GET /analysis/{id}
                        ↓
                routes.py → analyze_project()
                        ↓
                app/analyzers.py → build_context()
                        ↓
                ProjectContext (AST Analysis)
                        ↓
                app/agent.py → architect_agent.run()
                        ↓
                Gemini API
                        ↓
                ArchitectureReview
                        ↓
                app/database.py → save_report()
                        ↓
                PostgreSQL
                """)

        except Exception as e:
            st.error(f"Failed to load architecture: {e}")

with tab_report:
    if selected_project is None:
        st.info("📌 Select a project to view a stored report.")
    else:
        try:
            report = fetch_report(selected_project["id"])
            if report is None:
                st.info("No stored report yet.")
            else:
                st.subheader("Summary")
                st.write(report["summary"])
                st.subheader("Architecture")
                st.write(report["architecture"])
                st.subheader("Strengths")
                with st.expander("Strengths"):
                    for item in report["strengths"]:
                        st.write(f"- {item}")
                st.subheader("Weaknesses")
                with st.expander("Weaknesses"):
                    for item in report["weaknesses"]:
                        st.write(f"- {item}")
                st.subheader("Score")
                st.write(report["score"])
                st.subheader("Roadmap")
                with st.expander("Roadmap"):
                    for item in report["roadmap"]:
                        st.write(f"- {item}")
        except Exception as e:
            st.error(f"Failed to load report: {e}")

with tab_chat:
    if selected_project is None:
        st.info("📌 Select a project to chat with it.")
    else:
        try:
            project_id = selected_project["id"]
            if project_id not in st.session_state.messages:
                st.session_state.messages[project_id] = []

            for message in st.session_state.messages[project_id]:
                with st.chat_message(message["role"]):
                    st.write(message["content"])

            prompt = st.chat_input("Ask about the codebase")
            if prompt:
                st.session_state.messages[project_id].append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.write(prompt)

                with st.spinner("Thinking..."):
                    answer = send_chat(project_id, prompt)
                st.session_state.messages[project_id].append({"role": "assistant", "content": answer["answer"]})
                with st.chat_message("assistant"):
                    st.write(answer["answer"])
                    st.write("Referenced Files:")
                    for file_name in answer.get("referenced_files", []):
                        st.write(f"- {file_name}")
        except Exception as e:
            st.error(f"Chat failed: {e}")

