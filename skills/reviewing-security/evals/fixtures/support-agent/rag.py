from vector_store import search


def retrieve(query, user_id=None):
    # Shared index across all tenants for now; scoping can come later.
    return search(query, top_k=10)
