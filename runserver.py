#!/usr/bin/env python
import os
import sys
import uvicorn

# Cambiar a la carpeta del proyecto
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Asegurar que el directorio actual esté en sys.path
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8009,
        reload=False,
        log_level="info"
    )
