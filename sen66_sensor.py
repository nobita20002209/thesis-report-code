"""
SEN66 environmental sensor implementation module
"""

import time
from typing import Dict, Any, Optional

from sensors.base_sensor import BaseSensor

try:
    from sensirion_i2c_driver import LinuxI2cTransceiver, I2cConnection, CrcCalculator
    from sensirion_driver_adapters.i2c_adapter.i2c_channel import I2cChannel
    from sensirion_i2c_sen66.device import Sen66Device
    SENSIRION_AVAILABLE = True
except ImportError:
    SENSIRION_AVAILABLE = False
    print("Warning: Sensirion libraries not available, SEN66 sensor will not work")


class SEN66Sensor(BaseSensor):
    """
    Class for interfacing with SEN66 environmental sensor over I2C
    """
    
    def __init__(self, i2c_port: str, address: int = 0x6B, calibration_time: int = 10, sensor_name: str = "SEN66"):
        """
        Initialize the SEN66 sensor
        
        Args:
            i2c_port (str): I2C port
            address (int): I2C slave address
            calibration_time (int): Calibration time in seconds
            sensor_name (str): Name of the sensor for identification
        """
        super().__init__(sensor_name)
        
        if not SENSIRION_AVAILABLE:
            self.log_error("Sensirion libraries not available")
            return
            
        self.i2c_port = i2c_port
        self.address = address
        self.calibration_time = calibration_time
        self.transceiver = None
        self.channel = None
        self.sensor = None
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
        Initialize and calibrate the sensor
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        if not SENSIRION_AVAILABLE:
            return False
            
        try:
            self.transceiver = LinuxI2cTransceiver(self.i2c_port)
            self.transceiver.__enter__()
            
            self.channel = I2cChannel(
                I2cConnection(self.transceiver),
                slave_address=self.address,
                crc=CrcCalculator(8, 0x31, 0xff, 0x0)
            )
            
            self.sensor = Sen66Device(self.channel)
            self.sensor.device_reset()
            
            self.log_info(f"Calibrating... Please wait for {self.calibration_time} seconds.")
            time.sleep(self.calibration_time)
            self.log_info("✅ Calibration complete.")
            
            self.sensor.start_continuous_measurement()
            self.initialized = True
            self.connected = True
            return True
            
        except Exception as e:
            self.log_error(f"Error initializing: {e}")
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
            
        # Check if any environmental values are negative
        if (data["pm1.0"] < 0 or data["pm2.5"] < 0 or data["pm4.0"] < 0 or 
            data["pm10"] < 0 or data["VOC_Index"] < 0 or data["NOx_Index"] < 0 or 
            data["CO2"] < 0):
            return False
            
        # Check if temperature is outside reasonable range
        if data["temperature"] < -40 or data["temperature"] > 85:
            return False
            
        # Check if humidity is outside valid range
        if data["humidity"] < 0 or data["humidity"] > 100:
            return False
            
        return True

    def read_measurement(self) -> Optional[Dict[str, Any]]:
        """
        Read measurement from the sensor
        
        Returns:
            dict: Measurement data or None if failed
        """
        if not SENSIRION_AVAILABLE:
            return None
            
        if not self.initialized:
            if not self.initialize():
                return self.last_valid_reading  # Return last valid reading if available
                
        try:
            values = self.sensor.read_measured_values()
            data = {
                "sensor": self.sensor_name,
                "temperature": values[5].value,
                "humidity": values[4].value,
                "pm1.0": values[0].value,
                "pm2.5": values[1].value,
                "pm4.0": values[2].value,
                "pm10": values[3].value,
                "VOC_Index": values[6].value,
                "NOx_Index": values[7].value,
                "CO2": values[8].value,
            }
            
            # Check for suspicious values
            if not self.is_valid_reading(data):
                self.log_warning(
                    f"Suspicious reading: PM2.5={data['pm2.5']}, PM10={data['pm10']}, "
                    f"VOC={data['VOC_Index']}, NOx={data['NOx_Index']}, CO2={data['CO2']}, "
                    f"Temp={data['temperature']}°C, RH={data['humidity']}%"
                )
                return self.last_valid_reading
            
            # Update last valid reading
            self.last_valid_reading = data
            return data
            
        except Exception as e:
            self.log_error(f"Error reading: {e}")
            self.initialized = False
            return self.last_valid_reading

    def cleanup(self) -> None:
        """Clean up resources"""
        if not SENSIRION_AVAILABLE:
            return
            
        try:
            if self.transceiver:
                self.transceiver.__exit__(None, None, None)
            self.initialized = False
            self.connected = False
            self.log_info("Resources cleaned up")
        except Exception as e:
            self.log_error(f"Error during cleanup: {e}")
