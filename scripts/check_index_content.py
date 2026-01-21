
import os
import sys
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient


# Configuration
SEARCH_SERVICE_NAME = os.environ.get("AZURE_SEARCH_SERVICE_NAME", "srch-drvagnt2-dev-7vczbz")
INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "driving-manual-index")
ENDPOINT = f"https://{SEARCH_SERVICE_NAME}.search.windows.net"

def check_index():
    print(f"Checking index: {INDEX_NAME}...")
    
    credential = DefaultAzureCredential()
    client = SearchClient(endpoint=ENDPOINT, index_name=INDEX_NAME, credential=credential)
    
    try:
        count = client.get_document_count()
        print(f"Total documents in index: {count}")
        
        if count == 0:
            print("Index is empty.")
            return

        # Query a few documents to check vector field
        results = client.search(
            search_text="*", 
            select=["chunk_id", "document_id", "chunk_vector", "parent_id", "content"], 
            top=5
        )
        
        print("\nSampling documents:")
        for doc in results:
            chunk_id = doc.get("chunk_id")
            doc_id = doc.get("document_id")
            parent_id = doc.get("parent_id")
            vector = doc.get("chunk_vector")
            content = doc.get("content")
            
            print(f"- Chunk ID: {chunk_id}")
            print(f"  Parent ID: {parent_id}")
            print(f"  Document ID: {doc_id}")
            print(f"  Content Length: {len(content) if content else 0}")
            
            if vector:
                print(f"  Vector found! Dimensions: {len(vector)}")
                # Check for zero vector? Unlikely but possible
                if all(v == 0 for v in vector):
                    print("  WARNING: Vector contains all zeros!")
            else:
                print("  WARNING: Vector field is None or missing!")
                
    except Exception as e:
        print(f"Error accessing index: {e}")

if __name__ == "__main__":
    check_index()
