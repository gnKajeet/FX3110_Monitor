"""
Base interfaces for data collectors.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional


class CellularCollector(ABC):
    """Base interface for all cellular device collectors."""

    @abstractmethod
    def get_signal_metrics(self) -> Dict:
        """
        Get cellular signal quality metrics.

        Returns:
            Dict with keys: rsrp, rsrq, snr (or sinr), rssi
            Values are integers in dBm (rsrp, rssi) or dB (rsrq, snr)
        """
        pass

    @abstractmethod
    def get_network_info(self) -> Dict:
        """
        Get network and carrier information.

        Returns:
            Dict with keys: carrier, technology, band, bandwidth
        """
        pass

    @abstractmethod
    def get_connection_status(self) -> Dict:
        """
        Get WAN connection status.

        Returns:
            Dict with keys: wan_status, wan_source, device_ipv4
        """
        pass

    @abstractmethod
    def get_sim_info(self) -> Dict:
        """
        Get SIM card information.

        Returns:
            Dict with keys: apn, iccid, sim_status
        """
        pass

    @abstractmethod
    def get_device_info(self) -> Dict:
        """
        Get device/modem information.

        Returns:
            Dict with keys: model, manufacturer, firmware, imei, serial
        """
        pass

    def get_all(self) -> Dict:
        """
        Get all metrics in a single call.

        Returns:
            Combined dict from all get_* methods
        """
        result = {}
        result.update(self.get_signal_metrics())
        result.update(self.get_network_info())
        result.update(self.get_connection_status())
        result.update(self.get_sim_info())
        result.update(self.get_device_info())
        return result


class NetworkCollector(ABC):
    """Base interface for network connectivity testing."""

    @abstractmethod
    def ping(self, dest: str, interface: Optional[str] = None) -> Dict:
        """
        Ping a destination and return metrics.

        Args:
            dest: Destination IP or hostname
            interface: Optional interface to bind to (e.g., "eth0")

        Returns:
            Dict with keys: success (bool), latency_ms (int), source_ip (str)
        """
        pass

    @abstractmethod
    def get_active_interface(self, dest: str) -> str:
        """
        Determine which network interface would be used to reach dest.

        Args:
            dest: Destination IP or hostname

        Returns:
            Interface name (e.g., "eth0", "wlan0")
        """
        pass

    @abstractmethod
    def get_public_ip(self) -> Optional[str]:
        """
        Get the public IP address.

        Returns:
            Public IP address as string, or None if unavailable
        """
        pass
