#!/usr/bin/env python
"""
Main entry point for Resume Screening API
Run this file to start the Flask development server
"""

import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app

if __name__ == '__main__':
    app = create_app()
    
    print("""
    ════════════════════════════════════════════════════════════
    Resume Screening & Job Matching API
    ════════════════════════════════════════════════════════════
    
    Flask server starting...
    
    API Endpoints:
    - POST   /api/resumes/upload     - Upload resumes
    - POST   /api/jobs/parse         - Parse job description
    - GET    /api/results/<batch_id> - Get results
    - GET    /api/status/<batch_id>  - Get processing status
    - GET    /health                 - Health check
    
    Local URL: http://localhost:5000
    
    ════════════════════════════════════════════════════════════
    """)
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=True
    )
