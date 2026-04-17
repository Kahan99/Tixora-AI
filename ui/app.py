import streamlit as st
import asyncio
import json
import os
import pandas as pd
from datetime import datetime
import time
import sys

# Add the project root to sys.path to allow importing backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import process_ticket
from agent.classifier import classify_ticket

# Page Configuration
st.set_page_config(
    page_title="Tixora-AI | Autonomous Support Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .status-badge {
        padding: 5px 10px;
        border-radius: 15px;
        font-weight: bold;
        font-size: 0.8em;
    }
    .status-success { background-color: #d4edda; color: #155724; }
    .status-escalated { background-color: #f8d7da; color: #721c24; }
    .status-running { background-color: #fff3cd; color: #856404; }
</style>
""", unsafe_allow_html=True)

# Session State Initialization
if 'results' not in st.session_state:
    st.session_state.results = []
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'tickets' not in st.session_state:
    st.session_state.tickets = []

# Sidebar - Configuration & Inputs
with st.sidebar:
    st.title("⚙️ Controller")
    
    input_source = st.radio("Ticket Source", ["Predefined (data/tickets.json)", "Upload JSON File"])
    
    loaded_tickets = []
    if input_source == "Predefined (data/tickets.json)":
        try:
            with open("data/tickets.json", "r") as f:
                loaded_tickets = json.load(f)
            st.success(f"Loaded {len(loaded_tickets)} tickets from disk.")
        except FileNotFoundError:
            st.error("data/tickets.json not found!")
    else:
        uploaded_file = st.file_uploader("Upload tickets.json", type=["json"])
        if uploaded_file is not None:
            loaded_tickets = json.load(uploaded_file)
            st.success(f"Uploaded {len(loaded_tickets)} tickets.")

    st.session_state.tickets = loaded_tickets
    
    st.divider()
    
    concurrency = st.slider("Concurrency Limit", 1, 5, 2)
    process_btn = st.button("🚀 Process Tickets", disabled=st.session_state.is_running or not st.session_state.tickets, type="primary")

# Main Dashboard
st.title("🤖 Tixora-AI Dashboard")
st.markdown("### Tixora-AI Reasoning & Resolution Engine")

# Top Metrics Row
cols = st.columns(4)
total_tickets = len(st.session_state.tickets)
processed = len([r for r in st.session_state.results if r.get('status') != 'running'])
successes = len([r for r in st.session_state.results if r.get('status') == 'success' and "escalate" not in str(r.get('decision')).lower()])
escalations = len([r for r in st.session_state.results if "escalate" in str(r.get('decision')).lower() or r.get('status') == 'escalated'])

with cols[0]:
    st.metric("Total Tickets", total_tickets)
with cols[1]:
    st.metric("Processed", processed)
with cols[2]:
    st.metric("Success Rate", f"{(successes/processed*100):.1f}%" if processed > 0 else "0.0%")
with cols[3]:
    st.metric("Escalations", escalations)

st.divider()

# Progress and Live View Area
if st.session_state.is_running:
    st.info("Agent is currently thinking... 🧠")
    progress_bar = st.progress(0)
    status_text = st.empty()

# Ticket Resolution View
tab1, tab2 = st.tabs(["📋 Live Resolution View", "📊 Audit Log Inspector"])

with tab1:
    if not st.session_state.results:
        st.write("No tickets processed yet. Load tickets and click 'Process Tickets' to start.")
    else:
        # Display Results in reverse chronological order
        for res in reversed(st.session_state.results):
            ticket_id = res.get('ticket_id')
            status = res.get('status', 'running')
            decision = res.get('decision', 'Thinking...')
            confidence = res.get('confidence', 0.0)
            
            # Determine Color/Badge
            if "escalate" in str(decision).lower():
                header_text = f"🚨 {ticket_id} | Escalated"
                color_type = "status-escalated"
            elif status == "success":
                header_text = f"✅ {ticket_id} | Resolved"
                color_type = "status-success"
            else:
                header_text = f"⏳ {ticket_id} | Processing..."
                color_type = "status-running"

            with st.expander(header_text):
                info_cols = st.columns([2, 1])
                with info_cols[0]:
                    st.write(f"**Final Decision:** `{decision}`")
                with info_cols[1]:
                    st.write(f"**Confidence:** `{confidence:.2f}`")
                
                # Reasoning Chain Table
                if res.get('reasoning_chain'):
                    st.markdown("**Reasoning Chain:**")
                    chain_df = pd.DataFrame(res['reasoning_chain'])
                    # Clean up for display
                    if not chain_df.empty:
                        # Select relevant columns for display
                        display_cols = ['step', 'thought', 'action', 'params', 'status']
                        available_cols = [c for c in display_cols if c in chain_df.columns]
                        st.table(chain_df[available_cols])
                
                if res.get('error'):
                    st.error(f"Error: {res['error']}")

with tab2:
    if st.session_state.results:
        st.json(st.session_state.results)
    else:
        st.write("Audit log will appear after processing.")

# Async Processing Logic
async def run_batch():
    st.session_state.is_running = True
    st.session_state.results = [] # Clear old results for demo
    
    tickets_to_process = st.session_state.tickets
    semaphore = asyncio.Semaphore(concurrency)
    
    # We want to update the UI as they complete
    tasks = [process_ticket(t, semaphore) for t in tickets_to_process]
    
    completed = 0
    for task in asyncio.as_completed(tasks):
        result = await task
        st.session_state.results.append(result)
        completed += 1
        
        # Explicit UI updates
        # st.rerun() # In Streamlit, this restarts the script, so we use it sparingly or handle state carefully
        # However, for live updates inside a loop, we can't easily 'rerun' without losing loop context 
        # unless we find a better way. Modern Streamlit supports containers.
        
    st.session_state.is_running = False
    st.rerun()

if process_btn:
    asyncio.run(run_batch())
