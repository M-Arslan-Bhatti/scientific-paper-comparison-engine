"""
frontend/components.py
Reusable styled Streamlit UI components.
"""
import streamlit as st


def render_header():
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #1F3864 0%, #2E75B6 60%, #4BACC6 100%);
        padding: 2.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 8px 32px rgba(46,117,182,0.35);
    ">
        <div style="font-size:3rem; margin-bottom:0.4rem;">&#128214;</div>
        <h1 style="color:white; font-size:2rem; font-weight:700; margin:0;">
            Scientific Paper Comparison Engine
        </h1>
        <p style="color:rgba(255,255,255,0.72); font-size:0.95rem; margin:0.5rem 0 0 0;">
            Multi-Document RAG &bull; AWS Bedrock Claude 3.5 Sonnet
            &bull; Amazon Titan V2 &bull; Pinecone &bull; LangChain
        </p>
    </div>
    """, unsafe_allow_html=True)


def service_badge(label: str, ok: bool):
    c, icon = ("#22c55e", "&#10003;") if ok else ("#ef4444", "&#10007;")
    st.markdown(f"""
    <span style="background:{c}22;color:{c};border:1px solid {c}55;
    border-radius:20px;padding:3px 12px;font-size:0.78rem;font-weight:600;
    margin-right:6px;">{icon} {label}</span>
    """, unsafe_allow_html=True)


def paper_card(filename: str, title: str, chunks: int, paper_id: str, sections: int = 0):
    st.markdown(f"""
    <div style="background:rgba(46,117,182,0.1);border:1px solid rgba(46,117,182,0.28);
    border-radius:12px;padding:1rem 1.2rem;margin-bottom:0.7rem;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">
            <span style="font-size:1.3rem;">&#128196;</span>
            <span style="color:#4BACC6;font-weight:600;font-size:0.88rem;">{filename}</span>
        </div>
        <div style="color:rgba(255,255,255,0.65);font-size:0.8rem;margin-bottom:6px;">
            {title[:90]}{'...' if len(title)>90 else ''}
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <span style="background:#1F3864;color:#BDD7EE;border-radius:6px;
            padding:2px 9px;font-size:0.72rem;">ID: {paper_id}</span>
            <span style="background:#14532d;color:#86efac;border-radius:6px;
            padding:2px 9px;font-size:0.72rem;">{chunks} chunks</span>
            {'<span style="background:#3b0764;color:#d8b4fe;border-radius:6px;padding:2px 9px;font-size:0.72rem;">' + str(sections) + ' sections</span>' if sections else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)


def finding_card(item, category: str, index: int):
    cfg = {
        "agreements":              ("#22c55e", "#14532d33", "&#10003; Agreement"),
        "contradictions":          ("#ef4444", "#450a0a33", "&#9888; Contradiction"),
        "methodology_differences": ("#f59e0b", "#451a0333", "&#9881; Method Diff"),
        "research_gaps":           ("#a78bfa", "#2e106533", "&#128270; Research Gap"),
    }
    colour, bg, label = cfg.get(category, ("#6b7280","#11182733","Finding"))

    description = item.description if hasattr(item, 'description') else item.get('description','')
    sources     = item.sources if hasattr(item, 'sources') else item.get('sources', [])
    confidence  = item.confidence if hasattr(item, 'confidence') else item.get('confidence', None)

    conf_bar = ""
    if confidence is not None:
        pct = int(float(confidence) * 100)
        conf_bar = f"""<div style="margin-top:8px;">
            <span style="color:rgba(255,255,255,0.45);font-size:0.72rem;">Confidence: {pct}%</span>
            <div style="background:rgba(255,255,255,0.08);border-radius:3px;height:4px;margin-top:3px;">
              <div style="background:{colour};width:{pct}%;height:4px;border-radius:3px;"></div>
            </div></div>"""

    src_tags = "".join([
        f'<span style="background:{bg};color:{colour};border:1px solid {colour}33;'
        f'border-radius:5px;padding:2px 7px;font-size:0.7rem;margin:2px;display:inline-block;">'
        f'{str(s)[:70]}</span>'
        for s in sources
    ])
    src_html = f'<div style="margin-top:8px;">{src_tags}</div>' if sources else ""

    st.markdown(f"""
    <div style="background:{bg};border:1px solid {colour}2A;border-left:4px solid {colour};
    border-radius:12px;padding:1rem 1.2rem;margin-bottom:0.8rem;">
        <div style="display:flex;align-items:flex-start;gap:10px;">
            <div style="flex:1;">
                <div style="color:{colour};font-size:0.72rem;font-weight:700;
                margin-bottom:5px;text-transform:uppercase;letter-spacing:0.5px;">{label}</div>
                <p style="color:rgba(255,255,255,0.9);font-size:0.88rem;
                line-height:1.6;margin:0;">{description}</p>
                {src_html}
                {conf_bar}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def metric_row(agreements: int, contradictions: int, methods: int, gaps: int, time_s: float):
    cols = st.columns(5)
    data = [
        ("Agreements",     agreements,     "#22c55e"),
        ("Contradictions", contradictions, "#ef4444"),
        ("Method Diffs",   methods,        "#f59e0b"),
        ("Research Gaps",  gaps,           "#a78bfa"),
        ("Time (s)",       f"{time_s:.1f}","#4BACC6"),
    ]
    for col, (label, val, colour) in zip(cols, data):
        with col:
            st.markdown(f"""
            <div style="background:{colour}1A;border:1px solid {colour}44;
            border-radius:12px;padding:0.85rem;text-align:center;">
                <div style="color:{colour};font-size:1.6rem;font-weight:700;">{val}</div>
                <div style="color:rgba(255,255,255,0.55);font-size:0.75rem;margin-top:3px;">{label}</div>
            </div>
            """, unsafe_allow_html=True)


def empty_state(category: str):
    msgs = {
        "agreements":              ("&#9711;", "No agreements detected across these papers."),
        "contradictions":          ("&#9711;", "No direct contradictions found."),
        "methodology_differences": ("&#9711;", "No significant methodology differences identified."),
        "research_gaps":           ("&#9711;", "No explicit research gaps identified."),
    }
    icon, msg = msgs.get(category, ("&#9711;", "No items found."))
    st.markdown(f"""
    <div style="text-align:center;padding:2rem;
    color:rgba(255,255,255,0.3);
    border:1px dashed rgba(255,255,255,0.12);border-radius:12px;">
        <div style="font-size:2rem;margin-bottom:0.5rem;">{icon}</div>
        <p style="margin:0;font-size:0.88rem;">{msg}</p>
    </div>
    """, unsafe_allow_html=True)


def progress_log(message: str):
    """Show a small info line during processing."""
    st.markdown(f"""
    <div style="color:rgba(255,255,255,0.5);font-size:0.8rem;
    padding:4px 12px;border-left:3px solid #4BACC6;margin:4px 0;">
        {message}
    </div>
    """, unsafe_allow_html=True)
