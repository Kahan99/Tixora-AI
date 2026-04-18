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

# --- PREMIUM CSS TEMPLATE ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    
    /* Main Background */
    .stApp {
        background: #0a0e1a;
        color: #e2e8f0;
    }

    /* Sidebar Background */
    section[data-testid="stSidebar"] {
        background-color: #0d1117 !important;
    }

    /* Subtexts & Labels */
    .stCaption, p, span {
        color: #64748b !important;
    }

    /* Metric Cards */
    [data-testid="stMetric"] {
        background: #111827;
        border: 1px solid #1f2937;
        padding: 15px;
        border-radius: 8px;
    }
    
    [data-testid="stMetricValue"] {
        color: #f1f5f9 !important;
        font-weight: 600 !important;
        font-size: 1.6rem !important;
    }

    [data-testid="stMetricLabel"] {
        color: #64748b !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.7rem !important;
    }

    /* Dashboard Navigation Tabs */
    button[data-baseweb="tab"] {
        background-color: transparent !important;
    }
    
    button[data-baseweb="tab"] p {
        color: #94a3b8 !important;
        font-weight: 400 !important;
        font-size: 0.85rem !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] p {
        color: #3b82f6 !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        border-bottom: 2px solid #3b82f6 !important;
        background: transparent !important;
    }

    /* Primary Button */
    .stButton>button {
        background-color: #3b82f6 !important;
        color: white !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        border: none !important;
        text-transform: none !important;
        box-shadow: none !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton>button:hover {
        background-color: #2563eb !important;
        color: white !important;
    }

    /* Expander Elements */
    div[data-testid="stExpander"] {
        background: #0f172a;
        border: 1px solid #1e2d3d;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    
    /* Hide Default DataFrame Borders where possible */
    [data-testid="stDataFrame"] > div {
        border: none !important;
    }

    /* Badges */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 500;
        letter-spacing: 0.04em;
    }
    .status-success  { background: rgba(16,185,129,0.1); color:#10b981; border:1px solid rgba(16,185,129,0.25); }
    .status-warning  { background: rgba(245,158,11,0.1);  color:#f59e0b; border:1px solid rgba(245,158,11,0.25); }
    .status-escalated{ background: rgba(239,68,68,0.1);   color:#ef4444; border:1px solid rgba(239,68,68,0.25); }
    .status-recovery { background: rgba(99,102,241,0.1);  color:#6366f1; border:1px solid rgba(99,102,241,0.25); }

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
    st.caption("v2.0.0 · Enterprise")
    
    st.divider()
    
    input_source = st.radio("Data Source", ["Default (tickets.json)", "Upload JSON"])
    if input_source == "Default (tickets.json)":
        try:
            with open("data/tickets.json", "r") as f:
                st.session_state.tickets = json.load(f)
            st.info(f"{len(st.session_state.tickets)} tickets loaded")
        except: st.error("No tickets found.")
    else:
        file = st.file_uploader("Upload JSON stream", type=["json"])
        if file: st.session_state.tickets = json.load(file)

    st.divider()
    
    st.markdown("<p style='font-size:13px; color:#64748b; text-transform:uppercase; letter-spacing:0.05em; font-weight:600; margin-bottom:8px;'>Execution Policy</p>", unsafe_allow_html=True)
    concurrency = st.slider("Concurrency Limit", 1, 5, 2)
    process_btn = st.button("Run Batch", disabled=st.session_state.is_running or not st.session_state.tickets, type="primary", use_container_width=True)

# --- MAIN DASHBOARD INTERFACE ---
st.markdown("<div style='margin-top: -30px;'></div>", unsafe_allow_html=True) 

title_col1, title_col2 = st.columns([1, 20])
with title_col1:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=50)

with title_col2:
    st.markdown("""
      <h2 style="margin:0; font-size:1.6rem; font-weight:600; color:#f1f5f9">
        Tixora-AI
        <span style="color:#64748b; font-weight:400; font-size:1rem; margin-left:8px">
          Production Monitoring
        </span>
      </h2>
      <p style="margin:4px 0 0; color:#64748b; font-size:0.85rem">
        Autonomous support resolution · Real-time reasoning audit
      </p>
    """, unsafe_allow_html=True)

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

    reli_color = "#10b981" if reliability >= 90 else "#f59e0b" if reliability >= 70 else "#ef4444"

    # Injecting specific CSS for metric borders based on semantic meaning
    st.markdown(f"""
    <style>
    div[data-testid="column"]:nth-child(1) [data-testid="stMetric"] {{ border-left-color: #3b82f6; }}
    div[data-testid="column"]:nth-child(2) [data-testid="stMetric"] {{ border-left-color: #10b981; }}
    div[data-testid="column"]:nth-child(3) [data-testid="stMetric"] {{ border-left-color: #10b981; }}
    div[data-testid="column"]:nth-child(4) [data-testid="stMetric"] {{ border-left-color: {reli_color}; }}
    </style>
    """, unsafe_allow_html=True)

    with m_col1: st.metric("Total Tickets", total)
    with m_col2: st.metric("Processed", f"{processed}")
    with m_col3: st.metric("Resolution Rate", f"{(successes/processed*100):.1f}%" if processed > 0 else "0.0%")
    with m_col4: st.metric("Tool Reliability", f"{reliability:.1f}%", delta=f"{retry_count} retries used", delta_color="off")

st.markdown("<div style='margin-top: 30px; border-bottom: 1px solid rgba(255,255,255,0.05)'></div>", unsafe_allow_html=True)
st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

# --- EXECUTION VIEWS ---
tabs = st.tabs(["Real-time Stream", "Analytics & Audit", "Failure Modes"])

with tabs[0]:
    if not results:
        st.caption("No results yet. Run a batch from the sidebar to begin.")
    else:
        for res in reversed(results):
            label, icon, css_class = get_enriched_status(res)
            ticket_id = res.get('ticket_id', 'Unknown')
            
            with st.expander(f"{ticket_id} · {label}"):
                st.markdown(
                    f'<span class="badge {css_class}">{label}</span>',
                    unsafe_allow_html=True
                )
                st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

                # Detail Logic
                i_col1, i_col2, i_col3 = st.columns([2, 1, 1])
                with i_col1:
                    st.caption("Decision")
                    st.code(res.get('decision'), language=None)
                with i_col2: st.metric("Confidence", f"{res.get('confidence', 0):.2f}")
                with i_col3: st.metric("Latency", f"{res.get('duration', 0):.2f}s")
                
                # Reasoning Chain with better visibility
                chain_df = pd.DataFrame(res.get('reasoning_chain', []))
                if not chain_df.empty:
                    st.caption("Reasoning chain")
                    st.dataframe(
                        chain_df[['step', 'thought', 'action', 'status']], 
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "step": st.column_config.NumberColumn("Step", width="small"),
                            "thought": "Reasoning",
                            "action": "Tool Called",
                            "status": "Result"
                        }
                    )
                
                if res.get('error'):
                    st.error(res['error'])

with tabs[1]:
    if results:
        st.caption("Resolution breakdown")
        
        c1, c2, c3 = st.columns(3)
        t_resolved = len([r for r in results if not is_escalated_decision(r.get('decision', ''))])
        t_escalated = len([r for r in results if is_escalated_decision(r.get('decision', ''))])
        avg_conf = sum([r.get('confidence', 0) for r in results]) / len(results) if results else 0
        
        c1.metric("Resolved", t_resolved)
        c2.metric("Escalated", t_escalated)
        c3.metric("Average Confidence", f"{avg_conf:.2f}")

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

        decisions = [r.get('decision', 'unknown').split(':')[0] for r in results]
        dist = pd.Series(decisions).value_counts()
        st.bar_chart(dist)
        
        st.caption("Full audit log")
        st.json(results)
    else:
        st.caption("Run a batch to see analytics.")

with tabs[2]:
    st.subheader("Failure Report")
    
    # Filter for only failed steps
    failures = []
    for r in results:
        for step in r.get('reasoning_chain', []):
            if step.get('status') == 'fatal_failure' or len(step.get('attempts', [])) > 1:
                failures.append({
                    "ticket_id": r['ticket_id'],
                    "step": step['step'],
                    "action": step['action'],
                    "failure type": "Tool failed after retries" if step.get('status') == 'fatal_failure' else "Retried (recovered)",
                    "retry count": len(step.get('attempts', []))
                })
    
    if failures:
        st.table(pd.DataFrame(failures))
    else:
        st.success("No failures detected in this batch.")

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
        p_text.caption(f"Processing {completed} of {len(st.session_state.tickets)} tickets...")
        
    st.session_state.is_running = False
    st.success("Done. All tickets processed.")
    time.sleep(1)
    st.rerun()

if process_btn:
    asyncio.run(execute_batch())
