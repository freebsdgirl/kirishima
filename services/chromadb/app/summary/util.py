import app.summary.setup


async def get_collection():
    """
    Asynchronously retrieves the ChromaDB collection instance.
    
    Returns:
        ChromaDB Collection: The configured ChromaDB collection for summary storage.
    """
    return app.summary.setup.collection()