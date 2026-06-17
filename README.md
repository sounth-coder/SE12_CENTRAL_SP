# SE12_CENTRAL_SP

Girra Portal is a Flask-based student portal major project. It includes login/registration, resources, announcements/news, profile management, teacher chat, student ID barcodes, and an AI chat endpoint that can search school documents.

## Requirements

- Python 3.10 or newer, preferably Python 3.11
- Internet access for first install/model download
- A Gemini API key if using the AI chat feature

Install the Python dependencies with:

```bash
pip install -r requirements.txt
```

The required packages are:

- Flask
- Flask-Bcrypt
- python-dotenv
- google-generativeai
- python-barcode
- numpy
- sentence-transformers
- pypdf

`sentence-transformers` will also install larger machine-learning dependencies such as PyTorch/Transformers. The first run of the AI document search may download the `all-MiniLM-L6-v2` model, so startup/chat may be slower on a fresh computer. Please allow 10-30 minutes for a fresh install if the model is not already cached.

