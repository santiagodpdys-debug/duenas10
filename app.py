"""
Aplicación principal del Bot de Gestión de Anuncios
Flask con integración de WhatsApp y Meta Ads
"""

import logging
import os
from flask import Flask, request, jsonify
from datetime import datetime

from config import (
    FLASK_ENV,
    FLASK_DEBUG,
    PORT,
    LOG_LEVEL,
    validate_configuration,
)
from whatsapp_handler import WhatsAppHandler
from meta_ads_client import MetaAdsClient
from command_parser import CommandParser, CommandAction, CommandPlatform

# Configurar logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Crear aplicación Flask
app = Flask(__name__)
app.config['ENV'] = FLASK_ENV
app.config['DEBUG'] = FLASK_DEBUG

# Inicializar clientes
try:
    validate_configuration()
    whatsapp = WhatsAppHandler()
    meta_ads = MetaAdsClient()
    logger.info("Todos los clientes inicializados correctamente")
except ValueError as e:
    logger.error(f"Error en configuración: {str(e)}")
    raise


# ============================================================================
# ENDPOINTS DE HEALTHCHECK
# ============================================================================

@app.route('/', methods=['GET'])
def healthcheck():
    """
    Endpoint de healthcheck.
    Retorna estado de la aplicación.
    """
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'service': 'Bot de Gestión de Anuncios',
        'version': '1.0.0',
    }), 200


# ============================================================================
# ENDPOINTS DE WEBHOOK DE WHATSAPP
# ============================================================================

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """
    Verifica el webhook de WhatsApp.
    Meta requiere este endpoint para la verificación inicial.
    """
    try:
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        success, response = whatsapp.verify_webhook(mode, token, challenge)

        if success:
            return response, 200
        else:
            logger.warning("Intento fallido de verificación de webhook")
            return 'Invalid verification token', 403

    except Exception as e:
        logger.error(f"Error en verificación de webhook: {str(e)}")
        return 'Error in webhook verification', 500


@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Maneja mensajes entrantes del webhook de WhatsApp.
    """
    try:
        body = request.get_json()

        # Procesar webhook
        message_data = whatsapp.process_webhook(body)

        if not message_data:
            logger.debug("Webhook procesado sin acción de mensaje")
            return jsonify({'status': 'received'}), 200

        # Procesar comando
        phone = message_data['phone_number']
        message_text = message_data['message_text']
        contact_name = message_data['contact_name']

        logger.info(f"Procesando comando de {contact_name} ({phone}): {message_text[:50]}")

        # Parsear comando
        parsed = CommandParser.parse(message_text)
        action = parsed['action']
        platform = parsed['platform']
        account = parsed['account']
        campaign_name = parsed['campaign_name']

        # Ejecutar comando
        response_text = execute_command(
            action=action,
            platform=platform,
            account=account,
            campaign_name=campaign_name,
            parsed=parsed,
        )

        # Enviar respuesta
        whatsapp.send_message(phone, response_text)

        return jsonify({'status': 'ok'}), 200

    except Exception as e:
        logger.error(f"Error en manejador de webhook: {str(e)}")
        # No interrumpir el webhook, solo loguear
        return jsonify({'status': 'error', 'message': str(e)}), 200


# ============================================================================
# LÓGICA DE EJECUCIÓN DE COMANDOS
# ============================================================================

def format_campaign_status(campaign: dict) -> str:
    """Formatea la información de estado de una campaña."""
    status_emoji = '✅' if campaign.get('status') in ['ACTIVE', 'ENABLED'] else '⏸️'
    name = campaign.get('name') or campaign.get('campaign_name', 'Sin nombre')
    status = campaign.get('status', 'DESCONOCIDO')

    return f"{status_emoji} *{name}*\nEstado: {status}"


def format_metrics(metrics: dict) -> str:
    """Formatea la información de métricas."""
    campaign_name = metrics.get('name') or metrics.get('campaign_name', 'Campaña')
    period = metrics.get('period', 'N/A')
    data = metrics.get('data')

    if not data:
        return f"📊 *{campaign_name}*\nNo hay datos disponibles para {period}"

    spend = data.get('spend', 0)
    impressions = data.get('impressions', 0)
    clicks = data.get('clicks', 0)
    conversions = data.get('conversions', 0)

    cpc = (spend / clicks) if clicks > 0 else 0
    cpi = (spend / impressions) if impressions > 0 else 0

    text = f"""📊 *{campaign_name}*
Período: {period}

💰 Gasto: ${spend:.2f}
👁️ Impresiones: {impressions}
👆 Clics: {clicks}
🎯 Conversiones: {conversions}
📈 CPC: ${cpc:.2f}
📈 CPI: ${cpi:.4f}
"""
    return text


def execute_command(
    action: CommandAction,
    platform: CommandPlatform,
    account: str = None,
    campaign_name: str = None,
    parsed: dict = None,
) -> str:
    """
    Ejecuta un comando parseado.

    Args:
        action: Tipo de acción
        platform: Plataforma destino
        account: Alias de cuenta (para Meta)
        campaign_name: Nombre de campaña
        parsed: Diccionario completo parseado

    Returns:
        Texto de respuesta a enviar por WhatsApp
    """
    try:
        # Comandos que no requieren plataforma específica
        if action == CommandAction.HELP:
            return CommandParser.get_help_message()

        if action == CommandAction.LIST_ACCOUNTS:
            accounts = meta_ads.list_accounts()
            if not accounts:
                return "❌ No hay cuentas de Meta configuradas."

            text = "📋 *Cuentas disponibles:*\n\n"
            for acc in accounts:
                text += f"• {acc['alias'].upper()}: {acc['id']}\n"

            return text

        if action == CommandAction.UNKNOWN:
            return (
                "❌ No entendí tu comando.\n\n"
                "Escribe *'ayuda'* para ver los comandos disponibles."
            )

        # Comandos que requieren campaña pero no cuenta específica
        if action == CommandAction.LIST_CAMPAIGNS:
            if not account:
                # Asumir que es una acción de listar de Meta si no se especifica
                account = 'cp1'

            campaigns = meta_ads.list_campaigns(account)
            if not campaigns:
                return f"❌ No hay campañas en la cuenta {account.upper()}."

            total = len(campaigns)
            max_show = 20
            text = f"📋 *Campañas de {account.upper()}* ({total} total):\n\n"
            for c in campaigns[:max_show]:
                status_emoji = '✅' if c['status'] in ['ACTIVE', 'ENABLED'] else '⏸️'
                name = c['name'][:40]
                text += f"{status_emoji} {name}\n"

            if total > max_show:
                text += f"\n... y {total - max_show} campañas más."

            return text

        if action == CommandAction.STATUS:
            if not campaign_name:
                return (
                    "❌ Debes especificar una campaña.\n"
                    "Ejemplo: 'Estado de Black Friday en CP1'"
                )

            if not account:
                account = 'cp1'

            try:
                campaign = meta_ads.get_campaign_status(account, campaign_name)
                return f"📱 *Meta:*\n{format_campaign_status(campaign)}"
            except ValueError as e:
                return f"❌ Meta: {str(e)}"

        if action == CommandAction.GET_METRICS:
            if not campaign_name:
                return (
                    "❌ Debes especificar una campaña.\n"
                    "Ejemplo: 'Métricas de Black Friday en CP1'"
                )

            if not account:
                account = 'cp1'

            try:
                metrics = meta_ads.get_campaign_metrics(account, campaign_name)
                return f"📱 *Meta:*\n{format_metrics(metrics)}"
            except ValueError as e:
                return f"❌ Meta: {str(e)}"

        # Comandos que requieren campaña y pueden tener plataforma
        if action in [CommandAction.PAUSE, CommandAction.ACTIVATE]:
            if not campaign_name:
                return (
                    "❌ Debes especificar una campaña.\n"
                    "Ejemplo: 'Pausa Black Friday en CP1'"
                )

            action_text = "pausar" if action == CommandAction.PAUSE else "activar"
            method = meta_ads.pause_campaign if action == CommandAction.PAUSE else meta_ads.activate_campaign

            if not account:
                account = 'cp1'

            try:
                result = method(account, campaign_name)
                status_emoji = '⏸️' if action == CommandAction.PAUSE else '✅'
                return (
                    f"📱 *Meta ({account.upper()}):*\n"
                    f"{status_emoji} {result.get('message', f'Campaña {action_text}a')}"
                )
            except ValueError as e:
                return f"❌ Meta: {str(e)}"

        return "❌ Comando desconocido."

    except Exception as e:
        logger.error(f"Error ejecutando comando: {str(e)}")
        return f"❌ Error: {str(e)}"


# ============================================================================
# MANEJO DE ERRORES
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Maneja errores 404."""
    return jsonify({'error': 'Endpoint no encontrado'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Maneja errores 500."""
    logger.error(f"Error interno: {str(error)}")
    return jsonify({'error': 'Error interno del servidor'}), 500


# ============================================================================
# INICIO DE LA APLICACIÓN
# ============================================================================

if __name__ == '__main__':
    logger.info(f"Iniciando Bot de Gestión de Anuncios en {FLASK_ENV}")
    logger.info(f"Escuchando en puerto {PORT}")

    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=FLASK_DEBUG,
    )
"""
Aplicación principal del Bot de Gestión de Anuncios
Flask con integración de WhatsApp y Meta Ads
"""

import logging
import os
from flask import Flask, request, jsonify
from datetime import datetime

from config import (
    FLASK_ENV,
    FLASK_DEBUG,
    PORT,
    LOG_LEVEL,
    validate_configuration,
)
from whatsapp_handler import WhatsAppHandler
from meta_ads_client import MetaAdsClient
from command_parser import CommandParser, CommandAction, CommandPlatform

# Configurar logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Crear aplicación Flask
app = Flask(__name__)
app.config['ENV'] = FLASK_ENV
app.config['DEBUG'] = FLASK_DEBUG

# Inicializar clientes
try:
    validate_configuration()
    whatsapp = WhatsAppHandler()
    meta_ads = MetaAdsClient()
    logger.info("Todos los clientes inicializados correctamente")
except ValueError as e:
    logger.error(f"Error en configuración: {str(e)}")
    raise


# ============================================================================
# ENDPOINTS DE HEALTHCHECK
# ============================================================================

@app.route('/', methods=['GET'])
def healthcheck():
    """
    Endpoint de healthcheck.
    Retorna estado de la aplicación.
    """
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'service': 'Bot de Gestión de Anuncios',
        'version': '1.0.0',
    }), 200


# ============================================================================
# ENDPOINTS DE WEBHOOK DE WHATSAPP
# ============================================================================

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """
    Verifica el webhook de WhatsApp.
    Meta requiere este endpoint para la verificación inicial.
    """
    try:
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        success, response = whatsapp.verify_webhook(mode, token, challenge)

        if success:
            return response, 200
        else:
            logger.warning("Intento fallido de verificación de webhook")
            return 'Invalid verification token', 403

    except Exception as e:
        logger.error(f"Error en verificación de webhook: {str(e)}")
        return 'Error in webhook verification', 500


@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Maneja mensajes entrantes del webhook de WhatsApp.
    """
    try:
        body = request.get_json()

        # Procesar webhook
        message_data = whatsapp.process_webhook(body)

        if not message_data:
            logger.debug("Webhook procesado sin acción de mensaje")
            return jsonify({'status': 'received'}), 200

        # Procesar comando
        phone = message_data['phone_number']
        message_text = message_data['message_text']
        contact_name = message_data['contact_name']

        logger.info(f"Procesando comando de {contact_name} ({phone}): {message_text[:50]}")

        # Parsear comando
        parsed = CommandParser.parse(message_text)
        action = parsed['action']
        platform = parsed['platform']
        account = parsed['account']
        campaign_name = parsed['campaign_name']

        # Ejecutar comando
        response_text = execute_command(
            action=action,
            platform=platform,
            account=account,
            campaign_name=campaign_name,
            parsed=parsed,
        )

        # Enviar respuesta
        whatsapp.send_message(phone, response_text)

        return jsonify({'status': 'ok'}), 200

    except Exception as e:
        logger.error(f"Error en manejador de webhook: {str(e)}")
        # No interrumpir el webhook, solo loguear
        return jsonify({'status': 'error', 'message': str(e)}), 200


# ============================================================================
# LÓGICA DE EJECUCIÓN DE COMANDOS
# ============================================================================

def format_campaign_status(campaign: dict) -> str:
    """Formatea la información de estado de una campaña."""
    status_emoji = '✅' if campaign.get('status') in ['ACTIVE', 'ENABLED'] else '⏸️'
    name = campaign.get('name') or campaign.get('campaign_name', 'Sin nombre')
    status = campaign.get('status', 'DESCONOCIDO')

    return f"{status_emoji} *{name}*\nEstado: {status}"


def format_metrics(metrics: dict) -> str:
    """Formatea la información de métricas."""
    campaign_name = metrics.get('name') or metrics.get('campaign_name', 'Campaña')
    period = metrics.get('period', 'N/A')
    data = metrics.get('data')

    if not data:
        return f"📊 *{campaign_name}*\nNo hay datos disponibles para {period}"

    spend = data.get('spend', 0)
    impressions = data.get('impressions', 0)
    clicks = data.get('clicks', 0)
    conversions = data.get('conversions', 0)

    cpc = (spend / clicks) if clicks > 0 else 0
    cpi = (spend / impressions) if impressions > 0 else 0

    text = f"""📊 *{campaign_name}*
Período: {period}

💰 Gasto: ${spend:.2f}
👁️ Impresiones: {impressions}
👆 Clics: {clicks}
🎯 Conversiones: {conversions}
📈 CPC: ${cpc:.2f}
📈 CPI: ${cpi:.4f}
"""
    return text


def execute_command(
    action: CommandAction,
    platform: CommandPlatform,
    account: str = None,
    campaign_name: str = None,
    parsed: dict = None,
) -> str:
    """
    Ejecuta un comando parseado.

    Args:
        action: Tipo de acción
        platform: Plataforma destino
        account: Alias de cuenta (para Meta)
        campaign_name: Nombre de campaña
        parsed: Diccionario completo parseado

    Returns:
        Texto de respuesta a enviar por WhatsApp
    """
    try:
        # Comandos que no requieren plataforma específica
        if action == CommandAction.HELP:
            return CommandParser.get_help_message()

        if action == CommandAction.LIST_ACCOUNTS:
            accounts = meta_ads.list_accounts()
            if not accounts:
                return "❌ No hay cuentas de Meta configuradas."

            text = "📋 *Cuentas disponibles:*\n\n"
            for acc in accounts:
                text += f"• {acc['alias'].upper()}: {acc['id']}\n"

            return text

        if action == CommandAction.UNKNOWN:
            return (
                "❌ No entendí tu comando.\n\n"
                "Escribe *'ayuda'* para ver los comandos disponibles."
            )

        # Comandos que requieren campaña pero no cuenta específica
        if action == CommandAction.LIST_CAMPAIGNS:
            if not account:
                # Asumir que es una acción de listar de Meta si no se especifica
                account = 'cp1'

            campaigns = meta_ads.list_campaigns(account)
            if not campaigns:
                return f"❌ No hay campañas en la cuenta {account.upper()}."

            text = f"📋 *Campañas de {account.upper()}:*\n\n"
            for c in campaigns:
                status_emoji = '✅' if c['status'] in ['ACTIVE', 'ENABLED'] else '⏸️'
                text += f"{status_emoji} {c['name']}\n"

            return text

        if action == CommandAction.STATUS:
            if not campaign_name:
                return (
                    "❌ Debes especificar una campaña.\n"
                    "Ejemplo: 'Estado de Black Friday en CP1'"
                )

            if not account:
                account = 'cp1'

            try:
                campaign = meta_ads.get_campaign_status(account, campaign_name)
                return f"📱 *Meta:*\n{format_campaign_status(campaign)}"
            except ValueError as e:
                return f"❌ Meta: {str(e)}"

        if action == CommandAction.GET_METRICS:
            if not campaign_name:
                return (
                    "❌ Debes especificar una campaña.\n"
                    "Ejemplo: 'Métricas de Black Friday en CP1'"
                )

            if not account:
                account = 'cp1'

            try:
                metrics = meta_ads.get_campaign_metrics(account, campaign_name)
                return f"📱 *Meta:*\n{format_metrics(metrics)}"
            except ValueError as e:
                return f"❌ Meta: {str(e)}"

        # Comandos que requieren campaña y pueden tener plataforma
        if action in [CommandAction.PAUSE, CommandAction.ACTIVATE]:
            if not campaign_name:
                return (
                    "❌ Debes especificar una campaña.\n"
                    "Ejemplo: 'Pausa Black Friday en CP1'"
                )

            action_text = "pausar" if action == CommandAction.PAUSE else "activar"
            method = meta_ads.pause_campaign if action == CommandAction.PAUSE else meta_ads.activate_campaign

            if not account:
                account = 'cp1'

            try:
                result = method(account, campaign_name)
                status_emoji = '⏸️' if action == CommandAction.PAUSE else '✅'
                return (
                    f"📱 *Meta ({account.upper()}):*\n"
                    f"{status_emoji} {result.get('message', f'Campaña {action_text}a')}"
                )
            except ValueError as e:
                return f"❌ Meta: {str(e)}"

        return "❌ Comando desconocido."

    except Exception as e:
        logger.error(f"Error ejecutando comando: {str(e)}")
        return f"❌ Error: {str(e)}"


# ============================================================================
# MANEJO DE ERRORES
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Maneja errores 404."""
    return jsonify({'error': 'Endpoint no encontrado'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Maneja errores 500."""
    logger.error(f"Error interno: {str(error)}")
    return jsonify({'error': 'Error interno del servidor'}), 500


# ============================================================================
# INICIO DE LA APLICACIÓN
# ============================================================================

if __name__ == '__main__':
    logger.info(f"Iniciando Bot de Gestión de Anuncios en {FLASK_ENV}")
    logger.info(f"Escuchando en puerto {PORT}")

    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=FLASK_DEBUG,
    )
