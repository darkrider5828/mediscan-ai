import google.generativeai as genai
import os
import traceback

class GeminiAPI:
    def __init__(self, api_key, model_name="gemini-2.0-flash"):
        """
        Initializes the Gemini API client.

        Args:
            api_key (str): The Gemini API key.
            model_name (str): The specific Gemini model to use.
                               Verify valid model names from Google AI documentation.
        """
        if not api_key:
            raise ValueError("Gemini API key is required.")

        try:
            # Configure the API key (can be done once globally, but doing it here is safe)
            genai.configure(api_key=api_key)
            print(f"Gemini API configured for model: {model_name}")
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to configure Gemini API: {e}")
            raise

        # Default generation config (can be overridden if needed)
        self.generation_config = {
            "temperature": 0.8,      # Slightly less random for more consistent table structure
            "top_p": 0.95,
            "top_k": 40
        }

        # Initialize the model
        try:
            self.model = genai.GenerativeModel(model_name, generation_config=self.generation_config)
            print(f"Successfully initialized Gemini model: {model_name}")
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to initialize Gemini model '{model_name}': {e}")
            print("Please ensure the model name is correct and the API key is valid.")
            raise

    def generate_analysis(self, context, query):
        """Generate analysis using the configured Gemini model."""
        if not self.model:
            return "Error: Gemini model not initialized."
        if not context or not query:
            return "Error: Context and query are required for analysis."

        # Refined prompt for clarity and specific instructions
        prompt = f"""
        Analyze the following medical report context based on the user's query.

        **Context from Report:**
        ```
        {context}
        ```

        **User Query:**
        {query}

        **Instructions:**
        Provide the output in the following structured format:
        1. Overall Summary (make sure that you include all relevant details and the parameters).
        2. Explanation about the report (make sure that you include all relevant details and the parameters).
        3. Potential Diagnoses 
        4. Medical Recommendations
        Use color-coded risk levels (🟢 Normal, 🟡 Borderline, 🔴 Concerning) for each finding. + [Table format] 
        Include ALL parameters from the report in the output table.make sure that u use all the perameters and the extract text and mention all the range in the table 
        Do not exclude any parameters, even if they are within normal ranges.
        Table format : Test	Value | Reference Range | Units | Risk Level | Note | Explanation
        Note column contain Normal, Borderline, Concerning accordingly to the color in Risk Level column.
        Give title of table "Table Format with Color-Coded Risk Levels"

        """
        try:
            response = self.model.generate_content(prompt)
            # Basic check for blocked content
            if response.prompt_feedback.block_reason:
                 reason = response.prompt_feedback.block_reason
                 print(f"Warning: Gemini analysis generation blocked. Reason: {reason}")
                 return f"Error: Analysis generation failed due to content policy ({reason})."
            # Return text content
            return response.text
        except Exception as e:
            print(f"ERROR during Gemini analysis generation: {str(e)}")
            traceback.print_exc()
            # Provide a more informative error message
            return f"Error generating analysis: An issue occurred with the AI model ({type(e).__name__}). Please check logs."