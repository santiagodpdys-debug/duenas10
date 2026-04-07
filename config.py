"""
Configuración de la aplicación - Carga variables de entorno y establece mapeos de cuentas
"""

import os
import logging
from dotenv import load_dotenv
from typing import Dict, List

# Cargar variables de entorno desde .env
load_dotenv()

logger = logging.getLogger(__name__)

# ===== META ADS CONFIGURATION =====
META_APP_ID = os.getenv('META_APP_ID', '')
META_APP_SECRET = os.getenv('META_APP_SECRET', '')
META_ACCESS_TOKEN = os.getenv('META_ACCESS_TOKEN', '')

# Mapeo de alias de cuenta a IDs de cuenta de Meta
META_ACCOUNTS: Dict[str, str] = {
    'cp1': os.getenv('META_AD_ACCOUNT_CP1', ''),
    'cp20': os.getenv('META_AD_ACCOUNT_CP20', ''),
    'cp25': os.getenv('META_AD_ACCOUNT_CP25', ''),
    'cp2': os.getenv('META_AD_ACCOUNT_CP2', ''),
}

# Validar que las cuentas de Meta estén configuradas
VALID_META_ACCOUNTS = {k: v for k, v in META_ACCOUNTS.items() if v}

# ===== WHATSAPP CONFIGURATION =====
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', '')

# Lista de números de teléfono permitidos (seguridad)
ALLOWED_PHONE_NUMBERS: List[str] = [
    num.strip() for num in os.getenv('ALLOWED_PHONE_NUMBERS', '').split(',')
    if num.strip()
]

# ===== FLASK CONFIGURATION =====
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
PORT = int(os.getenv('PORT', 10000))

# ===== LOGGING CONFIGURATION =====
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Configurar logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_meta_account_id(alias: str) -> str:
    alias_lower = alias.lower()
    if alias_lower not in VALID_META_ACCOUNTS:
        raise ValueError(
            f"Cuenta de Meta '{alias}' no configurada. Cuentas disponibles: {list(VALID_META_ACCOUNTS.keys())}"
        )
    return VALID_META_ACCOUNTS[alias_lower]

def get_all_meta_accounts() -> Dict[str, str]:
    return VALID_META_ACCOUNTS.copy()

def is_phone_allowed(phone_number: str) -> bool:
    """
    Verifica si un número de teléfono está permitido.
    Normaliza los números eliminando el '+' para comparación.
    """
    normalized = phone_number.lstrip('+')
    allowed_normalized = [num.lstrip('+') for num in ALLOWED_PHONE_NUMBERS]
    return normalized in allowed_normalized

def validate_configuration() -> bool:
    required_vars = {
        'WhatsApp': [WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN],
        'Meta Ads': [META_ACCESS_TOKEN],
    }

    missing = []
    for service, vars in required_vars.items():
        if not all(vars):
            missing.append(service)

    if missing:
        raise ValueError(
            f"Configuración incompleta para: {', '.join(missing)}. "
            f"Asegúrate de llenar correctamente el archivo .env"
        )

    if not ALLOWED_PHONE_NUMBERS:
        raise ValueError(
            "No hay números de teléfono permitidos configurados. "
            "Configura ALLOWED_PHONE_NUMBERS en .env"
        )

    logger.info(f"Configuración validada. Cuentas de Meta disponibles: {list(VALID_META_ACCOUNTS.keys())}")
    return True
