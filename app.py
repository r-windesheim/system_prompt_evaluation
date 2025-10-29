"""
Streamlit UI for Prompt Testing Tool - Clean Version

A web interface for exploring cached prompt evaluation results.
"""
import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from evaluation import PromptEvaluator
from loguru import logger
from utils.ui_helpers import (
    extract_dimension_scores, create_radar_chart, create_bar_chart,
    create_response_metrics_charts, extract_response_metrics_summary,
    extract_question_asking_metrics, create_question_asking_chart,
    create_section_impact_heatmap
)
from config import (
    DEFAULT_MODEL, DEFAULT_MAX_CONCURRENT,
    DEFAULT_PROMPT_SECTIONS, EVALUATION_DIMENSIONS,
    QUERY_COUNT_OPTIONS, DEFAULT_QUERY_COUNT_INDEX,
    APP_LOG_FILE, LOG_ROTATION_SIZE, LOG_RETENTION_DAYS, LOG_FORMAT,
    get_rating_from_score, get_rating_style, calculate_evaluation_cost,
    HAS_AMBIGUOUS_QUERIES
)

# Import ambiguous queries if available
if HAS_AMBIGUOUS_QUERIES:
    try:
        from ambiguous_test_queries import AMBIGUOUS_TEST_QUERIES
    except ImportError:
        HAS_AMBIGUOUS_QUERIES = False
        AMBIGUOUS_TEST_QUERIES = []
else:
    AMBIGUOUS_TEST_QUERIES = []
import asyncio
import nest_asyncio

# Apply nest_asyncio to allow nested event loops (fixes anyio deadlock)
nest_asyncio.apply()

load_dotenv()
print(f"API Key loaded: {os.getenv('OPENROUTER_API_KEY') is not None}")
try:
    from utils.prompt_analyzer import decompose_system_prompt
except ImportError:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
    from prompt_analyzer import decompose_system_prompt

st.set_page_config(
    page_title="Prompt Testing Tool",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    .stApp {
        background-color: #0a0a0a;
        color: #fafafa;
        font-family: 'Inter', sans-serif;
    }
    
    .css-1d391kg, .css-1cypcdb {
        background-color: #18181b !important;
        border-right: 1px solid #27272a !important;
    }
    
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    h1 {
        color: #fafafa !important;
        font-weight: 700 !important;
        font-size: 2rem !important;
        margin-bottom: 1rem !important;
    }
    
    .css-1d391kg h2, .css-1cypcdb h2 {
        color: #fafafa !important;
        font-weight: 600 !important;
        font-size: 1.125rem !important;
    }
    
    .stCheckbox > label {
        color: #d4d4d8 !important;
        font-size: 0.875rem !important;
        line-height: 1.5 !important;
    }
    
    [data-testid="metric-container"] {
        display: none;
    }
    
    .stSuccess {
        background-color: rgba(5, 46, 22, 0.2) !important;
        border: 1px solid rgba(34, 197, 94, 0.3) !important;
        color: #4ade80 !important;
        border-radius: 12px !important;
    }
    
    .stWarning {
        background-color: rgba(69, 26, 3, 0.2) !important;
        border: 1px solid rgba(251, 146, 60, 0.3) !important;
        color: #fb923c !important;
        border-radius: 12px !important;
    }
    
    .stInfo {
        background-color: rgba(5, 46, 22, 0.2) !important;
        border: 1px solid rgba(34, 197, 94, 0.3) !important;
        color: #4ade80 !important;
        border-radius: 12px !important;
    }
    
    .stSelectbox > div > div {
        background-color: #27272a !important;
        border-color: #3f3f46 !important;
        color: #fafafa !important;
    }
    
    .css-1y4p8pa {
        padding-top: 1rem;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .stSelectbox input {
        caret-color: transparent !important;
        cursor: pointer !important;
    }
    
    .stSelectbox input:focus {
        caret-color: transparent !important;
        outline: none !important;
    }
    
    hr {
        display: none !important;
    }
    
    .stMarkdown hr {
        display: none !important;
    }
    
    .element-container:has(hr) {
        display: none !important;
    }
    
    .stColumns > div:first-child > div > div:empty {
        display: none !important;
    }
    
    div[data-testid="stMarkdownContainer"] > div:empty {
        display: none !important;
    }
    
    div[style*="background: rgba(39, 39, 42, 0.5)"]:empty {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# Configure logging - remove default stderr handler
logger.remove()  # Remove default handler that prints to stderr
logger.add(APP_LOG_FILE, rotation=LOG_ROTATION_SIZE, retention=LOG_RETENTION_DAYS, format=LOG_FORMAT)


@st.cache_data
def load_cached_results(use_original_dataset=False):
    """Load cached evaluation results with caching for performance"""
    evaluator = PromptEvaluator()
    try:
        if use_original_dataset:
            # Load the original large dataset for default sections
            df = evaluator.load_cached_results("cached_results/full_evaluation_backup.csv")
            logger.info(f"Loaded {len(df)} original cached results")
        else:
            # Load current results (custom evaluations)
            df = evaluator.load_cached_results()
            logger.info(f"Loaded {len(df)} current cached results")
        return df
    except Exception as e:
        logger.error(f"Failed to load cached results: {e}")
        return pd.DataFrame()


def render_metric_card(dimension: str, score: float):
    """Render a single metric card"""
    # Use centralized rating functions from config
    rating, color = get_rating_from_score(score)
    style = get_rating_style(score)
    bg_gradient = style['gradient']
    border_color = style['border_color']
    shadow = style['shadow']

    st.markdown(f"""
    <div style="background: {bg_gradient}; border: 1px solid {border_color}; border-radius: 12px;
                padding: 16px 8px; margin-bottom: 16px; height: 140px; display: flex;
                flex-direction: column; justify-content: space-between; box-shadow: {shadow};
                transition: all 0.3s ease; animation: fadeIn 0.5s ease;">
        <h3 style="margin: 0; font-size: 0.65rem; font-weight: 600; color: #a1a1aa;
                   text-align: center; line-height: 1.2; letter-spacing: 0.02em;
                   text-transform: uppercase; word-wrap: break-word; overflow-wrap: break-word;
                   hyphens: auto;">{dimension}</h3>
        <div style="text-align: center; margin: 4px 0; flex-grow: 1; display: flex;
                    align-items: center; justify-content: center;">
            <span style="font-size: 2rem; font-weight: 700; color: #fafafa; line-height: 1;
                         letter-spacing: -0.02em;">{score:.0f}</span>
        </div>
        <div style="display: flex; align-items: center; justify-content: center; gap: 4px;
                    padding: 4px 8px; background: rgba(0, 0, 0, 0.2); border-radius: 6px;
                    min-height: 24px;">
            <svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24"
                 style="color: {color}; flex-shrink: 0;" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 10l7-7m0 0l7 7m-7-7v18"/>
            </svg>
            <span style="font-size: 0.7rem; font-weight: 600; color: {color};
                         letter-spacing: 0.01em; white-space: nowrap;">{rating}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def main():
    """Main Streamlit application"""
    st.title("Prompt Testing Tool")
    
    # Determine which dataset to load based on whether we have custom sections
    if 'custom_sections' not in st.session_state:
        st.session_state.custom_sections = []
    
    # Load appropriate dataset based on current toggle state
    if 'use_default_sections' not in st.session_state:
        st.session_state.use_default_sections = not bool(st.session_state.custom_sections)
    
    # Detect if custom results exist
    has_custom_results = False
    if os.path.exists("cached_results/batch_evaluation.csv") and os.path.exists("cached_results/full_evaluation_backup.csv"):
        try:
            import pandas as pd
            batch_df = pd.read_csv("cached_results/batch_evaluation.csv")
            backup_df = pd.read_csv("cached_results/full_evaluation_backup.csv")
            has_custom_results = len(batch_df) != len(backup_df) or \
                               batch_df['system_prompt'].nunique() != backup_df['system_prompt'].nunique()
        except:
            has_custom_results = False
    
    # Determine which dataset to load
    if (st.session_state.custom_sections or has_custom_results) and not st.session_state.use_default_sections:
        # Load custom evaluation results when using custom sections
        results_df = load_cached_results(use_original_dataset=False)
    else:
        # Load default evaluation results when using default sections or no custom sections exist
        results_df = load_cached_results(use_original_dataset=True)
    
    # Sidebar
    with st.sidebar:
        # Header
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;">
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="color: #71717a;">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
            <h2 style="margin: 0; font-size: 1.125rem; font-weight: 600; color: #fafafa;">Prompt Builder</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Simple toggle with tabs approach
        st.markdown("**MODE**")
        
        # Create two columns for toggle buttons
        col1, col2 = st.columns(2)
        
        # Initialize mode if not set
        if 'interface_mode' not in st.session_state:
            st.session_state.interface_mode = "Toggleable Sections"
        
        # Custom CSS for better button styling with clear active state
        st.markdown("""
        <style>
        /* Secondary (inactive) buttons */
        .stButton > button[kind="secondary"] {
            width: 100%;
            border-radius: 6px;
            border: 1px solid #404040;
            background-color: #2d2d2d;
            color: #888;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        .stButton > button[kind="secondary"]:hover {
            background-color: #3d3d3d;
            border-color: #505050;
            color: #aaa;
        }
        
        /* Primary (active) buttons */
        .stButton > button[kind="primary"] {
            width: 100%;
            border-radius: 6px;
            border: 1px solid #3b82f6;
            background-color: #3b82f6;
            color: white;
            font-weight: 600;
            transition: all 0.2s ease;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: #2563eb;
            border-color: #2563eb;
        }
        </style>
        """, unsafe_allow_html=True)
        
        with col1:
            if st.button(
                "Toggleable Sections",
                key="btn_default",
                use_container_width=True,
                type="primary" if st.session_state.interface_mode == "Toggleable Sections" else "secondary"
            ):
                st.session_state.interface_mode = "Toggleable Sections"
                st.rerun()
        
        with col2:
            if st.button(
                "Custom Analyzer", 
                key="btn_custom",
                use_container_width=True,
                type="primary" if st.session_state.interface_mode == "Custom Prompt Analyzer" else "secondary"
            ):
                st.session_state.interface_mode = "Custom Prompt Analyzer"
                st.rerun()
        
        mode = st.session_state.interface_mode
        
        st.markdown("<hr style='border: 1px solid #27272a; margin: 16px 0;'>", unsafe_allow_html=True)
        
        if 'custom_sections' not in st.session_state:
            st.session_state.custom_sections = []
        if 'analysis_result' not in st.session_state:
            st.session_state.analysis_result = None
        if 'use_custom_sections' not in st.session_state:
            st.session_state.use_custom_sections = False

        if mode == "Toggleable Sections":
            # Default interface - show custom sections if available, otherwise pre-built sections
            if not results_df.empty and 'system_prompt' in results_df.columns:
                # Initialize section source toggle if we have custom sections
                if 'use_default_sections' not in st.session_state:
                    st.session_state.use_default_sections = not bool(st.session_state.custom_sections)
                
                # Check if we have custom sections from a previous analysis OR custom evaluation results
                # Custom results exist if batch_evaluation.csv has different content than full_evaluation_backup.csv
                has_custom_results = False
                if os.path.exists("cached_results/batch_evaluation.csv") and os.path.exists("cached_results/full_evaluation_backup.csv"):
                    import pandas as pd
                    try:
                        batch_df = pd.read_csv("cached_results/batch_evaluation.csv")
                        backup_df = pd.read_csv("cached_results/full_evaluation_backup.csv")
                        # If they have different row counts or different unique prompts, we have custom results
                        has_custom_results = len(batch_df) != len(backup_df) or \
                                           batch_df['system_prompt'].nunique() != backup_df['system_prompt'].nunique()
                        
                        # If we have custom results but no custom sections in session state, extract them from the data
                        if has_custom_results and not st.session_state.custom_sections:
                            # Get unique system prompts from custom results that aren't in default results
                            custom_prompts = set(batch_df['system_prompt'].unique())
                            default_prompts = set(backup_df['system_prompt'].unique())
                            unique_custom_prompts = custom_prompts - default_prompts
                            
                            if unique_custom_prompts:
                                # Find the prompt with the most sections (prefer 6 sections if available)
                                best_prompt = None
                                max_sections = 0
                                
                                for prompt in unique_custom_prompts:
                                    sections = [section.strip() for section in prompt.split('\n\n') if section.strip()]
                                    if len(sections) > max_sections:
                                        max_sections = len(sections)
                                        best_prompt = prompt
                                
                                if best_prompt:
                                    sections = [section.strip() for section in best_prompt.split('\n\n') if section.strip()]
                                    # Remove duplicate sections while preserving order
                                    unique_sections = []
                                    seen = set()
                                    for section in sections:
                                        if section not in seen:
                                            unique_sections.append(section)
                                            seen.add(section)
                                    if unique_sections and len(unique_sections) > 1:  # Only if we have multiple sections
                                        st.session_state.custom_sections = unique_sections
                    except:
                        has_custom_results = False
                
                if st.session_state.custom_sections or has_custom_results:
                    # Show toggle to switch between default and custom sections
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        if st.session_state.use_default_sections:
                            st.markdown("**Default Prompt Sections:**")
                            st.caption("Pre-built sections for testing. Toggle to switch to your custom analyzed sections.")
                        else:
                            st.markdown("**Custom Analyzed Sections:**")
                            st.caption("Sections extracted from your analyzed prompt. Toggle to switch to default sections.")
                    with col2:
                        if st.session_state.use_default_sections:
                            if st.button("Use Custom", key="toggle_sections", help="Switch to your custom analyzed sections"):
                                st.session_state.use_default_sections = False
                                st.rerun()
                        else:
                            if st.button("Use Default", key="toggle_sections", help="Switch to pre-built default sections"):
                                st.session_state.use_default_sections = True
                                st.rerun()
                    
                    # Set sections based on toggle
                    if st.session_state.use_default_sections:
                        sections_to_use = DEFAULT_PROMPT_SECTIONS
                    else:
                        sections_to_use = st.session_state.custom_sections
                else:
                    sections_to_use = DEFAULT_PROMPT_SECTIONS
                    st.markdown("**Default Prompt Sections:**")
                    st.caption("Pre-built sections for testing. Switch to Custom Analyzer mode to analyze your own prompt.")
                
                # Simple toggle logic for all sections
                selected_sections = []
                for i, section in enumerate(sections_to_use):
                    key = f"section_{i}"
                    is_selected = st.checkbox(section, value=True, key=key)
                    if is_selected:
                        selected_sections.append(section)

                # Simple join with \n\n
                current_prompt_text = '\n\n'.join(selected_sections) if selected_sections else None
                current_combination = current_prompt_text

                if current_combination:

                    # Show config match indicator if metadata is available
                    if 'config_name' in results_df.columns and results_df['config_name'].notna().any():
                        matching_configs = results_df[results_df['system_prompt'] == current_prompt_text]['config_name'].unique()
                        if len(matching_configs) > 0 and matching_configs[0]:
                            st.caption(f"✓ Tested config: **{matching_configs[0]}**")
                        else:
                            st.caption("⚠️ No exact match in tested configs")

                        # Show collapsible list of all tested configurations
                        with st.expander("📋 View All Tested Configs", expanded=False):
                            unique_configs = sorted([c for c in results_df['config_name'].unique() if c])
                            st.caption(f"Total configurations tested: {len(unique_configs)}")
                            for config in unique_configs:
                                count = len(results_df[results_df['config_name'] == config])
                                st.text(f"  {config} ({count} evaluations)")
                else:
                    current_combination = None
            else:
                st.info("No cached data available. Run a batch evaluation first.")
                selected_sections = []
                current_combination = None
        
        
        elif mode == "Custom Prompt Analyzer":
            # Custom prompt analyzer interface
            st.markdown("**Custom Prompt Analysis:**")
            
            custom_prompt = st.text_area(
                "Paste your system prompt here:",
                height=150,
                placeholder="Paste a system prompt to analyze and test...",
                key="custom_prompt_input"
            )
            
            # Analysis mode toggle
            exclude_factual = st.checkbox(
                "Behavioral instructions only (exclude factual content)",
                value=True,
                help="If checked, only extracts behavioral instructions. If unchecked, decomposes ALL content into sections."
            )
        
            if st.button("Analyze Prompt", disabled=not custom_prompt.strip()):
                if custom_prompt.strip():
                    # Clear previous evaluation state when analyzing new prompt
                    for key in list(st.session_state.keys()):
                        if 'eval' in key.lower():
                            del st.session_state[key]
                    
                    with st.spinner("Analyzing prompt..."):
                        try:
                            result = asyncio.run(decompose_system_prompt(custom_prompt.strip(), exclude_factual=exclude_factual))
                            st.session_state.analysis_result = result
                            if result['success']:
                                st.session_state.custom_sections = result['sections']
                                st.session_state.use_custom_sections = True
                                st.success(f"Analyzed into {len(result['sections'])} sections")
                            else:
                                st.error(f"Analysis failed: {result['analysis']}")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
            
            # Display analysis results
            if st.session_state.analysis_result and st.session_state.analysis_result['success']:
                # Display extracted sections
                st.markdown("**Extracted Sections:**")
                for i, section in enumerate(st.session_state.analysis_result['sections'], 1):
                    st.markdown(f"**{i}.** {section}")
                
                # Toggle to use custom sections
                use_custom = st.checkbox(
                    "Use these sections for evaluation", 
                    value=st.session_state.use_custom_sections,
                    key="use_custom_toggle"
                )
                st.session_state.use_custom_sections = use_custom
                
                # Run evaluation button
                if st.button("Run Evaluation on These Sections", type="primary"):
                    st.session_state.show_eval_config = True

                # Quirk analysis button
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🔍 Analyze Behavioral Quirks", help="Detect emergent behavioral patterns in responses"):
                    st.session_state.show_quirk_config = True

            # Set variables for main interface
            selected_sections = st.session_state.custom_sections if st.session_state.use_custom_sections else []
            current_combination = '\n\n'.join(selected_sections) if selected_sections else None
        
        st.markdown("<hr style='border: 1px solid #27272a; margin: 24px 0;'>", unsafe_allow_html=True)
        
        # Options
        st.markdown("""
        <div style="margin-top: 24px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                <div style="width: 4px; height: 4px; border-radius: 50%; background-color: #6366f1;"></div>
                <span style="font-size: 0.75rem; font-weight: 500; color: #71717a; text-transform: uppercase; letter-spacing: 0.05em;">Options</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        show_raw_data = st.checkbox("Show Raw Data", value=False)
        
        # Status
        st.markdown("""
        <div style="margin-top: 24px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                <div style="width: 4px; height: 4px; border-radius: 50%; background-color: #22c55e;"></div>
                <span style="font-size: 0.75rem; font-weight: 500; color: #71717a; text-transform: uppercase; letter-spacing: 0.05em;">Status</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if os.path.exists("cached_results/"):
            # Determine which dataset is being used
            dataset_info = ""
            if st.session_state.custom_sections and not st.session_state.use_default_sections:
                dataset_info = " (Custom)"
            elif st.session_state.custom_sections and st.session_state.use_default_sections:
                dataset_info = " (Default)"
            
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 8px; padding: 12px 16px; background-color: rgba(5, 46, 22, 0.3); border: 1px solid rgba(34, 197, 94, 0.5); border-radius: 8px;">
                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="color: #22c55e;">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
                <span style="font-size: 0.875rem; color: #4ade80; font-weight: 500;">Data loaded{dataset_info}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; padding: 12px 16px; background-color: rgba(69, 26, 3, 0.3); border: 1px solid rgba(251, 146, 60, 0.5); border-radius: 8px;">
                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="color: #f59e0b;">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
                <span style="font-size: 0.875rem; color: #fb923c; font-weight: 500;">No data</span>
            </div>
            """, unsafe_allow_html=True)
    
    # Main content
    if results_df.empty:
        st.info("""
        **No evaluation results found.**
        
        To get started:
        1. Set up your `.env` file with `OPENROUTER_API_KEY`
        2. Run a batch evaluation using `evaluation.py`
        3. Results will appear here automatically
        
        The cached results will enable instant exploration of prompt effectiveness patterns.
        """)
        return
    
    # Filter data
    filtered_df = results_df
    if current_combination is not None:
        current_prompt_text = current_combination
        filtered_df = results_df[results_df['system_prompt'] == current_prompt_text]
        if filtered_df.empty:
            filtered_df = results_df
    
    # Status banner
    if current_combination is not None:
        current_prompt_text = current_combination
        matching_df = results_df[results_df['system_prompt'] == current_prompt_text]
        if not matching_df.empty:
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 8px; padding: 12px 16px; background-color: rgba(5, 46, 22, 0.3); border: 1px solid rgba(34, 197, 94, 0.5); border-radius: 8px; margin-bottom: 24px;">
                <div style="width: 6px; height: 6px; border-radius: 50%; background-color: #22c55e; animation: pulse 2s infinite;"></div>
                <span style="font-size: 0.875rem; font-weight: 500; color: #4ade80;">Analyzing {len(matching_df)} evaluations for your prompt selection</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 8px; padding: 12px 16px; background-color: rgba(69, 26, 3, 0.3); border: 1px solid rgba(251, 146, 60, 0.5); border-radius: 8px; margin-bottom: 24px;">
                <div style="width: 6px; height: 6px; border-radius: 50%; background-color: #f59e0b;"></div>
                <span style="font-size: 0.875rem; font-weight: 500; color: #fb923c;">No data for this combination. Showing all {len(results_df)} results.</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 8px; padding: 12px 16px; background-color: rgba(5, 46, 22, 0.3); border: 1px solid rgba(34, 197, 94, 0.5); border-radius: 8px; margin-bottom: 24px;">
            <div style="width: 6px; height: 6px; border-radius: 50%; background-color: #22c55e;"></div>
            <span style="font-size: 0.875rem; font-weight: 500; color: #4ade80;">Showing all {len(results_df)} evaluation results</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Calculate and display metrics
    if 'evaluation_question' in filtered_df.columns and 'evaluation_score' in filtered_df.columns and len(filtered_df) > 0:
        avg_scores = extract_dimension_scores(filtered_df)

        if any(v > 0 for v in avg_scores.values()):
            # Metric cards in fixed order (use centralized dimension list)
            cols = st.columns(6)

            for i, dim in enumerate(EVALUATION_DIMENSIONS):
                with cols[i]:
                    score = avg_scores.get(dim, 0)
                    render_metric_card(dim, score)

            # Charts
            st.markdown("""
            <div style="background: rgba(39, 39, 42, 0.5); border: 1px solid #27272a; border-radius: 12px; padding: 24px; margin-top: 32px;">
            """, unsafe_allow_html=True)

            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("""
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;">
                    <div style="width: 4px; height: 4px; border-radius: 50%; background-color: #3b82f6;"></div>
                    <span style="font-size: 0.875rem; font-weight: 500; color: #d4d4d8;">Chart Type</span>
                </div>
                """, unsafe_allow_html=True)
                chart_type = st.selectbox("", ["Bar Chart", "Radar Chart", "Section Impact Heatmap"], key="chart_type", label_visibility="collapsed")

            # Get full prompt comparison data if available (for charts)
            full_avg_scores = None
            baseline_label = None
            if not results_df.empty:
                unique_prompts = results_df['system_prompt'].unique()
                full_prompt = max(unique_prompts, key=len) if unique_prompts.size > 0 else None
                if full_prompt:
                    full_prompt_df = results_df[results_df['system_prompt'] == full_prompt]
                    if not full_prompt_df.empty:
                        full_avg_scores = extract_dimension_scores(full_prompt_df)

                        # Get baseline config name if metadata is available
                        if 'config_name' in full_prompt_df.columns and full_prompt_df['config_name'].notna().any():
                            config_names = full_prompt_df['config_name'].unique()
                            if len(config_names) > 0 and config_names[0]:
                                baseline_label = config_names[0]

            # Create and display chart based on selection
            if chart_type == "Section Impact Heatmap":
                # Get sections for heatmap (use custom sections if available, otherwise default)
                if st.session_state.custom_sections and not st.session_state.use_default_sections:
                    heatmap_sections = st.session_state.custom_sections
                else:
                    heatmap_sections = DEFAULT_PROMPT_SECTIONS

                fig = create_section_impact_heatmap(results_df, heatmap_sections)
            elif chart_type == "Radar Chart":
                fig = create_radar_chart(avg_scores, full_avg_scores, baseline_label)
            else:
                fig = create_bar_chart(avg_scores, full_avg_scores, baseline_label)

            st.plotly_chart(fig, use_container_width=True)
            
            # Missing dimensions info
            missing_dims = [dim for dim in EVALUATION_DIMENSIONS if avg_scores[dim] == 0]
            if missing_dims:
                st.caption(f"Missing data for: {', '.join(missing_dims)}")
            
            st.markdown("</div>", unsafe_allow_html=True)

            # Question-Asking Behavior Section
            st.markdown("---")
            st.markdown("### Question-Asking Behavior")

            # Get question-asking metrics
            qa_metrics = extract_question_asking_metrics(filtered_df)

            # Get baseline question-asking metrics (full prompt with all sections)
            qa_baseline_metrics = None
            if not results_df.empty:
                unique_prompts = results_df['system_prompt'].unique()
                full_prompt = max(unique_prompts, key=len) if unique_prompts.size > 0 else None
                if full_prompt:
                    full_prompt_df = results_df[results_df['system_prompt'] == full_prompt]
                    if not full_prompt_df.empty:
                        qa_baseline_metrics = extract_question_asking_metrics(full_prompt_df)

            # Calculate deltas
            score_delta = None
            asks_delta = None
            assumes_delta = None
            neutral_delta = None

            if qa_baseline_metrics:
                score_delta = qa_metrics['avg_question_asking_score'] - qa_baseline_metrics['avg_question_asking_score']
                asks_delta = qa_metrics['asks_percentage'] - qa_baseline_metrics['asks_percentage']
                assumes_delta = qa_metrics['assumes_percentage'] - qa_baseline_metrics['assumes_percentage']
                neutral_delta = qa_metrics['neutral_percentage'] - qa_baseline_metrics['neutral_percentage']

            # Display metrics in columns
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    label="Question-Asking Score",
                    value=f"{qa_metrics['avg_question_asking_score']:.0f}/100",
                    delta=f"{score_delta:+.1f}" if score_delta is not None and abs(score_delta) >= 0.5 else None,
                    help="Score measuring how often the AI asks clarifying questions (0-100)"
                )

            with col2:
                st.metric(
                    label="Asks Questions",
                    value=f"{qa_metrics['asks_percentage']:.1f}%",
                    delta=f"{asks_delta:+.1f}%" if asks_delta is not None and abs(asks_delta) >= 0.5 else None,
                    help="Percentage of responses that ask clarifying questions"
                )

            with col3:
                st.metric(
                    label="Makes Assumptions",
                    value=f"{qa_metrics['assumes_percentage']:.1f}%",
                    delta=f"{assumes_delta:+.1f}%" if assumes_delta is not None and abs(assumes_delta) >= 0.5 else None,
                    delta_color="inverse",  # Red for increases in assumptions (bad)
                    help="Percentage of responses that make assumptions"
                )

            with col4:
                st.metric(
                    label="Neutral",
                    value=f"{qa_metrics['neutral_percentage']:.1f}%",
                    delta=f"{neutral_delta:+.1f}%" if neutral_delta is not None and abs(neutral_delta) >= 0.5 else None,
                    delta_color="off",  # Neutral color for this metric
                    help="Percentage of responses that neither ask nor assume"
                )

            # Display question-asking chart
            if len(filtered_df) > 0:
                qa_chart = create_question_asking_chart(filtered_df, results_df)
                st.plotly_chart(qa_chart, use_container_width=True)

            # Response Characteristics Section
            st.markdown("---")
            st.markdown("### Response Characteristics")

            # Get response metrics summary
            metrics_summary = extract_response_metrics_summary(filtered_df)

            # Display metrics in columns
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    label="Average Word Count",
                    value=f"{metrics_summary['avg_word_count']:.0f}",
                    help="Average number of words per response"
                )

            with col2:
                st.metric(
                    label="Readability Score",
                    value=f"{metrics_summary['avg_readability']:.1f}",
                    help="Flesch Reading Ease (0-100, higher = easier to read)"
                )

            with col3:
                st.metric(
                    label="Grade Level",
                    value=f"{metrics_summary['avg_grade_level']:.1f}",
                    help="Flesch-Kincaid Grade Level (reading difficulty)"
                )

            # Create and display response metrics charts
            if len(filtered_df) > 0:
                word_chart, readability_chart = create_response_metrics_charts(filtered_df, results_df)

                col1, col2 = st.columns(2)
                with col1:
                    st.plotly_chart(word_chart, use_container_width=True)

                with col2:
                    st.plotly_chart(readability_chart, use_container_width=True)
        else:
            st.info("No evaluation data available")
    
    # Raw data
    if show_raw_data:
        st.subheader("Raw Data")
        st.dataframe(filtered_df, use_container_width=True)
    
    # Bottom caption
    if current_combination is not None:
        current_prompt_text = current_combination
        matching_df = results_df[results_df['system_prompt'] == current_prompt_text]
        if not matching_df.empty:
            st.caption(f"Showing {len(matching_df)} results for current prompt selection")
        else:
            st.caption(f"No results for this combination. Showing all {len(results_df)} results.")
    else:
        st.caption(f"Showing all {len(results_df)} evaluation results")


# Evaluation Configuration Modal
if 'show_eval_config' not in st.session_state:
    st.session_state.show_eval_config = False

if st.session_state.show_eval_config:
    st.markdown("---")
    st.markdown("### Run Evaluation Configuration")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Evaluation Type:**")
        eval_type = st.radio(
            "Choose evaluation method:",
            ["Y/N Questions (Binary Scoring)", "0-100 Scoring (Granular Scoring)"],
            key="eval_type_radio"
        )

        use_yn = eval_type.startswith("Y/N")

        if use_yn:
            st.info("6 Y/N questions - Binary scoring (0 or 100)")
        else:
            st.info("6 scoring dimensions with 0-100 scale")

        # Query set selection
        if HAS_AMBIGUOUS_QUERIES:
            st.markdown("**Test Query Set:**")
            query_set = st.radio(
                "Choose query type:",
                ["Standard Queries (Diverse scenarios)", "Ambiguous Queries (Question-asking behavior)"],
                key="query_set_radio"
            )
            use_ambiguous = query_set.startswith("Ambiguous")

            if use_ambiguous:
                st.info("30 ambiguous queries to test question-asking behavior")
            else:
                st.info("Diverse scenarios and edge cases")
        else:
            use_ambiguous = False

    with col2:
        st.markdown("**Number of Test Queries:**")
        num_queries = st.selectbox(
            "How many test queries to run:",
            QUERY_COUNT_OPTIONS,
            index=DEFAULT_QUERY_COUNT_INDEX,
            key="num_queries_select"
        )

        # Show concurrency info
        st.info(f"ℹ️ Concurrency: {DEFAULT_MAX_CONCURRENT} simultaneous API requests")

        # Cost estimation
        if st.session_state.custom_sections:
            from itertools import combinations
            n_sections = len(st.session_state.custom_sections)
            n_combinations = sum(1 for r in range(1, n_sections + 1)
                               for combo in combinations(range(n_sections), r))
            n_questions = 6
            total_calls = n_combinations * num_queries * n_questions * 2
            estimated_cost = calculate_evaluation_cost(n_combinations, num_queries, n_questions)

            st.info(f"Estimated cost: ~${estimated_cost:.3f}")
            st.caption(f"~{total_calls} API calls | {n_combinations} combinations")
    
    col3, col4, col5 = st.columns([1, 1, 1])
    
    with col3:
        if st.button("Cancel", key="cancel_eval"):
            st.session_state.show_eval_config = False
            st.rerun()
    
    with col5:
        if st.button("Start Evaluation", type="primary", key="start_eval"):
            if st.session_state.get('evaluation_complete', False):
                # Clear the completion flag and allow new evaluation
                st.session_state.evaluation_complete = False
                st.info("Starting new evaluation...")

            if st.session_state.custom_sections:
                st.session_state.eval_running = True
                eval_config = {
                    'sections': st.session_state.custom_sections,
                    'use_yn': use_yn,
                    'num_queries': num_queries
                }
                # Add ambiguous query flag if available
                if HAS_AMBIGUOUS_QUERIES:
                    eval_config['use_ambiguous'] = use_ambiguous
                st.session_state.eval_config = eval_config
                st.session_state.show_eval_config = False
                st.rerun()
            else:
                st.error("No custom sections available to evaluate!")

# Run Evaluation
if 'eval_running' not in st.session_state:
    st.session_state.eval_running = False

if st.session_state.eval_running and not st.session_state.get('evaluation_complete', False):
    st.markdown("---")
    st.markdown("### Running Evaluation...")

    progress_bar = st.progress(0)
    status_text = st.empty()

    # Add cancel button
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("❌ Cancel Evaluation", key="cancel_running_eval", type="secondary"):
            # Clear evaluation state
            st.session_state.eval_running = False
            if 'eval_config' in st.session_state:
                del st.session_state['eval_config']
            st.warning("Evaluation cancelled. Note: API calls already in progress cannot be stopped.")
            st.rerun()

    # Define helper function
    def update_status(msg):
        status_text.text(msg)

    # Import evaluation system
    try:
        from evaluation import PromptEvaluator
        from run_evaluation import all_test_queries, yn_evaluation_questions, detailed_evaluation_questions
        import pandas as pd

        # Get evaluation config
        config = st.session_state.eval_config
        sections = config['sections']
        use_yn = config['use_yn']
        num_queries = config['num_queries']
        use_ambiguous = config.get('use_ambiguous', False)

        # Get test queries based on query set selection
        if use_ambiguous and HAS_AMBIGUOUS_QUERIES:
            queries_to_use = AMBIGUOUS_TEST_QUERIES
            update_status(f"Using ambiguous queries for question-asking behavior testing")
        else:
            queries_to_use = all_test_queries
            update_status(f"Using standard query set")

        test_queries = queries_to_use[:num_queries]

        if use_yn:
            evaluation_questions = yn_evaluation_questions
        else:
            evaluation_questions = detailed_evaluation_questions

        update_status(f"Using {len(test_queries)} test queries and {len(evaluation_questions)} evaluation questions")
        progress_bar.progress(10)
        
        # Initialize evaluator with concurrent request limit
        evaluator = PromptEvaluator(model_name=DEFAULT_MODEL, max_concurrent=DEFAULT_MAX_CONCURRENT)
        
        # Run the existing batch evaluation method
        update_status("Starting batch evaluation...")
        progress_bar.progress(20)
        
        result_df = asyncio.run(evaluator.run_batch_evaluation(
            prompt_sections=sections,
            test_queries=test_queries,
            evaluation_questions=evaluation_questions
        ))
        
        # Create additional backup with custom run type for UI evaluations
        if st.session_state.custom_sections:
            evaluator.create_evaluation_backup(result_df, "custom_prompt_ui")
        else:
            evaluator.create_evaluation_backup(result_df, "default_sections_ui")
        
        progress_bar.progress(100)
        update_status("Evaluation completed!")
        
        # Create result summary
        successful_results = len(result_df[~result_df.get('success', pd.Series([True]*len(result_df))).isna()])
        failed_results = len(result_df) - successful_results
        
        # Calculate combinations tested
        from itertools import combinations
        n_sections = len(sections)
        n_combinations = sum(1 for r in range(1, n_sections + 1) 
                           for combo in combinations(range(n_sections), r))
        
        result = {
            'success': True,
            'total_evaluations': len(result_df),
            'successful_evaluations': successful_results,
            'failed_evaluations': failed_results,
            'combinations_tested': n_combinations,
            'results_saved_to': 'batch_evaluation.csv',
            'evaluation_type': 'Y/N Questions' if use_yn else '0-100 Scoring'
        }
        
        if result['success']:
            st.success(f"""Evaluation completed successfully!
            
**Results:**
- Total evaluations: {result['total_evaluations']}
- Successful: {result['successful_evaluations']}
- Failed: {result['failed_evaluations']}
- Combinations tested: {result['combinations_tested']}
- Evaluation type: {result['evaluation_type']}
- Results saved to: `{result['results_saved_to']}`

**Results are now available! Refresh the page manually to see the charts.**""")
            
            # Immediately clear cache and set completion flag
            load_cached_results.clear()
            st.session_state.evaluation_complete = True
            st.info("Please refresh your browser page (F5 or Ctrl+R) to see the evaluation results in the charts below.")
        else:
            st.error(f"Evaluation failed: {result.get('error', 'Unknown error')}")
            st.session_state.eval_running = False
        
        # Nuclear option - clear ALL eval-related state to prevent any restart
        for key in list(st.session_state.keys()):
            if 'eval' in key.lower() and key != 'evaluation_complete':
                del st.session_state[key]
        
    except Exception as e:
        st.error(f"Evaluation failed: {str(e)}")
        st.session_state.eval_running = False


# Quirk Analysis Configuration Modal
if 'show_quirk_config' not in st.session_state:
    st.session_state.show_quirk_config = False

if st.session_state.show_quirk_config:
    st.markdown("---")
    st.markdown("### Behavioral Quirk Analysis Configuration")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Analysis Settings:**")

        # Simple query input - single query only
        test_query = st.text_area(
            "Enter your test query:",
            value="I'm not sure what to do. Can you help?",
            height=100,
            help="Tip: Use ambiguous or open-ended queries for more quirks",
            key="quirk_test_query"
        )

        # Sensitivity slider
        st.markdown("**Sensitivity (min impact):**")
        min_impact = st.slider(
            "Show quirks with impact greater than:",
            min_value=0.0,
            max_value=2.0,
            value=0.3,
            step=0.1,
            help="Lower = more sensitive (shows smaller effects). Default was 1.0, try 0.3 to see more quirks",
            key="quirk_sensitivity"
        )

        if min_impact < 0.5:
            st.caption("⚠️ Very sensitive - may show minor effects")
        elif min_impact < 1.0:
            st.caption("✓ Moderate sensitivity - balanced view")
        else:
            st.caption("ℹ️ Low sensitivity - only major effects")

        test_queries = [test_query]

        st.info("ℹ️ **How it works:**\n\nGenerates 30 responses for each configuration:\n- Full prompt (all sections)\n- Without section 1\n- Without section 2\n- etc.\n\nCompares with vs without each section to detect which causes which quirk.\n\n**Statistical testing:** With 30 responses per config, you'll get reliable p-values and effect sizes!")

    with col2:
        st.markdown("**Cost Estimation:**")

        # Import cost estimation
        try:
            from utils.quirk_analyzer import estimate_quirk_analysis_cost

            n_sections = len(st.session_state.custom_sections) if st.session_state.custom_sections else 0

            cost_estimate = estimate_quirk_analysis_cost(
                n_sections=n_sections,
                n_responses_per_config=30
            )

            # Single query analysis with 30 responses per config
            total_cost = cost_estimate['total_cost']
            total_responses = cost_estimate['total_responses']

            st.metric("Total Cost", f"${total_cost:.4f}")
            st.caption(f"📈 {total_responses} total responses")
            st.caption(f"🔧 {cost_estimate['total_configs']} configs × 30 responses each")

            st.info(f"**Breakdown:**\n- {n_sections + 1} configs × 30 responses per config\n- ~${cost_estimate['cost_per_response']:.4f} per response")

        except Exception as e:
            st.warning(f"Could not estimate cost: {e}")

    col3, col4, col5 = st.columns([1, 1, 1])

    with col3:
        if st.button("Cancel", key="cancel_quirk"):
            st.session_state.show_quirk_config = False
            st.rerun()

    with col5:
        if st.button("Start Analysis", type="primary", key="start_quirk"):
            # Clear old results before starting new analysis
            if 'quirk_complete' in st.session_state:
                del st.session_state.quirk_complete
            if 'quirk_results' in st.session_state:
                del st.session_state.quirk_results
            if 'quirk_analysis_results' in st.session_state:
                del st.session_state.quirk_analysis_results

            if st.session_state.custom_sections:
                st.session_state.quirk_running = True
                quirk_config = {
                    'sections': st.session_state.custom_sections,
                    'test_query': test_query,
                    'min_impact': min_impact
                }
                st.session_state.quirk_config = quirk_config
                st.session_state.show_quirk_config = False
                st.rerun()
            else:
                st.error("No custom sections available to analyze!")


# Run Quirk Analysis
if 'quirk_running' not in st.session_state:
    st.session_state.quirk_running = False

if st.session_state.quirk_running and not st.session_state.get('quirk_complete', False):
    st.markdown("---")
    st.markdown("### Running Behavioral Quirk Analysis...")

    progress_bar = st.progress(0)
    status_text = st.empty()

    # Add cancel button
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("❌ Cancel Analysis", key="cancel_running_quirk", type="secondary"):
            st.session_state.quirk_running = False
            if 'quirk_config' in st.session_state:
                del st.session_state['quirk_config']
            st.warning("Analysis cancelled. Note: API calls already in progress cannot be stopped.")
            st.rerun()

    # Define helper function
    def update_quirk_status(msg):
        status_text.text(msg)

    # Run quirk analysis
    try:
        from utils.quirk_analyzer import (
            analyze_prompt_quirks,
            format_quirk_results_for_ui,
            save_quirk_analysis_results
        )
        from config import DEFAULT_MODEL

        # Get config
        config = st.session_state.quirk_config
        sections = config['sections']
        test_query = config['test_query']
        min_impact = config.get('min_impact', 1.0)  # Default to 1.0 if not set

        update_quirk_status(f"Analyzing {len(sections)} sections with leave-one-out testing...")
        progress_bar.progress(10)

        # Run the full analysis (always does leave-one-out)
        analysis_results = asyncio.run(analyze_prompt_quirks(
            sections=sections,
            test_query=test_query,
            n=30,
            model=DEFAULT_MODEL,
            min_impact=min_impact
        ))

        update_quirk_status("Formatting results...")
        progress_bar.progress(90)

        # Format results for UI
        formatted_results = format_quirk_results_for_ui(analysis_results)

        # Store results in session state
        st.session_state.quirk_results = formatted_results
        st.session_state.quirk_analysis_results = analysis_results
        st.session_state.quirk_complete = True

        # Save results to CSV with timestamped backup
        update_quirk_status("Saving results...")
        save_info = save_quirk_analysis_results(
            analysis_results=analysis_results,
            sections=sections,
            test_query=test_query,
            model=DEFAULT_MODEL
        )

        progress_bar.progress(100)
        update_quirk_status("Analysis complete!")

        total_responses = analysis_results['all_responses']
        total_response_count = sum(len(responses) for responses in total_responses.values())

        # Check for skipped sections or failed configs
        xml_sections = analysis_results.get('xml_only_sections', [])
        failed_configs = analysis_results.get('failed_configs', [])

        status_msg = f"""✅ Quirk analysis completed!

**Results:**
- Quirks detected: {formatted_results['total_quirks_detected']}
- Configurations tested: {len(analysis_results['all_quirk_rates'])}
- Total responses analyzed: {total_response_count}

**Saved to:**
- Latest: `{save_info['main_file']}`
- Backup: `{save_info['backup_file']}`

Scroll down to see detailed results."""

        # Add warnings if needed
        if xml_sections:
            status_msg += f"\n\n⚠️ **Note:** Skipped {len(xml_sections)} XML-only section(s) to prevent broken prompts."
        if failed_configs:
            status_msg += f"\n\n⚠️ **Warning:** {len(failed_configs)} configuration(s) failed to generate valid responses."

        st.success(status_msg)

        # Clear running flag to prevent restart
        st.session_state.quirk_running = False

    except Exception as e:
        st.error(f"Quirk analysis failed: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        st.session_state.quirk_running = False


# Display Quirk Analysis Results
if st.session_state.get('quirk_complete', False) and 'quirk_results' in st.session_state:
    st.markdown("---")
    st.markdown("## 🔍 Behavioral Quirk Analysis Results")

    results = st.session_state.quirk_results

    if results['total_quirks_detected'] == 0:
        st.info("No significant behavioral quirks detected. All sections have minimal impact (<1.0 per 100 words).")

        # Show raw responses even when no quirks detected
        if st.checkbox("🔍 Show raw API responses (debug mode)", key="show_raw_responses"):
            st.markdown("### Raw API Responses")

            analysis_results = st.session_state.get('quirk_analysis_results', {})
            all_responses = analysis_results.get('all_responses', {})

            if 'full' in all_responses and all_responses['full']:
                with st.expander("📄 Full prompt response", expanded=False):
                    st.text(all_responses['full'][0])

            for i in range(len(st.session_state.custom_sections)):
                config_key = f'without_{i}'
                if config_key in all_responses and all_responses[config_key]:
                    with st.expander(f"📄 Without section {i}", expanded=False):
                        st.caption(f"Section: {st.session_state.custom_sections[i][:100]}...")
                        st.text(all_responses[config_key][0])
    else:
        # =================================================================
        # LEVEL 1: EXECUTIVE SUMMARY (Always Visible)
        # =================================================================
        st.markdown("### 📊 Executive Summary")

        # Auto-generated one-sentence summary
        auto_summary = results.get('auto_summary', 'Behavioral changes detected.')
        st.info(f"**{auto_summary}**")

        # Top 3 auto-detected changes
        top_3_changes = results.get('top_3_changes', [])
        if top_3_changes:
            st.markdown("**🔝 Top 3 Behavioral Changes:**")

            for rank, change in enumerate(top_3_changes, 1):
                quirk_name = change.get('name', 'Unknown')
                impact = change.get('impact', 0)
                spike_ratio = change.get('spike_ratio', 1.0)
                p_value = change.get('p_value', 1.0)

                # Format impact display
                if spike_ratio >= 2.0:
                    impact_display = f"{spike_ratio:.1f}× increase"
                elif spike_ratio < 0.5 and spike_ratio > 0:
                    reduction = 1 / spike_ratio
                    impact_display = f"{reduction:.1f}× decrease"
                else:
                    impact_display = f"{abs(impact):.1f} per 100 words change"

                # Significance badge
                if p_value < 0.01:
                    sig_badge = "✨ Highly Significant"
                elif p_value < 0.05:
                    sig_badge = "📊 Significant"
                else:
                    sig_badge = "📈 Detected"

                st.markdown(f"**{rank}. {quirk_name}**: {impact_display} ({sig_badge})")

        st.markdown("")

        # =================================================================
        # LEVEL 2: DIMENSIONAL VIEW (Expandable)
        # =================================================================

        # Initialize session state for toggles
        if 'show_dimensions' not in st.session_state:
            st.session_state.show_dimensions = False
        if 'show_all_quirks' not in st.session_state:
            st.session_state.show_all_quirks = False

        # Toggle button for dimensional view
        if st.button(
            "🎨 Show Dimensional Analysis" if not st.session_state.show_dimensions else "🎨 Hide Dimensional Analysis",
            key="toggle_dimensions",
            help="Group quirks into 7 behavioral dimensions"
        ):
            st.session_state.show_dimensions = not st.session_state.show_dimensions

        if st.session_state.show_dimensions:
            st.markdown("---")
            st.markdown("### 🎨 Dimensional View")
            st.caption(f"35 individual quirks grouped into 7 coherent behavioral dimensions")

            dimensions_data = results.get('dimensions', {})

            if dimensions_data:
                # Display each dimension
                for dim_name, dim_data in dimensions_data.items():
                    icon = dim_data.get('icon', '📊')
                    description = dim_data.get('description', '')
                    dimension_score = dim_data.get('dimension_score', 1.0)
                    quirks_in_dim = dim_data.get('quirks', [])
                    visual_type = dim_data.get('visual_type', 'slider')

                    if not quirks_in_dim:
                        continue  # Skip dimensions with no detected quirks

                    with st.expander(f"{icon} **{dim_name}** ({len(quirks_in_dim)} quirks detected)", expanded=False):
                        st.markdown(f"*{description}*")
                        st.markdown("")

                        # Visual encoding based on dimension type
                        if visual_type == 'slider':
                            # Horizontal slider for spectrum dimensions
                            low_label = dim_data.get('low_label', 'Low')
                            high_label = dim_data.get('high_label', 'High')

                            # Calculate slider position (0-100)
                            if dimension_score < 1.0:
                                position = dimension_score * 50  # 0.0-1.0 → 0-50
                            else:
                                position = 50 + min((dimension_score - 1.0) * 50, 50)  # 1.0-2.0+ → 50-100

                            position = int(position)

                            # CSS slider with position indicator
                            st.markdown(f"""
                            <div style="margin: 20px 0;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                    <span style="font-size: 0.875rem; color: #a1a1aa;">{low_label}</span>
                                    <span style="font-size: 0.875rem; color: #a1a1aa;">{high_label}</span>
                                </div>
                                <div style="position: relative; width: 100%; height: 12px; background: linear-gradient(to right, #3b82f6, #8b5cf6); border-radius: 6px;">
                                    <div style="position: absolute; left: {position}%; top: 50%; transform: translate(-50%, -50%); width: 20px; height: 20px; background: white; border: 3px solid #fbbf24; border-radius: 50%; box-shadow: 0 2px 8px rgba(0,0,0,0.3);"></div>
                                </div>
                                <div style="text-align: center; margin-top: 8px;">
                                    <span style="font-size: 0.75rem; color: #71717a;">Score: {dimension_score:.2f}x</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        elif visual_type == 'gauge':
                            # Gauge visualization
                            gauge_pct = min(dimension_score * 50, 100)

                            st.markdown(f"""
                            <div style="margin: 20px 0;">
                                <div style="width: 100%; height: 24px; background: #27272a; border-radius: 12px; overflow: hidden;">
                                    <div style="width: {gauge_pct}%; height: 100%; background: linear-gradient(to right, #22c55e, #eab308); transition: width 0.5s ease;"></div>
                                </div>
                                <div style="text-align: center; margin-top: 8px;">
                                    <span style="font-size: 0.875rem; color: #d4d4d8;">{gauge_pct:.0f}% of maximum</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        elif visual_type == 'icon_grid':
                            # Icon grid for Structure & Organization
                            components = dim_data.get('components', {})

                            st.markdown("**Components:**")
                            for quirk in quirks_in_dim:
                                quirk_type = quirk.get('quirk_type', '')
                                if quirk_type in components:
                                    comp = components[quirk_type]
                                    label = comp.get('label', quirk_type)
                                    icon_char = comp.get('icon', '•')
                                    rate = quirk.get('full_prompt_rate', 0)

                                    # Create filled/unfilled bars based on rate
                                    max_bars = 6
                                    filled_bars = min(int(rate / 2), max_bars)  # 2 per 100 words = 1 bar
                                    empty_bars = max_bars - filled_bars

                                    bars = "█" * filled_bars + "░" * empty_bars

                                    st.markdown(f"{icon_char} **{label}**: {bars} ({rate:.1f} per 100 words)")

                        # List quirks in this dimension
                        st.markdown("")
                        st.markdown("**Individual quirks in this dimension:**")
                        for quirk in quirks_in_dim:
                            name = quirk.get('name', 'Unknown')
                            impact = quirk.get('impact', 0)
                            st.markdown(f"• {name}: {impact:+.2f} per 100 words")
            else:
                st.warning("Dimensional analysis data not available")

        # =================================================================
        # LEVEL 3: ALL INDIVIDUAL QUIRKS (Advanced View)
        # =================================================================

        st.markdown("")

        # Toggle button for full quirk details
        if st.button(
            "🔬 Show All Individual Quirks (Advanced)" if not st.session_state.show_all_quirks else "🔬 Hide Individual Quirks",
            key="toggle_all_quirks",
            help=f"View all {results['total_quirks_detected']} quirks with full statistical details"
        ):
            st.session_state.show_all_quirks = not st.session_state.show_all_quirks

        if st.session_state.show_all_quirks:
            st.markdown("---")
            st.markdown(f"### 🔬 All Individual Quirks ({results['total_quirks_detected']} detected)")
            st.caption("Detailed analysis of each behavioral quirk with statistical significance testing")
            st.markdown("")

            # Comprehensive quirk descriptions
            quirk_descriptions = {
                'parentheses_rate': 'Usage of parenthetical statements (asides, clarifications)',
                'apology_rate': 'Apologetic language ("sorry", "apologies")',
                'question_rate': 'Question marks (asking questions)',
                'enumeration_rate': 'Numbered/bulleted lists and structured enumerations',
                'hedge_rate': 'Hedging words ("might", "perhaps", "possibly", "somewhat")',
                'certainty_rate': 'Certainty markers ("definitely", "certainly", "clearly")',
                'metacommentary_rate': 'Meta-commentary about the response itself',
                'acknowledgment_rate': 'Acknowledgment phrases ("I understand", "I see")',
                'example_rate': '"For example" and similar example-introducing phrases',
                'action_rate': 'Action-oriented language ("should", "must", "need to")',
                'caveat_rate': 'Caveats and qualifications ("however", "although", "but")',
                'first_person_rate': 'First-person pronouns ("I", "me", "my", "we", "our")',
                'second_person_rate': 'Second-person pronouns ("you", "your", "yourself")',
                'third_person_rate': 'Third-person pronouns ("he", "she", "they", "it", "them")',
                'conditional_rate': 'Conditional language ("if", "when", "unless", "provided")',
                'modal_verb_rate': 'Modal verbs ("can", "could", "may", "might", "would")',
                'imperative_rate': 'Imperative/command forms (direct instructions)',
                'formality_score': 'Overall formality (word length, academic tone, lack of contractions)',
                'contraction_rate': 'Contractions ("don\'t", "can\'t", "it\'s")',
                'sentiment_polarity': 'Sentiment polarity (-1 negative to +1 positive)',
                'sentiment_subjectivity': 'Subjectivity score (0 objective to 1 subjective)',
                'passive_voice_rate': 'Passive voice constructions ("was done", "is made")',
                'technical_jargon_rate': 'Technical terminology and jargon',
                'emotional_language_rate': 'Emotional words ("feel", "love", "hate", "hope")',
                'transition_rate': 'Transition words ("furthermore", "moreover", "consequently")',
                'specification_rate': 'Specification phrases ("specifically", "precisely", "exactly")',
                'disclaimer_rate': 'Disclaimers and warnings ("note that", "be aware", "caution")',
                'elaboration_rate': 'Elaboration patterns ("in other words", "to clarify")',
                'quantifier_rate': 'Quantifiers ("all", "some", "many", "few", "several")',
                'comparison_rate': 'Comparison language ("better", "worse", "similar", "different")',
                'self_reference_rate': 'Self-referential language ("I\'m", "my response", "I will")',
                'future_tense_rate': 'Future tense markers ("will", "shall", "going to")',
                'past_tense_rate': 'Past tense usage (past actions and events)',
                'instruction_density': 'Commands per sentence (instructional density)',
                'repetition_rate': 'Repeated phrases (3+ word phrase repetitions)'
            }

            # Short quirk names for display
            quirk_short_names = {
                'Parentheses': 'Parentheses',
                'Apology': 'Apologies',
                'Question': 'Questions',
                'Enumeration': 'Lists',
                'Hedge': 'Hedging',
                'Certainty': 'Certainty',
                'Metacommentary': 'Meta-commentary',
                'Acknowledgment': 'Acknowledgments',
                'Example': 'Examples',
                'Action': 'Action items',
                'Caveat': 'Caveats',
                'First Person': '"I/me/my"',
                'Second Person': '"You/your"',
                'Third Person': '"He/she/they"',
                'Conditional': '"If/when"',
                'Modal Verb': '"Can/could/may"',
                'Imperative': 'Commands',
                'Formality Score': 'Formality',
                'Contraction': 'Contractions',
                'Sentiment Polarity': 'Sentiment',
                'Sentiment Subjectivity': 'Subjectivity',
                'Passive Voice': 'Passive Voice',
                'Technical Jargon': 'Technical Terms',
                'Emotional Language': 'Emotions',
                'Transition': 'Transitions',
                'Specification': 'Specifics',
                'Disclaimer': 'Disclaimers',
                'Elaboration': 'Elaborations',
                'Quantifier': 'Quantifiers',
                'Comparison': 'Comparisons',
                'Self Reference': 'Self-reference',
                'Future Tense': 'Future Tense',
                'Past Tense': 'Past Tense',
                'Instruction Density': 'Instructions',
                'Repetition': 'Repetitions'
            }

            # Display each quirk with full information
            for i, quirk in enumerate(results['quirks'], 1):
                attr = quirk['attribution']
                short_name = quirk_short_names.get(quirk['name'], quirk['name'])

                # Get full quirk data from analysis results
                analysis_results = st.session_state.get('quirk_analysis_results', {})

                # Calculate before/after and percentage
                with_section = attr.get('with_section', 0)
                without_section = attr.get('without_section', 0)
                impact = attr['impact']

                # Calculate percentage increase
                if without_section > 0:
                    pct_change = (impact / without_section) * 100
                    spike_ratio = with_section / without_section if without_section > 0 else 1.0
                else:
                    pct_change = float('inf') if impact > 0 else 0
                    spike_ratio = float('inf') if with_section > 0 else 1.0

                # Format percentage display
                if pct_change == float('inf'):
                    pct_display = "∞% (appeared from nothing)"
                elif spike_ratio >= 2.0:
                    pct_display = f"{spike_ratio:.1f}× increase"
                else:
                    pct_display = f"{pct_change:.1f}% increase"

                # Get quirk description
                quirk_key = quirk['name'].lower().replace(' ', '_').replace('"', '').replace('/', '_')
                description = quirk_descriptions.get(quirk_key, 'Behavioral pattern detected')

                # Display quirk header with description
                st.markdown(f"""
### {i}. {short_name}
**{description}**
                """)

                # Add statistical significance badge
                p_value = quirk.get('p_value', 1.0)
                effect_interpretation = quirk.get('effect_interpretation', 'unknown')

                if p_value < 0.001:
                    st.success(f"✨ **Highly Significant** (p < 0.001, effect size: {effect_interpretation})")
                elif p_value < 0.01:
                    st.info(f"📊 **Significant** (p < 0.01, effect size: {effect_interpretation})")
                elif p_value < 0.05:
                    st.warning(f"📈 **Marginally Significant** (p < 0.05, effect size: {effect_interpretation})")
                else:
                    st.error(f"❌ **Not Statistically Significant** (p = {p_value:.3f})")

                # Side-by-side comparison
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("#### ✅ WITH Section")
                    st.metric(
                        "Quirk Rate",
                        f"{with_section:.2f} per 100 words",
                        delta=f"+{impact:.2f}",
                        delta_color="normal"
                    )
                    st.caption(f"Section {attr['section_index'] + 1} is present")

                with col2:
                    st.markdown("#### ❌ WITHOUT Section")
                    st.metric(
                        "Quirk Rate",
                        f"{without_section:.2f} per 100 words"
                    )
                    st.caption(f"Section {attr['section_index'] + 1} is removed")

                # Overall metrics
                st.markdown(f"""
**Key Metrics:**
- **Percentage change:** {pct_display}
- **Spike ratio:** {spike_ratio:.1f}x
- **Effect size:** {quirk.get('effect_size', 0):.2f} ({effect_interpretation})
                """)

                # Warning if baseline is suspiciously low
                if without_section == 0:
                    st.warning(f"""⚠️ **Baseline may be unreliable** - Configuration without section {attr['section_index'] + 1} generated 0 valid responses, likely due to broken XML structure when this section was removed. Impact score may be artificially inflated.""")
                elif without_section < 0.1 and with_section > 5:
                    st.info(f"""ℹ️ **Low baseline detected** - The baseline quirk rate is very low ({without_section:.2f}), which amplifies the perceived impact. Consider whether this represents a true causal effect.""")

                # Show section text that causes this quirk (auto-expanded)
                if 'section_text' in attr and attr['section_text']:
                    # Get the full section text (not just the truncated preview)
                    section_idx = attr['section_index']
                    full_section_text = st.session_state.custom_sections[section_idx] if section_idx < len(st.session_state.custom_sections) else attr['section_text']

                    # Show a better preview
                    section_preview = full_section_text[:150] + "..." if len(full_section_text) > 150 else full_section_text

                    with st.expander(f"📄 Section {attr['section_index'] + 1}: {section_preview}", expanded=False):
                        st.markdown(f"```\n{full_section_text}\n```")

                # Extract and show smart examples
                example_snippets = quirk.get('example_snippets', {})

                if example_snippets:
                    # Show explanation of why this section was chosen
                    section_explanation = example_snippets.get('section_explanation', '')
                    if section_explanation:
                        st.info(f"ℹ️ **Why this section?** {section_explanation}")

                    # Get text diff if available
                    text_diff = example_snippets.get('text_diff', {})

                    # Get smart snippets showing specific quirk instances
                    with_snippets = example_snippets.get('with_snippets', [])
                    without_snippets = example_snippets.get('without_snippets', [])

                    # Get full responses for reference
                    with_full = example_snippets.get('with_full', '')
                    without_full = example_snippets.get('without_full', '')

                    if with_snippets or with_full:
                        st.markdown("**Example comparison:**")
                        st.caption(f"Comparing full prompt (all {len(st.session_state.custom_sections)} sections) vs. without section {attr['section_index'] + 1}")

                        # Show text diff highlighting if available
                        if text_diff and text_diff.get('has_differences'):
                            with st.expander("🔍 See what changed between responses", expanded=True):
                                st.caption("Showing sentence-level differences between responses")

                                # Get added and removed phrases
                                added = text_diff.get('added_phrases', [])
                                removed = text_diff.get('removed_phrases', [])

                                # Show added content (present with section, absent without)
                                if added:
                                    st.markdown("**➕ Added when section is present:**")
                                    for i, sentence in enumerate(added, 1):
                                        # Display each sentence in a nice format
                                        st.markdown(f"> {sentence}")
                                        if i < len(added):
                                            st.markdown("")  # Add spacing between sentences

                                # Add visual separator
                                if added and removed:
                                    st.markdown("---")

                                # Show removed content (present without section, absent with)
                                if removed:
                                    st.markdown("**➖ Removed when section is absent:**")
                                    for i, sentence in enumerate(removed, 1):
                                        st.markdown(f"> {sentence}")
                                        if i < len(removed):
                                            st.markdown("")  # Add spacing between sentences

                                # Show message if no significant differences
                                if not added and not removed:
                                    st.caption("*No major sentence-level differences detected*")

                        # Show side-by-side snippets
                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown(f"*Full prompt (with section {attr['section_index'] + 1}):*")
                            if with_snippets:
                                # Show smart snippets that highlight the quirk
                                for snippet in with_snippets[:2]:  # Max 2 snippets
                                    st.markdown(f"• {snippet}")
                            elif with_full:
                                # Fallback to truncated full response
                                snippet_with = with_full[:250] + "..." if len(with_full) > 250 else with_full
                                st.caption(snippet_with)

                        with col2:
                            st.markdown(f"*Without section {attr['section_index'] + 1} (baseline):*")
                            if without_snippets:
                                # Show baseline snippets if available
                                for snippet in without_snippets[:2]:  # Max 2 snippets
                                    st.markdown(f"• {snippet}")
                            elif without_full:
                                # Fallback to truncated full response
                                snippet_without = without_full[:250] + "..." if len(without_full) > 250 else without_full
                                st.caption(snippet_without)
                            else:
                                st.caption("*No baseline examples showing this quirk*")

                        # Show full responses in collapsible sections
                        if with_full or without_full:
                            with st.expander("📄 View full example responses"):
                                if with_full:
                                    st.markdown(f"**Full prompt response (shows {quirk['name'].lower()}):**")
                                    st.text(with_full)
                                    st.markdown("")
                                if without_full:
                                    st.markdown(f"**Without section {attr['section_index'] + 1} (baseline):**")
                                    st.text(without_full)

                st.markdown("---")


if __name__ == "__main__":
    main()
