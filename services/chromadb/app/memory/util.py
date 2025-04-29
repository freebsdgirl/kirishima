import app.memory.setup


async def get_collection():
    """
    Asynchronously retrieves the ChromaDB collection instance.
    
    Returns:
        ChromaDB Collection: The configured ChromaDB collection for memory storage.
    """
    return app.memory.setup.collection()