# --- START OF FILE vector_db.py ---

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import traceback

class VectorDB:
    def __init__(self, model_name='all-MiniLM-L6-v2'): # <<< MAKE SURE THIS LINE HAS model_name
        """
        Initializes the VectorDB, loading the Sentence Transformer model.

        Args:
            model_name (str): The name of the Sentence Transformer model to use.
                              Must match the model used for querying.
        """
        self.index = None
        self.chunks = [] # Store chunks alongside the index if needed for retrieval
        self.model_name = model_name
        # Corrected path to be relative to project root or use absolute paths
        self.embeddings_folder = os.path.join('processed_data', 'embeddings')

        try:
            print(f"Loading Sentence Transformer model: {self.model_name}...")
            self.model = SentenceTransformer(self.model_name)
            print("Sentence Transformer model loaded successfully.")
            # Check if model loaded successfully before getting dimension
            if self.model:
                self.dimension = self.model.get_sentence_embedding_dimension()
                print(f"Embedding dimension: {self.dimension}")
            else:
                raise ValueError("SentenceTransformer model object is None after initialization.")

        except Exception as e:
            print(f"CRITICAL ERROR: Failed to load Sentence Transformer model '{self.model_name}': {e}")
            print("Vector search functionality will not work.")
            traceback.print_exc()
            self.model = None # Ensure model is None if loading failed
            self.dimension = 0

    def create_index(self, chunks):
        """Create a FAISS index from a list of text chunks."""
        if not self.model:
            print("Error: Sentence Transformer model not loaded. Cannot create index.")
            return False
        if not chunks or not isinstance(chunks, list):
             print("Error: Invalid or empty chunks provided for indexing.")
             return False

        self.chunks = chunks
        print(f"Generating embeddings for {len(chunks)} chunks...")
        try:
            # Use the loaded self.model instance
            embeddings = self.model.encode(chunks, show_progress_bar=True)

            if not isinstance(embeddings, np.ndarray) or embeddings.ndim != 2 or embeddings.shape[1] != self.dimension:
                 print(f"Error: Embeddings generation failed or produced unexpected shape. Got shape: {embeddings.shape if isinstance(embeddings, np.ndarray) else type(embeddings)}")
                 return False

            print(f"Embeddings generated successfully. Shape: {embeddings.shape}")

            # Create FAISS index
            # Ensure dimension is correctly set from the loaded model
            if self.dimension <= 0:
                print("Error: Cannot create index with dimension <= 0.")
                return False
            self.index = faiss.IndexFlatL2(self.dimension) # Using L2 distance

            self.index.add(embeddings.astype('float32')) # Ensure correct dtype for FAISS
            print(f"FAISS index created and populated with {self.index.ntotal} vectors.")
            return True

        except Exception as e:
            print(f"Error during embedding generation or index creation: {e}")
            traceback.print_exc()
            self.index = None
            self.chunks = []
            return False

    def save_index(self, index_filepath, embeddings_filepath=None):
        """Save the FAISS index and optionally the raw embeddings."""
        if not self.index:
            print("Error: No index to save.")
            return False
        if not index_filepath:
            print("Error: Index filepath not provided for saving.")
            return False

        try:
            # Ensure directory exists
            index_dir = os.path.dirname(index_filepath)
            if index_dir: os.makedirs(index_dir, exist_ok=True)

            faiss.write_index(self.index, index_filepath)
            print(f"FAISS index saved successfully to: {index_filepath}")

            # Optionally save embeddings
            # Saving the numpy array used for self.index.add is more reliable than reconstructing
            # This requires passing the embeddings array to this function or storing it in self
            # For simplicity, we skip saving embeddings separately here.
            if embeddings_filepath:
                 print("Info: Saving embeddings separately is currently skipped in this version.")
                 # If you need it:
                 # 1. Modify create_index to store `embeddings` in `self.stored_embeddings`.
                 # 2. Modify this function to accept `embeddings` or use `self.stored_embeddings`.
                 # 3. Use np.savetxt(embeddings_filepath, embeddings_array) here.

            return True

        except Exception as e:
            print(f"Error saving FAISS index to {index_filepath}: {e}")
            traceback.print_exc()
            return False

    def load_index(self, index_filepath):
        """Load the FAISS index from a file."""
        if not index_filepath or not os.path.exists(index_filepath):
            print(f"Error: Index file not found at {index_filepath}")
            self.index = None
            return False
        try:
            print(f"Loading FAISS index from: {index_filepath}")
            self.index = faiss.read_index(index_filepath)

            # Verify the dimension matches the currently loaded model
            if self.dimension == 0 and self.model: # Try to get dimension if not set
                 self.dimension = self.model.get_sentence_embedding_dimension()

            # Crucial check: Compare index dimension with model dimension
            if self.index.d != self.dimension and self.dimension != 0:
                 print(f"CRITICAL WARNING: Loaded index dimension ({self.index.d}) does NOT match the current Sentence Transformer model dimension ({self.dimension}).")
                 print("This indicates a mismatch. Vector search will likely fail or produce incorrect results.")
                 print("Ensure the index was created with the same model ('{self.model_name}') being used now.")
                 # Optionally, reject loading the index:
                 # self.index = None
                 # return False
            elif self.dimension == 0:
                 print("Warning: Model dimension is unknown, cannot verify loaded index dimension.")


            print(f"FAISS index loaded successfully (ntotal={self.index.ntotal}, d={self.index.d})")
            return True
        except Exception as e:
            print(f"Error loading FAISS index from {index_filepath}: {e}")
            traceback.print_exc()
            self.index = None
            return False

    def search(self, query, k=5):
        """Search for the top k most relevant chunks for a given query string."""
        if not self.model:
            print("Error: Sentence Transformer model not loaded. Cannot perform search.")
            return None, None # Return tuple of None
        if not self.index:
            print("Error: FAISS index not created or loaded. Cannot perform search.")
            return None, None
        if not query or not isinstance(query, str):
             print("Error: Invalid query provided for search.")
             return None, None
        if self.index.ntotal == 0:
            print("Warning: Search attempted on an empty index.")
            return np.array([]), np.array([]) # Return empty arrays

        try:
            # Ensure k is valid
            k = min(k, self.index.ntotal)
            if k <= 0:
                print("Warning: k must be positive for search.")
                return np.array([]), np.array([])

            # Use the loaded self.model instance
            query_embedding = self.model.encode([query])

            # Check embedding dimension matches index dimension before searching
            if query_embedding.shape[1] != self.index.d:
                print(f"Error: Query embedding dimension ({query_embedding.shape[1]}) does not match index dimension ({self.index.d}).")
                return None, None

            # Perform search
            distances, indices = self.index.search(query_embedding.astype('float32'), k)
            # print(f"Search results: Indices={indices}, Distances={distances}") # Debug
            return distances, indices # Return tuple (distances, indices)

        except Exception as e:
            print(f"Error during FAISS search: {e}")
            traceback.print_exc()
            return None, None # Indicate error

# --- END OF FILE vector_db.py ---