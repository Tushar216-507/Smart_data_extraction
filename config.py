import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    GROQ_MODEL = os.getenv('GROQ_MODEL')

    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL')

    NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY')
    NVIDIA_MODEL = os.getenv('NVIDIA_MODEL')

    AZURE_IMG_ENDPOINT=os.getenv('AZURE_IMG_ENDPOINT')
    AZURE_PDF_ENDPOINT=os.getenv('AZURE_PDF_ENDPOINT')
    AZURE_IMG_KEY=os.getenv('AZURE_IMG_KEY')
    AZURE_PDF_KEY=os.getenv('AZURE_PDF_KEY')