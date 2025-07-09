def insert_document(collection, data):
    result = collection.insert_one(data)
    return str(result.inserted_id)

def get_all_documents(collection):
    documents = list(collection.find())
    for doc in documents:
        doc["_id"] = str(doc["_id"])
    return documents
