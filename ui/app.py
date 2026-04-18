import streamlit as st
import asyncio
import json
import os
import pandas as pd
import time
import sys

# Add the project root to sys.path to allow importing backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import process_ticket
from agent.classifier import classify_ticket
from tools.decision_utils import is_escalated_decision

# --- UI CONFIGURATION ---
LOGO_PATH = os.path.join(os.getcwd(), "assets", "logo.png")

st.set_page_config(
    page_title="Tixora-AI | Production Monitoring",
    page_icon=LOGO_PATH if os.path.exists(LOGO_PATH) else "🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PREMIUM CSS (Glassmorphism + Modern UI) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    
    /* Main Background - High Contrast Dark */
    .stApp {
        background: radial-gradient(circle at top right, #1e293b, #0f172a);
    }

    /* Modern Headers */
    h1, h2, h3 {
        color: #ffffff !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }

    /* Subtext Visibility */
    .stCaption, p, span {
        color: #94a3b8 !important;
    }

    /* Glass Cards - Enhanced Border & Blur */
    div[data-testid="stExpander"] {
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 12px;
        margin-bottom: 12px;
        backdrop-filter: blur(12px);
    }
    
    /* Metric Cards - Professional Inset Look */
    [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #38bdf8;
    }
    
    [data-testid="stMetricValue"] {
        color: #f8fafc !important;
        font-weight: 700 !important;
        font-size: 1.8rem !important;
    }

    [data-testid="stMetricLabel"] {
        color: #38bdf8 !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 0.75rem !important;
    }
    
    /* Custom Semantic Badges */
    .badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 8px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
    }
    .status-success { background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .status-warning { background: rgba(234, 179, 8, 0.15); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.3); }
    .status-escalated { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .status-recovery { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }

    /* Dashboard Navigation Tabs - High Visibility */
    button[data-baseweb="tab"] {
        background-color: transparent !important;
    }
    
    button[data-baseweb="tab"] p {
        color: #f8fafc !important; /* Bright off-white */
        font-weight: 700 !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.05em !important;
        transition: color 0.3s ease !important;
    }

    button[data-baseweb="tab"]:hover p {
        color: #38bdf8 !important; /* Cyan on hover */
    }

    button[data-baseweb="tab"][aria-selected="true"] p {
        color: #38bdf8 !important; /* Active Tab in Cyan */
    }

    /* Primary Button - High Visibility */
    .stButton>button {
        background-color: #00d4ff !important;
        color: #000000 !important;
        border-radius: 8px !important;
        font-weight: 800 !important;
        font-size: 0.9rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
        border: none !important;
        box-shadow: 0 10px 15px -3px rgba(0, 212, 255, 0.3) !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton>button:hover {
        background-color: #ffffff !important;
        color: #00d4ff !important;
        transform: translateY(-2px);
    }
    
    /* Sidebar Branding */
    section[data-testid="stSidebar"] {
        background-color: #111827 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- HELPER LOGIC ---
def get_enriched_status(res):
    """Deeply inspects the reasoning chain to determine environmental resilience."""
    chain = res.get('reasoning_chain', [])
    decision = str(res.get('decision', '')).lower()
    
    if is_escalated_decision(decision):
        return "Escalated", "🔴", "status-escalated"
    
    # Analyze internal step health
    has_fatal = any(step.get('status') == 'fatal_failure' for step in chain)
    has_retries = any(len(step.get('attempts', [])) > 1 for step in chain)
    
    if has_fatal:
        return "Resilient Success (Partial Step Failure)", "⚠️", "status-warning"
    if has_retries:
        return "Resolved (Stability Recovery Used)", "🔄", "status-recovery"
        
    return "Optimized Resolution", "✅", "status-success"

# --- STATE MANAGEMENT ---
if 'results' not in st.session_state: st.session_state.results = []
if 'is_running' not in st.session_state: st.session_state.is_running = False
if 'tickets' not in st.session_state: st.session_state.tickets = []

# --- SIDEBAR: TECHNICAL CONTROL ---
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=80)
    else:
        st.image("https://img.icons8.com/parakeet/512/processor.png", width=60)
    st.title("Tixora-AI Engine")
    st.markdown("`v2.0.0-Enterprise-Production`", help="Proprietary ReAct reasoning engine with forced schema validation.")
    
    st.divider()
    
    input_source = st.radio("Ticket Ingestion", ["Production (data/tickets.json)", "Manual Injection (Upload)"])
    if input_source == "Production (data/tickets.json)":
        try:
            with open("data/tickets.json", "r") as f:
                st.session_state.tickets = json.load(f)
            st.info(f"Buffered {len(st.session_state.tickets)} tickets from production database.")
        except: st.error("No ticket stream found.")
    else:
        file = st.file_uploader("Upload JSON stream", type=["json"])
        if file: st.session_state.tickets = json.load(file)

    st.divider()
    
    st.markdown("### ⚡ Execution Policy")
    concurrency = st.slider("Node Concurrency (Semaphore)", 1, 5, 2, help="Throttle parallel execution to respect Groq Free-Tier RPM limits.")
    process_btn = st.button("INIT BATCH PROCESS", disabled=st.session_state.is_running or not st.session_state.tickets, type="primary", use_container_width=True)

# --- MAIN DASHBOARD INTERFACE ---
st.markdown("<div style='margin-top: -30px;'></div>", unsafe_allow_html=True) 

title_col1, title_col2 = st.columns([1, 10])
with title_col1:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=70)
    else:
        st.markdown("# 🛡️")

with title_col2:
    st.title("Tixora-AI | Production Monitoring")

st.caption("Autonomous Support Resolution Pipeline • Real-time Reasoning Audit")

st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)

# Technical Metrics Ribbon in a Container for better grouping
with st.container():
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)

    total = len(st.session_state.tickets)
    results = st.session_state.results
    processed = len([r for r in results if r.get('status') != 'running'])
    successes = len([r for r in results if not is_escalated_decision(r.get('decision', ''))])
    total_steps = sum([len(r.get('reasoning_chain', [])) for r in results])
    retry_count = sum([1 for r in results for step in r.get('reasoning_chain', []) if len(step.get('attempts', [])) > 1])

    # Dynamic Reliability Metric
    reliability = ((total_steps - retry_count) / total_steps * 100) if total_steps > 0 else 100.0

    with m_col1: st.metric("Stream Volume", total)
    with m_col2: st.metric("Autonomous Resolve", f"{processed} Units")
    with m_col3: st.metric("Success Rate", f"{(successes/processed*100):.1f}%" if processed > 0 else "0.0%")
    with m_col4: st.metric("Node Reliability", f"{reliability:.1f}%", delta=f"{retry_count} recoveries active")

st.markdown("<div style='margin-top: 30px; border-bottom: 1px solid rgba(255,255,255,0.05)'></div>", unsafe_allow_html=True)
st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

# --- EXECUTION VIEWS ---
tabs = st.tabs(["⚡ REAL-TIME STREAM", "📂 ANALYTICS & AUDIT", "🔍 FAILURE MODES"])

with tabs[0]:
    if not results:
        st.write("Initializing pipeline listener... Wait for batch initiation.")
    else:
        for res in reversed(results):
            label, icon, css_class = get_enriched_status(res)
            ticket_id = res.get('ticket_id')
            
            # Premium Header
            header_html = f"""
            <div style="display:flex; justify-content:space-between; align-items:center; width:100%">
                <span>{icon} <b>{ticket_id}</b></span>
                <span class="badge {css_class}">{label}</span>
            </div>
            """
            
            with st.expander(label, expanded=True):
                st.markdown(header_html, unsafe_allow_html=True)
                
                # Detail Logic
                i_col1, i_col2, i_col3 = st.columns([3, 1, 1])
                i_col1.markdown(f"**Final Decision:** `{res.get('decision')}`")
                i_col2.metric("Confidence", f"{res.get('confidence', 0):.2f}")
                i_col3.metric("Latency", f"{res.get('duration', 0):.2f}s")
                
                # Reasoning Chain with better visibility
                chain_df = pd.DataFrame(res.get('reasoning_chain', []))
                if not chain_df.empty:
                    st.markdown("#### Cognitive Chain Analysis")
                    st.dataframe(
                        chain_df[['step', 'thought', 'action', 'status']], 
                        use_container_width=True,
                        hide_index=True
                    )
                
                if res.get('error'):
                    st.error(f"Environmental Error: {res['error']}")

with tabs[1]:
    if results:
        st.markdown("### Resolution Distribution")
        # Simple Bar Chart for distribution
        decisions = [r.get('decision', 'unknown').split(':')[0] for r in results]
        dist = pd.Series(decisions).value_counts()
        st.bar_chart(dist)
        
        st.markdown("### Raw Pipeline Audit")
        st.json(results)
    else:
        st.write("Awaiting data stream...")

with tabs[2]:
    st.markdown("### Chaos Engineering Report")
    st.write("Below are the detected failure vectors handled by the Tixora-AI resilience layer:")
    
    # Filter for only failed steps
    failures = []
    for r in results:
        for step in r.get('reasoning_chain', []):
            if step.get('status') == 'fatal_failure' or len(step.get('attempts', [])) > 1:
                failures.append({
                    "ticket_id": r['ticket_id'],
                    "step": step['step'],
                    "action": step['action'],
                    "issue": "Fatal failure (Recovered/Ignored)" if step.get('status') == 'fatal_failure' else "Network Jitter/Retry",
                    "attempts": len(step.get('attempts', []))
                })
    
    if failures:
        st.table(pd.DataFrame(failures))
    else:
        st.info("No environmental failures detected in this batch.")

# --- BATCH RUNNER ---
async def execute_batch():
    st.session_state.is_running = True
    st.session_state.results = []
    
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [process_ticket(t, semaphore) for t in st.session_state.tickets]
    
    # Live Progress
    progress_container = st.container()
    p_text = progress_container.empty()
    p_bar = progress_container.progress(0)
    
    completed = 0
    for task in asyncio.as_completed(tasks):
        result = await task
        st.session_state.results.append(result)
        completed += 1
        p_bar.progress(completed / len(st.session_state.tickets))
        p_text.info(f"Pipeline: Processed {completed}/{len(st.session_state.tickets)} nodes...")
        # Note: We can't easily force-render the EXPANDERS inside this loop in 
        # Streamlit without st.rerun(), but st.rerun() stops this loop.
        # So we update metrics post-loop or use a smaller concurrency limit for "live" feel.
        
    st.session_state.is_running = False
    st.success("Batch Processing Concluded.")
    time.sleep(1)
    st.rerun()

if process_btn:
    asyncio.run(execute_batch())
