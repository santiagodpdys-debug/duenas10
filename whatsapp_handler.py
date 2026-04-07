"""
Manejador de webhooks y mensajes de WhatsApp Cloud API
Integración con Meta WhatsApp Business API
"""

import logging
import json
import requests
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

from config import (
    WHATSAPP_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_VERIFY_TOKEN,
    is_phone_allowed,
)

logger = logging.getLogger(__name__)

class WhatsAppHandler:
    """
    Manejador de integración con WhatsApp Cloud API.
    Gestiona verificación de webhook, recepción y envío de mensajes.
    """

    BASE_URL = 'https://graph.facebook.com/v22.0'

    def __init__(self):
        """Inicializa el manejador de WhatsApp."""
        if not all([WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN]):
            raise ValueError(
                "Configuración de WhatsApp incompleta. "
                "Verifica WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID y WHATSAPP_VERIFY_TOKEN en .env"
            )

        self.token = WHATSAPP_TOKEN
        self.phone_number_id = WHATSAPP_PHONE_NUMBER_ID
        self.verify_token = WHATSAPP_VERIFY_TOKEN
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        }

        logger.info("Manejador de WhatsApp inicializado correctamente")

    def verify_webhook(self, mode: str, token: str, challenge: str) -> Tuple[bool, Optional[str]]:
        """
        Verifica la solicitud de webhook de WhatsApp.
        """
        if mode != 'subscribe':
            logger.warning(f"Modo inválido en verificación: {mode}")
            return False, None

        if token != self.verify_token:
            logger.warning(f"Token de verificación inválido: {token}")
            return False, None

        logger.info("Webhook verificado exitosamente")
        return True, challenge

    def process_webhook(self, body: Dict) -> Optional[Dict]:
        """
        Procesa una solicitud POST del webhook de WhatsApp.
        """
        try:
            entry = body.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            message_data = changes.get('value', {})

            messages = message_data.get('messages', [])
            contacts = message_data.get('contacts', [])

            if not messages or not contacts:
                logger.debug("Webhook recibido sin mensajes o contactos")
                return None

            message = messages[0]
            contact = contacts[0]

            if message.get('type') != 'text':
                logger.info(f"Mensaje no-texto ignorado: {message.get('type')}")
                return None

            phone_number = message.get('from')
            message_text = message.get('text', {}).get('body', '').strip()
            message_id = message.get('id')

            if not is_phone_allowed(phone_number):
                logger.warning(f"Mensaje de número no permitido: {phone_number}")
                return None

            logger.info(f"Mensaje procesado de {phone_number}: {message_text[:50]}")

            return {
                'phone_number': phone_number,
                'message_text': message_text,
                'message_id': message_id,
                'contact_name': contact.get('profile', {}).get('name', 'Usuario'),
            }

        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Error al procesar webhook: {str(e)}")
            raise ValueError(f"Estructura de webhook inválida: {str(e)}")

    def send_message(self, phone_number: str, message_text: str) -> bool:
        """
        Envía un mensaje de texto a través de WhatsApp.
        """
        try:
            url = f'{self.BASE_URL}/{self.phone_number_id}/messages'

            payload = {
                'messaging_product': 'whatsapp',
                'to': phone_number,
                'type': 'text',
                'text': {
                    'body': message_text,
                },
            }

            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=10
            )

            response.raise_for_status()
            result = response.json()

            if result.get('messages'):
                message_id = result['messages'][0].get('id')
                logger.info(f"Mensaje enviado a {phone_number} (ID: {message_id})")
                return True
            else:
                logger.error(f"Error en respuesta de WhatsApp: {result}")
                return False

        except requests.exceptions.Timeout:
            logger.error("Timeout al enviar mensaje por WhatsApp")
            raise ValueError("Timeout al enviar mensaje. Intenta de nuevo más tarde.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al enviar mensaje por WhatsApp: {str(e)}")
            raise ValueError(f"Error de conexión con WhatsApp: {str(e)}")

    def send_template_message(
        self,
        phone_number: str,
        template_name: str,
        language_code: str = 'es',
        parameters: Optional[Dict] = None,
    ) -> bool:
        """
        Envía un mensaje usando una plantilla predefinida en WhatsApp.
        """
        try:
            url = f'{self.BASE_URL}/{self.phone_number_id}/messages'

            payload = {
                'messaging_product': 'whatsapp',
                'to': phone_number,
                'type': 'template',
                'template': {
                    'name': template_name,
                    'language': {
                        'code': language_code,
                    },
                },
            }

            if parameters:
                payload['template']['parameters'] = {
                    'body': {
                        'parameters': [{'type': 'text', 'text': param} for param in parameters]
                    }
                }

            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=10
            )

            response.raise_for_status()
            result = response.json()

            if result.get('messages'):
                message_id = result['messages'][0].get('id')
                logger.info(f"Mensaje de plantilla enviado a {phone_number} (ID: {message_id})")
                return True
            else:
                logger.error(f"Error en respuesta de WhatsApp: {result}")
                return False

        except requests.exceptions.Timeout:
            logger.error("Timeout al enviar mensaje de plantilla por WhatsApp")
            raise ValueError("Timeout al enviar mensaje. Intenta de nuevo más tarde.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al enviar mensaje de plantilla: {str(e)}")
            raise ValueError(f"Error de conexión con WhatsApp: {str(e)}")

    @staticmethod
    def mark_as_read(message_id: str) -> bool:
        """Marca un mensaje como leído."""
        logger.debug(f"Marcar mensaje como leído: {message_id}")
        return True
