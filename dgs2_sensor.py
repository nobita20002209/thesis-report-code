"""
DGS2 environmental sensor implementation module for H2S and CO sensors
"""

import time
import serial
from typing import Dict, Any, Optional

from sensors.base_sensor import BaseSensor


class DGS2Sensor(BaseSensor):
    """
    Class for interfacing with DGS2 environmental sensor over serial
    """
    
    def __init__(self, port: str, baudrate: int = 9600, sensor_name: str = "DGS2"):
        """
        Initialize the DGS2 sensor
        
        Args:
            port (str): Serial port
            baudrate (int): Serial communication baudrate
            sensor_name (str): Name of the sensor for identification (e.g., "H₂S" or "CO")
        """
        super().__init__(sensor_name)
        
        self.port = port
        self.baudrate = baudrate
        self.ser = None
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
        Initialize the sensor
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Allow time for the serial connection to stabilize
            
            # Test communication
            test_response = self.send_command("")
            if not test_response:
                self.log_warning("No response from DGS2 sensor during initialization")
            
            self.initialized = True
            self.connected = True
            self.log_info(f"Initialized {self.sensor_name} sensor on port {self.port}")
            return True
            
        except Exception as e:
            self.log_error(f"Error initializing: {e}")
            self.cleanup()
            return False
    
    def send_command(self, command: str = "") -> str:
        """
        Send command to the sensor and get response
        
        Args:
            command (str): Command string to send
            
        Returns:
            str: Response from sensor
        """
        if not self.initialized:
            self.log_error("Sensor not initialized")
            return ""
            
        try:
            self.ser.write((command + "\r").encode())
            time.sleep(0.1)
            response = self.ser.readline().decode().strip()
            return response
        except Exception as e:
            self.log_error(f"Error sending command: {e}")
            return ""
    
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
            
        # Check if gas levels are negative (which would be invalid)
        if data["gas_ppb"] < 0 or data["gas_ppm"] < 0:
            return False
            
        # Check if temperature is outside reasonable range
        if data["temperature"] < -40 or data["temperature"] > 85:
            return False
            
        # Check if humidity is outside valid range
        if data["relative_humidity"] < 0 or data["relative_humidity"] > 100:
            return False
            
        return True
    
    def parse_measurement(self, measurement_string: str) -> Optional[Dict[str, Any]]:
        """
        Parse the measurement string from the sensor
        
        Args:
            measurement_string (str): Raw measurement string
            
        Returns:
            dict: Parsed measurement data or None if parsing failed
        """
        try:
            parts = measurement_string.split(',')
            if len(parts) >= 7:
                return {
                    'sensor': self.sensor_name,
                    'gas_ppb': int(parts[1].strip()),
                    'temperature': float(parts[2].strip()) / 100,
                    'relative_humidity': float(parts[3].strip()) / 100,
                    'adc_g': int(parts[4].strip()),
                    'adc_t': int(parts[5].strip()),
                    'adc_h': int(parts[6].strip()),
                    'gas_ppm': int(parts[1].strip()) / 1000
                }
            else:
                self.log_warning(f"Invalid measurement format: {measurement_string}")
                return None
        except Exception as e:
            self.log_error(f"Error parsing measurement: {e}")
            return None
    def read_measurement(self) -> Optional[Dict[str, Any]]:
        """
        Read measurement from the sensor
        Replace any non-temperature readings with zero if they're invalid
        
        Returns:
            dict: Measurement data or None if failed
        """
        if not self.initialized:
            if not self.initialize():
                return self.last_valid_reading
        
        try:
            response = self.send_command()
            data = self.parse_measurement(response)
            
            if data:
                # Keep temperature as is, but sanitize other readings
                for key, value in data.items():
                    # Skip non-numeric values or temperature
                    if not isinstance(value, (int, float)) or 'temp' in key.lower():
                        continue
                    
                    # Replace invalid values with zero
                    if value < 0:
                        self.log_warning(f"Invalid {key} reading ({value}), replacing with 0")
                        data[key] = 0
                
                self.last_valid_reading = data
                
            return data
            
        except Exception as e:
            self.log_error(f"Error reading: {e}")
            return self.last_valid_reading 
    def cleanup(self) -> None:
        """Clean up resources"""
        try:
            if self.ser:
                self.ser.close()
            self.initialized = False
            self.connected = False
            self.log_info("Resources cleaned up")
        except Exception as e:
            self.log_error(f"Error during cleanup: {e}")
