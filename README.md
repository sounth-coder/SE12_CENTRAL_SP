# SE12_CENTRAL_SP
<img width="941" height="409" alt="image" src="https://github.com/user-attachments/assets/b9b6de9e-a68c-4b02-9eef-7216ca60c047" />


Girra Portal is a Flask-based student portal major project. It includes login/registration, resources, announcements/news, profile management, teacher chat, student ID barcodes, and an AI chat endpoint that can search school documents.

## Requirements 

- Python 3.10 or newer, preferably Python 3.11
- Internet access for first install/model download
- A Gemini API key if using the AI chat feature

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



## SETUP 
1. Clone or download the project. 

2. Open a terminal in the project. 

3. Optional but recommended: create a virtual environment.

```bash
python -m venv .venv
.venv\Scripts\activate
```

4. Install the Python dependencies with:

```bash
pip install -r requirements.txt
```

5. Create a .env file in the project folder. 

LEAVE SECRET_KEY EMPTY. 
Copy the following text over to that .env file: 

GEMINI_API_KEY = [API KEY IS IN PORTFOLIO]

SECRET_KEY=""

TRUST_PROXY_HEADERS=false

6. Run the app. 

```bash
pip python app.py
```

7. Open the portal in browser, with the link generated from flask. 

