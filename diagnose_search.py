from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient

endpoint = 'https://srch-drvagnt2-dev-7vczbz.search.windows.net'
index_name = 'driving-manual-index'
credential = DefaultAzureCredential()

client = SearchClient(endpoint, index_name, credential)

print("--- Searching for 'cell phone' with source_type='image' ---")
results = client.search(search_text='cell phone', filter="source_type eq 'image'", select='content, image_blob_name, image_blob_container')

count = 0
for r in results:
    count += 1
    print(f"[{r.get('@search.score')}] Container: {r.get('image_blob_container')} | Blob: {r.get('image_blob_name')}")
    print(f"Caption: {r.get('content')}")
    print("-" * 20)

if count == 0:
    print("No image results found for 'cell phone'.")

print("\n--- Sampling Image Captions (Top 20) ---")
results = client.search(search_text='*', filter="source_type eq 'image'", top=20, select='content')
for r in results:
    print(f"Caption: {r.get('content')}")
