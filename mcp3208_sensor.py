"""
MCP3208 analog sensor implementation module for HCHO and NH3
"""

import time
from typing import Dict, Any, Optional

import spidev
from sensors.base_sensor import BaseSensor

class MCP3208Sensor(BaseSensor):
    """
    Class for interfacing with MCP3208 ADC to read analog HCHO and NH3 sensors
    """
    
    def __init__(self, 
                 channel: int,
                 spi_bus: int = 0, 
                 spi_device: int = 0, 
                 spi_speed_hz: int = 1000000, 
                 vref: float = 3.282,
                 r_feedback: int = 22000,
                 sensitivity: float = 35.0,  # Default is HCHO sensitivity
                 sensor_name: str = "AnalogSensor"):
        """
        Initialize the MCP3208 analog sensor interface
        
        Args:
            channel (int): MCP3208 channel (0-7)
            spi_bus (int): SPI bus number
            spi_device (int): SPI device number
            spi_speed_hz (int): SPI speed in Hz
            vref (float): ADC reference voltage
            r_feedback (int): TIA feedback resistor in Ohms
            sensitivity (float): Sensor sensitivity in nA/ppm
            sensor_name (str): Name of the sensor for identification
        """
        super().__init__(sensor_name)
        
        if channel < 0 or channel > 7:
            raise ValueError("Invalid channel. Must be 0-7.")
            
        self.channel = channel
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.spi_speed_hz = spi_speed_hz
        self.vref = vref
        self.r_feedback = r_feedback
        self.sensitivity = sensitivity
        self.spi = None
        self.initialized = False

    def connect(self) -> bool:
        """
        Alias for initialize
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        return self.initialize()

    def initialize(self) -> bool:
        """
        Initialize the SPI interface
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            self.spi = spidev.SpiDev()
            self.spi.open(self.spi_bus, self.spi_device)
            self.spi.max_speed_hz = self.spi_speed_hz
            self.initialized = True
            self.connected = True
            self.log_info(f"MCP3208 sensor on channel {self.channel} initialized")
            return True
            
        except Exception as e:
            self.log_error(f"Error initializing MCP3208: {e}")
            self.cleanup()
            return False

    def is_valid_reading(self, data: Optional[Dict[str, Any]]) -> bool:
        """
        Check if the sensor reading contains valid values
        
        Args:
            data (dict): Sensor data dictionary
            
        Returns:
            bool: True if all values are valid, False otherwise
        """
        if not data:
            return False
            
        # Check if concentration is negative or unrealistically high
        if data["concentration"] < 0:
            return False
            
        # Different thresholds for different gases
        if self.sensor_name == "HCHO" and data["concentration"] > 100:  # Increased threshold based on all.py readings
            return False
            
        if self.sensor_name == "NH3" and data["concentration"] > 100:  # Increased threshold based on all.py readings
            return False
            
        return True

    def read_channel(self) -> int:
        """
        Read the raw value from the MCP3208 channel
        
        Returns:
            int: Raw ADC value (0-4095)
        """
        if not self.initialized or not self.spi:
            if not self.initialize():
                return 0
                
        try:
            cmd = [0b00000110 | ((self.channel & 0b100) >> 2), (self.channel & 0b011) << 6, 0]
            resp = self.spi.xfer2(cmd)
            result = ((resp[1] & 0x0F) << 8) | resp[2]
            return result
            
        except Exception as e:
            self.log_error(f"Error reading ADC channel: {e}")
            return 0

    def adc_to_voltage(self, adc_value: int) -> float:
        """
        Convert ADC value to voltage - matching all.py exactly
        
        Args:
            adc_value (int): Raw ADC value (0-4095)
            
        Returns:
            float: Voltage value
        """
        return (adc_value / 4095.0) * self.vref

    def calculate_iout(self, vout: float) -> float:
        """
        Calculate output current from voltage - matching all.py exactly
        
        Args:
            vout (float): Output voltage
            
        Returns:
            float: Output current in nA
        """
        return ((self.vref - vout) / self.r_feedback) * 1e9  # nA

    def calculate_concentration(self, iout: float) -> float:
        """
        Calculate gas concentration from output current - matching all.py exactly
        
        Args:
            iout (float): Output current in nA
            
        Returns:
            float: Gas concentration in ppm
        """
        # Avoid division by zero
        if self.sensitivity <= 0:
            self.log_error(f"Invalid sensitivity value: {self.sensitivity}")
            return 0.0
            
        return iout / self.sensitivity  # ppm

    def read_measurement(self) -> Optional[Dict[str, Any]]:
        """
        Read measurement from the sensor
        Match the format of readings in all.py
        
        Returns:
            dict: Measurement data or None if failed
        """
        if not self.initialized:
            if not self.initialize():
                return self.last_valid_reading
        
        try:
            raw_adc = self.read_channel()
            voltage = self.adc_to_voltage(raw_adc)
            iout = self.calculate_iout(voltage)
            concentration = self.calculate_concentration(iout)
            
            # For chemical sensors, concentration should never be negative
            if concentration < 0:
                self.log_warning(f"Invalid concentration reading: {concentration}, replacing with 0")
                concentration = 0
            
            data = {
                "sensor": self.sensor_name,
                "raw_adc": raw_adc,
                "voltage": voltage,
                "current_nA": iout,
                "concentration": concentration,  # ppm value
                "concentration_ppb": concentration * 1000  # ppb value
            }
            
            self.last_valid_reading = data
            return data
            
        except Exception as e:
            self.log_error(f"Error reading sensor: {e}")
            return self.last_valid_reading
            
    def cleanup(self) -> None:
        """Clean up resources"""
        try:
            if self.spi:
                self.spi.close()
            self.initialized = False
            self.connected = False
            self.log_info("SPI resources cleaned up")
        except Exception as e:
            self.log_error(f"Error during cleanup: {e}")