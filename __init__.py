"""
Custom integration to integrate Veolia with Home Assistant - FIXED BLOCKING IMPORT 2026
"""

import asyncio
import logging
import importlib
from datetime import timedelta  # ✅ Fix timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ABO_ID, CONF_PASSWORD, CONF_USERNAME, DOMAIN, PLATFORMS

SCAN_INTERVAL = timedelta(hours=10)  # ✅ timedelta classique

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config):
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Veolia - imports différés (anti-blocage HA)."""
    
    # ✅ IMPORTS CRITIQUES en executor (fix le blocking call)
    def _safe_import_modules():
        veolia_mod = importlib.import_module('.VeoliaClient', 'custom_components.veolia')
        debug_mod = importlib.import_module('.debug', 'custom_components.veolia')
        return veolia_mod.VeoliaClient, debug_mod.decoratorexceptionDebug
    
    loop = asyncio.get_running_loop()
    VeoliaClient, decoratorexceptionDebug = await loop.run_in_executor(
        None, _safe_import_modules
    )
    
    # ✅ Wrapper décorateur (logique originale préservée)
    @decoratorexceptionDebug
    async def _setup_core():
        hass.data.setdefault(DOMAIN, {})
        
        username = entry.data.get(CONF_USERNAME)
        password = entry.data.get(CONF_PASSWORD)
        abo_id = entry.data.get(CONF_ABO_ID)
        
        session = async_get_clientsession(hass)
        client = VeoliaClient(username, password, session, abo_id)
        
        coordinator = VeoliaDataUpdateCoordinator(hass, client)
        await coordinator.async_refresh()
        
        if not coordinator.last_update_success:
            raise ConfigEntryNotReady
        
        hass.data[DOMAIN][entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.info("✅ Veolia integration loaded successfully")
        return True
    
    return await _setup_core()


class VeoliaDataUpdateCoordinator(DataUpdateCoordinator):
    """Data coordinator for Veolia API."""

    def __init__(self, hass: HomeAssistant, client) -> None:
        """Initialize coordinator."""
        self.api = client
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL
        )

    async def _async_update_data(self):
        """Fetch data from Veolia API."""
        try:
            consumption = await self.hass.async_add_executor_job(self.api.update_all)
            _LOGGER.debug(f"Veolia data updated: {consumption}")
            return consumption
        except Exception as exc:
            _LOGGER.error(f"Veolia API error: {exc}")
            raise UpdateFailed(f"API error: {exc}") from exc


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload Veolia entry."""
    coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
    if coordinator:
        return await hass.config_entries.async_forward_entry_unload(entry, PLATFORMS[0])
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    return await async_setup_entry(hass, entry)
