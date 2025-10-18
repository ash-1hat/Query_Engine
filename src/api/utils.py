import os
import time
import httpx
import requests
import urllib.parse
from uuid import UUID
import warnings
import base64
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from openai import OpenAI
from io import BytesIO
from llama_cloud_services import LlamaParse
from youtube_transcript_api import YouTubeTranscriptApi
from config import OPENAI_API_KEY, LLAMA_CLOUD_API_KEY, DOMAIN_FILE_PATH
from database import supabase
from models import CreateVector
from fastapi import HTTPException

accepted_extensions = ['.c', '.cpp', '.css', '.csv', '.doc', '.docx', '.gif', '.go', '.html', \
                    '.java', '.jpeg', '.jpg', '.js', '.json', '.md', '.pdf', '.php', '.pkl', \
                    '.png', '.pptx', '.py', '.rb', '.tar', '.tex', '.ts', '.txt', '.webp', \
                    '.xlsx', '.xml', '.zip']

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def is_youtube_video(url: str) -> bool:
    """Check if a URL is a YouTube video."""
    import re
    youtube_patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]+)',
        r'youtube\.com\/embed\/([\w-]+)',
        r'youtube\.com\/v\/([\w-]+)',
        r'youtube\.com\/user\/[\w-]+\/\?v=([\w-]+)',
        r'youtube\.com\/attribution_link\?.*v%3D([\w-]+)',
    ]
    
    for pattern in youtube_patterns:
        if re.search(pattern, url):
            return True
    return False

def get_openai_client():
    """
    Returns an initialized OpenAI client
    
    Returns:
        OpenAI client instance
    """
    return OpenAI(api_key=OPENAI_API_KEY)

# Initialize LlamaParse client
llama_parser = LlamaParse(
    api_key=LLAMA_CLOUD_API_KEY,  # can also be set in your env as LLAMA_CLOUD_API_KEY
    num_workers=4,       # if multiple files passed, split in `num_workers` API calls
    verbose=True,
    language="en"       # optionally define a language, default=en
)

def is_youtube_video(url: str) -> bool:
    """Check if a URL is a YouTube video."""
    import re
    youtube_patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]+)',
        r'youtube\.com\/embed\/([\w-]+)',
        r'youtube\.com\/v\/([\w-]+)',
        r'youtube\.com\/user\/[\w-]+\/\?v=([\w-]+)',
        r'youtube\.com\/attribution_link\?.*v%3D([\w-]+)',
    ]
    
    for pattern in youtube_patterns:
        if re.search(pattern, url):
            return True
    return False

def get_youtube_transcript(video_url: str):
    if not is_youtube_video(video_url):
        raise ValueError(f"Invalid YouTube URL: {video_url}")
    print(f"Getting transcript for YouTube video: {video_url}")
    
    try:
        # Extract video ID from URL
        video_id = extract_youtube_id(video_url)
        if not video_id:
            raise ValueError(f"Could not extract YouTube video ID from URL: {video_url}")
            
        print(f"Fetching transcript for YouTube video ID: {video_id}")
        
        # Get transcript using YouTubeTranscriptApi directly with the fetch method
        transcript_api = YouTubeTranscriptApi()
        fetched_transcript = transcript_api.fetch(video_id, languages=['en'])
        
        # Format transcript into a single text with timestamps
        full_transcript = ""
        for snippet in fetched_transcript.snippets:
            timestamp = snippet.start
            minutes = int(timestamp // 60)
            seconds = int(timestamp % 60)
            time_str = f"[{minutes:02d}:{seconds:02d}] "
            full_transcript += snippet.text + " "
        '''
        # Create a document object similar to what llama_index would return
        from llama_index.core.schema import Document
        document = Document(
            text=full_transcript,
            metadata={
                "source": video_url,
                "video_id": fetched_transcript.video_id,
                "language": fetched_transcript.language,
                "language_code": fetched_transcript.language_code,
                "is_generated": fetched_transcript.is_generated,
                "title": f"YouTube Transcript: {fetched_transcript.video_id}"
            }
        )
        '''
        print(f"Successfully retrieved transcript for YouTube video: {video_url}")
        return full_transcript
        
    except Exception as e:
        print(f"Error getting YouTube transcript: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve YouTube transcript: {str(e)}")

def extract_youtube_id(url: str) -> Optional[str]:
    """
    Extract YouTube video ID from various YouTube URL formats
    
    Args:
        url: YouTube URL in any format
        
    Returns:
        YouTube video ID or None if not a valid YouTube URL
    """
    import re
    # Regular expressions for different YouTube URL formats
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]+)',  # Standard and shortened URLs
        r'youtube\.com\/embed\/([\w-]+)',                      # Embed URLs
        r'youtube\.com\/v\/([\w-]+)',                          # Old embed URLs
        r'youtube\.com\/user\/[\w-]+\/\?v=([\w-]+)',         # User URLs
        r'youtube\.com\/attribution_link\?.*v%3D([\w-]+)',    # Attribution links
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

async def create_vector_store(client, vector_name: str):
    try:
        # Create a vector store for the document
        vector_store = client.vector_stores.create(
            name = vector_name
        )
        return vector_store
    except Exception as e:
        print(f"Error creating vector store: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating vector store: {str(e)}")

async def create_file_for_vector_store(client, document_url: str, document_name: str = None, owner_id: str = None) -> str:
    """
    Create a file from a document URL and return the file ID
    
    Args:
        client: OpenAI client
        document_url: URL or local path to the document
        document_name: Optional name for the document (will be generated if not provided)
        owner_id: Optional owner ID to associate the document with
    Returns:
        File ID created in OpenAI
    """
    try:
        print(f"[API DEBUG] create_file_for_vector_store: Starting to process document URL: {document_url}")
        print(f"[API DEBUG] create_file_for_vector_store: Document name: {document_name}, Owner ID: {owner_id}")
        
        if document_url:
            print(f"[API DEBUG] create_file_for_vector_store: Checking if document already exists in database")
            existing_doc = supabase.table("documents").select("*").eq("document_link", document_url).eq("owner_id", owner_id).execute()
            
            if existing_doc.data and len(existing_doc.data) > 0:
                # Document with this name already exists
                print(f"[API DEBUG] create_file_for_vector_store: Document with URL '{document_url}' already exists under name '{existing_doc.data[0].get('name')}'")
                file_id = existing_doc.data[0].get("openai_file_id")
                print(f"[API DEBUG] create_file_for_vector_store: Returning existing file ID: {file_id}")
                return file_id
        
        if document_url.__contains__("youtube"):
            transcript = get_youtube_transcript(document_url)
            # Convert string to bytes before using BytesIO
            file_content = BytesIO(transcript.encode('utf-8'))
            # Create a more descriptive filename with .txt extension
            video_id = extract_youtube_id(document_url) or "video"
            file_name = f"youtube_transcript_{video_id}.txt"
            file_tuple = (file_name, file_content)
            result = client.files.create(
                file=file_tuple,
                purpose="assistants"
            )
        # Download the document if it's a web URL
        elif document_url.startswith(('http://', 'https://')):
            print(f"[API DEBUG] create_file_for_vector_store: Processing web URL: {document_url}")
            # Extract file extension from URL
            url_path = urllib.parse.urlparse(document_url).path
            file_extension = os.path.splitext(url_path)[1]
            print(f"[API DEBUG] create_file_for_vector_store: Detected file extension from URL: {file_extension}")
            
            # Special handling for arxiv URLs
            if not file_extension or file_extension not in accepted_extensions:
                print(f"[API WARNING] create_file_for_vector_store: No valid extension detected in URL: {document_url}")
                warnings.warn(f"No valid extension detected skipping url: {document_url}")
                return None
                
            # Ensure the file has a proper extension for OpenAI vector store
            print(f"[API DEBUG] create_file_for_vector_store: Original document name: {document_name}")
            if not any(document_name.lower().endswith(ext) for ext in accepted_extensions):
                # Try to extract extension from URL or use .txt as fallback
                if file_extension and file_extension in accepted_extensions:
                    document_name = f"{document_name}{file_extension}"
                else:
                    document_name = f"{document_name}.txt"
                print(f"[API DEBUG] create_file_for_vector_store: Updated document name with extension: {document_name}")
            
            file_name = document_name
            # Add timestamp to file_name to make it unique
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{timestamp}_{file_name}"
            print(f"[API DEBUG] create_file_for_vector_store: Final file name with timestamp: {file_name}")
            
            # Implement retry logic with exponential backoff for URL downloads
            max_retries = 3
            retry_delay = 2  # Initial delay in seconds
            attempt = 0
            file_content = None
            
            while attempt < max_retries:
                try:
                    # Increase timeout for potentially large files
                    timeout = httpx.Timeout(connect=10.0, read=120.0, write=60.0, pool=60.0)
                    print(f"[API DEBUG] create_file_for_vector_store: Starting download attempt {attempt+1}/{max_retries} with timeout settings: {timeout}")
                    
                    async with httpx.AsyncClient(timeout=timeout) as httpclient:
                        print(f"[API DEBUG] create_file_for_vector_store: Downloading URL: {document_url}")
                        response = await httpclient.get(document_url)
                        response.raise_for_status()
                        content_length = len(response.content)
                        print(f"[API DEBUG] create_file_for_vector_store: Successfully downloaded {content_length} bytes from {document_url}")
                        
                        # using OpenAI document to create BytesIO object
                        file_content = BytesIO(response.content)
                        file_tuple = (file_name, file_content)
                        
                        print(f"[API DEBUG] create_file_for_vector_store: Creating OpenAI file with name: {file_name} and size: {content_length} bytes")
                        result = client.files.create(
                            file=file_tuple,
                            purpose="assistants"
                        )
                        print(f"[API DEBUG] create_file_for_vector_store: Successfully created OpenAI file with ID: {result.id}")
                        break  # Success, exit the retry loop
                except (httpx.RequestError, httpx.HTTPStatusError, asyncio.TimeoutError) as e:
                    attempt += 1
                    if attempt >= max_retries:
                        print(f"[API ERROR] create_file_for_vector_store: Failed to download after {max_retries} attempts: {document_url}")
                        print(f"[API ERROR] create_file_for_vector_store: Error type: {type(e).__name__}, Error: {str(e)}")
                        print(f"[API DEBUG] create_file_for_vector_store: Attempting fallback download methods")
                        try:
                            
                            # Ensure the file has a proper extension for OpenAI vector store
                            # Create target folder path (../../Docs from src/api)
                            current_dir = os.path.dirname(os.path.abspath(__file__))
                            docs_folder = os.path.join(current_dir, "..", "..", "Docs")
                            os.makedirs(docs_folder, exist_ok=True)
                            
                            file_path = os.path.join(docs_folder, document_name)
                            
                            # Try a different approach to download the file - using requests instead of httpx
                            print(f"Attempting fallback download using requests: {document_url}")
                            
                            try:
                                # First try with requests
                                # Disable SSL verification with a warning for problematic sites
                                warnings.filterwarnings('once', message='Unverified HTTPS request')
                                print(f"[API DEBUG] create_file_for_vector_store: Attempting download with SSL verification disabled for: {document_url}")
                                with requests.get(document_url, stream=True, timeout=120, verify=False) as r:
                                    r.raise_for_status()
                                    with open(file_path, "wb") as buffer:
                                        for chunk in r.iter_content(chunk_size=8192):
                                            buffer.write(chunk)
                                
                                print(f"[API DEBUG] create_file_for_vector_store: Successfully downloaded file to {file_path} using requests fallback method")
                            except Exception as requests_error:
                                print(f"[API ERROR] create_file_for_vector_store: Requests fallback failed: {type(requests_error).__name__}: {str(requests_error)}")
                                print(f"[API DEBUG] create_file_for_vector_store: Attempting curl fallback method")
                                
                                # Try curl as a last resort
                                try:
                                    curl_command = ["curl", "-L", "-o", file_path, document_url]
                                    print(f"[API DEBUG] create_file_for_vector_store: Running curl command: {' '.join(curl_command)}")
                                    result = subprocess.run(curl_command, check=True)
                                    
                                    if result.returncode == 0:
                                        print(f"[API DEBUG] create_file_for_vector_store: Successfully downloaded file to {file_path} using curl fallback method")
                                    else:
                                        raise Exception(f"Curl process returned non-zero exit code: {result.returncode}")
                                except Exception as curl_error:
                                    print(f"[API ERROR] create_file_for_vector_store: Curl fallback also failed: {type(curl_error).__name__}: {str(curl_error)}")
                                    raise curl_error
                            
                            # Now create the OpenAI file from the downloaded file
                            with open(file_path, "rb") as f:
                                result = client.files.create(
                                    file=(file_name, f),
                                    purpose="assistants"
                                )
                            
                        except Exception as e:
                            print(f"[API ERROR] create_file_for_vector_store: All download methods failed: {type(e).__name__}: {str(e)}")
                            traceback.print_exc()  # Print full stack trace for debugging
                            raise HTTPException(status_code=500, detail=f"Failed to download document after all attempts: {str(e)}")
                    
                    # Exponential backoff
                    wait_time = retry_delay * (2 ** (attempt - 1))
                    print(f"[API DEBUG] create_file_for_vector_store: Download attempt {attempt} failed. Retrying in {wait_time} seconds. Error: {str(e)}")
                    await asyncio.sleep(wait_time)       
        else:
            # It's a local file path
            print(f"[API DEBUG] create_file_for_vector_store: Processing local file path: {document_url}")
            # Try different path resolutions to find the file
            file_path = document_url
            found = False
            
            # List of possible base directories to try
            base_dirs = [
                os.getcwd(),  # Current working directory
                os.path.dirname(os.path.abspath(__file__)),  # Directory of this script
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),  # Project root
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Docs"),  # Docs folder
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data"),  # data folder
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "documents")  # documents folder
            ]
            
            print(f"[API DEBUG] create_file_for_vector_store: Checking base directories: {[os.path.exists(d) for d in base_dirs]}")
            
            # First try the path as is
            if os.path.exists(file_path) and os.path.isfile(file_path):
                found = True
                print(f"[API DEBUG] create_file_for_vector_store: Found file at original path: {file_path}")
            else:
                # Try resolving against different base directories
                for base_dir in base_dirs:
                    resolved_path = os.path.join(base_dir, document_url)
                    print(f"[API DEBUG] create_file_for_vector_store: Trying path: {resolved_path}")
                    if os.path.exists(resolved_path) and os.path.isfile(resolved_path):
                        file_path = resolved_path
                        found = True
                        print(f"[API DEBUG] create_file_for_vector_store: Found file at: {file_path}")
                        break
            
            if not found:
                print(f"[API ERROR] create_file_for_vector_store: Could not find file at {document_url} or any resolved paths")
                raise FileNotFoundError(f"Could not find file at {document_url} or any resolved paths")
            
            print(f"[API DEBUG] create_file_for_vector_store: Creating OpenAI file from local file: {file_path}")
            try:    
                with open(file_path, "rb") as file_content:
                    result = client.files.create(
                        file=(os.path.basename(file_path), file_content),
                        purpose="assistants"
                    )
                print(f"[API DEBUG] create_file_for_vector_store: Successfully created OpenAI file with ID: {result.id} from local file")
            except Exception as e:
                print(f"[API ERROR] create_file_for_vector_store: Failed to create OpenAI file from local file: {type(e).__name__}: {str(e)}")
                traceback.print_exc()
                raise

        # Store document information in the documents table if domain is provided
        if result.id:
            print(f"[API DEBUG] create_file_for_vector_store: Storing document information in database for file ID: {result.id}")
            try:
                # Check if document name is already used. If so, rename
                print(f"[API DEBUG] create_file_for_vector_store: Checking if document name already exists: {document_name}, owner_id: {owner_id}")
                existing_doc = supabase.table("documents").select("*").eq("name", document_name).eq("owner_id", owner_id).execute()
                if existing_doc.data and len(existing_doc.data) > 0:
                    print(f"[API DEBUG] create_file_for_vector_store: Document name already exists, will create unique name")
                
                # If it's a different URL, make the name unique by adding a timestamp
                timestamp = int(time.time())
                storage_file_name = f"{timestamp}_{document_name if document_name else 'document'}"
                print(f"[API DEBUG] create_file_for_vector_store: Generated storage file name: {storage_file_name}")
                
                # Ensure the file has a proper extension for OpenAI vector store
                if not any(storage_file_name.lower().endswith(ext) for ext in accepted_extensions):
                    # Try to extract extension from URL or use .txt as fallback
                    url_path = urllib.parse.urlparse(document_url).path
                    ext = os.path.splitext(url_path)[1].lower()
                    if ext and ext in accepted_extensions:
                        storage_file_name = f"{storage_file_name}{ext}"
                    else:
                        storage_file_name = f"{storage_file_name}.txt"
                    print(f"[API DEBUG] create_file_for_vector_store: Added extension to file name: {storage_file_name}")
                
                # Insert document record
                doc_record = {
                    "name": storage_file_name,
                    "document_link": document_url,
                    "openai_file_id": result.id
                }
                if owner_id:
                    doc_record["owner_id"] = owner_id
                
                print(f"[API DEBUG] create_file_for_vector_store: Inserting document record: {doc_record}")
                # Insert the complete record
                insert_result = supabase.table("documents").insert(doc_record).execute()
                print(f"[API DEBUG] create_file_for_vector_store: Document inserted successfully, response: {insert_result}")
                
                print(f"[API DEBUG] create_file_for_vector_store: Stored document in database: {document_name}, OpenAI file ID: {result.id}")
            except Exception as db_error:
                print(f"[API ERROR] create_file_for_vector_store: Error storing document in database: {type(db_error).__name__}: {str(db_error)}")
                traceback.print_exc()
                # Continue despite database error - we still want to return the file ID
                print(f"[API WARNING] create_file_for_vector_store: Continuing despite database error, returning file ID: {result.id}")
        
        # Return the extracted result id
        print(f"[API DEBUG] create_file_for_vector_store: Returning file ID: {result.id}")
        return result.id
    except Exception as e:
        print(f"[API ERROR] create_file_for_vector_store: Error processing document URL '{document_url}': {str(e)}")
        print(f"[API ERROR] create_file_for_vector_store: Error type: {type(e).__name__}")
        traceback.print_exc()  # Print full stack trace for debugging
        print(f"[API ERROR] create_file_for_vector_store: Document name: {document_name}, Owner ID: {owner_id}")
        raise HTTPException(status_code=500, detail=f"Error creating file: {str(e)}")

async def create_file_from_json(client, file_content_json: Any, file_name: str, owner_id: str = None, vector_store_id: str = None) -> str:
    """
    Create a file from bytes content, store it in Supabase storage, and return the file ID
    
    Args:
        client: OpenAI client
        file_content_json: JSON content of the file
        file_name: Name for the document
        owner_id: Optional owner ID to associate the document with
        vector_store_id: Optional vector store ID to associate the document with
        
    Returns:
        File ID created in OpenAI
    """
    try:
        print(f"Processing document from json: {file_name}")
        
        # Generate a unique storage file name to avoid conflicts
        
        if file_content_json:
            doc_link = json.dumps(file_content_json)
            existing_doc = supabase.table("documents").select("*").eq("name", file_name).eq("owner_id", owner_id).eq("doc_type", "json").execute()
            
            if existing_doc.data and len(existing_doc.data) > 0:
                # Document with this name already exists
                print(f"Json Document {file_name} already exists under name {existing_doc.data[0]['name']}")
                await delete_file_ids(vector_store_id, [existing_doc.data[0]["openai_file_id"]], owner_id)
            
        #timestamp = int(time.time())
        # Ensure the file has a proper extension for OpenAI vector store
        storage_file_name = f"{file_name}.json"
           
        file_content = BytesIO(json.dumps(file_content_json).encode("utf-8"))
        file_tuple = (storage_file_name, file_content)
        
        # Create file in OpenAI
        result = client.files.create(
            file=file_tuple,
            purpose="assistants"
        )
        
        # Store document information in the documents table if domain is provided
        if result.id:
            # Insert document record
            doc_record = {
                "name": file_name,
                "document_link": json.dumps(file_content_json),  # Use Supabase URL if available
                "openai_file_id": result.id,
                "doc_type": "json"
            }
            if owner_id:
                doc_record["owner_id"] = owner_id

            # Insert the complete record
            supabase.table("documents").insert(doc_record).execute()
            
            print(f"Stored document in database: {storage_file_name}, OpenAI file ID: {result.id}")
            
        # Return the extracted result id
        return result.id
    except Exception as e:
        print(f"Error in create_file_from_json: {str(e)}")
        print(f"Error type: {type(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def create_files_for_vector_store(client, document_urls: dict, other_docs: dict = None, owner_id: str = None, vector_store_id: str = None) -> list:
    """
    Create multiple files from document URLs and/or PDF document bytes and return the file IDs
    
    Args:
        client: OpenAI client
        document_urls: Dictionary of document names to URLs or local paths
        other_docs: Dictionary of document names to document content like json
        owner_id: Optional owner ID to associate the documents with
        vector_store_id: Optional vector store ID to associate the documents with
        
    Returns:
        List of file IDs created in OpenAI
    """
    print(f"Processing batch of {len(document_urls) if document_urls else 0} URL documents and {len(other_docs) if other_docs else 0} other documents")
    file_ids = []
    failed_docs = []
    error_details = {}
    
    # Process each document URL and collect file IDs
    if document_urls:
        for doc_name, document_url in document_urls.items():
            try:
                print(f"\n--- Processing document: {doc_name} ---")
                file_id = await create_file_for_vector_store(client, document_url, document_name=doc_name, owner_id=owner_id)
                file_ids.append(file_id)
                print(f"Created file with ID: {file_id} for document URL: {doc_name}")
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                print(f"Failed to process document '{doc_name}' with URL '{document_url}'")
                print(f"Error type: {error_type}, Error message: {error_msg}")
                
                # Store detailed error information
                failed_docs.append(doc_name)
                error_details[doc_name] = {
                    "url": document_url,
                    "error_type": error_type,
                    "error_message": error_msg
                }
                continue  # Skip this document and continue with the next one
    
    # Process each other document and collect file IDs
    if other_docs:
        for doc_name, doc_binary in other_docs.items():
            try:    
                print(f"\n--- Processing JSON document: {doc_name} ---")
                file_id = await create_file_from_json(client, doc_binary, doc_name, owner_id=owner_id, vector_store_id=vector_store_id)
                file_ids.append(file_id)

                print(f"Created file with ID: {file_id} for other document: {doc_name}")
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                print(f"Failed to process other document '{doc_name}'")
                print(f"Error type: {error_type}, Error message: {error_msg}")
                
                # Store detailed error information
                failed_docs.append(doc_name)
                error_details[doc_name] = {
                    "type": "json_document",
                    "error_type": error_type,
                    "error_message": error_msg
                }
                continue  # Skip this document and continue with the next one
    
    # Report on any failed documents
    if failed_docs:
        print(f"Warning: {len(failed_docs)} documents failed to process:")
        for doc in failed_docs:
            error = error_details.get(doc, {})
            error_type = error.get("error_type", "Unknown")
            print(f"  - {doc}: {error_type}")
    
    # Return both successful file IDs and error information
    return file_ids

async def add_documents_to_vector_store(client, vector_store_id: str, document_urls: dict = None, other_doc: dict = None, owner_id: str = None):
    """
    Process multiple documents and add them to a vector store using batch API
    
    Args:
        client: OpenAI client
        vector_store_id: ID of the vector store
        document_urls: Dictionary of document names to URLs or local paths
        other_doc: Dictionary of document names to document content like json
        owner_id: Optional owner ID to associate the documents with
        
    Returns:
        Dictionary with file_ids, batch_id, status, and detailed information about processing
    """
    print(f"Adding documents to vector store {vector_store_id}")
    
    # Track document processing statistics
    stats = {
        "total_documents": len(document_urls or {}) + len(other_doc or {}),
        "url_documents": len(document_urls or {}),
        "json_documents": len(other_doc or {}),
        "successful_files": 0,
        "failed_documents": 0
    }
    
    # Create files for all documents
    try:
        file_ids = await create_files_for_vector_store(client, document_urls, other_doc, owner_id, vector_store_id)
        stats["successful_files"] = len(file_ids)
        stats["failed_documents"] = stats["total_documents"] - stats["successful_files"]
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"Error in create_files_for_vector_store: {error_type}: {error_msg}")
        return {
            "file_ids": [], 
            "batch_id": None, 
            "status": "failed", 
            "message": f"Error creating files: {error_msg}",
            "error_type": error_type,
            "stats": stats
        }
    
    if not file_ids:
        print("No files were created successfully. Skipping batch creation.")
        return {
            "file_ids": [], 
            "batch_id": None, 
            "status": "failed", 
            "message": "No files were created successfully",
            "stats": stats
        }
    
    # Create a batch with the file IDs
    print(f"Creating batch with {len(file_ids)} files")
    try:
        # Get existing vector store information from Supabase
        try:
            vector_store_result = supabase.table("vector_stores").select("*").eq("vector_id", vector_store_id).execute()
            existing_file_ids = []
            if vector_store_result.data and len(vector_store_result.data) > 0:
                # Extract existing file IDs from the result
                existing_file_ids = vector_store_result.data[0].get("file_ids", [])
                if existing_file_ids is None:
                    existing_file_ids = []
                print(f"Found {len(existing_file_ids)} existing file IDs in vector store {vector_store_id}")
        except Exception as e:
            print(f"Warning: Could not retrieve existing file IDs: {str(e)}")
            existing_file_ids = []
        
        # Filter out file IDs that already exist in the vector store
        new_file_ids = [file_id for file_id in file_ids if file_id not in existing_file_ids]
        
        if not new_file_ids:
            print("All files already exist in the vector store. No new files to add.")
            return {
                "file_ids": file_ids,
                "batch_id": None,
                "status": "skipped",
                "message": "All files already exist in the vector store",
                "stats": stats
            }
        
        print(f"Adding {len(new_file_ids)} new files to vector store {vector_store_id}")
        
        # Then add only the new files to the vector store as a batch
        batch_result = await add_batch_to_vector_store(client, vector_store_id, new_file_ids)
        print(f"Added files to vector store as batch: {batch_result['id']}")
        
        return {
            "file_ids": file_ids,
            "batch_id": batch_result['id'],
            "status": batch_result['status'],
            "message": f"Successfully added {len(new_file_ids)} files to vector store",
            "stats": stats
        }
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"Error adding documents to vector store: {error_type}: {error_msg}")
        # Return partial success if we at least created some files
        return {
            "file_ids": file_ids,
            "batch_id": None,
            "status": "partial_failure",
            "message": f"Created {len(new_file_ids)} files but failed to add them to vector store: {error_msg}",
            "error_type": error_type,
            "stats": stats
        }

async def add_batch_to_vector_store(client, vector_store_id: str, document_ids: list):
    """
    Add multiple documents to a vector store using batch API
    
    Args:
        client: OpenAI client
        vector_store_id: ID of the vector store
        document_ids: List of document IDs to add to the vector store
        
    Returns:
        Batch creation result
    """
    try:
        print(f"Adding batch of {len(document_ids)} documents to vector store {vector_store_id}")
        result = client.vector_stores.file_batches.create(
            vector_store_id=vector_store_id,
            file_ids=document_ids
        )
        print(f"Batch creation initiated with ID: {result.id}")
        
        # Return a consistent dictionary format instead of the raw APIResponse
        return {
            "id": result.id,
            "status": result.status,
            "vector_store_id": vector_store_id,
            "file_ids": document_ids
        }
    except Exception as e:
        print(f"Error adding batch to vector store: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error adding batch to vector store: {str(e)}")
        
async def edit_vector_store(client, vector_store_id: str, file_ids: list, document_urls: dict, other_doc: dict = None, owner_id: str = None):
    """
    Edit an existing vector store by adding new documents and/or removing deselected documents
    
    Args:
        client: OpenAI client
        vector_store_id: ID of the vector store to edit
        file_ids: Existing file IDs in the vector store
        document_urls: Dictionary mapping document names to URLs to keep or add to the vector store
        owner_id: Optional owner ID to associate the documents with
        other_docs: Dictionary mapping document names to json content bytes
        
    Returns:
        Dictionary with status, message, file_ids, and batch_id
    """
    try:
        print(f"[API DEBUG] edit_vector_store: Starting edit process for vector store {vector_store_id}")
        print(f"[API DEBUG] edit_vector_store: Input parameters - file_ids count: {len(file_ids) if file_ids else 0}, owner_id: {owner_id}")
        
        # Initialize other_documents if not provided
        if other_doc is None:
            print("[EDIT VECTOR] No json content provided to edit vector")
            other_doc = {}
            
        url_count = len(document_urls) if document_urls else 0
        other_doc_count = len(other_doc) if other_doc else 0
        total_docs = url_count + other_doc_count
        
        print(f"Editing vector store {vector_store_id} with {total_docs} documents ({url_count} URLs, {other_doc_count} other)")
        
        # Get existing document URLs from the documents table that match the file_ids
        print(f"[API DEBUG] edit_vector_store: Querying existing documents for file_ids: {file_ids}")
        query = supabase.table("documents").select("id, document_link, openai_file_id").in_("openai_file_id", file_ids).neq("doc_type", "json").eq("owner_id", owner_id)
        existing_docs_query = query.execute()
        existing_docs = existing_docs_query.data
        print(f"[API DEBUG] edit_vector_store: Found {len(existing_docs)} existing documents")
        
        # Create a mapping of document URLs to their file IDs
        existing_url_to_file_id = {doc["document_link"]: doc["openai_file_id"] for doc in existing_docs if "document_link" in doc and "openai_file_id" in doc}
        print(f"[API DEBUG] edit_vector_store: Created mapping of {len(existing_url_to_file_id)} URLs to file IDs")
        
        # Identify which URLs are new and need to be added
        existing_urls = list(existing_url_to_file_id.keys())
        document_urls_values = list(document_urls.values())
        new_urls_dict = {name: url for name, url in document_urls.items() if url not in existing_urls}
        print(f"[API DEBUG] edit_vector_store: Identified {len(new_urls_dict)} new URLs to add")
        
        # Create files for each new json document content
        new_file_ids = []
        
        # Process document URLs
        print(f"[API DEBUG] edit_vector_store: Starting to process {len(new_urls_dict)} new document URLs")
        for doc_name, document_url in new_urls_dict.items():
            try:
                print(f"[API DEBUG] edit_vector_store: Creating file for document '{doc_name}' with URL: {document_url[:50]}...")
                file_id = await create_file_for_vector_store(client, document_url, document_name=doc_name, owner_id=owner_id)
                new_file_ids.append(file_id)
                print(f"[API DEBUG] edit_vector_store: Successfully created file with ID {file_id} for document '{doc_name}'")
            except Exception as e:
                print(f"[API ERROR] edit_vector_store: Error creating file for document '{doc_name}': {str(e)}")
                print(f"[API ERROR] edit_vector_store: Error type: {type(e).__name__}")
                # Continue with other documents even if one fails
                continue
                
        # Process Other documents
        print(f"[API DEBUG] edit_vector_store: Starting to process {len(other_doc)} other documents")
        for doc_name, json_content in other_doc.items():
            try:
                print(f"[API DEBUG] edit_vector_store: Creating file for JSON document '{doc_name}'")
                file_id = await create_file_from_json(client, json_content, file_name=doc_name, owner_id=owner_id, vector_store_id=vector_store_id)
                new_file_ids.append(file_id)
                print(f"[API DEBUG] edit_vector_store: Successfully created file with ID {file_id} for JSON document '{doc_name}'")
            except Exception as e:
                print(f"[API ERROR] edit_vector_store: Error creating file for JSON document '{doc_name}': {str(e)}")
                print(f"[API ERROR] edit_vector_store: Error type: {type(e).__name__}")
                # Continue with other documents even if one fails
                continue
        
        # Get file IDs for URLs that should be kept
        kept_file_ids = [existing_url_to_file_id[url] for url in document_urls.values() if url in existing_urls]
        print(f"[API DEBUG] edit_vector_store: Keeping {len(kept_file_ids)} existing file IDs")
        
        # Keep track of all file IDs for database records
        all_file_ids = kept_file_ids + new_file_ids
        print(f"[API DEBUG] edit_vector_store: Total file IDs after update: {len(all_file_ids)}")
        
        # Only add new files to the vector store batch
        batch_id = None
        if new_file_ids:
            print(f"[API DEBUG] edit_vector_store: Adding {len(new_file_ids)} new files to vector store {vector_store_id}")
            try:
                batch_result = await add_batch_to_vector_store(client, vector_store_id, new_file_ids)
                batch_id = batch_result['id']  # Using dictionary access since we updated the function
                print(f"[API DEBUG] edit_vector_store: Successfully added batch with ID {batch_id} to vector store {vector_store_id}")
            except Exception as batch_error:
                print(f"[API ERROR] edit_vector_store: Error adding batch to vector store: {str(batch_error)}")
                print(f"[API ERROR] edit_vector_store: Error type: {type(batch_error).__name__}")
                raise  # Re-raise to handle at the caller level
        else:
            print("[API DEBUG] edit_vector_store: No new files to add to vector store")
            
        # Delete files that are not part of kept_file_ids from documents table
        files_to_delete = [file_id for file_id in file_ids if file_id not in kept_file_ids and file_id not in new_file_ids]
        if files_to_delete:
            print(f"[API DEBUG] edit_vector_store: Deleting {len(files_to_delete)} files that are no longer needed")
            delete_result = await delete_file_ids(vector_store_id, files_to_delete, owner_id)
            
        # Calculate document counts for the return message
        url_count = len(new_urls_dict) if new_urls_dict else 0
        other_doc_count = len(other_doc) if other_doc else 0
        total_new_docs = len(new_file_ids)
        
        print(f"[API DEBUG] edit_vector_store: Successfully completed vector store edit process")
        return {
            "status": "success",
            "message": f"Updated vector store {vector_store_id} with {total_new_docs} new documents ({url_count} URLs, {other_doc_count} other)",
            "file_ids": new_file_ids,
            "all_file_ids": all_file_ids,
            "batch_id": batch_id,
            "vector_store_id": vector_store_id,
            "url_count": url_count,
            "other_doc_count": other_doc_count
        }
    except Exception as e:
        print(f"[API ERROR] edit_vector_store: Error editing vector store: {str(e)}")
        print(f"[API ERROR] edit_vector_store: Error type: {type(e).__name__}")
        import traceback
        print(f"[API ERROR] edit_vector_store: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error editing vector store: {str(e)}")

async def check_document_urls(document_urls):    
    try:
        docs_to_pop = []
        for key, url in document_urls.items():
            print(f"Checking document URL: {url}")
            if url.startswith(('http://', 'https://')) and not url.__contains__("youtube"):
                # Extract file extension from URL
                url_path = urllib.parse.urlparse(url).path
                file_extension = os.path.splitext(url_path)[1]
                print(f"File extension: {file_extension}")
                
                if file_extension and file_extension in accepted_extensions:
                    continue
                print(f"Skipping document URL: {url}")
                docs_to_pop.append(key)
        for key in docs_to_pop:
            document_urls.pop(key)
        return document_urls
    except Exception as e:
        print(f"Error checking document urls: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking document urls: {str(e)}")

def extract_text_from_response(response):
    """
    Extract text content from various OpenAI response formats.
    Handles different response structures including ResponseOutputMessage objects.
    
    Based on OpenAI's standard response structure:
    response.output: List[ResponseOutputMessage]
    
    Where each ResponseOutputMessage has:
    - id: str
    - role: str (usually 'assistant')
    - content: List[ResponseOutputText]
    - type: str (usually 'message')
    
    And each ResponseOutputText has:
    - text: str (the actual content we want)
    - type: str (usually 'output_text')
    """
    try:
        print(f"[DEBUG] extract_text_from_response: Response type: {type(response)}")
        
        # Standard way based on OpenAI's response structure
        if hasattr(response, 'output'):
            
            # Handle the standard case where output is a list of ResponseOutputMessage objects
            if isinstance(response.output, list):
                print(f"[DEBUG] extract_text_from_response: Output is a list with {len(response.output)} items")
                
                # Extract text using the pattern shown in the example
                for msg in response.output:
                    if hasattr(msg, 'role') and msg.role == "assistant" and hasattr(msg, 'content'):
                        for content in msg.content:
                            if hasattr(content, 'text'):
                                print(f"[DEBUG] extract_text_from_response: Found text in assistant message")
                                return content.text
                
                # If we didn't find an assistant message, try any message
                for msg in response.output:
                    if hasattr(msg, 'content') and isinstance(msg.content, list):
                        for content in msg.content:
                            print(f"[DEBUG] extract_text_from_response: Found content in message content")
                            if hasattr(content, 'text'):
                                print(f"[DEBUG] extract_text_from_response: Found text in message content")
                                return content.text
        
        # Handle ResponseOutputMessage string representation
        if hasattr(response, 'text'):
            text_value = response.text
            if isinstance(text_value, str):
                # Check if it's a ResponseOutputMessage string representation
                print(f"[DEBUG] extract_text_from_response: Found text in message content")
                if 'ResponseOutputMessage' in text_value and 'text=' in text_value:
                    # Extract using regex
                    import re
                    print(f"[DEBUG] extract_text_from_response: Attempting to extract text with regex")
                    match = re.search(r"text='([^']*)'(?:, type='output_text')", text_value)
                    if match:
                        extracted_text = match.group(1)
                        # Unescape any escaped quotes
                        extracted_text = extracted_text.replace("\'", "'")
                        print(f"[DEBUG] extract_text_from_response: Extracted text from ResponseOutputMessage using regex")
                        return extracted_text
                    else:
                        # Try a more general pattern
                        match = re.search(r"text='(.*?)'", text_value)
                        if match:
                            extracted_text = match.group(1)
                            extracted_text = extracted_text.replace("\'", "'")
                            print(f"[DEBUG] extract_text_from_response: Extracted text using general regex")
                            return extracted_text
                # Just a regular string
                return text_value
            # It's an object with potential text attribute
            elif hasattr(text_value, 'text'):
                print(f"[DEBUG] extract_text_from_response: Found text in message content")
                return text_value.text
        
        # Fallback to other possible structures
        
        # Check for content attribute
        if hasattr(response, 'content') and isinstance(response.content, list):
            for item in response.content:
                print(f"[DEBUG] extract_text_from_response: Found content in message content")
                if hasattr(item, 'text'):
                    print(f"[DEBUG] extract_text_from_response: Found text in message content")
                    return item.text
        
        # If we got here, return the string representation as a last resort
        print(f"[DEBUG] extract_text_from_response: No structured text found, using string representation")
        return str(response)
    except Exception as e:
        print(f"[ERROR] extract_text_from_response: {str(e)}")
        return str(response)

# Parse file to get domain names and document URLs from config file
async def parse_domain_config_file(config_file_path=None):
    """
    Parse a domain config file that contains domains and their associated files.
    
    Expected JSON format:
    {
      "domains": [
        {
          "domain_name": "Domain Name",
          "files": [
            {
              "file_name": "Document Name",
              "url": "Document URL"
            }
          ]
        }
      ]
    }
    
    Returns:
        dict: A dictionary with domain names as keys and document_urls dictionaries as values
              Each document_urls dictionary has document names as keys and URLs as values
    """
    # Use environment variable as default if no path provided
    if config_file_path is None:
        config_file_path = DOMAIN_FILE_PATH
        print(f"Using default domain file path from environment: {config_file_path}")
    
    # Initialize result structure
    domain_data = {}
    
    try:
        # Check if file exists
        if not config_file_path or not os.path.exists(config_file_path):
            print(f"Warning: Config file {config_file_path} does not exist or path is invalid")
            return domain_data
            
        with open(config_file_path, 'r') as file:
            file_content = file.read().strip()
            if not file_content:  # Check if file is empty
                print(f"Warning: Config file {config_file_path} is empty")
                return domain_data
                
            config_data = json.loads(file_content)
            
            # Validate the JSON structure
            if not isinstance(config_data, dict) or 'domains' not in config_data or not isinstance(config_data['domains'], list):
                raise HTTPException(status_code=400, detail="Invalid config file format. Expected JSON with 'domains' array")
            
            # Process each domain
            for domain_entry in config_data['domains']:
                if 'domain_name' not in domain_entry or 'files' not in domain_entry:
                    print(f"Warning: Skipping invalid domain entry: {domain_entry}")
                    continue
                    
                domain_name = domain_entry['domain_name']
                document_urls = {}
                
                # Process files for this domain
                for file_entry in domain_entry['files']:
                    if 'file_name' in file_entry and 'url' in file_entry:
                        document_urls[file_entry['file_name']] = file_entry['url']
                    else:
                        print(f"Warning: Skipping invalid file entry in domain {domain_name}: {file_entry}")
                
                # Add domain data if it has any files
                if document_urls:
                    domain_data[domain_name] = document_urls
                    print(f"Parsed {len(document_urls)} document URLs for domain '{domain_name}'")
                else:
                    print(f"Warning: No valid file entries found for domain '{domain_name}'")
            
            print(f"Parsed {len(domain_data)} domains from config file")
            
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in config file: {str(e)}")
    except Exception as e:
        print(f"Error parsing domain config file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error parsing domain config file: {str(e)}")
        
    return domain_data

# Get domain name for an expert
async def get_domain_id(org_id: UUID, domain_name: str):
    """
    Get domain name for a given expert name
    """
    try:
        print(f"Getting domain for org_id: {org_id}, domain_name: {domain_name}")
        
        org_result = supabase.table("organizations").select("id").eq("id", org_id).execute()
        if not org_result.data:
            raise HTTPException(status_code=404, detail=f"Organization {org_id} not found")

        # Query the expert by name
        result = supabase.table("domains").select("id").eq("org_id", org_id).eq("domain_name", domain_name).execute()
        print(f"Domain query result: {result.data}")
        
        if not result.data:
            return None
        
        domain_id = result.data[0].get("id")
        
        return domain_id
    except Exception as e:
        print(f"Error getting domain id: {str(e)}")
        return None

async def get_file_ids(vectorname: Optional[str] = None, vector_id: Optional[str] = None):
    """
    Get file_ids filtered by vector_name
    
    Priority rules:
    1. If vector_name is provided, return file_ids matching vector_name, else return all file_ids
    """
    try:
        
        # Start building the query
        query = supabase.table("vector_stores").select("*")
        
        if vectorname:
            query = query.eq("vector_name", vectorname)
        if vector_id:
            query = query.eq("vector_id", vector_id)
        # Execute the query
        result = query.execute()
        
        # Check if result.data is a coroutine and await it if necessary
        if hasattr(result, 'data'):
            data = result.data
            #print(f"Found {len(data)} vector stores")
            if data and len(data) > 0:
                return data[0].get("file_ids", [])
            return []
        else:
            print("No data attribute found in result")
            return []
    except Exception as e:
        print(f"Error getting documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def delete_file_for_vector_store(vector_id: str):
    """
    Delete file_ids filtered by vector_id and owner_id 
    """
    try:
        # Get the file_ids from the vector_stores table
        response = supabase.table("vector_stores").select("file_ids").eq("vector_id", vector_id).execute()
        
        # Check if we have data and file_ids
        if not response.data or not response.data[0].get("file_ids"):
            print(f"[Delete file ids]: No file IDs found for vector store {vector_id}")
            return True
        
        # Extract the actual file IDs from the response
        file_ids_list = response.data[0].get("file_ids", [])
        print(f"[Delete file ids]: Found {len(file_ids_list)} file IDs for vector store {vector_id}")
        
        # Delete each file ID
        for file_id in file_ids_list:
            if not file_id or not isinstance(file_id, str):
                print(f"[Delete file ids]: Skipping invalid file ID: {file_id}")
                continue
                
            try:
                print(f"[Delete file ids]: Deleting file {file_id} from vector store {vector_id}")
                # Delete from vector store
                client.vector_stores.files.delete(
                    vector_store_id=vector_id,
                    file_id=file_id
                )
                print(f"[Delete file ids]: Successfully deleted file {file_id} from vector store")
                
                # Delete from OpenAI files
                client.files.delete(file_id)
                print(f"[Delete file ids]: Successfully deleted file {file_id} from OpenAI")
                
                # Delete from documents table
                delete_result = supabase.table("documents").delete().eq("openai_file_id", file_id).execute()
                print(f"[Delete file ids]: Deleted {file_id} from documents table")
            except Exception as delete_error:
                print(f"[Delete file ids]: Error deleting file {file_id}: {str(delete_error)}")
                # Continue with other files even if one fails
    except Exception as e:
        print(f"[Delete file ids]: Error retrieving file IDs: {str(e)}")
    
    return True


async def delete_file_ids(vector_id: str, file_ids: List[str], owner_id: str):
    """
    Delete file_ids filtered by vector_id and owner_id 
    """
    # Delete from documents table where openai_file_id is in files_to_delete
    delete_result = supabase.table("documents").delete().in_("openai_file_id", file_ids).eq("owner_id", owner_id).execute()
    # Deleting from vector_stores table happens automatically through add_files_to_vector function            
    print(f"[Delete file ids]: Deleted {len(delete_result.data)} documents from the database")
                
    # Delete files from the vector store in OpenAI
    for file_id in file_ids:
        try:
            print(f"[Delete file ids]: Deleting file {file_id} from vector store {vector_id}")
            client.vector_stores.files.delete(
                vector_store_id=vector_id,
                file_id=file_id
            )
            print(f"[Delete file ids]: Successfully deleted file {file_id} from vector store")
            client.files.delete(file_id)
            print(f"[Delete file ids]: Successfully deleted file {file_id} from OpenAI")
        except Exception as delete_error:
            print(f"[Delete file ids]: Error deleting file {file_id}: {str(delete_error)}")
            # Continue with other files even if one fails
    return True

async def generate_persona_from_qa(client, qa_data):
    """
    Generate a persona summary from question-answer data
    
    Args:
        client: OpenAI client
        qa_data: List of dictionaries with 'question' and 'answer' keys
        
    Returns:
        Generated persona summary as a string
    """
    try:
        print(f"[DEBUG] generate_persona_from_qa: Generating persona from {len(qa_data)} QA pairs")
        
        # Format QA data as a string
        qa_formatted = ""
        for i, qa in enumerate(qa_data):
            qa_formatted += f"Question {i+1}: {qa.get('question', '')}\n"
            qa_formatted += f"Answer {i+1}: {qa.get('answer', '')}\n\n"
        
        # Create system prompt
        system_prompt = """Use the question and answers to understand the experience and expertise of the individual. 
        Summarize them into a five to six line summary describing the individual's persona. 
        This summary should capture their expertise, experience, and communication style 
        so that it can be passed as a system prompt to any LLM call."""
        
        # Create user prompt
        user_prompt = f"Here are the question-answer pairs:\n\n{qa_formatted}\n\nBased on these, create a concise persona summary."
        
        # Call OpenAI API
        response = client.responses.create(
            model="gpt-4o",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        
        # Extract the generated persona
        persona_summary = extract_text_from_response(response)
        print(f"[DEBUG] generate_persona_from_qa: Generated persona summary")
        
        return persona_summary
    except Exception as e:
        print(f"[ERROR] generate_persona_from_qa: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating persona from QA data: {str(e)}")

async def update_expert_with_domains(expert, domains):
    try:
        expert_id = expert.get("id")
        name = expert.get("name")
        org_id = expert.get("org_id")
        expert_domains = expert.get("domains")
        #check if expert.domains in the expert_domains list, if not append it
        # Check each domain in expert.domains and add it if not already in expert_domains
        domains_added = False
        for d in domains:
            if d not in expert_domains:
                expert_domains.append(d)
                domains_added = True
            
        # Only update if we actually added new domains
        if domains_added:
            supabase.table("experts").update({"domains": expert_domains}).eq("id", expert_id).execute()
            print(f"Updated expert domains to: {expert_domains}")
            await update_domains_with_experts(name, expert_domains, org_id)
            #check if expert name exists in the domains table (expert_names) for each domain and if not add it
            
        return expert_id
    except Exception as e:
        print(f"Error updating expert with domains: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def update_domains_with_experts(name, expert_domains, org_id):
    try:
        print(f"Updating domains with experts: {name}, {expert_domains}, {org_id}")
        for domain in expert_domains:
            domain_exists = supabase.table("domains").select("*").eq("domain_name", domain).eq("org_id", org_id).execute()
            if domain_exists.data:
                print(f"Domain already exists: {domain_exists.data}")
                domain_id = domain_exists.data[0].get("id")
                #check if expert name exists in the domains table (expert_names) for each domain and if not add it
                expert_names = domain_exists.data[0].get("expert_names")
                if name not in expert_names:
                    expert_names.append(name)
                    supabase.table("domains").update({"expert_names": expert_names}).eq("id", domain_id).execute()
                    print(f"Updated expert names to: {expert_names}")
            else:
                # Create domain data
                domain_data = {
                    "domain_name": domain,
                    "expert_names": [name],
                    "org_id": org_id
                    }
                
                # Insert domain into database
                result = supabase.table("domains").insert(domain_data).execute()
                if not result.data:
                    raise HTTPException(status_code=500, detail="Failed to create domain")
    except Exception as e:
        print(f"Error updating domains with experts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_query_for_vector_store(request: CreateVector):
    org_id = request.org_id
    domain_name = request.domain_name
    expert_id = request.expert_id
    client_id = request.client_id
    memory_type = request.memory_type
    query = None
    vector_name = None
    
    try:
        match memory_type:
            case "llm" | "organization":
                query = supabase.table("vector_stores").select("id, vector_id").eq("org_id", org_id).eq("owner", memory_type)
                vector_name = str(org_id)
            case "domain":
                # Check if domain_name is provided for domain memory type
                if domain_name is None:
                    print(f"Error: domain_name is None for memory_type 'domain'.")
                    raise HTTPException(status_code=400, detail="domain_name is required for memory_type 'domain'")
                
                # Get domain_id only if domain_name is provided
                domain_id = await get_domain_id(org_id, domain_name)
                if not domain_id:
                    print(f"Error: No domain_id found for domain_name '{domain_name}' and org_id '{org_id}'.")
                    raise HTTPException(status_code=404, detail=f"No domain found with name '{domain_name}' for organization '{org_id}'")
                
                query = supabase.table("vector_stores").select("id, vector_id").eq("domain_id", domain_id).eq("org_id", org_id).eq("owner", memory_type)
                vector_name = str(domain_id)
            case "expert":
                if not expert_id or not org_id:
                    raise HTTPException(status_code=400, detail="expert_id and org_id are required for memory_type 'expert'")
                query = supabase.table("vector_stores").select("id, vector_id").eq("expert_id", expert_id).eq("org_id", org_id).eq("owner", memory_type).is_("client_id", "null")
                vector_name = str(expert_id)
            case "client":
                if not client_id or not org_id:
                    raise HTTPException(status_code=400, detail="client_id and org_id are required for memory_type 'client'")
                query = supabase.table("vector_stores").select("id, vector_id").eq("client_id", client_id).eq("org_id", org_id).eq("owner", memory_type).is_("expert_id", "null")
                vector_name = str(client_id)
            case "myclient":
                if not client_id or not org_id or not expert_id:
                    raise HTTPException(status_code=400, detail="client_id, org_id, and expert_id are required for memory_type 'myclient'")
                query = supabase.table("vector_stores").select("id, vector_id").eq("client_id", client_id).eq("org_id", org_id).eq("expert_id", expert_id).eq("owner", memory_type)
                vector_name = str("myclient" + str(client_id))
            case _:
                raise HTTPException(status_code=400, detail="Invalid memory type")
    except HTTPException as he:
        # Re-raise HTTP exceptions with their original status code and detail
        print(f"HTTP Exception in get_query_for_vector_store: {str(he.detail)}")
        raise he
    except Exception as e:
        print(f"Error getting query for vector store: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    return query, vector_name

async def delete_files_in_vector_store(client, vector_store_id: str, file_ids: list):
    """
    Delete files from a vector store and from OpenAI
    
    Args:
        client: OpenAI client
        vector_store_id: ID of the vector store
        file_ids: List of file IDs to delete
        
    Returns:
        Dictionary with status and deleted_files count
    """
    try:
        deleted_count = 0
        failed_count = 0
        failed_files = []
        
        for file_id in file_ids:
            try:
                # First delete from vector store
                client.vector_stores.files.delete(
                    vector_store_id=vector_store_id,
                    file_id=file_id
                )
                print(f"Deleted file {file_id} from vector store {vector_store_id}")
                
                # Then delete the file from OpenAI
                client.files.delete(file_id)
                print(f"Deleted file {file_id} from OpenAI")
                deleted_count += 1
            except Exception as e:
                print(f"Error deleting file {file_id} from OpenAI: {str(e)}")
                failed_count += 1
                failed_files.append(file_id)
                # Continue with other files even if one fails
        
        return {
            "status": "completed",
            "deleted_files": deleted_count,
            "failed_files": failed_count,
            "failed_file_ids": failed_files
        }
    except Exception as e:
        print(f"Error in delete_files_in_vector_store: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "deleted_files": 0
        }

async def delete_vector_index(vector_id: str) -> bool:
    """
    Delete a vector index using OpenAI's vectorStores API
    """
    try:
        print(f"[DEBUG] delete_vector_index: Attempting to delete vector store with ID: {vector_id}")
        
        # Delete the vector store using the client
        print(f"[DEBUG] delete_vector_index: Deleting vector store with ID: {vector_id}")
        await delete_file_for_vector_store(vector_id)
        client.vector_stores.delete(vector_id)
        print(f"[DEBUG] delete_vector_index: Successfully deleted vector store with ID: {vector_id}")
        return True
    except Exception as e:
        print(f"[ERROR] delete_vector_index: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting vector index: {str(e)}")

def validate_file_paths(uploaded_documents: Dict[str, str]) -> Dict[str, str]:
    """
    Validate that file paths exist and are accessible, or process base64-encoded content
    
    Args:
        uploaded_documents: Dictionary with document names as keys and either file paths or base64-encoded content as values
        
    Returns:
        Dictionary with document names as keys and validated file paths or temporary file paths for base64 content
    """
    import base64
    import tempfile
    import uuid

    if not uploaded_documents:
        return {}
    
    validated_files = {}
    temp_files = []
    
    for doc_name, content in uploaded_documents.items():
        try:
            # Check if it's a file path
            if isinstance(content, str) and os.path.exists(content) and os.path.isfile(content):
                # Verify it's an accepted file
                if any(content.lower().endswith(ext) for ext in accepted_extensions):
                    validated_files[doc_name] = content
                    print(f"Validated file '{doc_name}' at {content}")
                else:
                    print(f"Warning: File '{doc_name}' at {content} is not an accepted file type")
            
            # Check if it's a base64-encoded string (starts with data:application/pdf;base64, or similar)
            elif isinstance(content, str) and (
                content.startswith('data:application/pdf;base64,') or 
                content.startswith('data:application/octet-stream;base64,') or
                ';base64,' in content
            ):
                print(f"Processing base64-encoded content for '{doc_name}'")
                
                # Extract the base64 content
                base64_content = content.split(';base64,')[1] if ';base64,' in content else content
                
                try:
                    # Decode the base64 content
                    file_content = base64.b64decode(base64_content)
                    
                    # Create a temporary file
                    file_ext = '.pdf'  # Default to PDF
                    if ';base64,' in content:
                        mime_type = content.split('data:')[1].split(';')[0]
                        if mime_type == 'application/pdf':
                            file_ext = '.pdf'
                    
                    # Create a unique filename
                    unique_id = str(uuid.uuid4())[:8]
                    temp_file = tempfile.NamedTemporaryFile(suffix=file_ext, prefix=f"{unique_id}_", delete=False)
                    temp_file_path = temp_file.name
                    
                    # Write the content to the file
                    with open(temp_file_path, 'wb') as f:
                        f.write(file_content)
                    
                    validated_files[doc_name] = temp_file_path
                    temp_files.append(temp_file_path)
                    print(f"Created temporary file for '{doc_name}' at {temp_file_path}")
                    
                except Exception as decode_error:
                    print(f"Error decoding base64 content for '{doc_name}': {str(decode_error)}")
            else:
                print(f"Warning: Content for '{doc_name}' is neither a valid file path nor base64-encoded content")
        except Exception as e:
            print(f"Error validating content for '{doc_name}': {str(e)}")
            continue
    
    print(f"Successfully validated {len(validated_files)} files")
    return validated_files


# OpenAI Assistant API functions
async def create_assistant(org_id: UUID, domain_name: str = None, expert_id: UUID = None, expert_name: str = None, client_id: UUID = None, memory_type: str = "expert", model: str = "gpt-4o"):
    """
    Create an OpenAI Assistant for a specific expert and memory type
    
    Args:
        org_id: ID of the organization
        domain_name: Name of the domain
        expert_id: ID of the expert
        client_id: ID of the client
        memory_type: Type of memory to use (llm, domain, expert, myclient, client)
        model: OpenAI model to use
        
    Returns:
        Assistant object with ID
    """
    try:
        print(f"[DEBUG] create_assistant: Creating assistant for org '{org_id}', domain '{domain_name}', expert '{expert_id}', client '{client_id}' with memory type '{memory_type}'")
        
        request = CreateVector(org_id=org_id, domain_name=domain_name, expert_id=expert_id, client_id=client_id, memory_type=memory_type)
        query, vector_name = await get_query_for_vector_store(request)
        vector_store_result = query.execute()
        print(f"Vector store query result: {vector_store_result.data}")
        
        vector_id = None
        role = "You are an AI assistant"
        context = None
        if vector_store_result.data and len(vector_store_result.data) > 0:
            vector_id = vector_store_result.data[0].get("vector_id")
        else:
            print(f"[ERROR] create_assistant: Vector store not found")
            # Continue execution even if there's an error retrieving vector IDs    
        if expert_name != None:
            role = "You are named " + expert_name
            result = supabase.table("experts").select("context").eq("id", expert_id).execute()
            if not result.data:
                raise HTTPException(status_code=404, detail=f"Expert {expert_id} not found")
            context = result.data[0]["context"]

        # Create assistant instructions based on expert context and memory type
        instructions = role
        if context:
            instructions += f"\n\nYou have the following experience and expertise: {context}."
        
        if memory_type == "domain":
            instructions += f"\n\nYou have access to domain knowledge about {domain_name}."
        elif memory_type == "expert":
            instructions += f"\n\nYou have access to expert-specific knowledge."
        
        # Create the assistant
        tools = []
        tool_resources = {}
        if vector_id and memory_type != "llm":
            # Use file_search instead of retrieval as per the latest OpenAI API
            tools.append({"type": "file_search"})
            tool_resources = {
                "file_search": {
                    "vector_store_ids": [vector_id]
                }
            }
        
        assistant = client.beta.assistants.create(
            name=f"{vector_name}",
            instructions=instructions,
            model=model,
            tools=tools,
            tool_resources=tool_resources
        )
        
        # Store assistant ID in database
        try:
            # Create a table entry for the assistant
            assistant_data = {
                "assistant_id": assistant.id,
                "vector_name": vector_name,
                "expert_id": str(expert_id) if expert_id else None,
                "org_id": str(org_id) if org_id else None,
                "domain_name": domain_name,
                "client_id": str(client_id) if client_id else None,
                "memory_type": memory_type,
                "vector_id": vector_id  # Changed from vector_ids to match database schema
            }
            
            supabase.table("assistants").insert(assistant_data).execute()
            print(f"[DEBUG] create_assistant: Assistant created with ID: {assistant.id}")
        except Exception as e:
            print(f"[ERROR] create_assistant: Error storing assistant data: {str(e)}")
            # Try to delete the assistant if we couldn't store it
            try:
                client.beta.assistants.delete(assistant.id)
            except:
                pass
            raise HTTPException(status_code=500, detail=f"Error storing assistant data: {str(e)}")
        
        return assistant
    except Exception as e:
        print(f"[ERROR] create_assistant: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating assistant: {str(e)}")

async def get_or_create_assistant(org_id: UUID, domain_name: str = None, expert_id: UUID = None, expert_name: str = None, client_id: UUID = None, memory_type: str = "expert", model: str = "gpt-4o"):
    """
    Get an existing assistant or create a new one
    
    Args:
        expert_name: Name of the expert
        memory_type: Type of memory to use (llm, domain, expert, client)
        model: OpenAI model to use
        
    Returns:
        Assistant object with ID
    """
    try:
        print(f"[DEBUG] get_or_create_assistant: Looking for assistant for expert '{expert_name}' with memory type '{memory_type}'")
        domain_id = None
        if domain_name:
            domain_id = await get_domain_id(org_id, domain_name)
        query = supabase.table("assistants").select("*").eq("memory_type", memory_type)
        match memory_type:
            case "llm" | "organization":
                query = query.eq("vector_name", str(org_id))
            case "domain":
                query = query.eq("vector_name", str(domain_id))
            case "expert":
                query = query.eq("vector_name", str(expert_id))
            case "client":
                if client_id is None:
                    raise HTTPException(status_code=400, detail="client_id is required for client memory type")
                query = query.eq("vector_name", str(client_id))
            case "myclient":
                if client_id is None:
                    raise HTTPException(status_code=400, detail="client_id is required for myclient memory type")
                query = query.eq("vector_name", str("myclient"+str(client_id)))
            case _:
                raise HTTPException(status_code=400, detail="Invalid memory type")
            

        result = query.execute()
        
        if result.data and len(result.data) > 0:
            assistant_id = result.data[0].get("assistant_id")
            print(f"[DEBUG] get_or_create_assistant: Found existing assistant with ID: {assistant_id}")
            
            # Get the assistant from OpenAI
            try:
                assistant = client.beta.assistants.retrieve(assistant_id)
                return assistant
            except Exception as e:
                print(f"[ERROR] get_or_create_assistant: Error retrieving assistant: {str(e)}")
                # If the assistant doesn't exist in OpenAI, create a new one
                print(f"[DEBUG] get_or_create_assistant: Creating new assistant since retrieval failed")
                return await create_assistant(org_id, domain_name, expert_id, expert_name, client_id, memory_type, model)
        else:
            # Create a new assistant
            print(f"[DEBUG] get_or_create_assistant: No existing assistant found, creating new one")
            return await create_assistant(org_id, domain_name, expert_id, expert_name, client_id, memory_type, model)
    except Exception as e:
        print(f"[ERROR] get_or_create_assistant: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting or creating assistant: {str(e)}")

async def create_thread():
    """
    Create a new thread for conversation
    
    Returns:
        Thread object with ID
    """
    try:
        print(f"[DEBUG] create_thread: Creating new thread")
        thread = client.beta.threads.create()
        return thread
    except Exception as e:
        print(f"[ERROR] create_thread: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating thread: {str(e)}")

async def add_message_to_thread(thread_id: str, content: str, role: str = "user"):
    """
    Add a message to a thread
    
    Args:
        thread_id: ID of the thread
        content: Message content
        role: Message role (user or assistant)
        
    Returns:
        Message object
    """
    try:
        print(f"[DEBUG] add_message_to_thread: Adding message to thread {thread_id}")
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role=role,
            content=content
        )
        return message
    except Exception as e:
        print(f"[ERROR] add_message_to_thread: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error adding message to thread: {str(e)}")

async def run_thread(thread_id: str, assistant_id: str):
    """
    Run a thread with an assistant
    
    Args:
        thread_id: ID of the thread
        assistant_id: ID of the assistant
        
    Returns:
        Run object
    """
    try:
        print(f"[DEBUG] run_thread: Running thread {thread_id} with assistant {assistant_id}")
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        return run
    except Exception as e:
        print(f"[ERROR] run_thread: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error running thread: {str(e)}")

async def get_run_status(thread_id: str, run_id: str):
    """
    Get the status of a run
    
    Args:
        thread_id: ID of the thread
        run_id: ID of the run
        
    Returns:
        Run object
    """
    try:
        print(f"[DEBUG] get_run_status: Getting status of run {run_id} in thread {thread_id}")
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run_id
        )
        return run
    except Exception as e:
        print(f"[ERROR] get_run_status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting run status: {str(e)}")

async def get_thread_messages(thread_id: str, limit: int = 10):
    """
    Get messages from a thread
    
    Args:
        thread_id: ID of the thread
        limit: Maximum number of messages to retrieve
        
    Returns:
        List of messages
    """
    try:
        print(f"[DEBUG] get_thread_messages: Getting messages from thread {thread_id}")
        messages = client.beta.threads.messages.list(
            thread_id=thread_id,
            limit=limit
        )
        return messages
    except Exception as e:
        print(f"[ERROR] get_thread_messages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting thread messages: {str(e)}")

async def wait_for_run_completion(thread_id: str, run_id: str, max_wait_seconds: int = 60):
    """
    Wait for a run to complete
    
    Args:
        thread_id: ID of the thread
        run_id: ID of the run
        max_wait_seconds: Maximum time to wait in seconds
        
    Returns:
        Run object when complete
    """
    import time
    import asyncio
    
    try:
        print(f"[DEBUG] wait_for_run_completion: Waiting for run {run_id} to complete")
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            run = await get_run_status(thread_id, run_id)
            
            if run.status in ["completed", "failed", "cancelled", "expired"]:
                return run
            
            # Wait a bit before checking again
            await asyncio.sleep(1)
        
        # If we get here, we timed out
        print(f"[WARNING] wait_for_run_completion: Timed out waiting for run {run_id} to complete")
        return await get_run_status(thread_id, run_id)
    except Exception as e:
        print(f"[ERROR] wait_for_run_completion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error waiting for run completion: {str(e)}")

async def get_assistant_response(thread_id: str, run_id: str):
    """
    Get the assistant's response from a completed run
    
    Args:
        thread_id: ID of the thread
        run_id: ID of the run
        
    Returns:
        Assistant's response text with source citations removed
    """
    try:
        print(f"[DEBUG] get_assistant_response: Getting response from run {run_id}")
        
        # Get the messages from the thread
        messages = await get_thread_messages(thread_id, limit=1)
        
        if not messages.data:
            return "No response from assistant."
        
        # Get the latest message (should be from the assistant)
        latest_message = messages.data[0]
        
        if latest_message.role != "assistant":
            return "No response from assistant."
        
        # Extract the text from the message content
        response_text = ""
        for content_item in latest_message.content:
            if content_item.type == "text":
                response_text += content_item.text.value
        
        # Remove source citations like 【4:6†source】 using regex
        import re
        cleaned_response = re.sub(r'【\d+:\d+†source】', '', response_text)
        
        print(f"[DEBUG] get_assistant_response: Removed source citations from response")
        return cleaned_response
    except Exception as e:
        print(f"[ERROR] get_assistant_response: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting assistant response: {str(e)}")


async def query_expert_with_assistant(org_id: UUID, expert_id: UUID, expert_name: str, domain_name: str, client_id: UUID, query: str, memory_type: str = "expert", thread_id: str = None):
    """
    Query an expert using the OpenAI Assistant API
    
    Args:
        org_id: ID of the organization
        expert_id: ID of the expert
        expert_name: Name of the expert
        domain_name: Name of the domain
        client_id: ID of the client
        query: User query
        memory_type: Type of memory to use (llm, domain, expert, client)
        thread_id: Optional thread ID for continuing a conversation
        
    Returns:
        Dictionary with response, thread_id, and run_id
    """
    try:
        
        # Get or create the assistant
        assistant = await get_or_create_assistant(org_id, domain_name, expert_id, expert_name, client_id, memory_type)
        print(f"[DEBUG] query_expert_with_assistant: Querying with memory type '{memory_type}' and assistant id '{assistant.id}'")
        
        # Create a thread if one wasn't provided
        if not thread_id:
            thread = await create_thread()
            thread_id = thread.id
        
        # Add the user message to the thread
        await add_message_to_thread(thread_id, query)
        
        # Run the thread with the assistant
        run = await run_thread(thread_id, assistant.id)
        
        # Wait for the run to complete
        run = await wait_for_run_completion(thread_id, run.id)
        
        # Get the assistant's response
        response = await get_assistant_response(thread_id, run.id)
        
        return {
            "response": {"text": response},
            "thread_id": thread_id,
            "run_id": run.id,
            "status": run.status
        }
    except Exception as e:
        print(f"[ERROR] query_expert_with_assistant: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying expert with assistant: {str(e)}")

# ----- Unused functions -----
async def upload_to_supabase_storage(file_content: str, file_name: str) -> str:
    """
    Upload a file to Supabase storage and return the URL
    """
    try:
        # Upload the file to Supabase storage
        response = supabase.storage.from_("documents").upload(
            file_name, 
            file_content.encode('utf-8'),
            file_options={"content-type": "text/markdown"}
        )
        
        # Get the public URL
        file_url = supabase.storage.from_("documents").get_public_url(file_name)
        return file_url
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading to Supabase storage: {str(e)}")

async def create_vector_index(documents: List[str], namespace: str) -> str:
    """
    Create a vector index using OpenAI's vectorStores API
    """
    try:
        print(f"[DEBUG] create_vector_index: Starting with {len(documents)} documents for namespace '{namespace}'")
        
        # Prepare the documents for vector store creation
        vector_docs = []
        for i, doc in enumerate(documents):
            try:
                vector_docs.append({
                    "id": f"doc_{i}",
                    "text": doc,
                    "metadata": {"source": namespace}
                })
                if i % 10 == 0 and i > 0:
                    print(f"[DEBUG] create_vector_index: Processed {i}/{len(documents)} documents")
            except Exception as e:
                print(f"[ERROR] create_vector_index: Error processing document {i}: {str(e)}")
                print(f"[ERROR] Document content type: {type(doc)}")
                if isinstance(doc, str):
                    print(f"[ERROR] Document length: {len(doc)}")
                    print(f"[ERROR] Document preview: {doc[:100]}...")
                raise
        
        print(f"[DEBUG] create_vector_index: Creating vector store with name 'Vector Store - {namespace}'")
        try:
            # Create a vector store using the client.vector_stores.create method
            vector_store = client.vector_stores.create(
                name=f"Vector Store - {namespace}",
                type="text",
                vector_dimensions=1536,  # Default for text-embedding-ada-002
                model="text-embedding-ada-002",
                content_type="application/json"
            )
            print(f"[DEBUG] create_vector_index: Vector store created with ID: {vector_store.id}")
        except Exception as e:
            print(f"[ERROR] create_vector_index: Failed to create vector store: {str(e)}")
            raise
        
        # Add documents to the vector store
        batch_size = 100  # Process in batches to avoid API limits
        print(f"[DEBUG] create_vector_index: Adding documents in batches of {batch_size}")
        for i in range(0, len(vector_docs), batch_size):
            batch = vector_docs[i:i+batch_size]
            batch_end = min(i+batch_size, len(vector_docs))
            print(f"[DEBUG] create_vector_index: Processing batch {i}-{batch_end} of {len(vector_docs)}")
            try:
                client.vector_stores.add_vectors(
                    vector_store_id=vector_store.id,
                    vectors=batch
                )
                print(f"[DEBUG] create_vector_index: Successfully added batch {i}-{batch_end}")
            except Exception as e:
                print(f"[ERROR] create_vector_index: Failed to add vectors batch {i}-{batch_end}: {str(e)}")
                raise
        
        print(f"[DEBUG] create_vector_index: Successfully created vector store with ID: {vector_store.id}")
        return vector_store.id
    except Exception as e:
        print(f"[ERROR] create_vector_index: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating vector index: {str(e)}")

async def query_vector_index(query: str, vector_store_ids: list = None, context: str = "") -> dict:
    """
    Query a vector index using OpenAI's vectorStores API with file_search tool
    If vector_store_ids is None, use LLM memory (no vector search)
    """
    try:
        print(f"[DEBUG] query_vector_index: Starting query '{query}' with vector_store_ids '{vector_store_ids}'")

        try:
            # Use LLM directly if no vector_store_ids provided
            if not vector_store_ids:
                print(f"[DEBUG] query_vector_index: No vector_store_ids provided, using LLM directly")
                response = client.responses.create(
                    model="gpt-4o",
                    input=[
                            {"role": "system", "content": context},
                            {"role": "user", "content": query}
                        ],
                    temperature=0
                )
            else:
                # Use vector search
                print(f"[DEBUG] query_vector_index: Creating OpenAI response with file_search tool")
                response = client.responses.create(
                    model="gpt-4o",
                    input=[
                            {"role": "system", "content": context},
                            {"role": "user", "content": query}
                        ],
                    tools=[
                        {
                            "type": "file_search",
                            "vector_store_ids": vector_store_ids,
                            "max_num_results": 2
                        }
                    ],
                    include=["file_search_call.results"],
                    temperature=0
                )
            print(f"[DEBUG] query_vector_index: Response type: {type(response)}")
        except Exception as e:
            print(f"[ERROR] query_vector_index: Failed to create OpenAI response: {str(e)}")
            raise

        # Process the response
        print(f"[DEBUG] query_vector_index: Processing response")
        
        # Extract the text from the response using our helper function
        actual_text = extract_text_from_response(response)
        print(f"[DEBUG] query_vector_index: Extracted text: {actual_text[:50]}...")
        
        # Ensure we have a string
        if not isinstance(actual_text, str):
            print(f"[DEBUG] query_vector_index: Converting non-string text to string")
            actual_text = str(actual_text)
        return {"text": actual_text, "citations": None}
    except HTTPException as e:
        print(f"[ERROR] query_vector_index: Error in vector search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error in vector search: {str(e)}")

#check for status as 'completed'
async def check_vector_store_status(client, vector_store_id: str):
    try:
        result = client.vector_stores.files.list(
            vector_store_id=vector_store_id
        )
        return result
    except Exception as e:
        print(f"Error checking vector store status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking vector store status: {str(e)}")

async def check_batch_status(client, vector_store_id: str, batch_id: str):
    """
    Check the status of a file batch operation
    
    Args:
        client: OpenAI client
        vector_store_id: ID of the vector store
        batch_id: ID of the batch operation to check
        
    Returns:
        Batch status information
    """
    try:
        result = client.vector_stores.file_batches.retrieve(
            vector_store_id=vector_store_id,
            file_batch_id=batch_id
        )
        print(f"Batch status: {result.status}")
        return result
    except Exception as e:
        print(f"Error checking batch status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking batch status: {str(e)}")
