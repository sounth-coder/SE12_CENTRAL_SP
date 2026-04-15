from google import genai
import os

client = genai.Client(api_key=os.getenv("AIzaSyATYwtvqt24rhj0DZVwO8EuM6EHywhZTpw"))

response = client.models.generate_content(
    model="models/gemini-1.5-pro",
    contents="why is the sky blue"

)

print(response.text)