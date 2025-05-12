from flask import Blueprint, render_template, redirect, request, url_for, jsonify, flash, current_app, Response, session, g
# Keep minimal necessary imports if any are needed directly by the blueprint setup

# Define the blueprint
crm_bp = Blueprint(
    'crm', 
    __name__, 
    template_folder='../templates/crm', # Point to the crm templates directory
    url_prefix='/crm' # Set base URL prefix for all routes in this blueprint
)

# Import the route modules to register the routes with the blueprint
# These imports MUST come AFTER the blueprint definition
from .crm import dashboard_routes
from .crm import contact_routes
from .crm import account_routes
from .crm import deal_routes
from .crm import task_routes
from .crm import call_routes
from .crm import import_routes
