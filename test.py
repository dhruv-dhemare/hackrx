import google.generativeai as genai
genai.configure(api_key="AIzaSyDIG0PeSGZiQR8HH3J61kku86J0juAfE48")

print(genai.GenerativeModel("gemini-1.5-flash").generate_content("Test").text)
