import os
import io
import pandas as pd
import requests  # Нужно добавить эту библиотеку
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import google.generativeai as genai

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# [Тут те же настройки GOOGLE_API_KEY и функций поиска колонок, что были раньше]
# ... (оставь всё без изменений до функции analyze)

@app.post("/analyze")
async def analyze(
    file_url: str = Form(...), # Теперь принимаем URL вместо файла
    user_query: str = Form(None),
    app_password: str = Form(...)
):
    if app_password != os.environ.get("APP_PASSWORD", "wb140"):
        return JSONResponse(status_code=401, content={"error": "Неверный пароль"})

    # Скачивание файла по ссылке
    try:
        response = requests.get(file_url)
        response.raise_for_status()
        df = pd.read_excel(io.BytesIO(response.content))
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Ошибка скачивания или чтения файла: {str(e)}"})

    # [Дальше идет та же логика анализа, что была в первом коде]
    # ...
    # (после расчетов возвращай тот же JSON)
