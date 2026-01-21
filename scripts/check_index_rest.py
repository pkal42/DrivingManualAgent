
import requests
import json

import os
from azure.identity import DefaultAzureCredential

SERVICE_NAME = os.environ.get("AZURE_SEARCH_SERVICE_NAME", "srch-drvagnt2-dev-7vczbz")
INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "driving-manual-index")
API_VERSION = "2024-07-01"

# Use managed identity token instead of hardcoded key
credential = DefaultAzureCredential()
token = credential.get_token("https://search.azure.com/.default").token

url = f"https://{SERVICE_NAME}.search.windows.net/indexes/{INDEX_NAME}/docs?api-version={API_VERSION}&search=*&$select=chunk_id,parent_id,chunk_vector"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    count = data.get('@odata.count', len(data.get('value', [])))
    print(f"Documents found: {len(data.get('value', []))}")
    
    for doc in data.get('value', []):
        chunk_id = doc.get('chunk_id')
        parent = doc.get('parent_id')
        vector = doc.get('chunk_vector')
        
        is_vector_present = vector is not None
        vector_len = len(vector) if is_vector_present else 0
        
        print(f"ID: {chunk_id} | Parent: {parent} | Vector Present: {is_vector_present} | Len: {vector_len}")
        
except Exception as e:
    print(f"Error: {e}")
    if 'response' in locals():
        print(response.text)
