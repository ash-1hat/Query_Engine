import streamlit as st
import requests
import json
import os
import random

# Configuration
#API_BASE_URL = "https://gracious-enjoyment-staging.up.railway.app/"
API_BASE_URL = "http://localhost:8000"

# Page configuration
st.set_page_config(
    page_title="AI Clone",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for 1hat.in branding and healthcare theme
st.markdown("""
<style>
    /* Main color scheme inspired by healthcare/medical themes */
    :root {
        --primary-color: #2E86AB;
        --secondary-color: #A23B72;
        --accent-color: #F18F01;
        --success-color: #4CAF50;
        --background-color: #F8F9FA;
        --text-color: #2C3E50;
        --light-blue: #E3F2FD;
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 4rem;
        color: white;
        text-align: center;
    }
    
    /* Logo styling */
    .logo-container {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 15px;
        margin-bottom: 2rem;
    }
    
    .logo-container img {
        max-height: 60px;
        width: auto;
    }
    
    /* Sidebar styling - multiple selectors for compatibility */
    .css-1d391kg, 
    .css-1lcbmhc,
    .css-17eq0hr,
    section[data-testid="stSidebar"] {
        background-color: #1e3a8a !important;
        padding: 0.5rem !important;
        margin: 0 !important;
    }
    
    /* Sidebar content wrapper */
    section[data-testid="stSidebar"] > div {
        background-color: #1e3a8a !important;
        padding: 0.5rem !important;
        margin: 0 !important;
    }
    
    /* Reduce sidebar internal spacing */
    section[data-testid="stSidebar"] .block-container {
        padding: 0.5rem !important;
        margin: 0 !important;
    }
    
    /* All text in sidebar */
    section[data-testid="stSidebar"] * {
        color: white !important;
    }
    
    /* Sidebar headers and subheaders */
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] h4 {
        color: white !important;
    }
    
    /* Radio button styling in sidebar */
    section[data-testid="stSidebar"] .stRadio > label,
    section[data-testid="stSidebar"] .stRadio > div,
    section[data-testid="stSidebar"] [role="radiogroup"] label {
        color: white !important;
    }
    
    /* Radio button selected state */
    section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] + label {
        background-color: rgba(255, 255, 255, 0.1) !important;
        border-radius: 4px;
        padding: 0.25rem 0.5rem;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(45deg, var(--primary-color), var(--secondary-color));
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background: linear-gradient(45deg, var(--secondary-color), var(--primary-color));
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* Form styling */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > select {
        border: 2px solid var(--light-blue);
        border-radius: 8px;
        padding: 0.5rem;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stSelectbox > div > div > select:focus {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 2px rgba(46, 134, 171, 0.2);
    }
    
    /* Success/Error message styling */
    .stSuccess {
        background-color: rgba(76, 175, 80, 0.1);
        border-left: 4px solid var(--success-color);
    }
    
    .stError {
        background-color: rgba(244, 67, 54, 0.1);
        border-left: 4px solid #F44336;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        background-color: var(--light-blue);
        border-radius: 5px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: var(--text-color);
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: var(--primary-color);
        color: white;
    }
    
    /* Checkbox styling */
    .stCheckbox > label {
        background-color: white;
        padding: 0.5rem;
        border-radius: 8px;
        border: 1px solid var(--light-blue);
        margin: 0.25rem 0;
    }
    
    .stCheckbox > label:hover {
        border-color: var(--primary-color);
    }
</style>
""", unsafe_allow_html=True)

# Get the current directory of the app.py file
current_dir = os.path.dirname(os.path.abspath(__file__))

# Path to the logo file in the same directory as app.py
logo_path = os.path.join(current_dir, "1Hat Logo_transparent.png")
sidebar_logo_path = os.path.join(current_dir, "1Hat_logo.png")   

# Create a two-column layout for the header
header_col1, header_col2 = st.columns([1, 4])

# Display the logo in the first column if the file exists
if os.path.exists(logo_path):
    with header_col1:
        st.image(logo_path, width=100)
else:
    st.warning("Logo file not found. Please check the path.")
    
# Display the title and subtitle in the second column
with header_col2:
    st.markdown("<h1 style='margin: 0; font-size: 2.5rem;'>AI Clone</h1>", unsafe_allow_html=True)

# Sidebar navigation with logo
# Display the logo in the sidebar if the file exists
if os.path.exists(sidebar_logo_path):
    st.sidebar.image(sidebar_logo_path, width=80)

# Display the title in the sidebar
st.sidebar.markdown("<h2 style='color: white; margin: 0; font-size: 1.5rem; text-align: left;'>AI Clone</h2>", unsafe_allow_html=True)

page = st.sidebar.radio(
    "Select a page:",
    ["Create 1hat patient", "Assistant", "Update", "Delete Vector"]
)

def get_domains(org_id):
    """Get all domains for an organization"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/domains?org_id={org_id}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting domains: {response.text}")
            return []
    except Exception as e:
        print(f"Error getting domains: {str(e)}")
        return []

def get_organizations():
    try:
        response = requests.get(f"{API_BASE_URL}/api/organization")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting organizations: {response.text}")
            return []
    except Exception as e:
        print(f"Error getting organizations: {str(e)}")
        return []

def get_expert_domains(expert_id):
    """Get domains associated with an expert"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/experts/{expert_id}/domains")
        if response.status_code == 200:
            print(f"[UI DEBUG] get_expert_domains: Response data: {response.json()}")
            return response.json().get("domains", [])
        return []
    except Exception as e:
        print(f"[UI ERROR] get_expert_domains: Request failed: {str(e)}")
        return []

def get_available_domains(expert_id, org_id):
    """Get available domains for an expert"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/experts/{expert_id}/available-domains?org_id={org_id}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting available domains: {response.text}")
            return {}
    except Exception as e:
        print(f"Error getting available domains: {str(e)}")
        return {}

def create_expert(expert_name, domain_name, qa_pairs, document_urls, org_id, pdf_documents=None):
    try:
        print(f"[UI DEBUG] create_expert: Creating expert '{expert_name}' in domain '{domain_name}'")
        
        
        request_data = {
            "org_id": org_id,
            "expert_name": expert_name,
            "domain_name": domain_name,
            "qa_pairs": qa_pairs,
            "document_urls": document_urls
        }
        
        # Add PDF documents to request if available
        if pdf_documents and len(pdf_documents) > 0:
            # PDF documents now contain file paths instead of bytes
            request_data["pdf_documents"] = pdf_documents
            print(f"[UI DEBUG] create_expert: Added {len(pdf_documents)} PDF file paths to request")
        
        print(f"[UI DEBUG] create_expert: Request URL: {API_BASE_URL}/api/memory/expert/initialize")
        
        response = requests.post(
            f"{API_BASE_URL}/api/memory/expert/initialize",
            json=request_data
        )
        
        print(f"[UI DEBUG] create_expert: Response status code: {response.status_code}")
        
        try:
            response_data = response.json()
            print(f"[UI DEBUG] create_expert: Response data: {response_data}")
            return response_data, response.status_code
        except Exception as e:
            print(f"[UI ERROR] create_expert: Failed to parse JSON response: {str(e)}")
            print(f"[UI ERROR] create_expert: Raw response text: {response.text}")
            return {"error": f"Failed to parse response: {str(e)}"}, response.status_code
    except Exception as e:
        print(f"[UI ERROR] create_expert: Request failed: {str(e)}")
        return {"error": str(e)}, 500

def get_expert_context(expert_id):
    try:
        response = requests.get(f"{API_BASE_URL}/api/experts/{expert_id}/context")
        if response.status_code == 200:
            print(f"[UI DEBUG] get_expert_context: Response data: {response.json()}")
            return response.json()
        return {"context": ""}
    except Exception as e:
        print(f"[UI ERROR] get_expert_context: Request failed: {str(e)}")
        return {"context": ""}

def update_memory(memory_type, org_id, expert_id= None, expert_name= None, domain_name= None, client_id= None, qa_pairs=None, document_urls=None, pdf_documents=None):
    try:
        print(f"[UI DEBUG] update_memory: Updating expert '{expert_name}' in domain '{domain_name}'")
        print(f"[UI DEBUG] update_memory: memory_type={memory_type}, org_id={org_id}, expert_id={expert_id}")
        
        request_data = {
            "memory_type": memory_type,
            "org_id": org_id,
            "expert_id": expert_id,
            "client_id": client_id,
            "expert_name": expert_name,
            "domain_name": domain_name
        }
        
        # Add QA pairs to request if available
        if qa_pairs and len(qa_pairs) > 0:
            request_data["qa_pairs"] = qa_pairs
            print(f"[UI DEBUG] update_memory: Added {len(qa_pairs)} QA pairs to request")
        
        # Add document URLs to request if available
        if document_urls and len(document_urls) > 0:
            request_data["document_urls"] = document_urls
            print(f"[UI DEBUG] update_memory: Added {len(document_urls)} document URLs to request")
        
        # Add PDF documents to request if available
        if pdf_documents and len(pdf_documents) > 0:
            request_data["pdf_documents"] = pdf_documents
            print(f"[UI DEBUG] update_memory: Added {len(pdf_documents)} PDF file paths to request")
        
        print(f"[UI DEBUG] update_memory: Request URL: {API_BASE_URL}/api/update")
        print(f"[UI DEBUG] update_memory: Full request data: {request_data}")
        
        response = requests.post(
            f"{API_BASE_URL}/api/update",
            json=request_data
        )
        
        if response.status_code == 200:
            response_data = response.json()
            print(f"[UI DEBUG] update_memory: Success response: {response_data}")
            return response_data, response.status_code
        else:
            print(f"[UI ERROR] update_memory: Error {response.status_code}: {response.text}")
            print(f"[UI ERROR] update_memory: Response headers: {response.headers}")
            return {"error": f"Error {response.status_code}: {response.text}"}, response.status_code
    
    except Exception as e:
        print(f"[UI ERROR] update_memory: Exception: {str(e)}")
        return {"error": str(e)}, 500

def create_client(org_name, domain_name, expert_name, client_name, client_data, org_client_id, document_urls=None, pdf_documents=None, other_doc=None, consultation_id=None, created_time=None):
    try:
        print(f"[UI DEBUG] create_client: Creating client '{client_name}'")
        
        # Initialize with empty dictionaries if None is provided
        document_urls = document_urls or {}
        pdf_documents = pdf_documents or {}
        other_doc = other_doc or {}
        
        request_data = {
            "org_client_id": org_client_id,
            "org_name": org_name,
            "expert_name": expert_name,
            "client_name": client_name,
            "domain_name": domain_name,
            "client_data_jsonb": client_data,
            "document_urls": document_urls,
            "pdf_documents": pdf_documents,
            "other_doc": other_doc,
            "consultation_id": consultation_id,
            "created_time": created_time
        }
        
        print(f"[UI DEBUG] create_client: Request URL: {API_BASE_URL}/api/1hat/add-patient")
        
        response = requests.post(
            f"{API_BASE_URL}/api/1hat/add-patient",
            json=request_data
        )
        
        if response.status_code == 200:
            return response.json(), response.status_code
        else:
            print(f"[UI ERROR] create_client: Error {response.status_code}: {response.text}")
            return {"error": f"Error {response.status_code}: {response.text}"}, response.status_code
    
    except Exception as e:
        print(f"[UI ERROR] create_client: Exception: {str(e)}")
        return {"error": str(e)}, 500

def create_org_memory(org_name, document_urls=None, pdf_documents=None):
    try:
        print(f"[UI DEBUG] create_org_memory: Creating organization memory for '{org_name}'")
        
        request_data = {
            "org_name": org_name,
            "document_urls": document_urls or {},
            "pdf_documents": pdf_documents or {}
        }
        
        print(f"[UI DEBUG] create_org_memory: Request URL: {API_BASE_URL}/api/memory/org/initialize")
        
        response = requests.post(
            f"{API_BASE_URL}/api/memory/org/initialize",
            json=request_data
        )
        
        if response.status_code == 200:
            return response.json(), response.status_code
        else:
            print(f"[UI ERROR] create_org_memory: Error {response.status_code}: {response.text}")
            return {"error": f"Error {response.status_code}: {response.text}"}, response.status_code
    
    except Exception as e:
        print(f"[UI ERROR] create_org_memory: Exception: {str(e)}")
        return {"error": str(e)}, 500

def get_experts(org_id):
    try:
        response = requests.get(f"{API_BASE_URL}/api/experts", params={"org_id": org_id})
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []

def get_clients(org_id, expert_id=None):
    try:
        params = {"org_id": org_id}
        if expert_id:
            params["expert_id"] = expert_id
        response = requests.get(f"{API_BASE_URL}/api/clients", params=params)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []
       
def get_documents(owner_id):
    # Get documents for a specific expert and domain
    try:
        # Get documents where owner_id is the expert_id
        # This will get documents associated with this expert
        response = requests.get(
            f"{API_BASE_URL}/api/documents",
            params={"owner_id": owner_id}
        )
        
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"[UI ERROR] get_documents: {str(e)}")
        return []

def get_documents_by_vector_name(vector_name):
    # Get documents for a specific expert and domain
    try:
        # Get documents where owner_id is the expert_id
        # This will get documents associated with this expert
        response = requests.get(
            f"{API_BASE_URL}/api/documents/vector-name",
            params={"vector_name": vector_name}
        )
        
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"[UI ERROR] get_documents_by_vector_name: {str(e)}")
        return []
             

# Helper functions for OpenAI Assistant API
# Note: create_assistant and create_thread functions have been removed
# as they are now handled directly by the query_expert_with_assistant function

def query_expert_with_assistant(query, memory_type="organization", org_name=None, domain_name = None, expert_name = None, client_name=None, org_client_id=None, thread_id=None):
    try:
        print(f"[UI DEBUG] query_expert_with_assistant: Querying expert '{expert_name}' with memory type '{memory_type}'")
        
        request_data = {
            "query": query,
            "memory_type": memory_type,
            "org_name": org_name
        }
        if domain_name:
            request_data["domain_name"] = domain_name
        if thread_id:
            request_data["thread_id"] = thread_id
            
        print(f"[UI DEBUG] query_expert_with_assistant: Request data: {request_data}")
        
        response = requests.post(
            f"{API_BASE_URL}/api/query-clone",
            json=request_data
        )
        
        print(f"[UI DEBUG] query_expert_with_assistant: Response status code: {response.status_code}")
        
        try:
            response_data = response.json()
            print(f"[UI DEBUG] query_expert_with_assistant: Response data: {response_data}")
            return response_data, response.status_code
        except Exception as e:
            print(f"[UI ERROR] query_expert_with_assistant: Failed to parse JSON response: {str(e)}")
            return {"error": f"Failed to parse response: {str(e)}"}, response.status_code
    except Exception as e:
        print(f"[UI ERROR] query_expert_with_assistant: Request failed: {str(e)}")
        return {"error": str(e)}, 500
            
if page == "Assistant":
    st.title("Query Expert using Threads")
    
    # Get organizations first
    
    selected_org = st.text_input("Organization Name", key="hospital_name_input")
    selected_domain = ""
    selected_expert = ""
    selected_client = ""
    org_client_id = ""

    st.subheader("Select Memory Type")
    memory_options = ["llm", "organization"]
        
    # Default to expert selected
    default_selection = "organization"
    default_index = memory_options.index(default_selection)
        
    # Create a radio button for memory type selection
    selected_memory = st.radio(
        "Memory Type",
        options=memory_options,
        index=default_index,
        format_func=lambda x: x.capitalize(),
        horizontal=True,
        key="memory_type_radio"
    )
        
    # For compatibility with existing code
    selected_memory_types = [selected_memory]
    
    # Create unique keys for this conversation based on selections
    # Use the first selected memory type for the key if defined, otherwise use default
    conversation_key = f"{selected_org}_{selected_memory}"
    
    thread_key = f"thread_messages_{conversation_key}"
    thread_id_key = f"thread_id_{conversation_key}"
    
    # Initialize session state for thread ID and messages if not already present
    if thread_id_key not in st.session_state:
        st.session_state[thread_id_key] = None
    
    if thread_key not in st.session_state:
        st.session_state[thread_key] = []
    
    # Display chat messages
    for message in st.session_state[thread_key]:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    can_chat = True
    
    if can_chat:
        # User input
        prompt = st.chat_input("Ask a question...")
        if prompt:
            # Add user message to chat history
            st.session_state[thread_key].append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.write(prompt)
            
            # Get response from assistant
            with st.spinner("Thinking..."):
                # Pass the thread_id if we have one from a previous interaction
                result, status_code = query_expert_with_assistant(
                    query=prompt,
                    memory_type=selected_memory,
                    org_name=selected_org,
                    domain_name=selected_domain,
                    expert_name=selected_expert,
                    client_name=selected_client,
                    org_client_id=org_client_id
                    #thread_id=st.session_state[thread_id_key]
                )
                
                if status_code == 200:
                    # Update thread ID if it was returned
                    if result.get("thread_id"):
                        st.session_state[thread_id_key] = result.get("thread_id")
                    
                    # Display assistant response
                    with st.chat_message("assistant"):
                        response_text = result.get("response", {}).get("text", "No response from assistant.")
                        st.write(response_text)
                    
                    # Add assistant response to chat history
                    st.session_state[thread_key].append({"role": "assistant", "content": response_text})
                else:
                    error_msg = f"Error: {result.get('error', 'Unknown error')}"
                    st.error(error_msg)
                    # Add error response to chat history
                    st.session_state[thread_key].append({"role": "assistant", "content": error_msg})
    else:
        if selected_org == "--Select an organization--":
            with st.chat_message("assistant"):
                st.write("Please select an organization first.")
        # The other warnings are already displayed above

elif page == "Create Organization":
    st.title("Create Organization")
    st.write("Create a hospital with its general information documents.")
    
    # Initialize session state variables
    if "clear_org_form" in st.session_state and st.session_state["clear_org_form"]:
        st.session_state["clear_org_form"] = False
    
    with st.form("org_form"):
        st.subheader("Organization Information")
        
        # Organization basic info
        org_name = st.text_input("Organization Name", key="org_name_input")
        
        
        # Organization Documents Section
        st.subheader("Organization Documents")
        
        # Create tabs for organization documents
        org_doc_tabs = st.tabs(["Document URLs", "PDF Uploads"])
        
        org_doc_pairs = {}
        org_pdf_documents = {}
        
        # Organization URL Documents Tab
        with org_doc_tabs[0]:
            st.write("Organization Document URLs")
            num_org_docs = st.session_state.get('org_doc_inputs', 2)
            
            for i in range(num_org_docs):
                doc_cols = st.columns(2)
                with doc_cols[0]:
                    doc_name = st.text_input(f"Organization Doc Name {i+1}", key=f"org_doc_name_{i}")
                with doc_cols[1]:
                    doc_url = st.text_input(f"Organization Doc URL {i+1}", key=f"org_doc_url_{i}")
                
                if doc_name and doc_url:
                    if doc_name not in org_doc_pairs:
                        org_doc_pairs[doc_name] = doc_url
                    else:
                        st.warning(f"Organization document name '{doc_name}' already exists.")
        
        # Organization PDF Documents Tab
        with org_doc_tabs[1]:
            st.write("Upload Organization PDF documents")
            num_org_pdfs = st.session_state.get('org_pdf_uploads', 2)
            
            for i in range(num_org_pdfs):
                pdf_cols = st.columns(2)
                with pdf_cols[0]:
                    pdf_name = st.text_input(f"Organization PDF Name {i+1}", key=f"org_pdf_name_{i}")
                with pdf_cols[1]:
                    pdf_file = st.file_uploader(f"Upload Organization PDF {i+1}", type=["pdf"], key=f"org_pdf_file_{i}")
                
                if pdf_name and pdf_file is not None:
                    if pdf_name not in org_pdf_documents and pdf_name not in org_doc_pairs:
                        try:
                            files = {"file": (pdf_file.name, pdf_file, "application/pdf")}
                            data = {"pdf_name": pdf_name}
                            
                            response = requests.post(
                                f"{API_BASE_URL}/api/upload-pdf/",
                                files=files,
                                data=data
                            )
                            
                            if response.status_code == 200:
                                result = response.json()
                                org_pdf_documents[pdf_name] = result["file_path"]
                                st.success(f"Organization PDF uploaded: {result['message']}")
                            else:
                                st.error(f"Failed to upload organization PDF: {response.text}")
                        except Exception as e:
                            st.error(f"Error uploading organization PDF: {str(e)}")
                    else:
                        st.warning(f"Organization document name '{pdf_name}' already exists.")
        
        # Form submission buttons
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Create Organization")
        with col2:
            add_more_org_docs = st.form_submit_button("Add More Organization Documents")
    
    # Handle adding more organization documents
    if add_more_org_docs:
        st.session_state.org_doc_inputs = st.session_state.get('org_doc_inputs', 2) + 1
        st.experimental_rerun()
    
    # Process form submission
    if submitted:
        if not org_name:
            st.error("Please enter an organization name")
        else:
            # Check if we've already processed this submission
            submission_key = f"{org_name}"
            if "last_org_submission" not in st.session_state or st.session_state["last_org_submission"] != submission_key:
                
        # Handle form submission
        if submitted:
            has_updates = len(formatted_qa_pairs) > 0 or len(doc_pairs) > 0 or len(pdf_documents) > 0
            
            if has_updates:
                # Call the combined API endpoint
                result, status_code = update_memory(
                    memory_type=memory_type,
                    org_id=org_id,
                    expert_id=expert_id,
                    client_id=client_id,
                    expert_name=selected_expert if selected_expert and selected_expert != "--Select an expert--" else "",
                    domain_name=domain_name if isinstance(domain_name, str) else (domain_name[0] if isinstance(domain_name, list) and domain_name else ""),
                    qa_pairs=formatted_qa_pairs if formatted_qa_pairs else None,
                    document_urls=doc_pairs if doc_pairs else None,
                    pdf_documents=pdf_documents if pdf_documents else None
                )
                
                if status_code == 200:
                    memory_name = selected_name if selected_name != "Unknown" else memory_type
                    st.success(f"{memory_type.capitalize()} {memory_name} updated successfully!")
                    
                    # Show update details
                    with st.expander("Update Details"):
                        st.write(f"**Status:** {result.get('status', 'Unknown')}")
                        st.write(f"**Message:** {result.get('message', 'No message provided')}")
                        
                        # If context was updated, refresh it
                        if len(formatted_qa_pairs) > 0:
                            current_context = get_expert_context(selected_expert_id)
                            with update_tabs[0]:
                                with current_context_container:
                                    st.subheader("Current Context (Updated)")
                                    st.text_area("Current Context", value=current_context.get("context"), height=150, disabled=True, key="updated_context")
                else:
                    st.error(f"Error updating expert: {result.get('error', 'Unknown error')}")
            else:
                st.warning("No updates provided. Please add context questions, URL documents, or PDF documents.")
        
        # Handle adding more document inputs
        if add_more_url:
            st.session_state.expert_update_doc_inputs = st.session_state.get('expert_update_doc_inputs', 3) + 1
            st.experimental_rerun()
        if add_more_pdf:
            st.session_state.expert_update_pdf_uploads = st.session_state.get('expert_update_pdf_uploads', 3) + 1
            st.experimental_rerun()
    else:
        st.info("Please select an expert to update.")

elif page == "Create 1hat patient":
    st.title("Create 1hat patient")
    st.write("Create a new client with JSON data or update an existing client.")
    
    # Initialize session state variables if needed
    if "clear_client_form" in st.session_state and st.session_state["clear_client_form"]:
        # Reset the form by removing the flag
        st.session_state["clear_client_form"] = False
        # We don't need to clear the inputs here as they'll be reset on rerun
    
    # Get organizations first
    
    
    selected_org = st.text_input("Hospital Name", key="hospital_name_input")
    domain_name = st.text_input ("Domain", key="domain_key")
    selected_expert = st.text_input("Expert", key="expert_key")
    client_name = st.text_input("Client Name", key="client_name_key")
    org_client_id = st.number_input("Organization Client ID", key="org_client_id_input")
    consultation_id = st.text_input("Consultation ID", key="consultation_id_input")
    # Use datetime_input with both date and time for timestamptz compatibility
    created_date = st.date_input("Created Date", key="created_date_input")
    created_time_input = st.time_input("Created Time", key="created_time_input")
    
    # Combine date and time into a datetime object with timezone info for Supabase timestamptz
    import datetime
    created_time = datetime.datetime.combine(created_date, created_time_input)
    # Format as ISO 8601 string with timezone info for Supabase timestamptz compatibility
    created_time_iso = str(created_time.isoformat())
    # Initialize document pairs dictionary
    doc_pairs = {}
    
    # Initialize PDF documents dictionary
    pdf_documents = {}
    other_doc = {}

    if selected_org and domain_name and selected_expert and client_name and org_client_id and consultation_id and created_time_iso:
        # Find the organization by name to get its ID
        
        # Get experts for the selected organization
            # Generate random org_client_id internally (not visible in UI)
            st.subheader("Client Data (JSON)")
            json_str = st.text_area(
               "Edit JSON data",
                key="client_json_input"
            )
            # Option to load sample JSON
         
            client_data = json_str
            
        
            with st.form("client_create_form"):
                # Submit buttons for the form
                submit_button = st.form_submit_button("Create/Update Client")
            
            if submit_button:
                if not client_name:
                    st.error("Please enter a client name")
                elif not client_data:
                    st.error("Please enter JSON data")
                else:
                    # Check if we've already processed this submission
                    submission_key = f"{client_name}_{hash(client_data)}"
                    if "last_client_submission" not in st.session_state or st.session_state["last_client_submission"] != submission_key:
                        # Create other_doc with client data using the filename as the key
                        
                        # Call API to create/update client
                        result, status_code = create_client(
                            selected_org, 
                            domain_name,
                            selected_expert, 
                            client_name, 
                            client_data, 
                            org_client_id, 
                            doc_pairs, 
                            pdf_documents, 
                            other_doc,
                            consultation_id,
                            created_time_iso
                        )
                        
                        if org_status == 200:
                            org_id = org_result.get("org_id")
                            st.success(f"Organization '{org_name}' created successfully!")
                            
                                    
                                    # Show detailed results
                            with st.expander("Creation Details"):
                                st.write(f"**Organization:** {org_name}")
                                st.write(f"**Organization ID:** {org_id}")
                                st.write(f"**Organization Documents:** {len(org_doc_pairs) + len(org_pdf_documents)}")
                                        
                                    
                                # Store submission to prevent duplicates
                                st.session_state["last_org_submission"] = submission_key
                                st.session_state["clear_org_form"] = True
                        else:
                            st.error(f"Error creating/updating client: {result.get('error', 'Unknown error')}")
                    else:
                        st.info("Form already submitted. Refresh the page to submit again.")
                        # Clear the submission tracking after showing the message
                        del st.session_state["last_client_submission"]

elif page == "Delete Vector":
    st.title("Delete Vector Memory")
    st.write("Delete all vector memories for an organization. This action cannot be undone.")
    
    # Get all organizations
    try:
        response = requests.get(f"{API_BASE_URL}/api/organization")
        if response.status_code == 200:
            organizations = response.json()
            org_options = ["--Select an organization--"] + [org["org_name"] for org in organizations]
            
            # Organization selection
            selected_org = st.selectbox("Select Organization", org_options)
            
            if selected_org != "--Select an organization--":
                # Add a confirmation checkbox
                confirm_delete = st.checkbox("I understand this will permanently delete ALL vector memories for this organization")
                
                # Delete button with confirmation
                if st.button("Delete Vector Memories", disabled=not confirm_delete):
                    if confirm_delete:
                        try:
                            # Call the delete_org_vector_memory endpoint
                            response = requests.delete(f"{API_BASE_URL}/api/vectors/memory-org", params={"org_name": selected_org})
                            
                            if response.status_code == 200:
                                st.success(f"Successfully deleted all vector memories for {selected_org}")
                            else:
                                st.error(f"Failed to delete vector memories: {response.text}")
                        except Exception as e:
                            st.error(f"Error deleting vector memories: {str(e)}")
                    else:
                        st.warning("Please confirm deletion by checking the confirmation box")
            else:
                st.info("Please select an organization to delete its vector memories")
        else:
            st.error(f"Error fetching organizations: {response.text}")
    except Exception as e:
        st.error(f"Error: {str(e)}")
