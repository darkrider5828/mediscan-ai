# --- START OF FILE app.py ---

import os
import io
import uuid
import traceback
from flask import (
    Flask, request, render_template, session, redirect, url_for,
    send_file, jsonify, flash, Response, Config
)
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import pandas as pd
import markdown # For markdown filter
# --- CORRECTED IMPORT ---
from markupsafe import Markup # Import Markup from markupsafe
# ------------------------

# Import your project modules
from extract_text import extract_text_from_pdf
from utils import preprocess_text, chunk_text
from vector_db import VectorDB
from gemini_api import GeminiAPI
from generate_report import export_to_pdf
from save_text import save_extracted_text
from chat_feature import initialize_chat, process_chat_query
from save_table import save_table
from visualizations import generate_visualizations
import google.generativeai as genai # For initializing chat model separately

# --- Load Environment Variables ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "default-dev-secret-key") # Provide default for dev

if not GEMINI_API_KEY:
    print("\n" + "="*60)
    print(" CRITICAL ERROR: GEMINI_API_KEY not found in environment variables.")
    print(" Please ensure you have a .env file with GEMINI_API_KEY=YOUR_KEY")
    print(" Application might not function correctly.")
    print("="*60 + "\n")
else:
     print("Gemini API Key loaded successfully.")

if FLASK_SECRET_KEY == "default-dev-secret-key" or FLASK_SECRET_KEY == "replace-this-with-a-strong-random-secret-key":
     print("\n" + "="*60)
     print(" WARNING: Using default or placeholder FLASK_SECRET_KEY.")
     print(" Please set a strong, unique secret key in your .env file for security.")
     print("="*60 + "\n")


# --- Model Configuration ---
# IMPORTANT: Verify these model names are available in your Google AI region/project!
ANALYSIS_MODEL_NAME = "gemini-1.5-flash-latest" # Model for main analysis & table extraction
CHAT_MODEL_NAME = "gemini-1.5-flash-latest"     # Model specifically for the chat feature
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'       # Sentence Transformer for embeddings


# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' # Recommended for security
# Custom config for logo
app.config['SHOW_LOGO'] = True # Set to False to hide logo in sidebar

# --- File/Directory Configuration ---
UPLOAD_FOLDER = 'uploads'
PROCESSED_DATA_FOLDER = 'processed_data'
EXTRACTED_TEXTS_DIR = os.path.join(PROCESSED_DATA_FOLDER, 'extracted_texts')
TABLES_DIR = os.path.join(PROCESSED_DATA_FOLDER, 'tables')
EMBEDDINGS_DIR = os.path.join(PROCESSED_DATA_FOLDER, 'embeddings')
INDICES_DIR = os.path.join(PROCESSED_DATA_FOLDER, 'indices')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_DATA_FOLDER'] = PROCESSED_DATA_FOLDER
app.config['EXTRACTED_TEXTS_DIR'] = EXTRACTED_TEXTS_DIR
app.config['TABLES_DIR'] = TABLES_DIR
app.config['EMBEDDINGS_DIR'] = EMBEDDINGS_DIR
app.config['INDICES_DIR'] = INDICES_DIR

ALLOWED_EXTENSIONS = {'pdf'}

# --- Create Directories ---
dirs_to_create = [
    UPLOAD_FOLDER, PROCESSED_DATA_FOLDER, EXTRACTED_TEXTS_DIR,
    TABLES_DIR, EMBEDDINGS_DIR, INDICES_DIR,
    'static/css', 'static/js', 'static/images', 'templates'
]
for dir_path in dirs_to_create:
    try:
        os.makedirs(dir_path, exist_ok=True)
    except OSError as e:
        print(f"CRITICAL WARNING: Could not create directory {dir_path}: {e}")


# --- Initialize Shared Resources ---
gemini_api_instance = None
vector_db_instance = None
chat_model = None

try:
    print("\nInitializing AI Models...")
    if GEMINI_API_KEY:
        gemini_api_instance = GeminiAPI(api_key=GEMINI_API_KEY, model_name=ANALYSIS_MODEL_NAME)
        try:
             genai.configure(api_key=GEMINI_API_KEY)
             chat_model = genai.GenerativeModel(CHAT_MODEL_NAME)
             print(f"Chat model '{CHAT_MODEL_NAME}' initialized successfully.")
        except Exception as chat_e:
             print(f"ERROR: Failed to initialize chat model '{CHAT_MODEL_NAME}': {chat_e}")
             chat_model = None
    else:
         print("Skipping Gemini model initialization due to missing API key.")

    vector_db_instance = VectorDB(model_name=EMBEDDING_MODEL_NAME)
    if not vector_db_instance.model:
         print("ERROR: VectorDB could not load the Sentence Transformer model. Search/Chat features disabled.")
         vector_db_instance = None

    print("Model initialization complete.")
    if not gemini_api_instance: print("WARNING: Analysis features disabled (Gemini API init failed).")
    if not chat_model: print("WARNING: Chat feature disabled (Chat Model init failed).")
    if not vector_db_instance: print("WARNING: Search/Chat features disabled (Vector DB/ST Model init failed).")

except Exception as e:
    print(f"CRITICAL ERROR during global model initialization: {e}")
    traceback.print_exc()
    gemini_api_instance = None
    vector_db_instance = None
    chat_model = None
    print("FATAL: AI models failed to initialize. Core functionality may be broken.")

# --- Register Markdown Filter with Jinja2 ---
@app.template_filter('markdown')
def markdown_filter(s):
    if s:
        return Markup(markdown.markdown(s, extensions=['tables', 'fenced_code', 'nl2br']))
    return ''

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_session_filepaths(session_id, filename_base):
    if not session_id or not filename_base:
        print("Error: Missing session_id or filename_base for get_session_filepaths")
        return {}
    safe_base = secure_filename(filename_base)
    if not safe_base: safe_base = "untitled"

    session_prefix = f"{session_id}_{safe_base}"
    paths = {
        "raw": os.path.join(app.config['EXTRACTED_TEXTS_DIR'], f"{session_prefix}_raw.txt"),
        "anon": os.path.join(app.config['EXTRACTED_TEXTS_DIR'], f"{session_prefix}_anonymized.txt"),
        "chunks": os.path.join(app.config['EXTRACTED_TEXTS_DIR'], f"{session_prefix}_chunks.txt"),
        "csv": os.path.join(app.config['TABLES_DIR'], f"{session_prefix}_table.csv"),
        "index": os.path.join(app.config['INDICES_DIR'], f"{session_prefix}.index"),
        "embeddings": os.path.join(app.config['EMBEDDINGS_DIR'], f"{session_prefix}_embeddings.txt"),
    }
    for key, path in paths.items():
         try:
             dir_name = os.path.dirname(path)
             if dir_name: os.makedirs(dir_name, exist_ok=True)
         except OSError as e:
             print(f"Warning: Could not ensure directory for {key} path '{dir_name}': {e}")
    return paths

def cleanup_session_files(session_id):
    if not session_id: return
    print(f"Cleaning up files for session_id: {session_id}...")
    cleaned_count = 0
    error_count = 0
    scan_dirs = [
        app.config['UPLOAD_FOLDER'],
        app.config['EXTRACTED_TEXTS_DIR'],
        app.config['TABLES_DIR'],
        app.config['INDICES_DIR'],
        app.config['EMBEDDINGS_DIR']
    ]
    file_prefix = f"{session_id}_"

    for folder in scan_dirs:
        if not os.path.isdir(folder):
            continue
        try:
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                should_delete = False
                if filename.startswith(file_prefix):
                    should_delete = True
                elif folder == app.config['INDICES_DIR'] and filename.startswith(session_id) and filename.endswith(".index"):
                     should_delete = True

                if should_delete and os.path.isfile(filepath):
                    try:
                        os.remove(filepath)
                        cleaned_count += 1
                    except OSError as e:
                        print(f"Error removing file {filepath}: {e}")
                        error_count += 1
        except Exception as e:
            print(f"Error listing files during cleanup in {folder}: {e}")
            traceback.print_exc()
            error_count += 1
    print(f"Cleanup for session {session_id}: Removed {cleaned_count} files, encountered {error_count} errors.")


# --- Routes ---

@app.route('/', methods=['GET'])
def index():
    """Renders the main page."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        print(f"New session started: {session['session_id']}")
        session['chat_history'] = []
        session['processing_done'] = False
        session['current_file_name'] = None
        session['analysis'] = None
        session['csv_file_path'] = None
        session['index_filepath'] = None
        session['chunks_filepath'] = None
        session['chat_enabled_flag'] = False
    else:
         session.modified = True

    csv_available = False
    csv_path = session.get('csv_file_path')
    if csv_path and os.path.exists(csv_path):
        csv_available = True
    elif csv_path:
        session.pop('csv_file_path', None)
        session.modified = True

    # --- Debugging Log for Index Route ---
    print(f"\n--- State in index route (Session ID: {session.get('session_id')}) ---")
    print(f"Session processing_done: {session.get('processing_done')}")
    print(f"Session index_filepath: {session.get('index_filepath')}")
    print(f"Session chunks_filepath: {session.get('chunks_filepath')}")
    print(f"Session chat_enabled_flag: {session.get('chat_enabled_flag')}")
    print(f"Global chat_model available: {bool(chat_model)}")
    print(f"Global vector_db_instance available: {bool(vector_db_instance)}")
    index_exists = bool(session.get('index_filepath') and os.path.exists(session.get('index_filepath')))
    chunks_exist = bool(session.get('chunks_filepath') and os.path.exists(session.get('chunks_filepath')))
    print(f"Check: Index file exists on disk: {index_exists}")
    print(f"Check: Chunks file exists on disk: {chunks_exist}")
    print("-" * 20)
    # --- End Debugging Log ---

    template_context = {
        "session": session,
        "config": app.config,
        "analysis_available": bool(session.get('analysis')),
        "csv_available": csv_available,
        "processing_done": session.get('processing_done', False),
        "models_ready": bool(gemini_api_instance and vector_db_instance and chat_model),
        "chat_enabled": session.get('chat_enabled_flag', False) # Read flag from session
    }
    return render_template('index.html', **template_context)

@app.route('/upload', methods=['POST'])
def upload_process():
    """Handles file upload, extraction, chunking, and indexing."""
    print("--- >>> Entering /upload route <<< ---")
    global vector_db_instance

    # --- Pre-checks ---
    if not vector_db_instance or not vector_db_instance.model:
         flash('Vector Database or Embedding Model not ready. Cannot process file.', 'danger'); print("Error: /upload exit - VectorDB not ready.")
         return redirect(url_for('index'))
    if 'pdf_file' not in request.files:
        flash('No file part selected in the request.', 'warning'); print("Error: /upload exit - No 'pdf_file' in request.files.")
        return redirect(url_for('index'))
    file = request.files['pdf_file']
    if file.filename == '':
        flash('No file selected for upload.', 'warning'); print("Error: /upload exit - file.filename is empty.")
        return redirect(url_for('index'))
    if not file or not allowed_file(file.filename):
        flash('Invalid file type. Please upload a PDF file.', 'warning'); print(f"Error: /upload exit - Invalid file type or no file: {file.filename}")
        return redirect(url_for('index'))

    # --- Session Reset ---
    previous_session_id = session.get('session_id')
    if previous_session_id: cleanup_session_files(previous_session_id)
    session.clear(); session['session_id'] = str(uuid.uuid4()); session['chat_history'] = []; session['processing_done'] = False; session['chat_enabled_flag'] = False
    print(f"--- New Upload --- Session reset and started: {session['session_id']}")

    original_filename = file.filename
    filename_base = os.path.splitext(original_filename)[0]
    session['current_file_name'] = original_filename

    temp_pdf_path = None
    filepaths = get_session_filepaths(session['session_id'], filename_base)
    if not filepaths: flash("Internal Error: Failed to generate file paths.", "danger"); print("Error: /upload exit - Failed to get session filepaths."); return redirect(url_for('index'))

    print("--- Passed initial checks and session setup ---")
    session_index_filepath = None # Track path locally during this request
    session_chunks_filepath = None
    processing_succeeded = False

    try:
        print("--- Entering main processing TRY block ---")
        # --- 1. Save Temp File ---
        unique_filename = f"{session['session_id']}_{secure_filename(original_filename)}"
        temp_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        print(f"Attempting to save file to: {temp_pdf_path}")
        file.save(temp_pdf_path)
        print(f"File temporarily saved to: {temp_pdf_path}")

        # --- 2. Extract Text ---
        print("Step 1: Extracting text from PDF...")
        text_pages = extract_text_from_pdf(temp_pdf_path)
        if not text_pages or all(not page.strip() for page in text_pages): raise ValueError("Text extraction failed (no content).")
        print(f"Text extracted from {len(text_pages)} pages.")

        # --- 3. Save Text ---
        print("Step 2: Saving raw and anonymized text...")
        raw_path, anon_path, anon_text = save_extracted_text(text_pages, f"{session['session_id']}_{filename_base}", app.config['EXTRACTED_TEXTS_DIR'])
        if not raw_path or not anon_path: raise ValueError("Failed to save extracted text files.")
        session['raw_file_path'] = raw_path; session['anonymized_file_path'] = anon_path
        print("Raw and anonymized text saved.")

        # --- 4. Chunk Text ---
        print("Step 3: Chunking anonymized text...")
        processed_text = preprocess_text(anon_text); chunks = chunk_text(processed_text)
        if not chunks: print("Warning: No text chunks generated."); session_chunks_filepath = None
        else:
            chunks_filepath_local = filepaths.get('chunks');
            if not chunks_filepath_local: raise ValueError("Chunks file path not generated.")
            try:
                with open(chunks_filepath_local, 'w', encoding='utf-8') as f_chunks: f_chunks.write("\n<--MEDISCAN_CHUNK_SEPARATOR-->\n".join(chunks))
                session_chunks_filepath = chunks_filepath_local # Store locally
                print(f"{len(chunks)} chunks saved to: {chunks_filepath_local}")
            except IOError as e: raise ValueError(f"Failed to save text chunks: {e}")

        # --- 5. Create & Save Index ---
        session_index_filepath = None # Reset before attempt
        if chunks and vector_db_instance:
            print("Step 4: Creating vector index...")
            index_created = vector_db_instance.create_index(chunks)
            print(f"--> vector_db_instance.create_index returned: {index_created}")
            if index_created:
                index_filepath_local = filepaths.get('index'); embeddings_filepath = filepaths.get('embeddings')
                if not index_filepath_local: raise ValueError("Index file path not generated.")
                print(f"Attempting to save index to {index_filepath_local}...")
                index_saved = vector_db_instance.save_index(index_filepath_local, embeddings_filepath)
                print(f"--> vector_db_instance.save_index returned: {index_saved}")
                if index_saved: session_index_filepath = index_filepath_local # Store path locally
                else: print("Error: Failed to save vector index.")
            else: print("ERROR: Failed to create vector index from chunks.")
        elif not chunks: print("Skipping vector index creation (no chunks).")
        else: print("Skipping vector index creation (VectorDB not available).")

        processing_succeeded = True

    except ValueError as ve: print(f"--- Caught ValueError in /upload: {ve} ---"); flash(f"Processing Error: {str(ve)}", "danger")
    except Exception as e: print(f"--- Caught unexpected Exception in /upload: {type(e).__name__}: {e} ---"); traceback.print_exc(); flash(f"Unexpected processing error: {type(e).__name__}", "danger")
    finally:
        print("--- Entering FINALLY block for cleanup ---")
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            try: os.remove(temp_pdf_path); print(f"Temporary file deleted: {temp_pdf_path}")
            except OSError as e: print(f"Warning: Could not remove temporary file {temp_pdf_path}: {e}")
        print("--- Exiting FINALLY block ---")

    # --- Set final session state BEFORE redirect ---
    if processing_succeeded:
        session['processing_done'] = True
        session['chunks_filepath'] = session_chunks_filepath # Set session from local var
        session['index_filepath'] = session_index_filepath   # Set session from local var

        # Calculate chat enabled status HERE using local variables for accuracy
        chat_model_ready = bool(chat_model)
        vector_db_ready = bool(vector_db_instance)
        index_file_now_exists = bool(session_index_filepath and os.path.exists(session_index_filepath))
        chunks_file_now_exists = bool(session_chunks_filepath and os.path.exists(session_chunks_filepath))

        session['chat_enabled_flag'] = (
            processing_succeeded and
            index_file_now_exists and
            chunks_file_now_exists and
            chat_model_ready and
            vector_db_ready
        )
        print(f"--- Upload route finished. Setting chat_enabled_flag to: {session['chat_enabled_flag']} ---")
        print(f"(Based on: processing={processing_succeeded}, index_ok={index_file_now_exists}, chunks_ok={chunks_file_now_exists}, chat_model={chat_model_ready}, vectordb={vector_db_ready})")

        if session['chat_enabled_flag']: flash("File processed successfully! Ready for Analysis & Chat.", "success")
        elif session_chunks_filepath: flash("File processed for Analysis. Indexing for Chat failed or skipped.", "warning")
        else: flash("File processing finished with warnings or errors.", "warning")
    else:
        cleanup_session_files(session.get('session_id'))
        session.clear()

    print("--- Reached end of /upload route, redirecting ---")
    return redirect(url_for('index'))


@app.route('/analyze', methods=['POST'])
def analyze():
    """Generates the main analysis using Gemini and extracts the table."""
    print("\n--- >>> Entering /analyze route <<< ---")
    if not session.get('processing_done'): flash("Please upload and process a file first.", "warning"); return redirect(url_for('index'))
    if not gemini_api_instance: flash('Analysis Service (Gemini API) unavailable.', 'danger'); return redirect(url_for('index'))

    chunks_filepath = session.get('chunks_filepath')
    index_filepath = session.get('index_filepath')

    if not chunks_filepath or not os.path.exists(chunks_filepath):
         flash("Error: Text chunks file missing. Re-process.", "danger"); session['processing_done'] = False; session.pop('chunks_filepath', None)
         return redirect(url_for('index'))

    # --- Load Chunks ---
    try:
        with open(chunks_filepath, 'r', encoding='utf-8') as f_chunks: chunks = f_chunks.read().split("\n<--MEDISCAN_CHUNK_SEPARATOR-->\n")
        chunks = [c for c in chunks if c.strip()]
        if not chunks: raise ValueError("Chunks file empty.")
        print(f"Loaded {len(chunks)} chunks for analysis.")
    except Exception as e: print(f"Error reading chunks: {e}"); flash("Error reading text data. Re-upload.", "danger"); return redirect(url_for('index'))

    # --- Analysis Process ---
    context = ""; analysis_result = None
    try:
        # --- Retrieve Context ---
        analysis_query = "Provide a comprehensive analysis of this medical report, including summary, explanation, potential diagnoses, recommendations, and a detailed biomarker table following the specified format."
        if index_filepath and os.path.exists(index_filepath) and vector_db_instance:
            print("Attempting RAG context retrieval...")
            if vector_db_instance.load_index(index_filepath):
                distances, indices = vector_db_instance.search(analysis_query, k=7)
                if indices is not None and len(indices) > 0 and len(indices[0]) > 0:
                    relevant_indices = [idx for idx in indices[0] if 0 <= idx < len(chunks)]
                    if relevant_indices: context = "\n\n---\n\n".join([chunks[i] for i in relevant_indices]); print(f"Retrieved {len(relevant_indices)} relevant chunks.")
                    else: print("Warning: RAG indices invalid. Using full text.")
                else: print("Warning: RAG search empty. Using full text.")
            else: print("Warning: Failed to load index for RAG. Using full text.")
        else: print("Index not available. Using full text.")

        if not context: context = "\n\n---\n\n".join(chunks); print("Using full text as context.")

        # --- Generate Analysis ---
        print("Generating analysis using Gemini..."); analysis_result = gemini_api_instance.generate_analysis(context, analysis_query)
        if not analysis_result or analysis_result.startswith("Error"): raise ValueError(analysis_result or "Empty analysis response")
        session['analysis'] = analysis_result; print("Analysis generated.")

        # --- Extract Table ---
        print("Attempting table extraction..."); filename_base = os.path.splitext(session['current_file_name'])[0]; unique_csv_base = f"{session['session_id']}_{filename_base}"
        csv_path = save_table(analysis_result, unique_csv_base, output_dir=app.config['TABLES_DIR'])
        if csv_path and os.path.exists(csv_path): session['csv_file_path'] = csv_path; flash("Analysis complete. Table extracted.", "success"); print(f"Table saved: {csv_path}")
        else: flash("Analysis complete. No table auto-extracted.", "info"); print("No table extracted/saved."); session.pop('csv_file_path', None)

    except ValueError as ve: print(f"Analysis ValueError: {ve}"); flash(f"Analysis Error: {str(ve)}", "danger")
    except FileNotFoundError as fnf: print(f"Analysis File Error: {fnf}"); flash(f"Error: File missing ({fnf.filename}). Re-process.", "danger"); session['processing_done'] = False
    except Exception as e: print(f"Analysis Unexpected Error: {e}"); traceback.print_exc(); flash(f"Unexpected analysis error: {type(e).__name__}", "danger")
    finally:
        if not analysis_result or analysis_result.startswith("Error"): session.pop('analysis', None); session.pop('csv_file_path', None) # Clear on error

    print("--- Exiting /analyze route ---")
    return redirect(url_for('index'))


@app.route('/chat', methods=['POST'])
def chat():
    """Handles chat queries using RAG."""
    print("\n--- >>> Entering /chat route <<< ---")
    try:
        # --- Pre-checks ---
        if not session.get('processing_done'): raise ValueError("Processing not done.")
        if not chat_model: raise RuntimeError("Chat model unavailable.")
        if not vector_db_instance or not vector_db_instance.model: raise RuntimeError("VectorDB unavailable.")

        index_filepath = session.get('index_filepath')
        if not index_filepath or not os.path.exists(index_filepath): raise FileNotFoundError("Chat index missing.")
        if not vector_db_instance.index:
            print("Chat: Index not loaded, loading...");
            if not vector_db_instance.load_index(index_filepath): raise RuntimeError("Failed to load chat index.")
            print("Chat: Index loaded.")

        chunks_filepath = session.get('chunks_filepath')
        if not chunks_filepath or not os.path.exists(chunks_filepath): raise FileNotFoundError("Chat chunks missing.")

        # --- Get Query ---
        data = request.get_json();
        if not data: raise ValueError("Invalid request format.")
        user_query = data.get('query','').strip()
        if not user_query: raise ValueError("Empty query.")

        # --- Load Chunks ---
        try:
            with open(chunks_filepath, 'r', encoding='utf-8') as f: chunks = f.read().split("\n<--MEDISCAN_CHUNK_SEPARATOR-->\n")
            chunks = [c for c in chunks if c.strip()]
            if not chunks: raise ValueError("Report content empty.")
        except Exception as e: raise IOError(f"Internal error reading content: {type(e).__name__}")

        # --- Process Query ---
        if 'chat_session_data' not in session: session['chat_session_data'] = initialize_chat(); session['chat_history'] = []
        response_text = process_chat_query(user_query, vector_db_instance, chat_model, chunks, session['chat_session_data'])

        if response_text.startswith("Error:") or "encountered an error" in response_text:
            print(f"Chat Error from processing: {response_text}")
            return jsonify({"error": response_text}), 500 # Return specific error from processing

        # Success
        chat_history = session.get('chat_history', []); chat_history.append({"role": "user", "content": user_query}); chat_history.append({"role": "assistant", "content": response_text})
        session['chat_history'] = chat_history[-20:]; session.modified = True
        print("--- Exiting /chat route (Success) ---")
        return jsonify({"response": response_text})

    # --- Catch ALL Exceptions during route execution ---
    except (ValueError, RuntimeError, FileNotFoundError, IOError) as e:
        print(f"!!! Handled Error in /chat route: {type(e).__name__}: {e} !!!")
        return jsonify({"error": str(e)}), 400 # Bad request or specific resource error
    except Exception as e:
        error_type = type(e).__name__
        print(f"!!! Unhandled Error in /chat route: {error_type}: {e} !!!"); traceback.print_exc()
        print("--- Exiting /chat route (Unhandled Error - Returning JSON) ---")
        return jsonify({"error": f"A critical server error occurred ({error_type}). Check logs."}), 500


@app.route('/visualize', methods=['GET'])
def visualize():
    """Generates and returns visualizations."""
    print("\n--- >>> Entering /visualize route <<< ---")
    csv_path = session.get('csv_file_path')
    if not csv_path: print("Exiting /visualize: No CSV path."); return jsonify({"error": "No extracted table data found."}), 404
    if not os.path.exists(csv_path): print(f"Exiting /visualize: CSV not found at {csv_path}"); session.pop('csv_file_path', None); session.modified = True; return jsonify({"error": f"Table data file missing. Re-analyze."}), 404

    try:
        print(f"Generating visualizations from: {csv_path}"); plots_base64_dict = generate_visualizations(csv_path)
        if plots_base64_dict is None: print("Exiting /visualize: generate_visualizations returned None."); return jsonify({"error": "CSV file error during visualization."}), 404
        elif not plots_base64_dict: print("Exiting /visualize: No suitable data found."); return jsonify({"plots": {}, "message": "No data suitable for visualization."})
        else: print(f"Exiting /visualize: Returning {len(plots_base64_dict)} plot(s)."); return jsonify({"plots": plots_base64_dict})
    except pd.errors.EmptyDataError: print(f"Exiting /visualize: EmptyDataError: {csv_path}"); return jsonify({"error": "Extracted table data empty/invalid."}), 404
    except Exception as e: print(f"Error in /visualize: {e}"); traceback.print_exc(); print("Exiting /visualize: Unexpected error."); return jsonify({"error": f"Unexpected visualization error: {type(e).__name__}"}), 500


@app.route('/download_report', methods=['GET'])
def download_report():
    """Downloads the analysis as PDF."""
    print("\n--- >>> Entering /download_report route <<< ---")
    if 'analysis' not in session or not session.get('analysis'): flash("No analysis available.", "warning"); return redirect(url_for('index'))
    analysis_text = session['analysis']; filename_base = "MediScan_Analysis_Report"
    if 'current_file_name' in session and session['current_file_name']: safe_base = secure_filename(os.path.splitext(session['current_file_name'])[0]); filename_base = f"MediScan_Analysis_{safe_base}" if safe_base else filename_base
    pdf_filename = f"{filename_base}.pdf"
    try:
        print(f"Generating PDF: {pdf_filename}"); pdf_buffer = io.BytesIO()
        if not export_to_pdf(analysis_text, filename=pdf_buffer): raise ValueError("PDF generation failed.")
        pdf_buffer.seek(0); print("Sending PDF file...");
        return send_file(pdf_buffer, as_attachment=True, download_name=pdf_filename, mimetype='application/pdf')
    except Exception as e: print(f"Error generating/sending PDF: {e}"); traceback.print_exc(); flash(f"Could not generate PDF: {str(e)}", "danger"); return redirect(url_for('index'))


@app.route('/download_csv', methods=['GET'])
def download_csv():
    """Downloads the extracted table as CSV."""
    print("\n--- >>> Entering /download_csv route <<< ---")
    csv_path = session.get('csv_file_path')
    if not csv_path : flash("No CSV data available.", "warning"); return redirect(url_for('index'))
    if not os.path.exists(csv_path): flash(f"CSV file missing. Re-analyze.", "warning"); session.pop('csv_file_path', None); session.modified = True; return redirect(url_for('index'))
    filename_base = "MediScan_Extracted_Table"
    if 'current_file_name' in session and session['current_file_name']: safe_base = secure_filename(os.path.splitext(session['current_file_name'])[0]); filename_base = f"MediScan_Table_{safe_base}" if safe_base else filename_base
    download_filename = f"{filename_base}.csv"
    try:
        print(f"Sending CSV: {download_filename} from {csv_path}")
        return send_file(csv_path, as_attachment=True, download_name=download_filename, mimetype='text/csv')
    except Exception as e: print(f"Error sending CSV: {e}"); traceback.print_exc(); flash(f"Could not download CSV: {str(e)}", "danger"); return redirect(url_for('index'))


@app.route('/reset', methods=['POST'])
def reset():
    """Clears session and files."""
    print("\n--- >>> Entering /reset route <<< ---")
    session_id = session.get('session_id');
    if session_id: cleanup_session_files(session_id)
    session.clear(); flash("Session reset.", "info"); print("Session reset.")
    return redirect(url_for('index'))

# --- Run App ---
if __name__ == '__main__':
    print("Starting Flask application...")
    # Set debug=False for production deployment
    app.run(debug=True, host='127.0.0.1', port=5000)

# --- END OF FILE app.py ---