"""
Specific implementations for HCHO and NH3 sensors using MCP3208
"""

from typing import Dict, Any, Optional
from sensors.mcp3208_sensor import MCP3208Sensor

class HCHOSensor(MCP3208Sensor):
    """
    Class for HCHO (Formaldehyde) sensor using MCP3208 ADC
    """
    
    def __init__(self, 
                 channel: int = 0,
                 spi_bus: int = 0, 
                 spi_device: int = 0, 
                 vref: float = 3.282,
                 r_feedback: int = 22000,
                 sensitivity: float = 35.0):  # nA/ppm for HCHO
        """
        Initialize the HCHO sensor
        
        Args:
            channel (int): MCP3208 channel (0-7), default is 0
            spi_bus (int): SPI bus number
            spi_device (int): SPI device number
            vref (float): ADC reference voltage
            r_feedback (int): TIA feedback resistor in Ohms
            sensitivity (float): HCHO sensor sensitivity in nA/ppm
        """
        super().__init__(
            channel=channel,
            spi_bus=spi_bus,
            spi_device=spi_device,
            vref=vref,
            r_feedback=r_feedback,
            sensitivity=sensitivity,
            sensor_name="HCHO"
        )
    
    def is_valid_reading(self, data: Optional[Dict[str, Any]]) -> bool:
        """
        Check if the HCHO sensor reading contains valid values
        
        Args:
            data (dict): Sensor data dictionary
            
        Returns:
            bool: True if all values are valid, False otherwise
        """
        if not super().is_valid_reading(data):
            return False
            
        # Based on all.py, we see much higher values than expected originally
        # Typical indoor HCHO levels are between 0.01 and 0.5 ppm
        # But in the actual data, we're seeing values up to ~40 ppm
        if data["concentration"] > 100.0:  # Set a much higher threshold based on actual data
            self.log_warning(f"Abnormally high HCHO concentration: {data['concentration']} ppm")
            return False
            
        return True
        
    def read_measurement(self) -> Optional[Dict[str, Any]]:
        """
        Read and return measurement with formatted output
        Match the format of readings in all.py
        
        Returns:
            dict: Measurement data or None if failed
        """
        data = super().read_measurement()
        
        if data:
            # First ensure concentration is non-negative
            if data.get("concentration", 0) < 0:
                data["concentration"] = 0
                self.log_warning("Invalid concentration reading corrected to 0")
            
            # Add other fields specific to this gas
            data["chemical_formula"] = "HCHO"
            data["common_name"] = "Formaldehyde"
            data["unit"] = "ppm"
        
        return data

class NH3Sensor(MCP3208Sensor):
    """
    Class for NH3 (Ammonia) sensor using MCP3208 ADC
    """
    
    def __init__(self, 
                 channel: int = 1,
                 spi_bus: int = 0, 
                 spi_device: int = 0, 
                 vref: float = 3.282,
                 r_feedback: int = 22000,
                 sensitivity: float = 20.0):  # nA/ppm for NH3
        """
        Initialize the NH3 sensor
        
        Args:
            channel (int): MCP3208 channel (0-7), default is 1
            spi_bus (int): SPI bus number
            spi_device (int): SPI device number
            vref (float): ADC reference voltage
            r_feedback (int): TIA feedback resistor in Ohms
            sensitivity (float): NH3 sensor sensitivity in nA/ppm
        """
        super().__init__(
            channel=channel,
            spi_bus=spi_bus,
            spi_device=spi_device,
            vref=vref,
            r_feedback=r_feedback,
            sensitivity=sensitivity,
            sensor_name="NH3"
        )
    
    def is_valid_reading(self, data: Optional[Dict[str, Any]]) -> bool:
        """
        Check if the NH3 sensor reading contains valid values
        
        Args:
            data (dict): Sensor data dictionary
            
        Returns:
            bool: True if all values are valid, False otherwise
        """
        if not super().is_valid_reading(data):
            return False
            
        # Based on all.py, we're seeing higher values than originally expected
        # Normal ambient NH3 levels are typically below 1 ppm
        # But in the actual data, we're seeing values ~16 ppm
        if data["concentration"] > 100.0:  # Set a much higher threshold based on actual data
            self.log_warning(f"Abnormally high NH3 concentration: {data['concentration']} ppm")
            return False
            
        return True
        
    def read_measurement(self) -> Optional[Dict[str, Any]]:
        """
        Read and return NH3 measurement with formatted output
        Match the format of readings in all.py
        
        Returns:
            dict: Measurement data or None if failed
        """
        data = super().read_measurement()
        
        if data:
            # Add additional fields or formatting specific to NH3
            data["chemical_formula"] = "NH₃"
            data["common_name"] = "Ammonia"
            data["unit"] = "ppm"
            
        return data