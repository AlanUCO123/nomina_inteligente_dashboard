import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

WHATSAPP_API_URL = "http://192.168.39.122:5000"
WHATSAPP_SEND_ENDPOINT = f"{WHATSAPP_API_URL}/send-asistencia-alerta"

class WhatsAppService:
    """Servicio para consumir la API de WhatsApp Gateway"""
    
    @staticmethod
    def enviar_alerta(
        telefono: str,
        nombre_empleado: str,
        tipo_alerta: str,
        fecha: str,
        hora: str,
        valor: str,
        mensaje: str = None,
        numero_empleado: str = None
    ) -> dict:
        """
        Envía una alerta a través de WhatsApp usando el endpoint /send-asistencia-alerta.
        
        Args:
            telefono: Número de teléfono destino (con código de país)
            nombre_empleado: Nombre completo del empleado
            tipo_alerta: Tipo de alerta (FALTA_ENTRADA, RETARDO, etc)
            fecha: Fecha de la alerta (YYYY-MM-DD)
            hora: Hora de la alerta (HH:MM:SS)
            valor: Descripción/valor de la alerta (ej: "45 minutos de retardo")
            mensaje: Mensaje personalizado (opcional)
            numero_empleado: ID del empleado (opcional)
        
        Returns:
            dict con el resultado del envío
        """
        try:
            payload = {
                "to": telefono,
                "tipo_alerta": tipo_alerta,
                "nombre": nombre_empleado,
                "fecha": fecha,
                "hora": hora,
                "valor": valor,
            }
            
            # Agregar metadatos opcionales si se proporcionan
            if numero_empleado:
                payload["employee_id"] = numero_empleado
            if mensaje:
                payload["message"] = mensaje
            
            response = requests.post(
                WHATSAPP_SEND_ENDPOINT,
                json=payload,
                timeout=10
            )
            
            result = {
                "success": response.status_code in [200, 201, 202],
                "status_code": response.status_code,
                "response": response.json() if response.text else {}
            }
            
            if result["success"]:
                logger.info(f"Alerta enviada exitosamente a {telefono} - {tipo_alerta}")
            else:
                logger.error(f"Error al enviar alerta a {telefono}: {response.status_code}")
            
            return result
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout al enviar alerta a {telefono}")
            return {
                "success": False,
                "error": "Timeout en la conexión con WhatsApp API",
                "status_code": None
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión al enviar alerta a {telefono}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status_code": None
            }
        except Exception as e:
            logger.error(f"Error inesperado al enviar alerta: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status_code": None
            }
    
    @staticmethod
    def verificar_salud() -> bool:
        """Verifica que la API de WhatsApp esté disponible"""
        try:
            response = requests.get(
                f"{WHATSAPP_API_URL}/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error al verificar salud de WhatsApp API: {str(e)}")
            return False
