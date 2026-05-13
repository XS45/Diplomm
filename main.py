from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

# Подключаем статические файлы (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# API эндпоинты
@app.get("/api/hello")
def hello(name: str = "мир"):
    return {"message": f"Привет, {name}!"}

@app.get("/api/users")
def get_users():
    return [
        {"id": 1, "name": "Иван"},
        {"id": 2, "name": "Мария"},
        {"id": 3, "name": "Петр"}
    ]

@app.post("/api/echo")
async def echo(text: str):
    return {"echo": text}

# Главная страница
@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)