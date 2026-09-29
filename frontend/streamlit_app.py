from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Iterator

import requests
import streamlit as st
import streamlit.components.v1 as components


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


def stream_chat(project_id: int, question: str, result: dict) -> Iterator[str]:
    """Stream a chat answer as SSE text chunks for st.write_stream().

    Terminal event data (referenced_files, or an interruption message) is stashed
    into `result` as a side effect, since it arrives only after the last text chunk
    and st.write_stream() only collects the yielded chunks themselves.
    """
    response = requests.post(
        f"{BACKEND_URL}/chat/{project_id}/stream",
        json={"question": question},
        stream=True,
        timeout=300,
    )
    response.raise_for_status()

    event_name = None
    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue
        line = raw_line.strip()
        if not line:
            event_name = None
            continue
        if line.startswith("event:"):
            event_name = line[len("event:"):].strip()
            continue
        if not line.startswith("data:"):
            continue

        try:
            payload = json.loads(line[len("data:"):].strip())
        except json.JSONDecodeError:
            continue

        if event_name == "done":
            result["referenced_files"] = payload.get("referenced_files", [])
        elif event_name == "error":
            result["error"] = payload.get("message", "The response was interrupted.")
        elif "chunk" in payload:
            yield payload["chunk"]


def upload_zip(file_path: Path) -> dict:
    with file_path.open("rb") as handle:
        files = {"file": (file_path.name, handle.read(), "application/zip")}
        response = requests.post(f"{BACKEND_URL}/upload-project", files=files, timeout=300)
    response.raise_for_status()
    return response.json()


def delete_project(project_id: int) -> dict:
    response = requests.delete(f"{BACKEND_URL}/projects/{project_id}", timeout=60)
    response.raise_for_status()
    return response.json()


def _clean_project_label(name: str) -> str:
    """Strip trailing OS-duplicate-style suffixes like ' (1)' or ' (1) (2)' for display only."""
    return re.sub(r"(\s\(\d+\))+$", "", name)


st.set_page_config(page_title="AI Codebase Architect", layout="wide")
st.title("🏗️ AI Codebase Architect & Engineering Reviewer")

if "messages" not in st.session_state:
    st.session_state.messages = {}

sidebar_projects = []
try:
    sidebar_projects = fetch_projects()
except Exception as error:
    st.sidebar.error(
        f"Backend is not reachable yet. BACKEND_URL={BACKEND_URL!r}. Error: {error}"
    )

st.sidebar.header("📂 Project List")
project_labels = [f"{project['id']}: {_clean_project_label(project['project_name'])}" for project in sidebar_projects]
selected_label = st.sidebar.selectbox("Project Selection", [""] + project_labels)

selected_project = None
if selected_label:
    selected_id = int(selected_label.split(":")[0])
    selected_project = next((project for project in sidebar_projects if project["id"] == selected_id), None)

if selected_project is not None:
    delete_confirm_key = f"confirm_delete_{selected_project['id']}"
    if not st.session_state.get(delete_confirm_key):
        if st.sidebar.button("🗑️ Delete selected project"):
            st.session_state[delete_confirm_key] = True
            st.rerun()
    else:
        st.sidebar.warning("Are you sure? This removes all analysis and chat history for this project.")
        confirm_col, cancel_col = st.sidebar.columns(2)
        with confirm_col:
            if st.button("✅ Confirm", key=f"confirm_delete_btn_{selected_project['id']}"):
                try:
                    delete_project(selected_project["id"])
                    st.session_state.messages.pop(selected_project["id"], None)
                    st.session_state.pop(delete_confirm_key, None)
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Delete failed: {e}")
        with cancel_col:
            if st.button("❌ Cancel", key=f"cancel_delete_btn_{selected_project['id']}"):
                st.session_state.pop(delete_confirm_key, None)
                st.rerun()

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
    def render_mermaid(diagram_code: str, height: int = 750) -> None:
        """Render Mermaid diagram source as an interactive, theme-aware SVG.

        Mermaid's default useMaxWidth behavior caps the SVG at its own natural
        (often small) rendered size, which is why diagrams used to show up tiny
        inside a mostly-empty container. useMaxWidth is disabled here and a custom
        fit-to-container scale is computed after render instead, so the default
        view already fills the available space and is readable without zooming.
        """
        escaped_code = html.escape(diagram_code)
        component_html = f"""
        <div id="mermaid-outer" style="width:100%; height:{height}px; position:relative;
             border:1px solid rgba(128,128,128,0.25); border-radius:8px; overflow:hidden; background:transparent;">
            <div style="position:absolute; top:8px; right:8px; z-index:10; display:flex; gap:6px;">
                <button id="mermaid-zoom-in" title="Zoom in"
                    style="cursor:pointer; border:1px solid rgba(128,128,128,0.4); background:rgba(128,128,128,0.12);
                    color:inherit; border-radius:4px; padding:3px 8px; font-size:13px;">+</button>
                <button id="mermaid-zoom-out" title="Zoom out"
                    style="cursor:pointer; border:1px solid rgba(128,128,128,0.4); background:rgba(128,128,128,0.12);
                    color:inherit; border-radius:4px; padding:3px 8px; font-size:13px;">-</button>
                <button id="mermaid-reset" title="Fit to screen"
                    style="cursor:pointer; border:1px solid rgba(128,128,128,0.4); background:rgba(128,128,128,0.12);
                    color:inherit; border-radius:4px; padding:3px 8px; font-size:12px;">Fit</button>
            </div>
            <div id="mermaid-viewport" style="width:100%; height:100%; overflow:hidden; cursor:grab;">
                <div id="mermaid-pan" style="transform-origin: 0 0; width:fit-content; padding:16px;">
                    <div id="mermaid-target" class="mermaid">{escaped_code}</div>
                </div>
            </div>
        </div>
        <style>
            html, body {{ background: transparent; margin: 0; }}
            #mermaid-target svg {{ max-width: none !important; }}
        </style>
        <script type="module">
            import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";

            const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
            mermaid.initialize({{
                startOnLoad: false,
                theme: prefersDark ? "dark" : "default",
                securityLevel: "loose",
                themeVariables: {{ fontSize: "18px" }},
                flowchart: {{ useMaxWidth: false, curve: "linear", rankSpacing: 70, nodeSpacing: 45 }},
                sequence: {{ useMaxWidth: false, actorFontSize: 16, messageFontSize: 15, noteFontSize: 14 }},
            }});

            const viewport = document.getElementById("mermaid-viewport");
            const pan = document.getElementById("mermaid-pan");
            const target = document.getElementById("mermaid-target");

            let scale = 1;
            let originX = 0;
            let originY = 0;
            let isPanning = false;
            let startX = 0;
            let startY = 0;

            function applyTransform() {{
                pan.style.transform = `translate(${{originX}}px, ${{originY}}px) scale(${{scale}})`;
            }}

            function computeFitScale() {{
                const svg = target.querySelector("svg");
                if (!svg) return 1;
                const box = svg.getBBox ? svg.getBBox() : null;
                const naturalWidth = (box && box.width) || svg.getBoundingClientRect().width || 1;
                const naturalHeight = (box && box.height) || svg.getBoundingClientRect().height || 1;
                const availableWidth = Math.max(viewport.clientWidth - 32, 50);
                const availableHeight = Math.max(viewport.clientHeight - 32, 50);
                const fitScale = Math.min(availableWidth / naturalWidth, availableHeight / naturalHeight);
                return Math.max(0.4, Math.min(fitScale, 2.5));
            }}

            function resetView() {{
                scale = computeFitScale();
                originX = 0;
                originY = 0;
                applyTransform();
            }}

            mermaid.run({{ nodes: [target] }}).then(resetView).catch(() => {{
                target.innerText = "Failed to render diagram.";
            }});

            viewport.addEventListener("wheel", (event) => {{
                event.preventDefault();
                const delta = event.deltaY < 0 ? 0.1 : -0.1;
                scale = Math.min(4, Math.max(0.2, scale + delta));
                applyTransform();
            }}, {{ passive: false }});

            viewport.addEventListener("mousedown", (event) => {{
                isPanning = true;
                startX = event.clientX - originX;
                startY = event.clientY - originY;
                viewport.style.cursor = "grabbing";
            }});

            window.addEventListener("mouseup", () => {{
                isPanning = false;
                viewport.style.cursor = "grab";
            }});

            window.addEventListener("mousemove", (event) => {{
                if (!isPanning) return;
                originX = event.clientX - startX;
                originY = event.clientY - startY;
                applyTransform();
            }});

            document.getElementById("mermaid-zoom-in").addEventListener("click", () => {{
                scale = Math.min(4, scale + 0.2);
                applyTransform();
            }});
            document.getElementById("mermaid-zoom-out").addEventListener("click", () => {{
                scale = Math.max(0.2, scale - 0.2);
                applyTransform();
            }});
            document.getElementById("mermaid-reset").addEventListener("click", resetView);
        </script>
        """
        components.html(component_html, height=height, scrolling=False)

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
                # SECTION 2: ARCHITECTURE DIAGRAMS (main focus of the tab)
                # ============================================================
                st.subheader("📐 Architecture Diagrams")
                diagram_options = {
                    "How Files Connect": "mermaid_architecture",
                    "How Functions Call Each Other": "mermaid_function_flow",
                    "Database Usage": "mermaid_database_flow",
                    "Step-by-Step Flow": "mermaid_execution_flow",
                }
                selected_diagram_label = st.radio(
                    "Diagram type",
                    list(diagram_options.keys()),
                    horizontal=True,
                    key="architecture_diagram_selector",
                )
                if selected_diagram_label == "How Files Connect":
                    st.caption("Files at the top are used by files below them — follow the arrows downward.")
                elif selected_diagram_label == "How Functions Call Each Other":
                    st.caption(
                        "A more detailed, advanced view. It can look sparse or empty for "
                        "projects that mostly call UI widgets or library functions instead "
                        "of their own — that's expected, not a bug."
                    )
                selected_diagram_code = arch_data.get(diagram_options[selected_diagram_label])
                if selected_diagram_code:
                    render_mermaid(selected_diagram_code)
                else:
                    st.info("No diagram available for this selection.")

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

                with st.chat_message("assistant"):
                    stream_result: dict = {}
                    full_answer = st.write_stream(stream_chat(project_id, prompt, stream_result))
                    if stream_result.get("error"):
                        st.warning(stream_result["error"])
                    referenced_files = stream_result.get("referenced_files", [])
                    if referenced_files:
                        st.write("Referenced Files:")
                        for file_name in referenced_files:
                            st.write(f"- {file_name}")
                st.session_state.messages[project_id].append({"role": "assistant", "content": full_answer})
        except Exception as e:
            st.error(f"Chat failed: {e}")

