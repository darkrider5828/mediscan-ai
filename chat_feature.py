# --- START OF FILE chat_feature.py ---
# (v1.5 - Generalized Chat Response Logic with Strong Disclaimers)

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from sentence_transformers import SentenceTransformer
import os
import re
import traceback

# --- Constants ---
VECTOR_SEARCH_K = 5

# --- Initialization & Helper Functions (Keep as before) ---
def initialize_chat():
    """Initialize a new chat session."""
    return {"history": [], "previous_topics": [], "previous_recommendations": []}

def process_chat_query(query, vector_db, chat_model, chunks, chat_session):
    """Process a user query using RAG."""
    # ... (Vector search logic remains the same as v1.4) ...
    if not query: return "Please provide a query."
    if not vector_db or not vector_db.index or not vector_db.model:
        return "Error: Vector Database unavailable."
    if not chat_model: return "Error: Chat AI Model unavailable."
    if not chunks: return "Error: Report content (chunks) missing."

    print(f"\n--- Processing Chat Query: '{query}' ---")
    report_context = "No specific context found in the report for this query."
    relevant_chunks_found = False
    try:
        distances, indices = vector_db.search(query, k=VECTOR_SEARCH_K)
        if indices is not None and len(indices) > 0 and len(indices[0]) > 0:
            valid_indices = [idx for idx in indices[0] if idx != -1 and 0 <= idx < len(chunks)]
            if valid_indices:
                relevant_chunks = [chunks[i] for i in valid_indices]
                report_context = "\n\n---\n\n".join(relevant_chunks)
                relevant_chunks_found = True
                print(f"Found {len(valid_indices)} relevant chunks.")
            else: print("VectorDB search: No valid indices found.")
        else: print("Warning: VectorDB search returned no results.")
    except Exception as e:
        print(f"Error during vector_db search: {e}"); traceback.print_exc()
        report_context = "Error during report search."

    # Generate response using the NEW prompt logic
    response_text = generate_response(
        query,
        report_context,
        relevant_chunks_found,
        chat_model,
        chat_session
    )

    # Update session state (as before)
    is_error_response = response_text.startswith("Error:") or \
                        "encountered an error" in response_text or \
                        "cannot provide a response" in response_text or \
                        "response was blocked" in response_text
    if not is_error_response:
        current_history = chat_session.get("history", [])
        current_history.append({"user": query, "bot": response_text})
        chat_session["history"] = current_history[-20:]
        recs = extract_recommendations(response_text)
        if recs:
            prev_recs = chat_session.get("previous_recommendations", [])
            for r in recs:
                if r not in prev_recs: prev_recs.append(r)
            chat_session["previous_recommendations"] = prev_recs[-10:]
        topics = extract_topics(query + " " + response_text)
        if topics:
            prev_topics_list = chat_session.get("previous_topics", [])
            prev_topics_set = set(prev_topics_list); prev_topics_set.update(topics)
            chat_session["previous_topics"] = sorted(list(prev_topics_set))[:30]
        print(f"Chat response generated. History size: {len(chat_session['history'])}")
    else:
         print(f"Chat response resulted in error/block message: {response_text}")

    return response_text


def generate_response(query, report_context, relevant_chunks_found, chat_model, chat_session):
    """
    Generate a response using the Gemini API with RAG context.
    NEW: Allows more generalized answers for certain questions, with strong disclaimers.
    """
    # --- Construct History & Context Summary (Keep as before) ---
    conversation_history = ""
    recent_history = chat_session.get("history", [])[-4:]
    if recent_history:
        conversation_history += "Previous Conversation Turn(s):\n"
        for exchange in recent_history: conversation_history += f"User: {exchange.get('user', '')}\nAssistant: {exchange.get('bot', '')[:200]}\n\n"
        conversation_history = conversation_history.strip()
    else: conversation_history = "No previous turns."

    previous_interaction_summary = ""
    unique_recs = list(dict.fromkeys(chat_session.get("previous_recommendations", [])))
    if unique_recs: previous_interaction_summary += f"\nPrev Recs: {', '.join(unique_recs)}"
    previous_topics_list = chat_session.get("previous_topics", [])
    if previous_topics_list: previous_interaction_summary += f"\nPrev Topics: {', '.join(sorted(previous_topics_list))}"

    # --- MODIFIED PROMPT v1.5 ---
    prompt = f"""
    You are MediScan AI, a helpful assistant analyzing medical report data AND providing general health information.

    **CORE TASK:** Answer the user's question accurately and safely.

    **CONTEXT:**
    1.  **Medical Report Context:** Specific data extracted from the user's uploaded report. THIS IS THE PRIMARY SOURCE for questions about the report itself.
    ```
    {report_context}
    ```
    (Context Available in Report: {'Yes' if relevant_chunks_found else 'No'})

    2.  **Previous Conversation Context:** Recent chat history and topics.
    {conversation_history}
    {previous_interaction_summary.strip()}


    **RESPONSE RULES & PERSONA:**

    1.  **Report-Specific Questions:** If the question is clearly about the *content* of the report (e.g., "What was my hemoglobin level?", "What did the report say about RBC morphology?"), answer *strictly* based on the "Medical Report Context". State if the information isn't present.
    2.  **General Information Questions:** If the question asks for general knowledge about a medical term, test, or condition (e.g., "What is Hemoglobin (Hb)?", "What causes high cholesterol?"), provide a helpful, accurate, and neutral explanation based on general medical understanding. *Briefly check* if the report context mentions the term and include that if relevant (e.g., "Hemoglobin (Hb) is... Your report showed a value of X.").
    3.  **"How to Improve" Questions:** If the user asks how to improve a health parameter (e.g., "How to increase Hemoglobin?", "Ways to lower cholesterol?"), provide *general lifestyle and dietary suggestions* commonly associated with that parameter (e.g., iron-rich foods for Hb, balanced diet/exercise for cholesterol). You MAY include *general, conceptual* mentions of relevant nutrients or traditional approaches (like specific Ayurvedic herbs known for general wellness related to the topic, e.g., Ashwagandha for stress, Amla for Vitamin C/immunity) BUT frame them as "commonly discussed" or "traditionally used for general wellness" NOT as direct treatments or guaranteed solutions. **Avoid specific dosages or preparations.**
    4.  **"Should I..." / Advice Questions:** If the user asks for direct medical advice (e.g., "Should I consult a doctor?", "Is this result serious?", "Do I need medication?"):
        *   **NEVER give a direct 'yes' or 'no' answer.**
        *   **Start by stating you cannot give medical advice.** (e.g., "As an AI, I cannot provide medical advice or tell you definitively whether to consult a doctor.")
        *   **THEN, provide relevant GENERAL information:** Briefly explain what the parameter/finding typically relates to (e.g., "Low hemoglobin, as indicated in your report, is often associated with anemia...") OR discuss factors generally considered when deciding to consult a doctor about such results (e.g., "Factors physicians often consider include the specific value, other related results, symptoms, and medical history.")
        *   **Strongly recommend consultation:** Conclude by emphasizing the importance of discussing the specific results and concerns with a qualified healthcare professional.
    5.  **Safety First:** Prioritize user safety. Avoid definitive diagnoses, treatment plans, or specific medical instructions.
    6.  **Clarity & Tone:** Be clear, informative, helpful, and empathetic, but maintain professional boundaries. Use Markdown for formatting (bolding, lists).
    7.  **MANDATORY DISCLAIMER:** Include the following disclaimer at the end of **every** response that provides *any* general information or discusses health parameters (i.e., responds under Rules 2, 3, or 4):
        `\n\n**Disclaimer:** This information is for educational purposes only and does not constitute medical advice. Always consult your doctor or other qualified health provider with any questions you may have regarding a medical condition or treatment.`

    --- END RULES ---

    **User Question:** {query}

    --- Assistant Response (Follow Rules carefully): ---
    """

    print(f"--- Sending Prompt to Chat Model (Length: {len(prompt)}) ---")
    response_text = None

    try:
        print("--- Calling chat_model.generate_content ---")
        # Optional: Lower temperature slightly for more controlled general info
        generation_config = {"temperature": 0.75}
        response = chat_model.generate_content(prompt, generation_config=generation_config) # Add safety_settings if needed
        print("--- chat_model.generate_content finished ---")

        # --- Handle blocking ---
        prompt_feedback = getattr(response, 'prompt_feedback', None)
        if prompt_feedback and getattr(prompt_feedback, 'block_reason', None):
             reason = prompt_feedback.block_reason; print(f"Warning: Chat response blocked. Reason: {reason}")
             safety_ratings_str = str(getattr(prompt_feedback, 'safety_ratings', 'N/A')); print(f"Safety Ratings: {safety_ratings_str}")
             return f"My response was blocked due to content safety filters ({reason}). Please try rephrasing."

        # --- Extract text ---
        if hasattr(response, 'text') and isinstance(response.text, str): response_text = response.text; print("--- Extracted response via .text ---")
        elif hasattr(response, 'parts') and response.parts: response_text = "".join(part.text for part in response.parts if hasattr(part, 'text')); print("--- Extracted response via .parts ---")
        else: print(f"Warning: Unexpected response structure: {response}"); response_text = "Apologies, unexpected response format."

        # --- Add Mandatory Disclaimer if needed ---
        # Add if ANY general info/explanation/suggestion was given (Rules 2, 3, 4)
        # Heuristic: If response isn't just "Not found" or error/blocked message.
        needs_disclaimer = True # Default to needing it
        response_lower = response_text.lower().strip() if isinstance(response_text, str) else ""
        if response_lower.startswith("the provided report context does not contain specific information about") or \
           response_lower.startswith("based on the report context, the specific value for") or \
           response_lower.startswith("my response was blocked") or \
           response_lower.startswith("apologies, i received an empty") or \
           len(response_lower) < 50: # Very short responses might not need it
            needs_disclaimer = False

        if needs_disclaimer and "Disclaimer:" not in response_text:
             disclaimer = "\n\n**Disclaimer:** This information is for educational purposes only and does not constitute medical advice. Always consult your doctor or other qualified health provider with any questions you may have regarding a medical condition or treatment."
             response_text += disclaimer

        return response_text if response_text is not None else ""

    # --- Exception Handling ---
    except Exception as e:
        error_type = type(e).__name__; error_details = str(e)
        print(f"!!! ERROR during Gemini API call for chat: {error_type}: {error_details} !!!"); traceback.print_exc()
        user_error_message = f"Sorry, I encountered a server error ({error_type}) while generating response."
        # Add specific error checks as before...
        if "API key not valid" in error_details: user_error_message = "Error: Invalid API Key for chat model."
        elif "quota" in error_details.lower(): user_error_message = "Error: Chat API quota exceeded."
        elif "Deadline Exceeded" in error_type: user_error_message = "Error: AI request timed out."
        elif "permission denied" in error_details.lower(): user_error_message = "Error: Permission denied for AI service."
        elif "candidate" in error_details.lower() and "SAFETY" in error_details: user_error_message = "Error: Response blocked by safety settings."
        return user_error_message

# --- Helper Functions ---
# (Keep extract_recommendations and extract_topics as they were in the last complete version)
def extract_recommendations(response_text):
    """Extracts potential recommendations from the response text."""
    if not isinstance(response_text, str): return []
    recommendations = []; lines = response_text.split('\n'); in_recommendation_section = False
    recommendation_markers = ["recommendations:", "plan:", "suggestions:", "medical recommendations:", "lifestyle considerations:"]
    disclaimer_phrases = ["disclaimer:", "this information is for", "consult your doctor"]
    for line in lines:
        stripped_line = line.strip(); lower_line = stripped_line.lower()
        if any(phrase in lower_line for phrase in disclaimer_phrases): break
        if any(marker in lower_line for marker in recommendation_markers): in_recommendation_section = True; continue
        if in_recommendation_section:
            if stripped_line and (stripped_line[0] in ('*', '-', '•') or re.match(r'^\d+\.\s+', stripped_line)):
                 rec_text = re.sub(r'^[\d.*\-•]\s*', '', stripped_line).strip()
                 if rec_text and len(rec_text) > 10: recommendations.append(rec_text)
    return list(dict.fromkeys(recommendations))

def extract_topics(text):
    """Extracts potential medical topics from text."""
    if not isinstance(text, str): return set()
    medical_topics = [ # Keep this list comprehensive
        "fatigue", "diabetes", "hypertension", "anemia", "infection", "inflammation", "cancer", "tumor",
        "hypothyroid", "hyperthyroid", "cholesterol", "obesity", "pain", "fever", "headache", "leucopenia",
        "microcytic", "hypochromic", "glucose", "a1c", "hemoglobin", "wbc", "rbc", "platelet", "cbc",
        "bmp", "cmp", "hematocrit", "hct", "cholesterol", "ldl", "hdl", "triglycerides", "lipid panel",
        "packed cell volume", "pcv", "creatinine", "bun", "gfr", "kidney function", "renal", "mcv", "mch",
        "mchc", "rdw", "alt", "ast", "bilirubin", "liver function", "hepatic", "platelet count", "mpv",
        "pct", "pdw-sd", "pdw-cv", "p-lcc", "p-lcr", "tsh", "t3", "t4", "thyroid function", "sodium",
        "potassium", "chloride", "electrolytes", "crp", "esr", "iron", "ferritin", "b12", "folate", "psa",
        "biopsy", "imaging", "scan", "x-ray", "mri", "ct scan", "ultrasound", "medication", "prescription",
        "treatment", "therapy", "surgery", "lifestyle modification", "diet", "nutrition", "exercise",
        "hydration", "sleep", "stress management", "report", "summary", "findings", "observation",
        "impression", "diagnosis", "prognosis", "recommendation", "plan", "follow up", "consultation",
        "doctor", "physician", "specialist", "risk level", "reference range", "units", "value", "result",
        "parameter", "wellness", "health", "immunity", "ayurveda", "home remedy", "ashwagandha", "amla" # Added examples
    ]
    topics = set(); text_lower = text.lower()
    for topic in medical_topics:
        pattern = r'\b' + re.escape(topic) + r'(?:s)?\b'
        try:
            if re.search(pattern, text_lower): topics.add(topic)
        except re.error as e: print(f"Regex error searching for topic '{topic}': {e}")
    # Add broader categories
    if any(t in topics for t in ["alt", "ast", "bilirubin"]): topics.add("liver function")
    if any(t in topics for t in ["creatinine", "gfr", "bun"]): topics.add("kidney function")
    if any(t in topics for t in ["wbc", "rbc", "platelet", "hemoglobin", "hematocrit", "hct", "pcv"]): topics.add("cbc")
    if any(t in topics for t in ["ldl", "hdl", "triglycerides"]): topics.add("lipid panel")
    if any(t in topics for t in ["mcv", "mch", "mchc", "rdw"]): topics.add("rbc indices")
    if any(t in topics for t in ["mpv", "pct", "pdw-sd", "pdw-cv"]): topics.add("platelet indices")
    return set(list(topics)[:30])

# --- END OF FILE chat_feature.py ---