import streamlit as st
import os
import base64
from PIL import Image
import io

def main():
    """
    Main function to display the dashboard home page
    """
    # Display the logo and header
    display_logo_and_header()
    
    # Add copyright info
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem;">
        <p style="color: #757575; font-size: 1.2rem;">© LankaDigest</p>
    </div>
    """, unsafe_allow_html=True)


def display_logo_and_header():
    """Display the LankaDigest logo and header"""
    # Content with proper HTML structure and small image
    if os.path.exists("lankadigest_logo.png"):
        # Convert image to base64 to include directly in HTML
        import base64
        from PIL import Image
        import io
        
        img = Image.open("lankadigest_logo.png")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        # Create a complete HTML structure with the small image embedded
        st.markdown(f"""
        <div class="center-container">
            <img src="data:image/png;base64,{img_str}" class="logo-img" alt="LankaDigest Logo">
            <h1 class="main-header">LankaDigest</h1>
            <p class="sub-header">AI-powered easy-to-consume news summaries about Sri Lanka</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Fallback without the image
        st.markdown("""
        <div class="center-container">
            <div style="font-size: 2rem;">🇱🇰</div>  <!-- Smaller emoji size as well -->
            <h1 class="main-header">LankaDigest</h1>
            <p class="sub-header">AI-powered easy-to-consume news summaries about Sri Lanka</p>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()