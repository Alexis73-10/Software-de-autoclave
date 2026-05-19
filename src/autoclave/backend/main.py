# autoclave/backend/main.py

import uvicorn

def main():
    print("BACKEND INICIADO DESDE:", __file__)
    uvicorn.run(
        "autoclave.backend.server:app",
        host="0.0.0.0",   # CRÍTICO: escucha en red
        port=8000,
        log_level="info",
    )

if __name__ == "__main__":
    main()
    