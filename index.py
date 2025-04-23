import streamlit as st
import os
import base64
import importlib.util
import sys

# Set page configuration
st.set_page_config(
    page_title="LankaDigest : Quick and concise news summary",
    page_icon="🇱🇰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state for page navigation
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'dashboard'

# Apply custom CSS
def apply_custom_css():
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            color: #1E88E5;
            text-align: center;
            margin-bottom: 1rem;
        }
        .sub-header {
            font-size: 1.2rem;
            color: #424242;
            text-align: center;
            margin-bottom: 2rem;
        }
        /* Button styling */
        .css-1cpxqw2 {
            background-color: #1E88E5;
            color: white;
        }
        .css-1cpxqw2:hover {
            background-color: #1565C0;
        }
        /* Full-width sidebar buttons with proper justification */
        .stButton > button {
            width: 100%;
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 0.75rem 1rem !important;
            margin-bottom: 0.5rem;
            border-radius: 0.3rem;
            border: none;
            background-color: #f0f7ff;
            color: #424242;
            transition: background-color 0.3s;
        }
        .stButton > button:hover {
            background-color: #e3f2fd;
        }
        .stButton > button:disabled {
            background-color: #bbdefb;
            color: #1E88E5;
            cursor: default;
        }
        /* Add some space between icons and text */
        .stButton button {
            letter-spacing: 0.05rem;
        }
        /* Main area styling */
        .main-area {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 80vh;
            flex-direction: column;
            text-align: center;
        }
        .main-message {
            font-size: 1.5rem;
            color: #757575;
            margin-bottom: 2rem;
        }
    </style>
    """, unsafe_allow_html=True)

# Display header
def display_header():
    # Add custom CSS for centering with smaller image
    st.markdown("""
    <style>
        .center-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 1rem;
        }
        .logo-img {
            width: 200px;  /* Smaller fixed width */
            height: auto; /* Maintain aspect ratio */
            margin-bottom: 0.5rem;
        }
        .main-header {
            margin-top: 0.5rem;
            margin-bottom: 0.25rem;
        }
        .sub-header {
            margin-top: 0;
            opacity: 0.8;
        }
    </style>
    """, unsafe_allow_html=True)



# Custom sidebar button function - using simpler approach without HTML
def sidebar_button(label, icon, key, disabled=False):
    # Simply combine the icon and label as text - no HTML
    return st.button(f"{icon} {label}", key=key, disabled=disabled, help=f"Navigate to {label}", use_container_width=True)

# Function to load and execute Python file
def load_view(file_path):
    """
    Load and execute a Python file to display its content in the main area
    """
    try:
        # Get the module name from the file path
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Check if module is already in sys.modules to avoid reloading issues
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        # Load the module specification
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None:
            st.error(f"Could not load module specification from {file_path}")
            return False
        
        # Create the module
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        
        # Execute the module
        spec.loader.exec_module(module)
        
        # Look for and call a main function if it exists
        if hasattr(module, 'main'):
            module.main()
        
        return True
    except Exception as e:
        st.error(f"Error loading view {file_path}: {str(e)}")
        return False

# Main dashboard function
def dashboard():
    # Apply custom CSS
    apply_custom_css()
    
    # Display header
    display_header()
    
    # Create sidebar with Quick Links and About
    with st.sidebar:
        st.markdown("### Quick Links")
        
        # Dashboard button
        dashboard_btn = sidebar_button("Dashboard", "🏠", "dash_link", 
                                     disabled=(st.session_state.current_view == 'dashboard'))
        if dashboard_btn:
            st.session_state.current_view = 'dashboard'
            st.rerun()
        
        # News Search button
        search_btn = sidebar_button("RAG Search", "🔍", "search_link",
                                   disabled=(st.session_state.current_view == 'search'))
        if search_btn:
            st.session_state.current_view = 'search'
            st.rerun()
        
        # AI Agent button
        agent_btn = sidebar_button("Agentic RAG", "🤖", "agent_link",
                                  disabled=(st.session_state.current_view == 'agent'))
        if agent_btn:
            st.session_state.current_view = 'agent'
            st.rerun()
        
        st.markdown("---")
        
        st.markdown("### About LankaDigest")
        st.markdown("""
        <div style="text-align: justify; background-color: #f0f7ff; padding: 1rem; border-radius: 0.5rem; border-left: 0.3rem solid #1E88E5;">
            <p>LankaDigest is an AI-powered platform, delivers easy-to-consume news summaries about Sri Lanka. LankaDigest uses Retrieval-Augmented Generation (RAG) and with AI agents, for accurate, concise, and meaningful news updates for a better reading experience.</p>
            <p> </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Main content area
    if st.session_state.current_view == 'dashboard':
        # Display the dashboard welcome message
        if not load_view("step-03-view-dashboard.py"):
            st.error("Failed to load News Search view. Please check if the file exists.")
    
    elif st.session_state.current_view == 'search':
        # Load the search view
        if not load_view("step-03-view-search.py"):
            st.error("Failed to load News Search view. Please check if the file exists.")
    
    elif st.session_state.current_view == 'agent':
        # Load the agent view
        if not load_view("step-03-view-agent.py"):
            st.error("Failed to load AI Agent view. Please check if the file exists.")

# Run the dashboard
if __name__ == "__main__":
    dashboard()