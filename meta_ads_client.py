"""
Cliente para la API de Meta Ads (Facebook Ads)
Maneja todas las operaciones en campañas de Meta
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from rapidfuzz import fuzz
from rapidfuzz import process

from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.exceptions import FacebookRequestError

from config import META_APP_ID, META_APP_SECRET, META_ACCESS_TOKEN, get_meta_account_id, get_all_meta_accounts

logger = logging.getLogger(__name__)

class MetaAdsClient:
    """
    Cliente para gestionar campañas de Meta Ads.
    Utiliza el SDK oficial de Facebook Business.
    """

    def __init__(self):
        """Inicializa el cliente de Meta Ads."""
        if not all([META_APP_ID, META_APP_SECRET, META_ACCESS_TOKEN]):
            raise ValueError(
                "Configuración de Meta Ads incompleta. "
                "Verifica META_APP_ID, META_APP_SECRET y META_ACCESS_TOKEN en .env"
            )

        try:
            FacebookAdsApi.init(
                access_token=META_ACCESS_TOKEN,
                app_secret=META_APP_SECRET
            )
            logger.info("Cliente de Meta Ads inicializado correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar Meta Ads: {str(e)}")
            raise

    def _get_ad_account(self, account_alias: str) -> AdAccount:
        """
        Obtiene un objeto AdAccount de Meta.

        Args:
            account_alias: Alias de la cuenta (cp1, cp20, etc.)

        Returns:
            Objeto AdAccount

        Raises:
            ValueError: Si la cuenta no existe o no es válida
            FacebookRequestError: Si hay error en la API
        """
        account_id = get_meta_account_id(account_alias)
        try:
            account = AdAccount(f'act_{account_id}')
            account.remote_read(fields=['name', 'account_status'])
            logger.info(f"Conectado a cuenta Meta: {account_alias} ({account_id})")
            return account
        except FacebookRequestError as e:
            logger.error(f"Error de Meta API para cuenta {account_alias}: {str(e)}")
            raise ValueError(
                f"No se pudo acceder a la cuenta Meta '{account_alias}'. "
                f"Verifica el token de acceso y el ID de cuenta."
            )

    def _find_campaign_by_name(
        self, campaigns: List[Campaign], campaign_query: str
    ) -> Optional[Campaign]:
        """
        Busca una campaña por nombre usando búsqueda fuzzy.

        Args:
            campaigns: Lista de campañas disponibles
            campaign_query: Nombre o ID de campaña a buscar

        Returns:
            Objeto Campaign si encuentra coincidencia, None en caso contrario
        """
        for campaign in campaigns:
            if campaign['id'] == campaign_query:
                return campaign

        campaign_names = [(c['name'], c) for c in campaigns if 'name' in c]
        if not campaign_names:
            return None

        result = process.extractOne(
            campaign_query,
            [name for name, _ in campaign_names],
            scorer=fuzz.token_set_ratio
        )

        if not result:
            return None

        best_match, score, _ = result

        if score >= 60:
            for name, campaign in campaign_names:
                if name == best_match:
                    logger.info(
                        f"Campaña encontrada por fuzzy match: '{best_match}' "
                        f"(similitud: {score}%)"
                    )
                    return campaign

        return None

    def list_campaigns(self, account_alias: str) -> List[Dict]:
        """
        Lista todas las campañas de una cuenta con sus estados.

        Args:
            account_alias: Alias de la cuenta (cp1, cp20, etc.)

        Returns:
            Lista de diccionarios con información de campañas

        Raises:
            ValueError: Si la cuenta no existe
            FacebookRequestError: Si hay error en la API
        """
        try:
            account = self._get_ad_account(account_alias)
            campaigns = account.get_campaigns(
                fields=[
                    Campaign.Field.id,
                    Campaign.Field.name,
                    Campaign.Field.status,
                    Campaign.Field.created_time,
                    Campaign.Field.updated_time,
                ]
            )

            campaigns_list = []
            for campaign in campaigns:
                campaigns_list.append({
                    'id': campaign['id'],
                    'name': campaign.get('name', 'Sin nombre'),
                    'status': campaign.get('status', 'DESCONOCIDO'),
                    'created': campaign.get('created_time', 'N/A'),
                    'updated': campaign.get('updated_time', 'N/A'),
                })

            logger.info(f"Se listaron {len(campaigns_list)} campañas de {account_alias}")
            return campaigns_list

        except FacebookRequestError as e:
            logger.error(f"Error al listar campañas de {account_alias}: {str(e)}")
            raise ValueError(
                f"Error al obtener campañas de {account_alias}: {str(e)}"
            )

    def get_campaign_status(
        self, account_alias: str, campaign_name_or_id: str
    ) -> Dict:
        """
        Obtiene el estado detallado de una campaña.
        """
        try:
            campaigns = self.list_campaigns(account_alias)
            campaign = self._find_campaign_by_name(campaigns, campaign_name_or_id)

            if not campaign:
                available = ', '.join([c['name'] for c in campaigns[:5]])
                raise ValueError(
                    f"Campaña '{campaign_name_or_id}' no encontrada en {account_alias}. "
                    f"Campañas disponibles: {available}..."
                )

            return campaign

        except FacebookRequestError as e:
            logger.error(
                f"Error al obtener estado de campaña {campaign_name_or_id}: {str(e)}"
            )
            raise ValueError(f"Error al obtener estado de campaña: {str(e)}")

    def pause_campaign(self, account_alias: str, campaign_name_or_id: str) -> Dict:
        """
        Pausa una campaña.
        """
        try:
            account = self._get_ad_account(account_alias)
            campaigns = account.get_campaigns(
                fields=[Campaign.Field.id, Campaign.Field.name, Campaign.Field.status]
            )

            campaign = self._find_campaign_by_name(campaigns, campaign_name_or_id)
            if not campaign:
                raise ValueError(
                    f"Campaña '{campaign_name_or_id}' no encontrada en {account_alias}"
                )

            if campaign['status'] == 'PAUSED':
                logger.info(f"Campaña {campaign['id']} ya está pausada")
                return {
                    'id': campaign['id'],
                    'name': campaign.get('name'),
                    'status': 'PAUSED',
                    'message': 'La campaña ya estaba pausada'
                }

            campaign_obj = Campaign(campaign['id'])
            campaign_obj.update({Campaign.Field.status: 'PAUSED'})

            logger.info(f"Campaña {campaign['id']} pausada exitosamente")
            return {
                'id': campaign['id'],
                'name': campaign.get('name'),
                'status': 'PAUSED',
                'message': 'Campaña pausada exitosamente'
            }

        except FacebookRequestError as e:
            logger.error(f"Error al pausar campaña: {str(e)}")
            raise ValueError(f"Error al pausar campaña: {str(e)}")

    def activate_campaign(self, account_alias: str, campaign_name_or_id: str) -> Dict:
        """
        Activa (reanuda) una campaña.
        """
        try:
            account = self._get_ad_account(account_alias)
            campaigns = account.get_campaigns(
                fields=[Campaign.Field.id, Campaign.Field.name, Campaign.Field.status]
            )

            campaign = self._find_campaign_by_name(campaigns, campaign_name_or_id)
            if not campaign:
                raise ValueError(
                    f"Campaña '{campaign_name_or_id}' no encontrada en {account_alias}"
                )

            if campaign['status'] == 'ACTIVE':
                logger.info(f"Campaña {campaign['id']} ya está activa")
                return {
                    'id': campaign['id'],
                    'name': campaign.get('name'),
                    'status': 'ACTIVE',
                    'message': 'La campaña ya estaba activa'
                }

            campaign_obj = Campaign(campaign['id'])
            campaign_obj.update({Campaign.Field.status: 'ACTIVE'})

            logger.info(f"Campaña {campaign['id']} activada exitosamente")
            return {
                'id': campaign['id'],
                'name': campaign.get('name'),
                'status': 'ACTIVE',
                'message': 'Campaña activada exitosamente'
            }

        except FacebookRequestError as e:
            logger.error(f"Error al activar campaña: {str(e)}")
            raise ValueError(f"Error al activar campaña: {str(e)}")

    def get_campaign_metrics(
        self,
        account_alias: str,
        campaign_name_or_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict:
        """
        Obtiene métricas de una campaña para un rango de fechas.
        """
        try:
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

            account = self._get_ad_account(account_alias)
            campaigns = account.get_campaigns(
                fields=[Campaign.Field.id, Campaign.Field.name]
            )

            campaign = self._find_campaign_by_name(campaigns, campaign_name_or_id)
            if not campaign:
                raise ValueError(
                    f"Campaña '{campaign_name_or_id}' no encontrada en {account_alias}"
                )

            insights = campaign.get_insights(
                fields=[
                    'campaign_id',
                    'campaign_name',
                    'spend',
                    'impressions',
                    'clicks',
                    'actions',
                    'action_values',
                ],
                params={
                    'date_preset': 'custom',
                    'time_range': {
                        'since': start_date,
                        'until': end_date,
                    }
                }
            )

            if not insights:
                logger.warning(f"No hay datos de insights para {campaign['id']}")
                return {
                    'id': campaign['id'],
                    'name': campaign.get('name'),
                    'period': f'{start_date} a {end_date}',
                    'data': None,
                    'message': 'No hay datos disponibles para este período'
                }

            data = insights[0]

            return {
                'id': campaign['id'],
                'name': campaign.get('name'),
                'period': f'{start_date} a {end_date}',
                'data': {
                    'spend': float(data.get('spend', 0)),
                    'impressions': int(data.get('impressions', 0)),
                    'clicks': int(data.get('clicks', 0)),
                    'actions': data.get('actions', []),
                    'action_values': data.get('action_values', []),
                },
                'message': 'Métricas obtenidas exitosamente'
            }

        except FacebookRequestError as e:
            logger.error(f"Error al obtener métricas de campaña: {str(e)}")
            raise ValueError(f"Error al obtener métricas: {str(e)}")

    def list_accounts(self) -> List[Dict]:
        """
        Lista todas las cuentas de Meta configuradas.
        """
        accounts = get_all_meta_accounts()
        return [
            {
                'alias': alias,
                'id': account_id,
            }
            for alias, account_id in accounts.items()
        ]
