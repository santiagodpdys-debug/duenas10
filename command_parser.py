"""
Parser de comandos en español desde mensajes de WhatsApp
Convierte mensajes naturales en español a comandos estructurados
"""

import logging
import re
from typing import Dict, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)

class CommandAction(Enum):
    """Tipos de acciones soportadas."""
    PAUSE = 'pause'
    ACTIVATE = 'activate'
    STATUS = 'status'
    LIST_CAMPAIGNS = 'list_campaigns'
    GET_METRICS = 'get_metrics'
    HELP = 'help'
    LIST_ACCOUNTS = 'list_accounts'
    UNKNOWN = 'unknown'

class CommandPlatform(Enum):
    """Plataformas soportadas."""
    META = 'meta'

class CommandParser:
    """
    Parser de comandos en español desde WhatsApp.
    Soporta variaciones naturales en español.
    """

    # Palabras clave para pausar
    PAUSE_KEYWORDS = [
        'apaga', 'apagar', 'pausa', 'pausar', 'detén', 'detener',
        'para', 'parar', 'desactiva', 'desactivar', 'cierra', 'cerrar'
    ]

    # Palabras clave para activar
    ACTIVATE_KEYWORDS = [
        'enciende', 'encender', 'activa', 'activar', 'reanuda', 'reanudar',
        'abre', 'abrir', 'inicia', 'iniciar', 'empieza', 'empezar', 'on'
    ]

    # Palabras clave para estado
    STATUS_KEYWORDS = [
        'estado', 'status', 'cómo está', 'cómo va', 'viendo', 'muestrá'
    ]

    # Palabras clave para listar campañas
    LIST_KEYWORDS = [
        'lista', 'listá', 'campañas', 'cuáles', 'qué campañas', 'muéstra'
    ]

    # Palabras clave para métricas
    METRICS_KEYWORDS = [
        'métrica', 'métricas', 'resultado', 'resultados', 'performance',
        'rendimiento', 'datos', 'estadísticas', 'gasto', 'gastos'
    ]

    # Palabras clave para ayuda
    HELP_KEYWORDS = [
        'ayuda', 'help', 'cómo', 'qué puedo', 'qué hago', 'instrucciones',
        'comandos', 'funciona'
    ]

    # Palabras clave para listar cuentas
    ACCOUNTS_KEYWORDS = [
        'cuentas', 'mis cuentas', 'qué cuentas', 'cuáles cuentas'
    ]

    # Mapeo de nombres de plataforma
    META_ALIASES = ['meta', 'facebook', 'fb', 'ads', 'meta ads', 'facebook ads', 'cp1', 'cp20', 'cp25', 'cp2']

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normaliza el texto eliminando acentos y convirtiendo a minúsculas.

        Args:
            text: Texto a normalizar

        Returns:
            Texto normalizado
        """
        # Convertir a minúsculas
        text = text.lower().strip()

        # Remover puntuación común
        text = re.sub(r'[.!¿?;,]', '', text)

        return text

    @staticmethod
    def _extract_words(text: str) -> List[str]:
        """
        Extrae palabras del texto normalizado.

        Args:
            text: Texto normalizado

        Returns:
            Lista de palabras
        """
        return text.split()

    @classmethod
    def _detect_action(cls, normalized_text: str) -> CommandAction:
        """
        Detecta la acción basada en palabras clave.

        Args:
            normalized_text: Texto normalizado

        Returns:
            Tipo de acción detectada
        """
        words = cls._extract_words(normalized_text)

        # Verificar palabras clave para cada acción
        if any(word in cls.PAUSE_KEYWORDS for word in words):
            return CommandAction.PAUSE

        if any(word in cls.ACTIVATE_KEYWORDS for word in words):
            return CommandAction.ACTIVATE

        if any(word in cls.HELP_KEYWORDS for word in words):
            return CommandAction.HELP

        if any(word in cls.ACCOUNTS_KEYWORDS for word in words):
            return CommandAction.LIST_ACCOUNTS

        if any(word in cls.STATUS_KEYWORDS for word in words):
            return CommandAction.STATUS

        if any(word in cls.METRICS_KEYWORDS for word in words):
            return CommandAction.GET_METRICS

        if any(word in cls.LIST_KEYWORDS for word in words):
            return CommandAction.LIST_CAMPAIGNS

        return CommandAction.UNKNOWN

    @classmethod
    def _detect_platform(
        cls, normalized_text: str, original_text: str
    ) -> CommandPlatform:
        """
        Detecta la plataforma mencionada en el texto.

        Args:
            normalized_text: Texto normalizado
            original_text: Texto original

        Returns:
            Plataforma detectada (META por defecto)
        """
        # Solo soportamos Meta Ads
        return CommandPlatform.META

    @classmethod
    def _extract_campaign_name(cls, text: str) -> Optional[str]:
        """
        Intenta extraer el nombre de la campaña del texto.

        Args:
            text: Texto a procesar

        Returns:
            Nombre de campaña si se encuentra, None en caso contrario
        """
        normalized = cls._normalize_text(text)
        words = cls._extract_words(normalized)

        # Remover palabras clave conocidas
        keywords_to_remove = (
            cls.PAUSE_KEYWORDS + cls.ACTIVATE_KEYWORDS + cls.STATUS_KEYWORDS +
            cls.LIST_KEYWORDS + cls.METRICS_KEYWORDS + cls.HELP_KEYWORDS +
            cls.ACCOUNTS_KEYWORDS + cls.META_ALIASES +
            ['en', 'de', 'la', 'el', 'para', 'por', 'un', 'una', 'unos', 'unas',
             'con', 'sin', 'a', 'ante', 'bajo', 'cabe', 'desde', 'durante', 'entre',
             'hacia', 'hasta', 'mediante', 'según', 'sobre', 'tras']
        )

        remaining_words = [w for w in words if w not in keywords_to_remove and len(w) > 1]

        if remaining_words:
            # Retornar las palabras restantes como nombre de campaña
            return ' '.join(remaining_words)

        return None

    @classmethod
    def _extract_account_alias(cls, text: str) -> Optional[str]:
        """
        Intenta extraer el alias de la cuenta del texto.
        Soporta formatos: cp1, cp 1, cp20, cp 20, etc.

        Args:
            text: Texto a procesar

        Returns:
            Alias de cuenta (cp1, cp20, cp25, cp2) si se encuentra, None en caso contrario
        """
        normalized = cls._normalize_text(text)

        # Primero buscar "cp" seguido de número (con o sin espacio)
        match = re.search(r'cp\s*(\d+)', normalized)
        if match:
            alias = 'cp' + match.group(1)
            account_aliases = ['cp1', 'cp20', 'cp25', 'cp2']
            if alias in account_aliases:
                return alias

        return None

    @classmethod
    def parse(cls, message: str) -> Dict:
        """
        Parsea un mensaje de WhatsApp y retorna un comando estructurado.

        Args:
            message: Mensaje de WhatsApp en español

        Returns:
            Diccionario con estructura:
            {
                'action': CommandAction,
                'platform': CommandPlatform,
                'account': Optional[str] - alias de cuenta (cp1, cp20, etc.),
                'campaign_name': Optional[str] - nombre de campaña,
                'raw_message': str,
                'confidence': float (0.0-1.0) - confianza en el parseo,
            }
        """
        normalized = cls._normalize_text(message)
        action = cls._detect_action(normalized)
        platform = cls._detect_platform(normalized, message)
        campaign_name = cls._extract_campaign_name(message) if action not in [
            CommandAction.HELP,
            CommandAction.LIST_ACCOUNTS,
            CommandAction.LIST_CAMPAIGNS,
            CommandAction.STATUS,
        ] else None
        account_alias = cls._extract_account_alias(message)

        # Calcular confianza
        confidence = 1.0 if action != CommandAction.UNKNOWN else 0.0

        logger.info(
            f"Comando parseado: acción={action.value}, "
            f"plataforma={platform.value}, "
            f"campaña={campaign_name}, "
            f"cuenta={account_alias}"
        )

        return {
            'action': action,
            'platform': platform,
            'account': account_alias,
            'campaign_name': campaign_name,
            'raw_message': message,
            'confidence': confidence,
        }

    @staticmethod
    def get_help_message() -> str:
        """
        Retorna el mensaje de ayuda con instrucciones de uso.

        Returns:
            Mensaje de ayuda en español
        """
        return """
📱 *Bot de Gestión de Anuncios*

Puedo controlar tus campañas en Meta Ads desde WhatsApp.

*Comandos disponibles:*

⏸️ *Pausar campaña*
- "Pausa [campaña] en [cuenta]"
- Ejemplo: "Pausa Black Friday en CP1"

▶️ *Activar campaña*
- "Activa [campaña] en [cuenta]"
- Ejemplo: "Activa Promo en CP20"

📊 *Ver estado*
- "Estado de [campaña] en [cuenta]"
- "Status de CP1"

📋 *Listar campañas*
- "Campañas de [cuenta]"
- "Campañas de CP2"

📈 *Ver métricas*
- "Métricas de [campaña] en [cuenta]"
- "Resultados de Verano en CP1"

🔍 *Ver cuentas*
- "Mis cuentas"
- "Cuentas"

*Cuentas disponibles:*
- CP1
- CP20
- CP25
- CP2

*Plataforma soportada:*
- Meta Ads (Facebook)

¡Prueba enviándome un comando!
""""""
Parser de comandos en español desde mensajes de WhatsApp
Convierte mensajes naturales en español a comandos estructurados
"""

import logging
import re
from typing import Dict, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)

class CommandAction(Enum):
    """Tipos de acciones soportadas."""
    PAUSE = 'pause'
    ACTIVATE = 'activate'
    STATUS = 'status'
    LIST_CAMPAIGNS = 'list_campaigns'
    GET_METRICS = 'get_metrics'
    HELP = 'help'
    LIST_ACCOUNTS = 'list_accounts'
    UNKNOWN = 'unknown'

class CommandPlatform(Enum):
    """Plataformas soportadas."""
    META = 'meta'

class CommandParser:
    """
    Parser de comandos en español desde WhatsApp.
    Soporta variaciones naturales en español.
    """

    # Palabras clave para pausar
    PAUSE_KEYWORDS = [
        'apaga', 'apagar', 'pausa', 'pausar', 'detén', 'detener',
        'para', 'parar', 'desactiva', 'desactivar', 'cierra', 'cerrar'
    ]

    # Palabras clave para activar
    ACTIVATE_KEYWORDS = [
        'enciende', 'encender', 'activa', 'activar', 'reanuda', 'reanudar',
        'abre', 'abrir', 'inicia', 'iniciar', 'empieza', 'empezar', 'on'
    ]

    # Palabras clave para estado
    STATUS_KEYWORDS = [
        'estado', 'status', 'cómo está', 'cómo va', 'viendo', 'muestrá'
    ]

    # Palabras clave para listar campañas
    LIST_KEYWORDS = [
        'lista', 'listá', 'campañas', 'cuáles', 'qué campañas', 'muéstra'
    ]

    # Palabras clave para métricas
    METRICS_KEYWORDS = [
        'métrica', 'métricas', 'resultado', 'resultados', 'performance',
        'rendimiento', 'datos', 'estadísticas', 'gasto', 'gastos'
    ]

    # Palabras clave para ayuda
    HELP_KEYWORDS = [
        'ayuda', 'help', 'cómo', 'qué puedo', 'qué hago', 'instrucciones',
        'comandos', 'funciona'
    ]

    # Palabras clave para listar cuentas
    ACCOUNTS_KEYWORDS = [
        'cuentas', 'mis cuentas', 'qué cuentas', 'cuáles cuentas'
    ]

    # Mapeo de nombres de plataforma
    META_ALIASES = ['meta', 'facebook', 'fb', 'ads', 'meta ads', 'facebook ads', 'cp1', 'cp20', 'cp25', 'cp2']

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normaliza el texto eliminando acentos y convirtiendo a minúsculas.
        """
        text = text.lower().strip()
        text = re.sub(r'[\.!¿\?;,]', '', text)
        return text

    @staticmethod
    def _extract_words(text: str) -> List[str]:
        """Extrae palabras del texto normalizado."""
        return text.split()

    @classmethod
    def _detect_action(cls, normalized_text: str) -> CommandAction:
        """Detecta la acción basada en palabras clave."""
        words = cls._extract_words(normalized_text)

        if any(word in cls.PAUSE_KEYWORDS for word in words):
            return CommandAction.PAUSE
        if any(word in cls.ACTIVATE_KEYWORDS for word in words):
            return CommandAction.ACTIVATE
        if any(word in cls.HELP_KEYWORDS for word in words):
            return CommandAction.HELP
        if any(word in cls.ACCOUNTS_KEYWORDS for word in words):
            return CommandAction.LIST_ACCOUNTS
        if any(word in cls.STATUS_KEYWORDS for word in words):
            return CommandAction.STATUS
        if any(word in cls.METRICS_KEYWORDS for word in words):
            return CommandAction.GET_METRICS
        if any(word in cls.LIST_KEYWORDS for word in words):
            return CommandAction.LIST_CAMPAIGNS

        return CommandAction.UNKNOWN

    @classmethod
    def _detect_platform(cls, normalized_text: str, original_text: str) -> CommandPlatform:
        """Detecta la plataforma mencionada en el texto."""
        return CommandPlatform.META

    @classmethod
    def _extract_campaign_name(cls, text: str) -> Optional[str]:
        """Intenta extraer el nombre de la campaña del texto."""
        normalized = cls._normalize_text(text)
        words = cls._extract_words(normalized)

        keywords_to_remove = (
            cls.PAUSE_KEYWORDS + cls.ACTIVATE_KEYWORDS + cls.STATUS_KEYWORDS +
            cls.LIST_KEYWORDS + cls.METRICS_KEYWORDS + cls.HELP_KEYWORDS +
            cls.ACCOUNTS_KEYWORDS + cls.META_ALIASES +
            ['en', 'de', 'la', 'el', 'para', 'por', 'un', 'una', 'unos', 'unas',
             'con', 'sin', 'a', 'ante', 'bajo', 'cabe', 'desde', 'durante', 'entre',
             'hacia', 'hasta', 'mediante', 'según', 'sobre', 'tras']
        )

        remaining_words = [w for w in words if w not in keywords_to_remove and len(w) > 1]

        if remaining_words:
            return ' '.join(remaining_words)
        return None

    @classmethod
    def _extract_account_alias(cls, text: str) -> Optional[str]:
        """Intenta extraer el alias de la cuenta del texto."""
        normalized = cls._normalize_text(text)
        words = cls._extract_words(normalized)
        account_aliases = ['cp1', 'cp20', 'cp25', 'cp2']

        for word in words:
            if word in account_aliases:
                return word
        return None

    @classmethod
    def parse(cls, message: str) -> Dict:
        """
        Parsea un mensaje de WhatsApp y retorna un comando estructurado.
        """
        normalized = cls._normalize_text(message)
        action = cls._detect_action(normalized)
        platform = cls._detect_platform(normalized, message)
        campaign_name = cls._extract_campaign_name(message) if action not in [
            CommandAction.HELP,
            CommandAction.LIST_ACCOUNTS,
            CommandAction.LIST_CAMPAIGNS,
            CommandAction.STATUS,
        ] else None
        account_alias = cls._extract_account_alias(message)

        confidence = 1.0 if action != CommandAction.UNKNOWN else 0.0

        logger.info(
            f"Comando parseado: acción={action.value}, "
            f"plataforma={platform.value}, "
            f"campaña={campaign_name}, "
            f"cuenta={account_alias}"
        )

        return {
            'action': action,
            'platform': platform,
            'account': account_alias,
            'campaign_name': campaign_name,
            'raw_message': message,
            'confidence': confidence,
        }

    @staticmethod
    def get_help_message() -> str:
        """Retorna el mensaje de ayuda con instrucciones de uso."""
        return """
📱 *Bot de Gestión de Anuncios*

Puedo controlar tus campañas en Meta Ads desde WhatsApp.

*Comandos disponibles:*

⏸️ *Pausar campaña*
- "Pausa [campaña] en [cuenta]"
- Ejemplo: "Pausa Black Friday en CP1"

▶️ *Activar campaña*
- "Activa [campaña] en [cuenta]"
- Ejemplo: "Activa Promo en CP20"

📊 *Ver estado*
- "Estado de [campaña] en [cuenta]"
- "Status de CP1"

📋 *Listar campañas*
- "Campañas de [cuenta]"
- "Campañas de CP2"

📈 *Ver métricas*
- "Métricas de [campaña] en [cuenta]"
- "Resultados de Verano en CP1"

🔍 *Ver cuentas*
- "Mis cuentas"
- "Cuentas"

*Cuentas disponibles:*
- CP1
- CP20
- CP25
- CP2

*Plataforma soportada:*
- Meta Ads (Facebook)

¡Prueba enviándome un comando!
"""
