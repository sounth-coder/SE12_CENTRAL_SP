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

`sentence-transformers` will also install larger machine-learning dependencies such as PyTorch/Transformers. The AI document search uses the `all-MiniLM-L6-v2` model. If the model is not already cached locally, run `python ingest_documents.py` once with internet access so it can download the model. If the model is still missing, the portal remains usable and CENTRAL can still answer using Gemini, but local school-document search may be skipped.



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

5. Create a .env file in the project folder. COPY THE FOLLOWING TEXT IN THE BOX TO THE ENV FILE! 

```env
GEMINI_API_KEY=[API KEY IS IN PORTFOLIO]
SECRET_KEY=
TRUST_PROXY_HEADERS=false
```

For local testing, `SECRET_KEY` can be left blank because the app will generate a temporary one. However, users may be logged out whenever the app restarts.

6. Run the app. 

```bash
python app.py
```

7. Open the portal in browser. 

The link would usually be: 
```text
http://127.0.0.1:5000

IF not that link, select the generated one in the terminal from flask. 

And you're set!!


## Database Notes

This repository already includes the prepared SQLite databases:

- `girra_portal.db` for users, resources, announcements, teacher chat, and portal data
- `knowledge.db` for AI document search

You do not need to run `init_db.py` or `ingest_documents.py` for normal setup.

Only run `init_db.py` if you want to recreate/reset the main portal database. 
CAUTION: DATABASE MAY BE OVER-WRITTEN IF YOU RUN THIS FILE 

Only run `ingest_documents.py` if you change the PDFs in `documents/` and want to rebuild the AI search database. You can add other resources and test the AI chatboxes interpretation functionality. 



## Demo Login

Seeded accounts in `girra_portal.db` use this password:

```text
Password123!
```

The following accounts allow you to log in with that password (DEMONSTRATION PURPOSES):

```text
aarav.s@education.nsw.gov.au
raguram.ps@education.nsw.gov.au
sountharikan.thirukkumaran@education.nsw.gov.au
mr.patel@education.nsw.gov.au
```

They are all different roles, so by logging into each one, you can observe the Role Based Access Control (RBAC) of the portal. 