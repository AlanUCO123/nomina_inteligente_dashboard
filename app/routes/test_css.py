from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/test-colors")
async def test_colors():
    """Página de prueba simple para verificar los colores del CSS"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <link rel="stylesheet" href="/static/nova.css?v=2">
        <style>
            body { padding: 40px; font-family: Arial; }
            .test-box { margin: 20px 0; padding: 15px; background: #f5f5f5; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>Test de Colores CSS</h1>
        
        <div class="test-box">
            <h3>Textos en ROJO (Incidencias)</h3>
            <p><strong class="text-danger-bold">Retardos: 5</strong></p>
            <p><strong class="text-danger-bold">Faltas: 2</strong></p>
            <p><strong class="text-danger-bold">Sin salida: 1</strong></p>
        </div>
        
        <div class="test-box">
            <h3>Textos en VERDE (Horas Extra)</h3>
            <p><strong class="text-success-bold">HE detectada: 8</strong></p>
            <p><strong class="text-success-bold">HE final: 6</strong></p>
        </div>
        
        <div class="test-box">
            <h3>Verificación directa</h3>
            <p>Si ves rojo y verde → CSS está funcionando ✓</p>
            <p>Si solo ves bold → Hay problema con los colores ✗</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
