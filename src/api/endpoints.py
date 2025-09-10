from datetime import datetime
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from typing import List, Optional, Dict, Any
import json
import os
import shutil
import random
import copy
from uuid import UUID
from database import supabase
from models import (
    Expert, ExpertUpdate,
    QueryRequest, JsonStringRequest,
    DeleteVectorRequest, DomainBatchCreate,
    DomainCreate, DomainFilesRequest,
    FilesConfigRequest, PersonaGenerationRequest,
    UpdateVectorStoreRequest,
    UpdateExpertPersonaRequest,InitializeExpertMemoryRequest,
    InitializeMyClientMemoryRequest, CreateVector,
    UpdateRequest, ClientCreate, OrgCreate,
    InitializeOrgMemoryRequest, PatientCreate
)

from utils import (
    create_vector_store, 
    add_documents_to_vector_store,
    delete_vector_index,
    edit_vector_store, client,
    generate_persona_from_qa,
    query_expert_with_assistant,
    validate_file_paths,
    get_domain_id,
    get_query_for_vector_store,
    parse_domain_config_file,
    update_expert_with_domains,
    update_domains_with_experts,
    check_document_urls, get_file_ids
)

router = APIRouter()

@router.post("/memory/org/initialize", response_model=dict)
async def initialize_org_memory(request: InitializeOrgMemoryRequest):
    """
    Initialize a client's memory by:
    1. Creating client if it doesn't exist
    2. Create a client vector store with expert and domain reference
    3. Add files to client vector store
    """
    try:
        print(f"Initializing memory for client: {request.org_name}")

        # Step 1: Create org if org doesn't exist
        print("Step 1: Creating org if org doesn't exist")
        org_request = OrgCreate(org_name=request.org_name)
        org_result = await create_update_org(org_request)
        org_id = org_result["org_id"]
    
        # Create a filename with date_time, expert_name and client_name
        if (request.document_urls or request.pdf_documents):
            # Step 2: Create org vector store if it doesn't exist
            print("Step 2: Create org vector store if it doesn't exist")
            org_vs_request = CreateVector(memory_type = 'organization', org_id=org_id)
            org_vs_result = await create_or_get_vector(org_vs_request)
            org_vector_id = org_vs_result["vector_id"]
 
            # Step 3: Add files to org vector store
            print("Step 3: Adding files to org vector store")
            org_request = FilesConfigRequest(
                memory_type = 'organization',
                vector_id=org_vector_id,
                org_id=org_id,
                document_urls=request.document_urls,
                pdf_documents=request.pdf_documents,
            )
            await add_files_to_vector(org_request)
        
        return {
            "org_name": request.org_name,
            "org_id": org_id,
            "status": "success",
            "message": f"Successfully created org in clone {request.org_name}",
        }
    except Exception as e:
        print(f"Error creating org in clone: {str(e)}")
        # Return partial success with details about what succeeded and what failed
        return {
            "org_name": request.org_name,
            "org_id": org_id,
            "status": "partial_success",
            "message": f"Partially created org in clone {request.org_name}. Some steps may have failed: {str(e)}",
        }

# Create domain vectors and add files for multiple domains
@router.post("/domains/initialize", response_model=dict)
async def initialize_domains(request: DomainBatchCreate):
    """
    Create multiple domains with their vector stores and add files to each domain.
    
    For each domain in the list:
    1. Create the domain and its vector store
    2. Add files from document_urls and pdf_documents to the domain vector
    
    Returns:
        dict: Results for each domain with status and file information
    """
    try:
        results = {
            "org_id": request.org_id,
            "domains": []
        }
        
        # Process each domain
        for domain_entry in request.domains:
            domain_name = domain_entry.get("domain_name")
            document_urls = domain_entry.get("document_urls", {})
            pdf_documents = domain_entry.get("pdf_documents", {})
            other_doc = domain_entry.get("other_doc", {})
            
            print(f"Processing domain: {domain_name}")
            
            # Step 1: Create domain or get existing domain
            domain_request = DomainCreate(org_id=request.org_id, domain_name=domain_name)
            domain_result = await create_or_get_domain(domain_request)
            domain_id = domain_result["domain_id"]
            vector_id = None

            if(document_urls or pdf_documents or other_doc):
                vector_id_result = await create_or_get_vector(CreateVector(memory_type="domain", org_id=request.org_id, domain_name=domain_name))
                vector_id = vector_id_result.get("vector_id") if vector_id_result else None
                
                # Step 2: Add files to domain vector
                config_request = FilesConfigRequest(
                    memory_type='domain',
                    org_id=request.org_id,
                    domain_name=domain_name,
                    domain_id=domain_id,
                    vector_id=vector_id,
                    document_urls=document_urls,
                    pdf_documents=pdf_documents,
                    other_doc=other_doc
                )
            
                domain_files_result = await add_files_to_vector(config_request)
            
            # Add results for this domain
            domain_result = {
                "domain_name": domain_name,
                "domain_id": domain_id,
                "vector_id": vector_id,
            }
            
            results["domains"].append(domain_result)
            print(f"Completed processing for domain: {domain_name}")
        
        return results
    
    except Exception as e:
        print(f"Error creating domains with files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get domain documents for a list of domains
@router.post("/domains/documents", response_model=dict)
async def get_domain_documents(request: DomainFilesRequest):
    """
    For each domain name in the list, get their domain_id and then
    get their list of document_links and openai_file_id from the documents table
    where owner_id matches the domain_id.
    
    Returns:
        dict: Results for each domain with their documents
    """
    try:
        org_id = request.org_id
        domain_names = request.domain_name
        
        if not org_id:
            raise HTTPException(status_code=400, detail="org_id is required")
            
        if not domain_names:
            # If no domain names provided, get all domains for the organization
            all_domains = await get_domains(org_id)
            # Convert the list of domain dictionaries to a list of domain names
            domain_names = [domain["domain_name"] for domain in all_domains]
            
        print(f"Getting documents for {len(domain_names)} domains in organization {org_id}")
        
        results = {
            "org_id": org_id,
            "domains": []
        }
        
        # Process each domain name
        for domain_name in domain_names:
            # Step 1: Get domain_id for the domain_name
            domain_result = supabase.table("domains").select("id").eq("org_id", org_id).eq("domain_name", domain_name).execute()
            
            if not domain_result.data:
                print(f"Domain '{domain_name}' not found for organization {org_id}")
                continue
                
            domain_id = domain_result.data[0]["id"]
            
            # Step 2: Get documents where owner_id matches domain_id
            documents_result = supabase.table("documents").select("name, document_link, openai_file_id").eq("owner_id", str(domain_id)).execute()
            
            domain_info = {
                "domain_name": domain_name,
                "domain_id": domain_id,
                "documents": []
            }
            
            if documents_result.data:
                domain_info["documents"] = documents_result.data
                print(f"Found {len(documents_result.data)} documents for domain '{domain_name}'")
            else:
                print(f"No documents found for domain '{domain_name}'")
            
            results["domains"].append(domain_info)
        
        return results
        
    except Exception as e:
        print(f"Error getting domain documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/memory/expert/initialize", response_model=dict)
async def initialize_expert_memory(request: InitializeExpertMemoryRequest):
    """
    Initialize an expert's memory by:
    1. Creating domain if it doesn't exist
    2. Adding files to domain vector from config file
    3. Generating persona from QA data
    4. Creating expert with generated persona
    5. Adding files to expert vector
    """
    # Initialize variables at the beginning to ensure proper scope
    results = {}
    expert_id = None
    vector_id = None
    expert_files_result = None
    
    try:
        # Validate required request fields
        if not request.expert_name:
            raise ValueError("expert_name is required")
        if not request.domain_name:
            raise ValueError("domain_name is required")
        if not request.org_id:
            raise ValueError("org_id is required")
            
        print(f"Initializing memory for expert: {request.expert_name} in domain: {request.domain_name}")
        
        '''
        TODO expose required domain documents to expert using get_domain_documents(request.org_id, request.domain_name)
        '''

        # Step 1: Generate persona from QA data
        
        if request.qa_pairs:
            print("Step 1: Generating persona from QA data")
            persona_request = PersonaGenerationRequest(qa_pairs=request.qa_pairs)
            persona_result = await generate_persona_from_qa_data(persona_request)
            persona_text = persona_result.get("persona", "")
            results["persona"] = persona_result
            print(f"Persona result: {persona_result}")
        else:
            persona_text = ""
            results["persona"] = ""
            print("Warning: Expert persona is empty")
        
        # Step 2: Create expert with generated persona
        print("Creating expert")
        expert_request = Expert(
            name=request.expert_name,
            domains=request.domain_name,
            context=persona_text,  # Use the generated persona as context
            org_id=request.org_id
        )
        expert_result = await create_or_get_expert(expert_request)
        if not expert_result:
            raise ValueError("Failed to create or get expert vector")
        expert_id = expert_result.get("expert_id")

        
        # Step 3: Add files to expert vector
        # Initialize document collections with empty defaults if not provided
        document_urls = request.document_urls if request.document_urls else {}
        pdf_documents = request.pdf_documents if request.pdf_documents else {}
        other_doc = request.other_doc if request.other_doc else {}
        
        if (document_urls or pdf_documents or other_doc):
            print("Adding files to expert vector")
            # Create a vector store for the new expert
            vector_id_result = await create_or_get_vector(CreateVector(memory_type="expert", org_id=expert.org_id, expert_id=expert_id))
            vector_id = vector_id_result.get("vector_id") if vector_id_result else None
            print(f"Created new vector ID for new expert: {vector_id}")
        
            if not expert_id or not vector_id:
                raise ValueError("Expert creation succeeded but returned invalid ID or vector ID")
        

            expert_files_request = FilesConfigRequest(
                memory_type='expert',
                expert_id=expert_id,
                org_id=request.org_id,
                vector_id=vector_id,
                document_urls=document_urls,
                pdf_documents=pdf_documents,
                other_doc=other_doc
            )
            expert_files_result = await add_files_to_vector(expert_files_request)
            print(f"Expert files result: {expert_files_result}")
        
        return {
            "expert_name": request.expert_name,
            "expert_id": expert_id,
            "status": "success",
            "message": f"Successfully initialized memory for expert {request.expert_name} in domain {request.domain_name}",
            "results": results
        }
    except Exception as e:
        print(f"Error initializing expert memory: {str(e)}")
        # Return partial success with details about what succeeded and what failed
        return {
            "expert_name": request.expert_name,
            "expert_id": expert_id,
            "status": "partial_success",
            "message": f"Partially initialized memory for expert {request.expert_name}. Some steps may have failed: {str(e)}",
            "results": results
        }

@router.post("/memory/client/initialize", response_model=dict)
async def initialize_client_memory(request: InitializeMyClientMemoryRequest):
    """
    Initialize a client's memory by:
    1. Creating client if it doesn't exist
    2. Create a client vector store with expert and domain reference
    3. Add files to client vector store
    """
    # Initialize variables at the beginning to ensure proper scope
    results = {}
    overall_client_id = None
    overall_client_data = None
    expert_client_id = None
    expert_client_data = None
    overall_client_vector_id = None
    expert_client_vector_id = None
    overall_doc = {}
    expert_client_doc = {}
    
    try:
        # Validate required request fields
        if not request.client_name:
            raise ValueError("client_name is required")
        if not request.org_id:
            raise ValueError("org_id is required")
        if not request.expert_id:
            raise ValueError("expert_id is required")
        if not request.org_client_id:
            raise ValueError("org_client_id is required")
        if not request.client_data_jsonb:
            raise ValueError("client_data_jsonb is required")
        if not request.consultation_id:
            raise ValueError("consultation_id is required")
        if not request.created_time:
            raise ValueError("created_time is required")
            
        # Step 1: Create client if client doesn't exist
        print("Step 1: Creating client if client doesn't exist")
        
        client_request = ClientCreate(
            org_client_id=request.org_client_id, 
            org_id=request.org_id, 
            expert_id=request.expert_id, 
            client_name=request.client_name, 
            client_data_jsonb=request.client_data_jsonb,
            consultation_id=request.consultation_id,
            created_time=request.created_time if request.created_time else "",
        )
        client_result = await create_update_client(client_request)
        
        if not client_result:
            raise ValueError("Failed to create or update client")
            
        overall_client_id = client_result.get("client_id")
        overall_client_data = client_result.get("client_data", {})
        expert_client_id = client_result.get("expert_client_id")
        expert_client_data = client_result.get("expert_client_data", {})
        
        if not overall_client_id or not expert_client_id:
            raise ValueError("Client creation succeeded but returned invalid IDs")
        
        # Step 2: Create client vector store if it doesn't exist
        print("Step 2: Create client vector store if it doesn't exist")
        # Create overall client vector store
        overall_client_vs_request = CreateVector(
            memory_type='client', 
            org_id=request.org_id, 
            client_id=overall_client_id
        )
        overall_client_vs_result = await create_or_get_vector(overall_client_vs_request)
        
        if not overall_client_vs_result:
            raise ValueError("Failed to create or get overall client vector store")
            
        overall_client_vector_id = overall_client_vs_result.get("vector_id")
        
        if not overall_client_vector_id:
            raise ValueError("Overall client vector store creation succeeded but returned invalid vector ID")

        # Create expert-specific client vector store
        expert_client_vs_request = CreateVector(
            memory_type='myclient', 
            org_id=request.org_id, 
            expert_id=request.expert_id, 
            client_id=expert_client_id
        )
        expert_client_vs_result = await create_or_get_vector(expert_client_vs_request)
        
        if not expert_client_vs_result:
            raise ValueError("Failed to create or get expert client vector store")
            
        expert_client_vector_id = expert_client_vs_result.get("vector_id")
        
        if not expert_client_vector_id:
            raise ValueError("Expert client vector store creation succeeded but returned invalid vector ID")
       
        # Prepare expert client document
        expert_client_doc_name = f"{request.consultation_id}_{request.expert_id}_{expert_client_id}"
        expert_client_doc = {expert_client_doc_name: expert_client_data}   

        # Prepare overall client document
        overall_doc_name = f"{request.consultation_id}_{request.org_id}_{overall_client_id}"
        overall_doc = {overall_doc_name: overall_client_data}

        # Step 3: Add files to overall client vector store
        print("Step 3a: Adding files to overall client vector store")
        # Initialize document collections with empty defaults if not provided
        document_urls = request.document_urls if request.document_urls else {}
        pdf_documents = request.pdf_documents if request.pdf_documents else {}
        
        overall_client_request = FilesConfigRequest(
            memory_type='client',
            vector_id=overall_client_vector_id,
            client_id=overall_client_id,
            other_doc=overall_doc,
            org_client_id=request.org_client_id,
            org_id=request.org_id,
            document_urls=document_urls,
            pdf_documents=pdf_documents
        )
        overall_result = await add_files_to_vector(overall_client_request)
        results["overall_client_vector"] = overall_result
        
        # Step 3b: Add files to expert-specific client vector store
        print("Step 3b: Adding files to expert-specific client vector store")
        expert_client_request = FilesConfigRequest(
            memory_type='myclient',
            vector_id=expert_client_vector_id,
            client_id=expert_client_id,
            other_doc=expert_client_doc,
            org_client_id=request.org_client_id,
            org_id=request.org_id,
            document_urls=document_urls,
            pdf_documents=pdf_documents
        )
        expert_result = await add_files_to_vector(expert_client_request)
        results["expert_client_vector"] = expert_result
        
        return {
            "client_name": request.client_name,
            "org_client_id": request.org_client_id,
            "status": "success",
            "message": f"Successfully initialized memory for client {request.client_name} in expert {request.expert_name if hasattr(request, 'expert_name') else ''}",
            "results": results
        }
    except Exception as e:
        print(f"Error initializing client memory: {str(e)}")
        # Return partial success with details about what succeeded and what failed
        return {
            "client_name": request.client_name,
            "org_client_id": request.org_client_id,
            "status": "partial_success",
            "message": f"Partially initialized memory for client {request.client_name}. Some steps may have failed: {str(e)}",
            "results": results
        }

@router.post("/1hat/add-patient", response_model=dict)
async def initialize_1hat_patient(request: PatientCreate):
    org_id = None
    expert_id = None
    client_id = None

    try:
        # Validate required request fields
        if not request.org_name:
            raise ValueError("Hospital Name is required")
        if not request.domain_name:
            raise ValueError("Specialty is required")
        if not request.expert_name:
            raise ValueError("Doctor Name is required")
        if not request.client_name:
            raise ValueError("Patient Name is required")
        if not request.org_client_id:
            raise ValueError("1hat patient ID is required")
        if not request.client_data_jsonb:
            raise ValueError("Patient Data is required")
        if not request.consultation_id:
            raise ValueError("Patient Consultation ID is required")
        if not request.created_time:
            raise ValueError("Record Created Time is required")
            
        print("Initializing org")
        inputs = InitializeOrgMemoryRequest(
            org_name=request.org_name,
            document_urls={},
            pdf_documents={}
        )
        try:
            org_result = await initialize_org_memory(inputs)
            if not org_result or "org_id" not in org_result:
                print(f"Error: initialize_org_memory returned invalid result: {org_result}")
                raise ValueError(f"Failed to initialize organization: invalid result")
                
            org_id = org_result.get("org_id")
            print(f"Successfully initialized org with ID: {org_id}")
        except Exception as e:
            print(f"Error in initialize_org_memory: {str(e)}")
            raise ValueError(f"Failed to initialize organization: {str(e)}")

        print("Initializing domain")
        inputs = DomainBatchCreate(
            org_id=org_id,
            domains=[{
                "domain_name": request.domain_name,
                "document_urls": {},
                "pdf_documents": {},
                "other_doc": {}
            }]
        )
        domain_result = await initialize_domains(inputs)
        domain_id = domain_result.get("domains")[0].get("domain_id")

        print("Initializing expert")
        inputs = InitializeExpertMemoryRequest(
            org_id=org_id,
            domain_name = [request.domain_name],
            expert_name=request.expert_name,
            qa_pairs=[],
            document_urls={},
            pdf_documents={},
            other_doc={}
        )
        expert_result = await initialize_expert_memory(inputs)
        expert_id = expert_result.get("expert_id")

        client_data_raw=request.client_data_jsonb if request.client_data_jsonb else "{}"
        # Create a JsonStringRequest object to pass to parse_json_string
        print(f"[API DEBUG] initialize_1hat_patient: Client data raw: {type(client_data_raw)}")
        json_request = JsonStringRequest(json_string=client_data_raw)
        print(f"[API DEBUG] initialize_1hat_patient: Json request: {type(json_request)}")
        client_data_jsonb=await parse_json_string(json_request)

        print("Initializing client")
        inputs = InitializeMyClientMemoryRequest(
            org_id=org_id,
            expert_id=expert_id,
            org_client_id=request.org_client_id,
            client_name=request.client_name,
            client_data_jsonb=client_data_jsonb,
            consultation_id=request.consultation_id,
            created_time=request.created_time if request.created_time else "",
            document_urls={},
            pdf_documents={},
            other_doc={},
        )
        client_result = await initialize_client_memory(inputs)
        client_id = client_result.get("org_client_id")
        return {
            "status": "success",
            "message": "Successfully initialized 1hat patient memory"
        }
    except Exception as e:
        print(f"Error initializing 1hat patient memory: {str(e)}")
        return {
            "status": "error",
            "message": f"Error initializing 1hat patient memory: {str(e)}"
        }
        
@router.post("/query-clone")
async def query_clone(request: QueryRequest):
    """
    Query an expert using the OpenAI Assistant API
    """
    try:
        thread_id = request.thread_id if hasattr(request, 'thread_id') else None
        org_id = None
        if request.org_name:
            org_id = await get_org_id(request.org_name)
            print (f"[API DEBUG] query_clone: Organization ID: {org_id}")
        if not org_id:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        expert_id = None
        if request.expert_name:
            expert_id = await get_expert_id(org_id, request.domain_name, request.expert_name)
            print (f"[API DEBUG] query_clone: Expert ID: {expert_id}")
            if not expert_id:
                raise HTTPException(status_code=404, detail="Expert not found")

        client_id = None
        if (request.memory_type == "client" or request.memory_type == "myclient"):
            print (f"[API DEBUG] query_clone: OrgClient ID: {request.org_client_id}")
            client_id = await get_client_id(org_id, request.org_client_id, expert_id, request.memory_type)
            print (f"[API DEBUG] query_clone: Client ID: {client_id}")
            if not client_id:
                raise HTTPException(status_code=404, detail="Client not found")
        
        result = await query_expert_with_assistant(
            org_id=org_id,
            expert_id=expert_id,
            expert_name=request.expert_name,
            domain_name=request.domain_name,
            client_id=client_id,
            query=request.query,
            memory_type=request.memory_type,
            thread_id=thread_id
        )
        
        return result
    except Exception as e:
        print(f"[ERROR] query_expert_with_assistant_endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update", response_model=dict)
async def update(request: UpdateRequest):
    """
    Update an entity's memory by:
    1. Adding files to domain vector from config file
    2. Generating persona from QA data
    3. Updating entity with generated persona
    4. Adding files to entity vector
    """
    try:        
        results = {}
        
        org_id = None
        if request.org_name:
            org_id = await get_org_id(request.org_name)
        if not org_id:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        expert_id = None
        if request.expert_name:
            expert_id = await get_expert_id(org_id, request.domain_name, request.expert_name)
            if not expert_id:
                raise HTTPException(status_code=404, detail="Expert not found")

        client_id = None
        if (request.memory_type == "client" or request.memory_type == "myclient"):
            client_id = await get_client_id(org_id, request.org_client_id, expert_id, request.memory_type)
            if not client_id:
                raise HTTPException(status_code=404, detail="Client not found")
        
        print(f"[API DEBUG] update: Step 1: Creating or getting vector store")
        vector_request = CreateVector(
            memory_type = request.memory_type,
            org_id=org_id,
            expert_id=expert_id,
            client_id=client_id,
            domain_name=request.domain_name,
        )
        vector_result = await create_or_get_vector(vector_request)
        vector_id = vector_result["vector_id"]
        print(f"[API DEBUG] update: Vector store ID: {vector_id}")

        # Step 2: Update entity with new context
        if request.qa_pairs:
            print(f"[API DEBUG] update: Step 2: Updating expert {expert_id} with {len(request.qa_pairs)} QA pairs")
            update_persona_request = UpdateExpertPersonaRequest(
                expert_id=expert_id,
                qa_pairs=request.qa_pairs
            )
            try:
                persona_result = await update_expert_persona(update_persona_request)
                print(f"[API DEBUG] update: Expert persona updated successfully: {persona_result}")
                results['persona_update'] = 'success'
            except Exception as persona_error:
                print(f"[API ERROR] update: Failed to update expert persona: {str(persona_error)}")
                results['persona_update'] = f'failed: {str(persona_error)}'
        
        # Step 3: Updating files in vector store
        print(f"[API DEBUG] update: Step 3: Adding files to vector store {vector_id}")
        if request.document_urls or request.pdf_documents or request.other_doc:
            files_request = UpdateVectorStoreRequest(
                memory_type = request.memory_type,
                org_id=org_id,
                domain_name=request.domain_name,
                expert_id=expert_id,
                client_id=client_id,
                document_urls=request.document_urls,
                pdf_documents=request.pdf_documents,
                other_doc=request.other_doc
            )
            
            try:
                vector_result = await update_vector_store(files_request)
                print(f"[API DEBUG] update: Vector store updated successfully: {vector_result}")
                results['vector_update'] = 'success'
                results['vector_details'] = {
                    'new_file_count': len(vector_result.get('new_file_ids', [])),
                    'batch_id': vector_result.get('batch_id')
                }
            except Exception as vector_error:
                print(f"[API ERROR] update: Failed to update vector store: {str(vector_error)}")
                results['vector_update'] = f'failed: {str(vector_error)}'
        
        print(f"[API DEBUG] update: Update process completed successfully")
        return {
            "status": "success",
            "message": f"Successfully updated memory for {request.memory_type}",
            "results": results
        }
    except Exception as e:
        print(f"[API ERROR] update: Error updating memory: {str(e)}")
        print(f"[API ERROR] update: Error type: {type(e).__name__}")
        import traceback
        print(f"[API ERROR] update: Traceback: {traceback.format_exc()}")
        
        # Return partial success with details about what succeeded and what failed
        return {
            "status": "partial_success",
            "message": f"Partially updated memory for {request.memory_type}. Some steps may have failed: {str(e)}",
            "results": results
        }

# PDF Upload endpoint
@router.post("/upload-pdf/")
async def upload_pdf_file(file: UploadFile = File(...), pdf_name: str = Form(...)):
    """
    Upload PDF file and save to Docs folder
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Check file size - first read the file into memory to get its size
        contents = await file.read()
        file_size_mb = len(contents) / (1024 * 1024)  # Convert bytes to MB
        
        # Reset file position for later use
        await file.seek(0)
        
        # Validate file size
        if file_size_mb > 200:
            raise HTTPException(
                status_code=400, 
                detail=f"File size ({file_size_mb:.2f}MB) exceeds the maximum limit of 200MB. Please upload files smaller than 100MB for optimal processing."
            )
        
        # Warning for large files
        warning_message = None
        if file_size_mb > 100:
            warning_message = f"Warning: Large file detected ({file_size_mb:.2f}MB). Processing may take longer than usual. For optimal performance, consider splitting into smaller files under 100MB."
            print(warning_message)
        
        # Create target folder path (../../Docs from src/api)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        docs_folder = os.path.join(current_dir, "..", "..", "Docs")
        os.makedirs(docs_folder, exist_ok=True)
        
        # Create filename with .pdf extension if not present
        filename = pdf_name if pdf_name.endswith('.pdf') else f"{pdf_name}.pdf"
        file_path = os.path.join(docs_folder, filename)
        
        # Save file directly using the contents we already read
        with open(file_path, "wb") as buffer:
            #since file is already in memory to figure size, buffer.write is used. Else for large files shutil is better
            #shutil.copyfileobj(file.file, buffer) 
            buffer.write(contents)
        
        print(f"Uploaded PDF '{pdf_name}' ({file_size_mb:.2f}MB) to {file_path}")
        
        response = {
            "pdf_name": pdf_name,
            "file_path": file_path,
            "filename": filename,
            "file_size_mb": round(file_size_mb, 2),
            "message": f"PDF '{pdf_name}' uploaded successfully to {file_path}"
        }
        
        # Add warning to response if applicable
        if warning_message:
            response["warning"] = warning_message
            
        return response
        
    except Exception as e:
        print(f"Error uploading PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload PDF: {str(e)}")

@router.post("/parse-json-string")
async def parse_json_string(request: JsonStringRequest) -> dict:
    try:
        # The content is a JSON string that needs to be parsed
        print(f"[API DEBUG] parse_json_string: Received JSON string: {type(request.json_string)}")
        json_str = request.json_string.strip()
        sample_json = None
        
        # Parse the JSON string - it's a string containing escaped JSON
        if json_str.startswith('"') and json_str.endswith('"'):
            print(f"[API DEBUG] parse_json_string: JSON string starts and ends with quotes")
            # This is a JSON string containing escaped JSON
            # First, parse the outer JSON string
            try:
                json_content = json.loads(json_str)
                print(f"JSON content: {json_content}")
                
                # Check if the content is still a string with escaped characters
                if isinstance(json_content, str):
                    # Try to parse the inner JSON content
                    try:
                        # Remove any remaining escape characters
                        unescaped_content = json_content.replace('\\"', '"').replace('\\\\', '\\')
                        sample_json = json.loads(unescaped_content)
                        print(f"Sample JSON after unescaping: {sample_json}")
                    except json.JSONDecodeError as inner_error:
                        print(f"[API DEBUG] parse_json_string: Error parsing inner JSON after unescaping: {str(inner_error)}")
                        try:
                            # Try direct parsing without unescaping
                            sample_json = json.loads(json_content)
                            print(f"Sample JSON from direct parsing: {sample_json}")
                        except json.JSONDecodeError as direct_error:
                            print(f"[API DEBUG] parse_json_string: Error with direct parsing: {str(direct_error)}")
                            # Use the string content directly as a last resort
                            sample_json = json_content
                            print(f"Using JSON content directly: {sample_json}")
                else:
                    # If json_content is already a dict or other non-string type, use it directly
                    sample_json = json_content
                    print(f"Using parsed JSON directly: {type(sample_json)}")
            except json.JSONDecodeError as outer_error:
                print(f"[API DEBUG] parse_json_string: Error parsing outer JSON: {str(outer_error)}")
                raise
        else:
            # Try to parse as a regular JSON object
            print(f"[API DEBUG] parse_json_string: JSON string does not start and end with quotes")
            try:
                # First try direct JSON parsing
                sample_json = json.loads(json_str)
                print(f"Sample JSON parsed directly: {sample_json}")
            except json.JSONDecodeError:
                # If that fails, try the brace counting approach
                print(f"[API DEBUG] parse_json_string: Direct parsing failed, trying brace counting")
                
                # Fall back to brace counting
                brace_count = 0
                end_pos = 0
                
                for i, char in enumerate(json_str):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                    if brace_count == 0 and brace_count > 0:
                        end_pos = i + 1
                        break
                                    
                if end_pos > 0:
                    first_json = json_str[:end_pos]
                    try:
                        sample_json = json.loads(first_json)
                        print(f"Sample JSON from brace counting: {sample_json}")
                    except json.JSONDecodeError:
                        sample_json = {}
                else:
                    sample_json = {}
                        
        # Validate that we have a proper JSON object (dict) before reporting success
        if sample_json is not None:
            # Check if it's a string with escaped characters (not fully parsed)
            if isinstance(sample_json, str) and ('\\"' in sample_json or '\\\\' in sample_json):
                print("[API DEBUG] parse_json_string: Warning - JSON still contains escape characters")
                try:
                    # Try one more time to parse with json.loads
                    test_json = json.loads(sample_json.replace('\\"', '"').replace('\\\\', '\\'))
                    print(f"[API DEBUG] parse_json_string: Successfully parsed after additional unescaping")
                    sample_json = test_json
                except json.JSONDecodeError:
                    print("[API DEBUG] parse_json_string: Could not fully parse JSON, but using best available result")
            
            # Final validation - check if we have a proper dictionary
            if isinstance(sample_json, dict):
                print("[API DEBUG] parse_json_string: Successfully loaded valid JSON dictionary")
                return {"data": sample_json, "message": "JSON parsed successfully"}
            else:
                print(f"[API DEBUG] parse_json_string: Result is not a dictionary, type: {type(sample_json)}")
                # Try to convert string to dict if possible
                if isinstance(sample_json, str):
                    try:
                        # Last attempt to convert string to dict using ast.literal_eval
                        import ast
                        dict_result = ast.literal_eval(sample_json)
                        if isinstance(dict_result, dict):
                            print("[API DEBUG] parse_json_string: Successfully converted string to dictionary")
                            return {"data": dict_result, "message": "JSON parsed successfully after conversion"}
                    except (SyntaxError, ValueError):
                        pass
                
                # If we got here, we couldn't get a proper dictionary
                print("[API DEBUG] parse_json_string: Warning - returning non-dictionary result")
                return {"data": sample_json, "message": "JSON parsed but not as a dictionary"}
        else:
            print("[API DEBUG] parse_json_string: Failed to parse JSON data")
            return {"data": None, "message": "Failed to parse JSON"}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

'''
@router.post("/parse-json-string")
async def parse_json_string(request: Dict[str, Any]) -> dict:
    try:
        # The content is already a JSON object
        json_data = request.get("json_data")
                        
        if not json_data:
            raise HTTPException(status_code=400, detail="Missing json_data field")
            
        # If json_data is a string (serialized JSON), parse it
        if isinstance(json_data, str):
            try:
                sample_json = json.loads(json_data)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON string in json_data")
        else:
            # It's already a parsed JSON object
            sample_json = json_data
            
        if sample_json:
            print("Loaded JSON data successfully")
            return {"data": sample_json, "message": "JSON parsed successfully"}
        else:
            print("Failed to parse JSON data")
            return {"data": None, "message": "Failed to parse JSON"}
            
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

'''
#________Helper functions (potential APIs)________

# Org creation function
def history_preserving_merge(existing_data: Dict[str, Any], new_data: Dict[str, Any], new_consultation_id:str, new_created_time:str) -> Dict[str, Any]:
    """
    Preserve full history of updates.
    - `_history` grows indefinitely, storing past states.
    - Latest record also gets its own timestamp.
    """
    result = {}
    
    #check always if this is an update to existing consultation id in existing_data
    if "consultation_id" in existing_data and existing_data['consultation_id']==new_consultation_id:
        #old_state.update(copy.deepcopy(new_data))
        for key, value in new_data.items():
            result[key] = copy.deepcopy(value)
        # Carry forward history if exists, else start fresh
        result["_history"] = copy.deepcopy(existing_data.get("_history", []))
        return result
    elif "_history" in existing_data:
        for i, item in enumerate(existing_data['_history']): # as existing_data['_history'] is a list
            if "consultation_id" in item and item['consultation_id']==new_consultation_id:
                # Carry forward history if exists, else start fresh
                result = copy.deepcopy(existing_data)
                
                if "consultation_id" in result['_history'][i] and result['_history'][i]['consultation_id']==new_consultation_id:
                    result['_history'][i]['data'].update(copy.deepcopy(new_data))
                    print("Updated existing consultation id in history")
                else:
                    print("Error: Consultation ID does not match between existing and new history to update")
                
                return result
    
    # Carry forward history if exists, else start fresh
    result["_history"] = copy.deepcopy(existing_data.get("_history", []))
    #if not, then this is a new consultation id that needs to be appended
    created_time = None
    consultation_id = None
    
    # Add snapshot of old state to history (excluding its _history) and placing consultation id and created time at top of dictionary
    old_state = copy.deepcopy(existing_data)
    if "_history" in old_state:
        del old_state["_history"]
    if "created_time" in old_state:
        created_time = old_state["created_time"]
        del old_state["created_time"]
    if "consultation_id" in old_state:
        consultation_id = old_state["consultation_id"]
        del old_state["consultation_id"]

    if old_state:
        result["_history"].append({
            "created_time": created_time,
            "consultation_id": consultation_id,
            "data": old_state
        })

    # Add new data as latest record with timestamp
    # result.update(copy.deepcopy(new_data)) -> Same result as below and much more efficient but less understandable
    for key, value in new_data.items():
        result[key] = copy.deepcopy(value)

    return result

def deep_merge(existing_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new dictionary with data from both sources.
    This version doesn't modify the input dictionaries but creates a new result.
    
    Args:
        existing_data: The existing data dictionary
        new_data: The new data dictionary to incorporate
        
    Returns:
        A new dictionary containing data from both sources
    """
    # Create a new result dictionary to avoid modifying inputs
    result = copy.deepcopy(existing_data)
    
    # Process each key in new_data
    for key, value in new_data.items():
        # Skip the _history key as it's handled separately
        if key == "_history":
            continue
            
        if key in result:
            if isinstance(value, dict) and isinstance(result[key], dict):
                # For nested dictionaries, recursively create a new merged dictionary
                result[key] = deep_merge(result[key], value)
            elif isinstance(value, list) and isinstance(result[key], list):
                # For lists, create a new list with all unique items
                combined_list = copy.deepcopy(result[key])
                for item in value:
                    if item != "N/A" and item not in combined_list:
                        combined_list.append(item)
                result[key] = combined_list
            else:
                # For scalar values, use the new value if it's not N/A
                if value != "N/A":
                    result[key] = copy.deepcopy(value)
        else:
            # Add new key-value pair
            result[key] = copy.deepcopy(value)
    
    return result

async def create_update_org(request: OrgCreate):
    """
    Create a new org with JSON data or update an existing org.
    Stores the data as both JSON text and JSONB in the database.
    Uses history-preserving merge to maintain a record of all updates.
    
    Returns:
        org_id: uuid
    """
    try:
        org_name = request.org_name
        print("Checking if org exist ", org_name)
        # Check if org already exists
        org_check = supabase.table("organizations").select("*").eq("org_name", org_name).execute()
        
        if len(org_check.data) > 0:
            # Organization already exists
            print("Updating existing org", org_name)
            # Just return the existing org data without updating
            return {
                "status": "success",
                "message": f"Organization '{org_name}' already exists",
                "org_id": org_check.data[0]["id"],
            }
        else:
            # Create new org
            # Initialize with history if it's a new org
            print("Creating new org ", org_name)
            
            insert_result = supabase.table("organizations").insert({
                "org_name": org_name,
            }).execute()            
            return {
                "status": "success",
                "message": f"Organization '{org_name}' created successfully with history tracking",
                "org_id": insert_result.data[0]["id"],
            }
    
    except Exception as e:
        print(f"Error creating/updating org: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating/updating org: {str(e)}")

# Client creation function
async def create_update_client(request: ClientCreate):
    """
    Create a new client with JSON data or update an existing client.
    Stores the data as both JSON text and JSONB in the database.
    Returns:
        client_id: uuid
        client_name: str
        org_client_id: int
        client_data_jsonb: dict
        client_data: dict
    """
    try:
        # Initialize variables
        client_name = request.client_name
        org_client_id = request.org_client_id
        consultation_id = request.consultation_id
        created_time = request.created_time
        org_id = request.org_id
        expert_id = request.expert_id
        client_data_jsonb = None
        if (request.client_data_jsonb):
            client_data_jsonb = request.client_data_jsonb
            if "consultation_id" not in client_data_jsonb:
                client_data_jsonb["consultation_id"] = consultation_id
            if "created_time" not in client_data_jsonb:
                client_data_jsonb["created_time"] = created_time
            print("Data received to update / append: ", client_data_jsonb)
        
        overall_result_client_data = None
        overall_result_client_id = None
        expert_result_client_data = None
        expert_result_client_id = None
        
        # Check if client already exists for that org
        client_check = supabase.table("clients").select("*").eq("client_name", client_name).eq("org_client_id", org_client_id).eq("org_id", org_id).is_("expert_id", "null").execute()
           # Check if client exists for that expert
        client_expert_check = supabase.table("clients").select("*").eq("client_name", client_name).eq("org_client_id", org_client_id).eq("org_id", org_id).eq("expert_id", expert_id).execute()
        
        if client_check and len(client_check.data) > 0:
            # Get existing client data and update it with new data
            print("Client exists for that org")
            existing_client_data_jsonb = client_check.data[0]["client_data_jsonb"]
            merged_data = existing_client_data_jsonb
            if client_data_jsonb:
                merged_data = history_preserving_merge(existing_client_data_jsonb, client_data_jsonb, consultation_id, created_time)
            # Update existing client
            update_result = supabase.table("clients").update({
                "client_data_jsonb": merged_data
                # Let the database handle the updated_at timestamp automatically
            }).eq("org_client_id", org_client_id).eq("org_id", org_id).is_("expert_id", "null").execute()
            
            overall_result_client_data = update_result.data[0]["client_data_jsonb"]
            overall_result_client_id = update_result.data[0]["id"]
        else:
            # Create new client
            insert_result = supabase.table("clients").insert({
                "org_client_id": org_client_id,
                "client_name": client_name,
                "client_data_jsonb": client_data_jsonb,
                "org_id": str(org_id),
                "expert_id": None
            }).execute()

            overall_result_client_data = insert_result.data[0]["client_data_jsonb"]
            overall_result_client_id = insert_result.data[0]["id"]
        
        if client_expert_check and len(client_expert_check.data) > 0:
            # Get existing client data and update it with new data
            print("Updating existing expert client")
            existing_expert_client_data_jsonb = client_expert_check.data[0]["client_data_jsonb"]
            merged_data = existing_expert_client_data_jsonb
            if client_data_jsonb:
                merged_data = history_preserving_merge(existing_expert_client_data_jsonb, client_data_jsonb, consultation_id, created_time)
            # Update existing client
            update_result = supabase.table("clients").update({
                "client_data_jsonb": merged_data
                # Let the database handle the updated_at timestamp automatically
            }).eq("org_client_id", org_client_id).eq("org_id", org_id).eq("expert_id", expert_id).execute()
            
            expert_result_client_data = update_result.data[0]["client_data_jsonb"]
            expert_result_client_id = update_result.data[0]["id"]
        else:
            # Create new client
            insert_result = supabase.table("clients").insert({
                "org_client_id": org_client_id,
                "client_name": client_name,
                "client_data_jsonb": client_data_jsonb,
                "org_id": str(org_id),
                "expert_id": str(expert_id) if expert_id else None
            }).execute()    
            
            expert_result_client_data = insert_result.data[0]["client_data_jsonb"]
            expert_result_client_id = insert_result.data[0]["id"]
        
        return {
            "status": "success",
            "message": f"Client '{client_name}' created successfully",
            "client_id": overall_result_client_id,
            "client_data": overall_result_client_data,
            "expert_client_id": expert_result_client_id,
            "expert_client_data": expert_result_client_data
        }
    
    except Exception as e:
        print(f"Error creating/updating client: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating/updating client: {str(e)}")

async def create_or_get_vector(request: CreateVector):
    """
    Create a vector store for a client
    Returns:
        vector_id: str
        id: uuid
        memory_type: str
        message: str
    """
    try:
        print(f"Creating vector for memory: {request.memory_type}")
        vector_id_result = await get_vector_id(request)
        vector_id = vector_id_result.get("vector_id") if vector_id_result else None
        if vector_id:
            return {
                "vector_id": vector_id,
                "id": vector_id_result.get("id"),
                "memory_type": request.memory_type,
                "message": f"Vector store already exists"
            }
        
        vector_name = vector_id_result.get("vector_name")
        if not vector_name:
            raise HTTPException(status_code=400, detail="vector_name is required")
        vector_store = await create_vector_store(client, vector_name)
        print(f"Vector store created: {vector_store}")
        vector_id = vector_store.id if hasattr(vector_store, 'id') else None
        
        domain_id = None
        domain_name = None
        expert_id = None
        client_id = None
        
        if request.memory_type == "domain":
            domain_id = await get_domain_id(request.org_id, request.domain_name)
            domain_name = request.domain_name
        
        if request.memory_type == "expert":
            expert_id = request.expert_id
        
        if request.memory_type == "client":
            client_id = request.client_id
        
        if request.memory_type == "myclient":
            client_id = request.client_id
            expert_id = request.expert_id

        # Also add an entry to the vector_stores table if we have a vector_id
        
        if vector_id:
            vector_store_data = {
                "vector_id": vector_id,
                "vector_name": vector_name,
                "org_id": str(request.org_id),
                "owner": request.memory_type,
                "file_ids": [],
                "batch_ids": [],
                "domain_name": domain_name,
                "domain_id": str(domain_id) if domain_id else None,
                "expert_id": str(expert_id) if expert_id else None,
                "client_id": str(client_id) if client_id else None
            }

            print(f"Vector store data to insert: {vector_store_data}")
            # Insert into vector_stores table
            vector_result = supabase.table("vector_stores").insert(vector_store_data).execute()
        return {
            "vector_id": vector_id,
            "id": vector_result.data[0].get("id"),
            "memory_type": request.memory_type,
            "message": f"Vector store created successfully"
        }
    except Exception as e:
        print(f"Error creating organization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Create domain - will create default vector store for domain
async def create_or_get_domain(domain_create: DomainCreate):
    """
    Create a new domain with custom domain name or with domain from the enum DomainName
    Returns:
        domain_id: uuid
        vector_id: uuid
        message: str
    """
    try:
        print(f"Creating domain with name: {domain_create.domain_name} and org_id: {domain_create.org_id}")
        domain_id = await get_domain_id(domain_create.org_id, domain_create.domain_name)
        if not domain_id:
            # Create domain entry in database
            domain_data = {
                "domain_name": domain_create.domain_name,
                "expert_names": [],
                "org_id": str(domain_create.org_id)
            }
            # Insert domain into database
            result = supabase.table("domains").insert(domain_data).execute()
            domain_id = result.data[0].get("id")
            print(f"Inserted domain: {domain_id}")
            if not result.data:
                raise HTTPException(status_code=500, detail="Failed to create domain")
        else:
            print(f"Domain id: {domain_id}")
        
        return {
            "domain_id": domain_id,
            "message": "Domain Id returned successfully"
            }
    except Exception as e:
        print(f"Error creating domain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Create expert
async def create_or_get_expert(expert: Expert):
    """
    Create a new expert with domain and context
    """
    try:
        print(f"Creating expert with name: {expert.name}")
        expert_id = None
        
        # Check if expert exists and is associated with the domains
        expert_exists = supabase.table("experts").select("*").eq("name", expert.name).eq("org_id", expert.org_id).execute()
        if expert_exists.data:
            print(f"Expert already exists: {expert_exists.data}. Update expert to modify")
            expert_id = await update_expert_with_domains(expert_exists.data[0], expert.domains)
        else:
            # Create expert data
            expert_data = {
                "name": expert.name,
                "domains": expert.domains,
                "context": expert.context,
                "org_id": str(expert.org_id)
            }
            # Insert expert into database
            result = supabase.table("experts").insert(expert_data).execute()
            if not result.data:
                raise HTTPException(status_code=500, detail="Failed to create expert")
            expert_id = result.data[0].get("id")
            # Update domain with expert name
            await update_domains_with_experts(expert.name, expert.domains, expert.org_id)
            
            
        # Validate that we have both IDs before returning
        if not expert_id:
            print(f"Warning: Missing IDs - expert_id: {expert_id}")
            
        return {
            "expert_id": expert_id,
            "message": f"Expert {expert.name} created successfully"
        }
    except Exception as e:
        print(f"Error in create_or_get_expert: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add files to vector
async def add_files_to_vector(request: FilesConfigRequest):
    """
    Add files to a all the vector store
    """
    try:
        # Initialize variables
        memory_type = request.memory_type
        owner_id = None
        vector_id = request.vector_id
        document_urls = request.document_urls
        pdf_documents = request.pdf_documents
        other_doc = request.other_doc

        if memory_type == 'domain':
            owner_id = str(request.domain_id)
            domain_to_add = request.domain_name
            domain_data = await parse_domain_config_file(request.config_file_path)
            if not domain_data:
                print("No valid domain data found in domain config file")
            else:
                # Get document URLs for the specified domain directly from the dictionary
                if domain_to_add and domain_to_add in domain_data:
                    document_urls.update(domain_data[domain_to_add])
                    print(f"Found {len(domain_data[domain_to_add])} documents for domain '{domain_to_add}' in config file")
                else:
                    print(f"Domain '{domain_to_add}' not found in config file")

        elif memory_type == 'expert':
            owner_id = str(request.expert_id)
        elif memory_type == 'client':
            owner_id = str(request.client_id)
        elif memory_type == 'organization' or memory_type == 'llm':
            owner_id = str(request.org_id)
        elif memory_type == 'myclient':
            owner_id = str(request.expert_id) + "_" + str(request.client_id)
        
        if owner_id is None:
            raise HTTPException(status_code=400, detail="Invalid arguments for memory type")
        
        print(f"Adding files to vector store for memory {request.memory_type}")

        # Initialize result variables
        file_ids = []
        batch_id = None
        result = {"file_ids": [], "batch_id": None, "vector_id": vector_id, "status": "skipped", "message": "Initializing variables"}
        
        if document_urls:
            print(f"Checking document URLs: {document_urls}")
            document_urls = await check_document_urls(document_urls)
            if not document_urls:
                raise HTTPException(status_code=400, detail="No valid document URLs found")

        if pdf_documents:
            validated_pdf_documents = validate_file_paths(pdf_documents)
            document_urls.update(validated_pdf_documents)
        
        # Only add documents to vector store if we have valid document URLs
        if document_urls:
            result = await add_documents_to_vector_store(client, vector_id, document_urls, other_doc if other_doc else {}, owner_id)
            print(f"Added {result.get('stats', {}).get('successful_files', 0)} new documents to vector store: {result}")
        elif other_doc:
            result = await add_documents_to_vector_store(client, vector_id, {}, other_doc, owner_id)
            print(f"Added {result.get('stats', {}).get('successful_files', 0)} new JSON documents to vector store: {result}")
        else:
            print("Skipping document addition to vector store - no valid documents found")
            return result

        file_ids = result.get("file_ids", [])
        batch_id = result.get("batch_id")
        
        try:
            # Replace existing entry with new data
            update_data = {
                    "file_ids": file_ids,  # Replace with new file_ids
                    "batch_ids": [batch_id] if batch_id else [],  # Replace with new batch_id
                    "latest_batch_id": batch_id
                }
            supabase.table("vector_stores").update(update_data).eq("vector_id", vector_id).execute()
        except Exception as e:
            print(f"Error updating vector_stores table: {str(e)}")
            # Continue anyway, the vector store was updated successfully
        
        return {
            "vector_id": vector_id,
            "file_ids": result.get("file_ids"),
            "batch_id": result.get("batch_id"),
            "status": result.get("status"),
            "message": "Documents added to vector store successfully"
        }
    except Exception as e:
        print(f"Error adding files to domain vector from config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Generate persona from QA data
async def generate_persona_from_qa_data(persona_request: PersonaGenerationRequest):
    """
    Generate a persona summary from QA data provided directly in the request
    
    The request body should have the following structure:
    {
        "qa_pairs": [
            {"question": "What is your area of expertise?", "answer": "I specialize in pediatric cardiology..."},
            {"question": "How do you approach difficult cases?", "answer": "I believe in a collaborative approach..."}
        ]
    }
    """
    try:
        print(f"Generating persona from {len(persona_request.qa_pairs)} QA pairs")
        
        # Validate QA pairs
        if not persona_request.qa_pairs:
            raise HTTPException(status_code=400, detail="No QA pairs provided in request")
        
        valid_qa_pairs = []
        for qa in persona_request.qa_pairs:
            if isinstance(qa, dict) and 'question' in qa and 'answer' in qa:
                valid_qa_pairs.append(qa)
            else:
                print(f"Warning: Skipping invalid QA pair: {qa}")
        
        if not valid_qa_pairs:
            raise HTTPException(status_code=400, detail="No valid QA pairs found in request")
            
        print(f"Validated {len(valid_qa_pairs)} QA pairs from request")
        
        # Generate persona using OpenAI
        persona_summary = await generate_persona_from_qa(client, valid_qa_pairs)
        
        return {
            "qa_pairs_count": len(valid_qa_pairs),
            "persona": persona_summary,
            "message": "Successfully generated persona from QA pairs"
        }
    except Exception as e:
        print(f"Error generating persona from config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Update expert persona
async def update_expert_persona(request: UpdateExpertPersonaRequest):
    """
    Generate a persona from QA data and update the expert's context with it
    
    This endpoint combines the persona generation and context update steps:
    1. Generate a persona from the provided QA pairs
    2. Update the expert's context with the generated persona
    """
    try:
        print(f"Updating persona for expert: {request.expert_id} with {len(request.qa_pairs)} QA pairs")
        
        # Step 1: Generate persona from QA data
        persona_request = PersonaGenerationRequest(qa_pairs=request.qa_pairs)
        persona_result = await generate_persona_from_qa_data(persona_request)
        persona_summary = persona_result["persona"]
        print(f"Generated persona: {persona_summary}")
        
        # Step 2: Update expert's context with the generated persona
        expert_update = ExpertUpdate(expert_id=request.expert_id, context=persona_summary)
        update_result = await update_context(expert_update)
        
        return {
            "expert_id": request.expert_id,
            "qa_pairs_count": len(request.qa_pairs),
            "persona": persona_summary,
            "update_result": update_result,
            "status": "success",
            "message": f"Successfully updated persona for expert {request.expert_id}"
        }
    except Exception as e:
        print(f"Error initializing expert memory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


#________Helper functions (potential APIs)________
async def update_context(expert_update: ExpertUpdate):
    """
    Update an expert's context
    """
    try:
        # Update expert's context
        result = supabase.table("experts").update({"context": expert_update.context}).eq("id", expert_update.expert_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to update expert context")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Update vector store
async def update_vector_store(update_request: UpdateVectorStoreRequest):
    """
    Update an existing vector store by adding new documents
    
    Args:
        update_request: Request containing vector_id, document_urls, and pdf_documents
        
    Returns:
        Updated vector store information
    """
    # Initialize variables at the beginning to ensure proper scope
    vector_id = None
    id = None
    owner_id = None
    new_file_ids = []
    all_file_ids = []
    batch_id = None
    document_urls = {}
    file_ids = []
    
    try:
        # Validate required request fields
        if not update_request.memory_type:
            raise ValueError("memory_type is required")
        if not update_request.org_id:
            raise ValueError("org_id is required")
            
        # Initialize document collections with empty defaults if not provided
        url_count = len(update_request.document_urls) if update_request.document_urls else 0
        pdf_count = len(update_request.pdf_documents) if update_request.pdf_documents else 0
        other_doc_count = len(update_request.other_doc) if update_request.other_doc else 0
        total_docs = url_count + pdf_count + other_doc_count
        
        print(f"Updating vector store for {update_request.memory_type} with {total_docs} new documents ({url_count} URLs, {pdf_count} PDFs, {other_doc_count} Other Docs)")
        
        # Get vector store information
        print(f"Getting vector store ID for memory_type={update_request.memory_type}, org_id={update_request.org_id}, expert_id={update_request.expert_id}")
        vector_st = await get_vector_id(CreateVector(
            memory_type=update_request.memory_type, 
            org_id=update_request.org_id, 
            expert_id=update_request.expert_id, 
            client_id=update_request.client_id, 
            domain_name=update_request.domain_name
        ))
        
        if not vector_st:
            raise ValueError("Failed to get vector store information")
            
        vector_id = vector_st.get("vector_id")
        id = vector_st.get("id")
        print(f"Retrieved vector_id: {vector_id}, id: {id}")
        
        if not id:
            raise HTTPException(status_code=404, detail="Vector store ID not found")
            
        # Query by vector_id directly from the vector_stores table
        vector_store_result = supabase.table("vector_stores").select("*").eq("id", id).execute()
        print(f"Vector store query result: {vector_store_result.data}")
        
        if not vector_store_result.data:
            raise HTTPException(status_code=404, detail=f"Vector store with ID {id} not found")
        
        vector_store = vector_store_result.data[0]
        
        # Get file IDs with None check
        file_ids = vector_store.get("file_ids", [])
        if file_ids is None:
            file_ids = []
            
        # Initialize document_urls with the request data
        document_urls = update_request.document_urls if update_request.document_urls else {}
        if document_urls:
            document_urls = await check_document_urls(document_urls)
            if not document_urls:
                raise HTTPException(status_code=400, detail="No valid document URLs found")

        # Process PDF documents if available
        if pdf_count > 0 and update_request.pdf_documents:
            print(f"Processing {pdf_count} PDF documents")
            try:
                validated_pdfs = validate_file_paths(update_request.pdf_documents)
                if validated_pdfs:
                    print(f"Validated {len(validated_pdfs)} PDF documents")
                    document_urls.update(validated_pdfs)
                else:
                    print("No valid PDF documents found after validation")
            except Exception as pdf_error:
                print(f"Error validating PDF documents: {str(pdf_error)}")
                # Continue with other documents even if PDF validation fails
                
        # Set owner_id based on memory type with proper None checks
        owner_id = None
        if update_request.memory_type == 'domain' and update_request.domain_name:
            owner_id = str(await get_domain_id(update_request.org_id, update_request.domain_name))
        elif update_request.memory_type == 'expert' and update_request.expert_id:
            owner_id = str(update_request.expert_id)
        elif update_request.memory_type == 'client' and update_request.client_id:
            owner_id = str(update_request.client_id)
        elif update_request.memory_type == 'myclient' and update_request.expert_id and update_request.client_id:
            owner_id = str(update_request.expert_id) + "_" + str(update_request.client_id)
        elif (update_request.memory_type == 'organization' or update_request.memory_type == 'llm') and update_request.org_id:
            owner_id = str(update_request.org_id)
        
        if not owner_id:
            owner_id = str(update_request.org_id)  # Fallback to org_id if no specific owner is set

        # Call edit_vector_store with None checks
        if not vector_id:
            raise ValueError("Vector ID is required for updating vector store")
        
        print(f"Calling edit_vector_store with vector_id={vector_id}, {len(file_ids)} file_ids, {len(document_urls)} document_urls")
        try:
            result = await edit_vector_store(
                client, 
                vector_id, 
                file_ids, 
                document_urls, 
                update_request.other_doc,  # Pass other_doc from the request
                owner_id
            )
            
            if not result:
                raise ValueError("Failed to edit vector store - empty result returned")
                
            print(f"Successfully edited vector store: {result.get('message', 'No message')}")
        except Exception as edit_error:
            print(f"Error in edit_vector_store: {str(edit_error)}")
            raise ValueError(f"Failed to edit vector store: {str(edit_error)}")
        
        # Update vector_stores table with the new file information
        new_file_ids = result.get("file_ids", [])
        all_file_ids = result.get("all_file_ids", [])
        batch_id = result.get("batch_id")
        
        # Initialize batch_ids at function scope to ensure it's available in all code paths
        batch_ids = []
        update_result = None
        
        try:
            # Update the vector_stores entry
            # Get existing batch_ids from the vector store with None check
            existing_batch_ids = vector_store.get("batch_ids", [])
            if existing_batch_ids is None:
                existing_batch_ids = []
            
            # Process batch_ids with proper None checks
            if batch_id:
                if existing_batch_ids and isinstance(existing_batch_ids, list):
                    # If existing_batch_ids is already an array, append the new batch_id if not already present
                    if batch_id not in existing_batch_ids:
                        batch_ids = existing_batch_ids + [batch_id]
                    else:
                        batch_ids = existing_batch_ids.copy()  # Create a copy to avoid modifying the original
                else:
                    # If there are no existing batch_ids or it's not a list, create a new array
                    batch_ids = [batch_id]
            else:
                # If no new batch was created, keep the existing batch_ids
                batch_ids = existing_batch_ids.copy() if isinstance(existing_batch_ids, list) else []
            
            # Prepare update data with None checks
            latest_batch_id = batch_id if batch_id else vector_store.get("latest_batch_id")
            
            update_data = {
                "file_ids": all_file_ids if all_file_ids else [],
                "batch_ids": batch_ids,
                "latest_batch_id": latest_batch_id,
                "updated_at": "now()"
            }
            
            # Ensure id is valid before updating
            if not id:
                print("Warning: Missing vector store ID for update operation")
            else:
                update_result = supabase.table("vector_stores").update(update_data).eq("id", id).execute()
                print(f"Updated vector_stores entry: {update_result.data if hasattr(update_result, 'data') else update_result}")
        except Exception as e:
            print(f"Error updating vector_stores table: {str(e)}")
            # Log the error but continue since the vector store was already updated
        
        # Return consistent response with None checks
        return {
            "status": "success",
            "message": f"Added {len(new_file_ids)} documents to vector store {vector_id or 'unknown'}",
            "vector_id": vector_id,
            "owner_id": owner_id,
            "new_file_ids": new_file_ids if new_file_ids else [],
            "all_file_ids": all_file_ids if all_file_ids else [],
            "batch_id": batch_id,
            "update_success": update_result is not None
        }
    except Exception as e:
        error_message = f"Error updating vector store: {str(e)}"
        print(error_message)
        print(f"Error type: {type(e).__name__}")
        # Include more context in the error message
        context = {
            "memory_type": getattr(update_request, 'memory_type', None),
            "expert_id": getattr(update_request, 'expert_id', None),
            "domain_name": getattr(update_request, 'domain_name', None),
            "url_count": url_count,
            "pdf_count": pdf_count
        }
        print(f"Error context: {context}")
        raise HTTPException(status_code=500, detail=error_message)

# Get details from database if required and Delete vector memory if required
@router.get("/documents")
async def get_documents(owner_id: Optional[str] = None):
    """
    Get documents filtered by owner_id
    
    Priority rules:
    1. If owner_id is provided, return documents matching owner_id, else return all documents
    """
    try:
        print(f"Getting documents with filters - owner_id: {owner_id}")
        
        # Start building the query
        query = supabase.table("documents").select("*")
        
        if owner_id:
            query = query.eq("owner_id", owner_id)
            
        # Execute the query
        result = query.execute()
        print(f"Found {len(result.data)} documents")
        return result.data
    except Exception as e:
        print(f"Error getting documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents/vector-name")
async def get_documents_by_vector_name(vector_name: Optional[str] = None):
    """
    Get documents filtered by vector_name
    
    Priority rules:
    1. If vector_name is provided, return documents matching vector_name, else return all documents
    """
    try:
        print(f"Getting documents with filters - vector_name: {vector_name}")
        
        # Get file IDs from vector name
        file_ids = await get_file_ids(vector_name)

        if file_ids:
            documents = await get_documents_by_file_ids(file_ids)
        else:
            documents = []
        
        print(f"Found {len(documents)} documents")
        return documents
    except Exception as e:
        print(f"Error getting documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_documents_by_file_ids(file_ids: Optional[List[str]] = None):
    """
    Get documents filtered by file_ids
    
    Priority rules:
    1. If file_ids is provided, return documents matching file_ids, else return all documents
    """
    try:
        print(f"Getting documents with filters - file_ids: {file_ids}")
        
        # Start building the query
        query = supabase.table("documents").select("*")
        
        if file_ids:
            query = query.in_("openai_file_id", file_ids)
            
        # Execute the query
        result = query.execute()
        #print(f"Found {len(result.data)} documents")
        return result.data
    except Exception as e:
        print(f"Error getting documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_org_id(org_name: str):
    """
    Get organization ID by name
    """
    try:
        # Check if org_name is None or empty
        if not org_name or org_name == "None":
            print("Warning: org_name is None or empty")
            return None
            
        print(f"Getting organization ID for: {org_name}")
        result = supabase.table("organizations").select("id").eq("org_name", org_name).execute()
        print(f"Found {len(result.data)} organizations")
        
        if len(result.data) > 0:
            return result.data[0].get("id")
        else:
            print(f"No organization found with name: {org_name}")
            return None
    except Exception as e:
        print(f"Error getting organization ID: {str(e)}")
        return None

@router.get("/organization", response_model=List[dict])
async def get_organization():
    """
    Get all organizations
    """
    try:
        print("Getting all organizations")
        result = supabase.table("organizations").select("*").execute()
        print(f"Found {len(result.data)} organizations")
        return result.data
    except Exception as e:
        print(f"Error getting organizations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_client_id(org_id: UUID, org_client_id: int, expert_id: UUID = None, memory_type: str = "client"):
    """
    Get client ID by org_id, org_client_id, and optionally expert_id
    """
    try:
        # Check for null or invalid values
        if org_id is None or org_id == "None":
            print("Warning: org_id is None or invalid")
            return None
            
        if org_client_id is None or org_client_id == "None":
            print("Warning: org_client_id is None or invalid")
            return None
            
        
        # Build the query
        query = supabase.table("clients").select("id").eq("org_id", org_id).eq("org_client_id", org_client_id)
        
        # Add expert_id condition based on memory_type
        if memory_type == "client":
            query = query.is_("expert_id", "null")
        elif expert_id is not None and expert_id != "None":
            query = query.eq("expert_id", expert_id)

        print(f"Getting client with org_id: {org_id}, org_client_id: {org_client_id}", "expert_id: ", expert_id)
            
        # Execute the query
        result = query.execute()
        print(f"Found {len(result.data)} clients")
        
        if result.data and len(result.data) > 0:
            return result.data[0].get("id")
        return None
    except Exception as e:
        print(f"Error getting clients: {str(e)}")
        # Return None instead of raising an exception to make the function more robust
        return None

async def get_expert_id(org_id: UUID, domain_name: str, expert_name: str):
    """
    Get expert ID by org_id, domain_name, and expert_name
    """
    try:
        # Check for null or invalid values
        if org_id is None or org_id == "None":
            print("Warning: org_id is None or invalid in get_expert_id")
            return None
            
        if not domain_name or domain_name == "None":
            print("Warning: domain_name is None or empty in get_expert_id")
            return None
            
        if not expert_name or expert_name == "None":
            print("Warning: expert_name is None or empty in get_expert_id")
            return None
            
        print(f"Getting expert with org_id: {org_id}, domain_name: {domain_name}, expert_name: {expert_name}")
        
        # Build and execute the query
        # For domains, we need to check if the domain_name is contained in the domains array
        query = supabase.table("experts").select("id").eq("org_id", org_id).contains("domains", [domain_name]).eq("name", expert_name)
        result = query.execute()
        print(f"Found {len(result.data)} experts")
        
        if result.data and len(result.data) > 0:
            return result.data[0].get("id")
        return None
    except Exception as e:
        print(f"Error getting expert ID: {str(e)}")
        # Return None instead of raising an exception to make the function more robust
        return None

@router.get("/clients", response_model=List[dict])
async def get_clients(org_id: UUID, expert_id: UUID = None):
    """
    Get all clients
    """
    try:
        print("Getting all clients")
        query = supabase.table("clients").select("*").eq("org_id", org_id)
        if expert_id:
            query = query.eq("expert_id", expert_id)
        result = query.execute()
        print(f"Found {len(result.data)} clients")
        return result.data
    except Exception as e:
        print(f"Error getting clients: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get all domains list in org
@router.get("/domains", response_model=List[dict])
async def get_domains(org_id: UUID):
    """
    Get all domains
    """
    try:
        print("Getting all domains")
        result = supabase.table("domains").select("id, domain_name").eq("org_id", org_id).execute()
        print(f"Found {len(result.data)} domains")
        return result.data
    except Exception as e:
        print(f"Error getting domains: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get domains list for expert
@router.get("/experts/{expert_id}/domains", response_model=dict)
async def get_expert_domains(expert_id: UUID):
    """
    Get domain name for a given expert name
    """
    try:
        print(f"Getting domain for expert: {expert_id}")
        
        # Query the expert by name
        result = supabase.table("experts").select("name, domains").eq("id", expert_id).execute()
        print(f"Expert query result: {result.data}")
        
        if not result.data:
            raise HTTPException(status_code=404, detail=f"Expert {expert_id} not found")
        
        expert_data = result.data[0]
        domains = expert_data.get("domains")
        
        if not domains:
            return {
                "expert_name": expert_data.get("name"),
                "domains": None,
                "message": f"No domain associated with expert {expert_data.get("name")}"
            }
        
        return {
            "expert_name": expert_data.get("name"),
            "domains": domains,
            "message": f"Domain associated with expert {expert_data.get("name")}"
        }
    except Exception as e:
        print(f"Error getting expert domain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get domains not associated with an expert
@router.get("/experts/{expert_id}/available-domains", response_model=dict)
async def get_available_domains(expert_id: UUID, org_id: UUID):
    """
    Get domains that are in the organization but not associated with the specified expert.
    
    Args:
        expert_id: UUID of the expert
        org_id: UUID of the organization
        
    Returns:
        dict: List of domains with their IDs and names that are not associated with the expert
    """
    try:
        print(f"Getting available domains for expert: {expert_id} in organization: {org_id}")
        
        # Step 1: Get all domains for the organization
        all_domains_result = await get_domains(org_id) # returns a list of 'id' and 'domain_name' dictionaries
        if not all_domains_result:
            return {
                "expert_id": expert_id,
                "available_domains": [],
                "message": f"No domains found for organization {org_id}"
            }
            
        # Step 2: Get domains associated with the expert
        expert_domains_result = await get_expert_domains(expert_id) # returns a list of domains in names
        expert_domain_names = expert_domains_result.get("domains", [])
        
        # If expert has no domains, all organization domains are available
        if not expert_domain_names:
            return {
                "expert_id": expert_id,
                "expert_name": expert_domains_result.get("expert_name"),
                "available_domains": all_domains_result,
                "message": f"All domains are available for expert {expert_domains_result.get('expert_name')}"
            }
        
        # Step 3: Filter domains not associated with the expert
        available_domains = []
        for domain in all_domains_result:
            if domain["domain_name"] not in expert_domain_names:
                available_domains.append({
                    "id": domain["id"],
                    "domain_name": domain["domain_name"]
                })
        
        print(f"Found {len(available_domains)} available domains for expert {expert_id}")
        
        return {
            "expert_id": expert_id,
            "expert_name": expert_domains_result.get("expert_name"),
            "available_domains": available_domains,
            "message": f"Available domains for expert {expert_domains_result.get('expert_name')}"
        }
        
    except Exception as e:
        print(f"Error getting available domains: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get vector ID based on domain, expert, and client parameters
@router.get("/vectors/id", response_model=dict)
async def get_vector_id(request: CreateVector):
    """
    Get vector ID from the vector_stores table based on provided parameters.
    - memory_type is mandatory
    - org_id is mandatory
    - domain_name is optional (if not provided, gets org-level vector store)
    - expert_id is optional (if not provided, gets domain-level vector store)
    - client_id is optional (if provided with expert_id, gets client-level vector store)
    """
    # Initialize variables at the beginning to ensure proper scope
    vector_id = None
    id = None
    vector_name = None
    
    try:
        # Validate required request fields
        if not request.memory_type:
            raise ValueError("memory_type is required")
        if not request.org_id:
            raise ValueError("org_id is required")
            
        print(f"Getting vector ID for memory_type: {request.memory_type}, "
              f"org_id: {request.org_id}, "
              f"domain_name: {request.domain_name or 'None'}, "
              f"expert_id: {request.expert_id or 'None'}, "
              f"client_id: {request.client_id or 'None'}")
              
        # Get query and vector name
        query_result = await get_query_for_vector_store(request)
        
        if not query_result or len(query_result) != 2:
            raise ValueError("Invalid result from get_query_for_vector_store")
            
        query, vector_name = query_result
        
        if not query:
            raise ValueError("Failed to create query for vector store")
            
        # Execute query with error handling
        try:
            result = query.execute()
        except Exception as query_error:
            print(f"Error executing vector store query: {str(query_error)}")
            raise ValueError(f"Database query failed: {str(query_error)}")
            
        print(f"Vector store query result: {result.data if hasattr(result, 'data') else 'No data'}")
        
        # Handle case where no vector store is found
        if not result.data or len(result.data) == 0:
            return {
                "vector_id": None,
                "memory_type": request.memory_type,
                "id": None,
                "vector_name": vector_name
            }
        
        # Vector store found, extract data with None checks
        vector_store_record = result.data[0]
        
        if not vector_store_record:
            print("Warning: Empty vector store record returned")
            return {
                "vector_id": None,
                "memory_type": request.memory_type,
                "id": None,
                "vector_name": vector_name
            }
            
        vector_id = vector_store_record.get("vector_id")
        id = vector_store_record.get("id")
        
        # Return consistent response with all fields
        return {
            "vector_id": vector_id,
            "memory_type": request.memory_type,
            "id": id,
            "vector_name": vector_name,
            "found": True
        }
    except ValueError as ve:
        # Handle validation errors separately to provide better error messages
        print(f"Validation error in get_vector_id: {str(ve)}")
        return {
            "vector_id": None,
            "memory_type": request.memory_type if hasattr(request, 'memory_type') else None,
            "id": None,
            "vector_name": vector_name,
            "error": str(ve),
            "found": False
        }
    except Exception as e:
        # Log the error but don't expose internal details in the response
        print(f"Error getting vector ID: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get vector ID: {str(e)}")

# Get all experts - will return expert objects
@router.get("/experts", response_model=List)
async def get_experts(org_id: UUID):
    """
    Get all experts
    """
    try:
        print("Getting all experts")
        result = supabase.table("experts").select("*").eq("org_id", org_id).execute()
        print(f"Found {len(result.data)} experts and their names are {result.data}")
        return result.data
    except Exception as e:
        print(f"Error getting experts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get an expert's context
@router.get("/experts/{expert_id}/context", response_model=dict)
async def get_expert_context(expert_id: UUID):
    """
    Get an expert's context
    
    Args:
        expert_id: ID of the expert
        
    Returns:
        Expert context
    """
    try:
        print(f"Getting context for expert: {expert_id}")
        result = supabase.table("experts").select("context").eq("id", expert_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail=f"Expert {expert_id} not found")
        
        return {"context": result.data[0]["context"]}
    except Exception as e:
        print(f"Error getting expert context: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Delete vector memory
@router.delete("/vectors/memory", response_model=dict)
async def delete_vector_memory(request: DeleteVectorRequest):
    """
    Delete a vector memory based on domain, expert, and/or client name.
    This endpoint handles deletion of domain, expert, or client-specific vector stores.
    """
    try:
        print(f"[DEBUG] delete_vector_memory: Request received with domain_name={request.domain_name}, "
              f"expert_name={request.expert_name}, client_name={request.client_name}")
        org_id = None
        if request.org_name:
            org_id = await get_org_id(request.org_name)
        if not org_id:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        expert_id = None
        if request.expert_name:
            expert_id = await get_expert_id(org_id, request.domain_name, request.expert_name)
            if not expert_id:
                raise HTTPException(status_code=404, detail="Expert not found")

        client_id = None
        if (request.memory_type == "client" or request.memory_type == "myclient"):
            client_id = await get_client_id(org_id, request.org_client_id, expert_id, request.memory_type)
            if not client_id:
                raise HTTPException(status_code=404, detail="Client not found")
        
        vector_id = request.vector_id if request.vector_id else None
        vector_id_to_delete = request.delete_id if request.delete_id else None
        
        if not vector_id_to_delete:
            delete_request = CreateVector(memory_type=request.memory_type, org_id=org_id, domain_name=request.domain_name, expert_id=expert_id, client_id=client_id)
            query, vector_name = await get_query_for_vector_store(delete_request)
            result = query.execute()
            if result.data and len(result.data) > 0:
                print(f"Vector store query result: {result.data}")
                vector_id = result.data[0].get("vector_id")
                vector_id_to_delete = result.data[0].get("id")
            else:
                print(f"[ERROR] delete_vector_memory: Vector store not found")
                
        # Delete the vector index
        if vector_id:
            await delete_vector_index(vector_id)
            print(f"[DEBUG] delete_vector_memory: Vector index deleted with ID: {vector_id}")
        # Delete the vector store record
        if vector_id_to_delete:
            supabase.table("vector_stores").delete().eq("id", vector_id_to_delete).execute()
            print(f"[DEBUG] delete_vector_memory: Vector store record deleted with ID: {vector_id_to_delete}")
        
        return {"message": f"Vector memory deleted"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))