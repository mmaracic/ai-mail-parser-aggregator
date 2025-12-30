"""Azure Functions entry point for the FastAPI application."""

import azure.functions as func

from application import app as fastapi_app

app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
