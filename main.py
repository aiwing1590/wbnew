import os
import io
import pandas as pd
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import google.generativeai as genai

app = FastAPI(title="Wildberries AI Report Analyzer")

# 1. Настройка CORS-политики для Webflow
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешает запросы с любых доменов (включая Webflow)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Переменные окружения
APP_PASSWORD = os.environ.get("APP_PASSWORD", "wb140")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Настройка клиента Gemini
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Ключевые слова-синонимы для поиска колонок в Excel
REVENUE_SYNONYMS = ['выручка', 'продажи', 'сумма продаж', 'к перечислению', 'к начислению', 'вайлдберриз', 'revenue', 'sales', 'цена']
LOGISTICS_SYNONYMS = ['логистика', 'услуги по доставке', 'доставка', 'logistics', 'delivery', 'стоимость доставки']
PRODUCT_SYNONYMS = ['предмет', 'номенклатура', 'товар', 'название', 'product', 'name', 'артикул', 'обоснование для оплаты']

def find_column(df_columns, synonyms):
    """Поиск колонки в списке по ключевым словам-синонимам (без учета регистра)"""
    for col in df_columns:
        col_lower = str(col).lower().strip()
        for syn in synonyms:
            if syn in col_lower:
                return col
    return None

def clean_numeric_column(df, col_name):
    """Очистка строковых значений от пробелов, замена запятых и конвертация в float"""
    if not col_name:
        return pd.Series(0.0, index=df.index)
    
    cleaned = df[col_name].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.')
    return pd.to_numeric(cleaned, errors='coerce').fillna(0.0)

@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    user_query: str = Form(None),
    app_password: str = Form(...)
):
    # 2. Проверка пароля доступа
    if app_password != APP_PASSWORD:
        return JSONResponse(status_code=401, content={"error": "Неверный пароль"})

    # 3. Чтение файла Excel
    try:
        contents = await file.read()
        # openpyxl используется в качестве движка по умолчанию для xlsx
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Ошибка чтения файла Excel: {str(e)}"})

    df_cols = df.columns.tolist()

    # Поиск нужных колонок
    rev_col = find_column(df_cols, REVENUE_SYNONYMS)
    log_col = find_column(df_cols, LOGISTICS_SYNONYMS)
    prod_col = find_column(df_cols, PRODUCT_SYNONYMS)

    # Очистка числовых данных
    rev_series = clean_numeric_column(df, rev_col)
    log_series = clean_numeric_column(df, log_col)

    # 4. Расчет финансовых показателей
    total_revenue = float(rev_series.sum())
    total_logistics = float(log_series.sum())
    net_profit = total_revenue - total_logistics

    # Определение самого продаваемого товара по выручке
    best_product = "Не определен"
    if prod_col and not rev_series.empty:
        df['temp_revenue'] = rev_series
        grouped = df.groupby(prod_col)['temp_revenue'].sum()
        if not grouped.empty:
            best_product = str(grouped.idxmax())

    # 5. Интеграция с ИИ Gemini (gemini-2.0-flash)
    ai_response = ""
    if GOOGLE_API_KEY:
        try:
            # Формируем стандартный запрос, если пользователь не ввел свой
            final_query = user_query.strip() if user_query and user_query.strip() else "Сделай краткий финансовый разбор этих показателей и дай 3 совета по увеличению прибыли."
            
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            prompt = f"""
            Ты — опытный финансовый аналитик маркетплейса Wildberries.
            Вот ключевые показатели из отчета о продажах:
            - Общая выручка: {total_revenue:,.2f} руб.
            - Стоимость логистики: {total_logistics:,.2f} руб.
            - Чистая прибыль (Выручка - Логистика): {net_profit:,.2f} руб.
            - Самый продаваемый товар (по выручке): {best_product}

            Ответь на следующий вопрос пользователя, используя эти данные и свой профессиональный опыт:
            "{final_query}"

            Отвечай профессионально, кратко, структурированно, на русском языке. Используй списки и выделение текста для улучшения читаемости.
            """
            
            response = model.generate_content(prompt)
            ai_response = response.text
        except Exception as e:
            ai_response = f"Ошибка генерации ИИ: {str(e)}"
    else:
        ai_response = "Интеграция ИИ отключена (не задан GOOGLE_API_KEY на сервере)."

    # 6. Ответ сервера
    return {
        "status": "success",
        "total_revenue": round(total_revenue, 2),
        "net_profit": round(net_profit, 2),
        "logistics": round(total_logistics, 2),
        "best_product": best_product,
        "ai_response": ai_response
    }
