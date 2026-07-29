"""
frontend/app.py
Main Streamlit application with Single + Multiple Query modes.
Run: streamlit run frontend/app.py
"""
import sys
import time
import tempfile
import os
import io
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
from loguru import logger

from ingestion.pdf_loader import MultimodalPDFLoader
from ingestion.chunker import SmartChunker
from rag.embeddings import TitanEmbeddings
from rag.bedrock_llm import test_bedrock_connection
from vectorstore.pinecone_store import PaperVectorStore
from rag.comparison import MultiPaperComparator
from frontend.components import (
    render_header, service_badge, paper_card,
    finding_card, metric_row, empty_state, progress_log
)
from config import get_settings

settings = get_settings()

# ── Predefined queries ────────────────────────────────────────────────────────
PRESET_QUERIES = {
    "Agreements and Contradictions": (
        "Compare these papers focusing specifically on agreements and contradictions. "
        "Where do the papers agree and where do they directly disagree?"
    ),
    "Methodology Comparison": (
        "Compare the methodology, experimental setup, datasets used, and evaluation "
        "metrics across these papers. What are the key methodological differences?"
    ),
    "Research Gaps and Future Work": (
        "What research gaps, limitations, and future work directions does each paper "
        "identify? Are there common open problems across all papers?"
    ),
    "Research Objectives and Contributions": (
        "What is the main research objective and novel contribution of each paper? "
        "How does each paper advance the state of the art?"
    ),
    "Results and Performance": (
        "Compare the results and performance benchmarks reported in each paper. "
        "Which approach claims better performance and on what tasks?"
    ),
    "Technical Architecture": (
        "Compare the technical architecture and system design of each paper. "
        "What components are shared and what is unique to each approach?"
    ),
    "Full Literature Review": (
        "Provide a complete structured comparison covering: research problem, "
        "proposed solution, methodology, results, limitations, and future directions "
        "for each paper. Identify all agreements, contradictions, methodology "
        "differences, and research gaps."
    ),
}

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Paper Comparison Engine",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: rgba(31,56,100,0.35);
    padding: 5px;
    border-radius: 12px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 0.85rem;
    color: rgba(255,255,255,0.55);
    border: none;
}
.stTabs [aria-selected="true"] {
    background: rgba(46,117,182,0.55);
    color: white;
}
.stFileUploader > div {
    border: 2px dashed rgba(46,117,182,0.4);
    border-radius: 12px;
}
.stButton > button {
    background: linear-gradient(135deg, #1F3864, #2E75B6);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 0.55rem 1.8rem;
    font-weight: 600;
    font-size: 0.95rem;
    width: 100%;
    transition: all 0.2s ease;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(46,117,182,0.4);
}
[data-testid="stSidebar"] {
    background: rgba(10,14,23,0.97);
    border-right: 1px solid rgba(46,117,182,0.18);
}
textarea { font-size: 0.85rem !important; }
.query-result-box {
    background: rgba(31,56,100,0.2);
    border: 1px solid rgba(46,117,182,0.3);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)


# ── Cached services ───────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Initialising AI services...")
def init_services():
    embeddings   = TitanEmbeddings()
    vector_store = PaperVectorStore(embeddings)
    loader       = MultimodalPDFLoader()
    chunker      = SmartChunker()
    comparator   = MultiPaperComparator(vector_store)
    return embeddings, vector_store, loader, chunker, comparator

embeddings, vector_store, loader, chunker, comparator = init_services()


# ── Report generator loader ───────────────────────────────────────────────────
def load_report_generator():
    report_path = ROOT / "generate_report.py"
    if not report_path.exists():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("generate_report", str(report_path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.generate_comparison_report


# ── Helpers ───────────────────────────────────────────────────────────────────
def cleanup_papers(paper_ids: list):
    for pid in paper_ids:
        try:
            vector_store.delete_paper(pid)
        except Exception as e:
            logger.warning(f"Could not delete namespace {pid}: {e}")


def init_state():
    defaults = {
        "papers":             [],
        "paper_ids":          [],
        "paper_metadata":     {},
        "comparison_result":  None,
        "multi_results":      [],   # list of {query_name, query, result, time}
        "processing_time":    0.0,
        "query_mode":         "Single Query",
        "custom_query": (
            "Compare these research papers across agreements, contradictions, "
            "methodology differences, and research gaps."
        ),
        "uploaded": False,
        "show_multi_results": False,
        "bedrock_ok": None,
        "pinecone_ok": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


def full_reset():
    cleanup_papers(st.session_state.get("paper_ids", []))
    for k in ["papers", "paper_ids", "paper_metadata",
              "comparison_result", "multi_results", "uploaded",
              "show_multi_results", "bedrock_ok", "pinecone_ok"]:
        if k in st.session_state:
            del st.session_state[k]
    st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## Settings")
    st.divider()

    st.markdown("**Service Status**")
    # Cache health checks - refresh every 5 minutes
    import time as _time
    last_check = st.session_state.get("health_check_time", 0)
    if st.session_state.get("bedrock_ok") is None or (_time.time() - last_check > 300):
        st.session_state["bedrock_ok"]       = test_bedrock_connection()
        st.session_state["pinecone_ok"]      = vector_store.test_connection()
        st.session_state["health_check_time"] = _time.time()
    bedrock_ok  = st.session_state["bedrock_ok"]
    pinecone_ok = st.session_state["pinecone_ok"]
    service_badge("AWS Bedrock", bedrock_ok)
    service_badge("Pinecone DB", pinecone_ok)
    st.markdown("")

    if not bedrock_ok:
        st.error("AWS Bedrock not reachable. Check your .env keys.")
    if not pinecone_ok:
        st.error("Pinecone not reachable. Check your API key.")

    st.divider()

    if st.session_state["uploaded"]:
        st.markdown(f"**Session:** {len(st.session_state['paper_ids'])} papers loaded")
        st.markdown("")
        if st.button("Clear Session + Pinecone Data"):
            full_reset()

    st.divider()
    st.markdown("**Pinecone Management**")
    if st.button("Delete All Vectors from Pinecone"):
        with st.spinner("Clearing all Pinecone data..."):
            try:
                from pinecone import Pinecone as PC
                pc    = PC(api_key=settings.pinecone_api_key)
                idx   = pc.Index(settings.pinecone_index_name)
                stats = idx.describe_index_stats()
                nss   = list(stats.namespaces.keys())
                if nss:
                    for ns in nss:
                        idx.delete(delete_all=True, namespace=ns)
                    st.success(f"Deleted {len(nss)} namespace(s)!")
                else:
                    st.info("Pinecone is already empty.")
                for k in ["papers", "paper_ids", "paper_metadata",
                          "comparison_result", "multi_results", "uploaded",
                          "show_multi_results", "bedrock_ok", "pinecone_ok"]:
                    if k in st.session_state:
                        del st.session_state[k]
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()
    st.markdown("""
    <div style="color:rgba(255,255,255,0.3);font-size:0.73rem;line-height:1.7;">
    <b>Pipeline:</b><br>
    PDF Upload<br>
    pdfplumber (text + tables)<br>
    LangChain chunking<br>
    Amazon Titan embeddings<br>
    Pinecone (per-paper namespace)<br>
    LangChain RAG chains<br>
    Claude synthesis<br>
    Streamlit display
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# MAIN PAGE
# ════════════════════════════════════════════════════════════════════════════
render_header()

s1 = st.session_state["uploaded"]
s2 = (st.session_state["comparison_result"] is not None or
      len(st.session_state.get("multi_results", [])) > 0 or
      st.session_state.get("show_multi_results", False))

# Step indicators
c1, c2, c3 = st.columns(3)
for col, num, done, label in [
    (c1, "1", s1, "Upload Papers"),
    (c2, "2", s2, "Run Comparison"),
    (c3, "3", s2, "Explore Results"),
]:
    with col:
        bg = "rgba(34,197,94,0.15)" if done else "rgba(46,117,182,0.12)"
        bc = "#22c55e" if done else "rgba(46,117,182,0.3)"
        ic = "&#10003;" if done else num
        st.markdown(f"""
        <div style="background:{bg};border:1px solid {bc};border-radius:12px;
        padding:0.9rem;text-align:center;">
            <div style="font-size:1.3rem;">{ic}</div>
            <div style="font-size:0.82rem;color:rgba(255,255,255,0.75);
            margin-top:3px;">{label}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("")


# ── UPLOAD SECTION ────────────────────────────────────────────────────────────
with st.expander("Upload Research Papers", expanded=not s1):
    uploaded_files = st.file_uploader(
        "Upload 3 to 8 PDF research papers on the same topic",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        n = len(uploaded_files)
        if n < settings.min_papers:
            st.warning(f"Please upload at least {settings.min_papers} papers.")
        elif n > settings.max_papers:
            st.error(f"Maximum {settings.max_papers} papers per session.")
        else:
            st.markdown(f"**{n} files selected:**")
            for f in uploaded_files:
                st.markdown(f"- `{f.name}` ({round(len(f.getvalue())/1024,1)} KB)")

            if st.button(f"Process {n} Papers"):
                if st.session_state.get("paper_ids"):
                    cleanup_papers(st.session_state["paper_ids"])

                paper_ids      = []
                paper_metadata = {}
                paper_display  = []
                failed         = []
                progress       = st.progress(0)
                status         = st.empty()

                for idx, file in enumerate(uploaded_files):
                    status.markdown(f"Processing **{file.name}** ({idx+1}/{n})...")
                    progress.progress(idx / n)
                    os.makedirs("data/uploads", exist_ok=True)

                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".pdf", dir="data/uploads"
                    ) as tmp:
                        tmp.write(file.getvalue())
                        tmp_path = tmp.name

                    try:
                        parsed = loader.load(tmp_path, file.name)
                        progress_log(f"Parsed: {len(parsed.elements)} elements")
                        chunks = chunker.chunk_paper(parsed)
                        progress_log(f"Chunked: {len(chunks)} chunks")
                        vector_store.index_paper(chunks, parsed.paper_id)
                        progress_log(f"Indexed in Pinecone: namespace '{parsed.paper_id}'")

                        paper_ids.append(parsed.paper_id)
                        paper_metadata[parsed.paper_id] = {
                            "filename": file.name,
                            "title":    parsed.title,
                            "chunks":   len(chunks),
                            "sections": len(set(c.section for c in chunks)),
                        }
                        paper_display.append({
                            "paper_id": parsed.paper_id,
                            "filename": file.name,
                            "title":    parsed.title,
                            "chunks":   len(chunks),
                            "sections": len(set(c.section for c in chunks)),
                        })
                    except Exception as e:
                        st.error(f"Failed: {file.name} — {e}")
                        logger.error(e)
                        failed.append(file.name)
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass

                progress.progress(1.0)
                status.empty()

                if paper_ids:
                    st.session_state.update({
                        "paper_ids":         paper_ids,
                        "paper_metadata":    paper_metadata,
                        "papers":            paper_display,
                        "uploaded":          True,
                        "comparison_result": None,
                        "multi_results":     [],
                    })
                    if failed:
                        st.warning(f"{len(failed)} failed: {', '.join(failed)}")
                    st.success(f"{len(paper_ids)} paper(s) processed and indexed!")
                    st.rerun()
                else:
                    st.error("All papers failed. Check logs above.")


# ── LOADED PAPERS ─────────────────────────────────────────────────────────────
if st.session_state["papers"]:
    st.markdown("### Indexed Papers")
    for p in st.session_state["papers"]:
        paper_card(
            filename=p["filename"],
            title=p["title"],
            chunks=p["chunks"],
            paper_id=p["paper_id"],
            sections=p.get("sections", 0),
        )
    st.markdown("")


# ════════════════════════════════════════════════════════════════════════════
# QUERY SECTION
# ════════════════════════════════════════════════════════════════════════════
if s1 and not s2:  # Show query section only when no results yet
    st.markdown("---")
    st.markdown("### Query Mode")

    # Mode selector
    mode = st.radio(
        "Select query mode:",
        ["Single Query", "Multiple Queries"],
        horizontal=True,
        key="query_mode_radio",
    )
    st.session_state["query_mode"] = mode
    st.markdown("")

    # ── SINGLE QUERY MODE ────────────────────────────────────────────────────
    if mode == "Single Query":
        st.markdown("**Write your comparison query:**")

        # Quick preset buttons
        st.markdown("**Quick presets:**")
        preset_cols = st.columns(3)
        preset_names = list(PRESET_QUERIES.keys())

        for i, col in enumerate(preset_cols):
            if i < len(preset_names):
                with col:
                    if st.button(preset_names[i], key=f"preset_{i}"):
                        st.session_state["custom_query"] = PRESET_QUERIES[preset_names[i]]
                        st.rerun()

        preset_cols2 = st.columns(3)
        for i, col in enumerate(preset_cols2):
            idx = i + 3
            if idx < len(preset_names):
                with col:
                    if st.button(preset_names[idx], key=f"preset_{idx}"):
                        st.session_state["custom_query"] = PRESET_QUERIES[preset_names[idx]]
                        st.rerun()

        st.markdown("")
        st.session_state["custom_query"] = st.text_area(
            "Custom query:",
            value=st.session_state["custom_query"],
            height=100,
        )

        if st.button("Run Comparison"):
            with st.spinner("Claude is analysing your papers..."):
                t0 = time.time()
                try:
                    result  = comparator.compare(
                        paper_ids=st.session_state["paper_ids"],
                        paper_metadata=st.session_state["paper_metadata"],
                        user_query=st.session_state["custom_query"],
                    )
                    elapsed = round(time.time() - t0, 1)
                    st.session_state["comparison_result"] = result
                    st.session_state["processing_time"]   = elapsed
                    st.session_state["multi_results"]     = []
                    st.rerun()
                except Exception as e:
                    st.error(f"Comparison failed: {e}")
                    logger.error(e)

    # ── MULTIPLE QUERIES MODE ────────────────────────────────────────────────
    else:
        st.markdown("**Select queries to run (one after another):**")

        selected_queries = {}
        for name, query in PRESET_QUERIES.items():
            checked = st.checkbox(
                name,
                value=name in ["Agreements and Contradictions",
                               "Methodology Comparison",
                               "Research Gaps and Future Work"],
                key=f"chk_{name}"
            )
            if checked:
                selected_queries[name] = query

        # Custom query option
        add_custom = st.checkbox("Add custom query", key="add_custom_chk")
        if add_custom:
            custom_q = st.text_area(
                "Your custom query:",
                value=st.session_state["custom_query"],
                height=80,
            )
            if custom_q.strip():
                selected_queries["Custom Query"] = custom_q

        st.markdown("")

        if selected_queries:
            n_queries = len(selected_queries)
            # Estimate time: ~4-5 min per query per 3 papers
            est_min = n_queries * 4
            est_max = n_queries * 5

            st.markdown(f"""
            <div style="background:rgba(46,117,182,0.15);border:1px solid rgba(46,117,182,0.3);
            border-radius:10px;padding:0.8rem 1rem;margin-bottom:1rem;">
                <b style="color:#4BACC6;">Selected: {n_queries} queries</b>
                <span style="color:rgba(255,255,255,0.6);font-size:0.85rem;">
                &nbsp;&nbsp;|&nbsp;&nbsp; Estimated time: {est_min}–{est_max} minutes
                </span>
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"Run All {n_queries} Queries"):
                all_results = []
                overall_start = time.time()

                progress_container = st.container()

                for q_idx, (q_name, q_text) in enumerate(selected_queries.items()):
                    with progress_container:
                        st.markdown(f"""
                        <div style="background:rgba(31,56,100,0.3);border:1px solid rgba(46,117,182,0.3);
                        border-radius:10px;padding:0.8rem 1rem;margin:0.3rem 0;">
                            <span style="color:#4BACC6;font-weight:600;">
                            Running {q_idx+1}/{n_queries}: {q_name}
                            </span>
                        </div>
                        """, unsafe_allow_html=True)

                    with st.spinner(f"Query {q_idx+1}/{n_queries}: {q_name}..."):
                        t0 = time.time()
                        try:
                            result  = comparator.compare(
                                paper_ids=st.session_state["paper_ids"],
                                paper_metadata=st.session_state["paper_metadata"],
                                user_query=q_text,
                            )
                            elapsed = round(time.time() - t0, 1)
                            all_results.append({
                                "query_name": q_name,
                                "query":      q_text,
                                "result":     result,
                                "time":       elapsed,
                            })
                            st.success(f"Done: {q_name} ({elapsed}s)")
                        except Exception as e:
                            st.error(f"Failed: {q_name} — {e}")
                            logger.error(e)

                total_time = round(time.time() - overall_start, 1)
                st.session_state["multi_results"]     = all_results
                st.session_state["comparison_result"] = None
                st.session_state["processing_time"]   = total_time
                st.session_state["show_multi_results"] = True
        else:
            st.warning("Please select at least one query.")


# ════════════════════════════════════════════════════════════════════════════
# RESULTS — SINGLE QUERY
# ════════════════════════════════════════════════════════════════════════════
if st.session_state["comparison_result"] is not None:
    st.markdown("---")
    res = st.session_state["comparison_result"]
    pt  = st.session_state["processing_time"]

    st.markdown("### Comparison Results")
    metric_row(
        len(res.agreements),
        len(res.contradictions),
        len(res.methodology_differences),
        len(res.research_gaps),
        pt,
    )
    st.markdown("")

    tab1, tab2, tab3, tab4 = st.tabs([
        f"Agreements ({len(res.agreements)})",
        f"Contradictions ({len(res.contradictions)})",
        f"Methodology ({len(res.methodology_differences)})",
        f"Research Gaps ({len(res.research_gaps)})",
    ])
    with tab1:
        if res.agreements:
            for i, item in enumerate(res.agreements):
                finding_card(item, "agreements", i)
        else:
            empty_state("agreements")
    with tab2:
        if res.contradictions:
            for i, item in enumerate(res.contradictions):
                finding_card(item, "contradictions", i)
        else:
            empty_state("contradictions")
    with tab3:
        if res.methodology_differences:
            for i, item in enumerate(res.methodology_differences):
                finding_card(item, "methodology_differences", i)
        else:
            empty_state("methodology_differences")
    with tab4:
        if res.research_gaps:
            for i, item in enumerate(res.research_gaps):
                finding_card(item, "research_gaps", i)
        else:
            empty_state("research_gaps")

    # Download
    st.markdown("")
    st.markdown("### Download Report")
    generate_fn = load_report_generator()
    if generate_fn:
        try:
            report_bytes = generate_fn(
                result=res,
                paper_metadata=st.session_state["paper_metadata"],
                user_query=st.session_state["custom_query"],
                processing_time=pt,
            )
            st.download_button(
                label="Download Word Report (.docx)",
                data=report_bytes,
                file_name=f"report_{time.strftime('%Y%m%d_%H%M%S')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        except Exception as e:
            st.error(f"Report error: {e}")
    else:
        st.warning("generate_report.py not found in project root.")

    st.markdown("")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Run New Comparison (Same Papers)"):
            st.session_state["comparison_result"]  = None
            st.session_state["show_multi_results"] = False
            st.rerun()
    with col2:
        if st.button("Upload New Papers (Clear Everything)"):
            full_reset()


# ════════════════════════════════════════════════════════════════════════════
# RESULTS — MULTIPLE QUERIES
# ════════════════════════════════════════════════════════════════════════════
if len(st.session_state.get("multi_results", [])) > 0 or st.session_state.get("show_multi_results", False):
    st.markdown("---")
    multi = st.session_state["multi_results"]
    logger.info(f"Displaying multi results: {len(multi)} queries")
    total_time = st.session_state["processing_time"]

    # Summary banner
    total_findings = sum(
        len(r["result"].agreements) +
        len(r["result"].contradictions) +
        len(r["result"].methodology_differences) +
        len(r["result"].research_gaps)
        for r in multi
    )
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,rgba(31,56,100,0.4),rgba(46,117,182,0.2));
    border:1px solid rgba(46,117,182,0.4);border-radius:14px;
    padding:1.2rem 1.5rem;margin-bottom:1.5rem;text-align:center;">
        <div style="color:#4BACC6;font-size:1.5rem;font-weight:700;">{len(multi)} Queries Completed</div>
        <div style="color:rgba(255,255,255,0.6);font-size:0.9rem;margin-top:4px;">
        {total_findings} total findings &nbsp;|&nbsp; {total_time}s total time
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Each query result
    for q_data in multi:
        q_name  = q_data["query_name"]
        res     = q_data["result"]
        q_time  = q_data["time"]

        total_q = (
            len(res.agreements) + len(res.contradictions) +
            len(res.methodology_differences) + len(res.research_gaps)
        )

        with st.expander(
            f"{q_name}  —  {total_q} findings  ({q_time}s)",
            expanded=True
        ):
            metric_row(
                len(res.agreements),
                len(res.contradictions),
                len(res.methodology_differences),
                len(res.research_gaps),
                q_time,
            )
            st.markdown("")

            tab1, tab2, tab3, tab4 = st.tabs([
                f"Agreements ({len(res.agreements)})",
                f"Contradictions ({len(res.contradictions)})",
                f"Methodology ({len(res.methodology_differences)})",
                f"Research Gaps ({len(res.research_gaps)})",
            ])
            with tab1:
                if res.agreements:
                    for i, item in enumerate(res.agreements):
                        finding_card(item, "agreements", i)
                else:
                    empty_state("agreements")
            with tab2:
                if res.contradictions:
                    for i, item in enumerate(res.contradictions):
                        finding_card(item, "contradictions", i)
                else:
                    empty_state("contradictions")
            with tab3:
                if res.methodology_differences:
                    for i, item in enumerate(res.methodology_differences):
                        finding_card(item, "methodology_differences", i)
                else:
                    empty_state("methodology_differences")
            with tab4:
                if res.research_gaps:
                    for i, item in enumerate(res.research_gaps):
                        finding_card(item, "research_gaps", i)
                else:
                    empty_state("research_gaps")

    # Combined download
    st.markdown("")
    st.markdown("### Download Combined Report")
    generate_fn = load_report_generator()

    if generate_fn:
        try:
            # Generate one combined report with all query results
            # Use last result as primary, pass all in metadata
            combined_result = multi[-1]["result"]
            # Merge all findings from all queries
            from rag.comparison import ComparisonResult, ComparisonItem

            all_agreements   = []
            all_contradict   = []
            all_methods      = []
            all_gaps         = []

            for q_data in multi:
                r = q_data["result"]
                all_agreements.extend(r.agreements)
                all_contradict.extend(r.contradictions)
                all_methods.extend(r.methodology_differences)
                all_gaps.extend(r.research_gaps)

            merged = ComparisonResult(
                agreements=all_agreements,
                contradictions=all_contradict,
                methodology_differences=all_methods,
                research_gaps=all_gaps,
            )

            combined_query = " | ".join(q["query_name"] for q in multi)
            report_bytes   = generate_fn(
                result=merged,
                paper_metadata=st.session_state["paper_metadata"],
                user_query=f"Multiple Queries: {combined_query}",
                processing_time=total_time,
            )

            st.download_button(
                label=f"Download Combined Report ({len(multi)} queries, {total_findings} findings)",
                data=report_bytes,
                file_name=f"combined_report_{time.strftime('%Y%m%d_%H%M%S')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            st.success("Combined report ready with all query results merged!")
        except Exception as e:
            st.error(f"Report error: {e}")
            logger.error(e)
    else:
        st.warning("generate_report.py not found in project root.")

    st.markdown("")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Run More Queries (Same Papers)"):
            st.session_state["multi_results"]      = []
            st.session_state["comparison_result"]  = None
            st.session_state["show_multi_results"] = False
            st.rerun()
    with col2:
        if st.button("Upload New Papers (Clear Everything)"):
            full_reset()