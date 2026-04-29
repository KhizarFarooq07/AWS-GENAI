# Resume Screening & Job Matching - Local Development Setup

## Project Structure

```
resume-screening/
├── backend/
│   ├── app/
│   │   ├── __init__.py           # Flask app factory
│   │   ├── routes.py             # API endpoints
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── textract_service.py      # PDF text extraction
│   │       ├── comprehend_service.py    # NLP/skill extraction
│   │       ├── bedrock_service.py       # LLM scoring
│   │       ├── dynamodb_service.py      # Database ops
│   │       └── github_service.py        # GitHub profile fetching
│   ├── config.py                 # Configuration management
│   ├── run.py                    # Flask entry point
│   └── requirements.txt           # Python dependencies
│
├── frontend/                      # React app (coming next)
├── uploads/                       # Temporary resume storage
├── logs/                          # Application logs
├── .env.example                  # Template for .env file
└── .gitignore                    # Git ignore patterns
```

## Setup Instructions

### Step 1: Create Virtual Environment

```bash
cd /Users/khizar.khan/AWS-GENAI/resume-screening

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# OR
.\venv\Scripts\activate   # On Windows
```

### Step 2: Copy Environment Template

```bash
cp .env.example .env

# Note: You'll fill in AWS credentials after account setup
# For now, it's just placeholder values
```

### Step 3: Install Python Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- Flask (web framework)
- Flask-CORS (cross-origin requests)
- boto3 (AWS SDK)
- python-dotenv (environment management)
- pdf2image (PDF processing)
- And other utilities

### Step 4: Verify Installation

```bash
# Check if Flask is installed
python -c "import flask; print(f'Flask {flask.__version__}')"

# Check if boto3 is installed  
python -c "import boto3; print(f'boto3 {boto3.__version__}')"
```

### Step 5: Start the Backend Server

```bash
cd backend

# Run the Flask app
python run.py
```

You should see:
```
════════════════════════════════════════════════════════════
Resume Screening & Job Matching API
════════════════════════════════════════════════════════════

Flask server starting...

Local URL: http://localhost:5000
════════════════════════════════════════════════════════════
```

### Step 6: Test the API

In another terminal:

```bash
# Health check
curl http://localhost:5000/health

# Should return:
# {"status":"healthy","message":"Resume Screening API is running"}
```

### Step 7: Test file upload (mock)

```bash
# Create a dummy PDF for testing
echo "PDF mock file" > test_resume.txt

# Upload via curl
curl -X POST -F "files=@test_resume.txt" \
  -F "job_id=test-job-001" \
  http://localhost:5000/api/resumes/upload
```

---

## What's Working Now (Local Only)

✅ Flask API server running  
✅ File upload endpoint (saves files locally)  
✅ Job description parsing endpoint  
✅ Logging configured  
✅ Error handling in place  

## What's Next (After AWS Setup)

⏳ AWS Textract integration  
⏳ AWS Comprehend integration  
⏳ AWS Bedrock (Claude) integration  
⏳ AWS DynamoDB integration  
⏳ GitHub MCP integration  
⏳ React frontend  

---

## Useful Commands

### Activate virtual environment (every session)
```bash
source venv/bin/activate  # macOS/Linux
```

### Deactivate virtual environment
```bash
deactivate
```

### Install additional package
```bash
pip install package_name
```

### Update requirements.txt (after adding packages)
```bash
pip freeze > requirements.txt
```

### View logs
```bash
tail -f logs/app.log
```

---

## Environment Variables

When AWS is set up, you'll fill in `.env` with:
- `AWS_ACCESS_KEY_ID` - Your AWS Access Key
- `AWS_SECRET_ACCESS_KEY` - Your AWS Secret Key
- `AWS_REGION` - AWS region (us-east-1)
- `S3_BUCKET_NAME` - S3 bucket for resume storage
- `DYNAMODB_TABLE_NAME` - DynamoDB table name
- `GITHUB_TOKEN` - GitHub API token (for MCP)

**Never commit `.env` to git!**

---

## Troubleshooting

### Error: "ModuleNotFoundError: No module named 'flask'"
- Make sure virtual environment is activated: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

### Error: "Port 5000 already in use"
- Use different port: `python run.py` then change port in config
- Or kill process: `lsof -ti:5000 | xargs kill -9`

### Virtual environment not activating
- Delete `venv/` folder and recreate it
- Make sure you're in terminal (not IDE)

---

## Next Phase: AWS Setup

Once you're ready, we'll:
1. Create AWS account / use free tier
2. Set up IAM credentials
3. Create S3 bucket for resume storage
4. Create DynamoDB table for results
5. Configure Textract, Comprehend, Bedrock access
6. Update service files to use actual AWS APIs

Then local testing will work with real AWS services!
