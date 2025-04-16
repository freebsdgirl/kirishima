"""
This module provides an API endpoint for exporting internal documentation
of the `app` package. It uses the FastAPI framework to define a route
that walks through the `app` package, collects the `__doc__` strings
of all modules, functions, and classes, and returns them in a nested
dictionary format.

Functions:
-----------
- export_internal_docs():
    Walks the `app` package, finds all modules, functions, and classes,
    and returns their `__doc__` strings in a nested dictionary.

Dependencies:
-------------
- pkgutil: For walking through the package hierarchy.
- importlib: For dynamically importing modules.
- inspect: For retrieving documentation strings and inspecting members.
- fastapi.APIRouter: For defining the API route.
"""
import pkgutil
import importlib
import inspect


from fastapi import APIRouter
router = APIRouter()


@router.get("/docs/export", response_model=dict)
def export_internal_docs() -> dict:
    """
    Export internal documentation for the entire app package.

    Walks through all modules in the 'app' package, collecting module-level
    and member-level documentation strings. Returns a nested dictionary
    containing documentation for each module and its functions/classes.

    Returns:
        dict: A nested dictionary with module documentation and member documentation.
    """
    docs = {}
    for finder, module_name, is_pkg in pkgutil.walk_packages(path=["app"], prefix="app."):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue

        docs[module_name] = {"module_doc": inspect.getdoc(module), "members": {}}
        for name, member in inspect.getmembers(module, 
                       predicate=lambda x: inspect.isfunction(x) or inspect.isclass(x)):
            docs[module_name]["members"][name] = inspect.getdoc(member)

    return docs
