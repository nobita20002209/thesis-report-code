"""
MICS6814 gas sensor implementation module
"""

import time
import datetime
from typing import Dict, Any, Optional

from sensors.base_sensor import BaseSensor

try:
    from mics6814 import MICS6814
    MICS6814_AVAILABLE = True
except ImportError:
    MICS6814_AVAILABLE = False
    print("Warning: MICS6814 library not available, MICS6814 sensor will not work")


class MICS6814Sensor(BaseSensor):
    """
    Class for interfacing with MICS6814 gas sensor
    """
    
    def __init__(
        self,
        i2c_port: int = 1,
        address: int = 0x19,
        warmup_time: int = 30,
        print_readings: bool = False,
        enable_led: bool = True,
        sensor_name: str = "MICS6814"
    ):
        """
        Initialize the MICS6814 gas sensor

        Args:
            i2c_port (int): I2C bus number (usually 1 for Raspberry Pi)
            address (int): I2C address (not always used depending on library)
            warmup_time (int): Calibration/warm-up time in seconds
            print_readings (bool): If True, print readings during update
            enable_led (bool): If True, control LED based on gas values
            sensor_name (str): Name of the sensor for identification
        """
        super().__init__(sensor_name)

        if not MICS6814_AVAILABLE:
            self.log_error("MICS6814 library not available")
            return

        self.i2c_port = i2c_port
        self.address = address  # Currently not used unless needed by lib
        self.calibration_time = warmup_time
        self.print_readings = print_readings
        self.enable_led = enable_led

        self.gas = None
        self.baseline = {
            "oxidising": None,
            "reducing": None,
            "nh3": None
        }
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
        if not MICS6814_AVAILABLE:
            return False
            
        try:
            # Initialize the sensor
            self.gas = MICS6814()
            # Set the LED to green (if the breakout has an LED)
            self.gas.set_led(0, 255, 0)
            
            self.log_info(f"Warming up and calibrating... Please wait for {self.calibration_time} seconds.")
            
            # Enable heater for warm-up
            self.gas.set_heater(True)
            
            # Warm-up period
            time.sleep(self.calibration_time)
            
            # Read baseline values
            baseline_reading = self.gas.read_all()
            self.baseline["oxidising"] = baseline_reading.oxidising
            self.baseline["reducing"] = baseline_reading.reducing
            self.baseline["nh3"] = baseline_reading.nh3
            
            self.log_info(
                f"Baseline values - Oxidising: {self.baseline['oxidising']:.2f} Ω, "
                f"Reducing: {self.baseline['reducing']:.2f} Ω, "
                f"NH3: {self.baseline['nh3']:.2f} Ω"
            )
            
            self.initialized = True
            self.connected = True
            return True
            
        except Exception as e:
            self.log_error(f"Error initializing: {e}")
            self.cleanup()
            return False

    def is_valid_reading(self, readings) -> bool:
        """
        Check if sensor readings are valid
        
        Args:
            readings: Raw sensor readings
            
        Returns:
            bool: True if all values are valid, False otherwise
        """
        # Check if any reading is None or less than or equal to zero
        if (readings.oxidising is None or readings.reducing is None or 
            readings.nh3 is None or readings.oxidising <= 0 or 
            readings.reducing <= 0 or readings.nh3 <= 0):
            return False
        
        # Check if baseline values are properly set
        if (self.baseline["oxidising"] is None or 
            self.baseline["reducing"] is None or 
            self.baseline["nh3"] is None):
            return False
            
        return True

    def calculate_ppm(self, current: float, baseline_value: float, gas_type: str) -> float:
        """
        Calculate approximate gas concentration in ppm based on resistance ratio
        
        Args:
            current (float): Current resistance value
            baseline_value (float): Baseline resistance value
            gas_type (str): Type of gas ("oxidising", "reducing", or "nh3")
            
        Returns:
            float: Gas concentration in ppm
        """
        if baseline_value is None or current <= 0 or baseline_value <= 0:
            return 0.0
            
        if gas_type == "oxidising":  # NO2 typically
            ratio = baseline_value / current  # Inverted for oxidizing gases
            return max(0, 0.1 * (ratio - 1))
        elif gas_type == "reducing":  # CO typically
            ratio = current / baseline_value
            return max(0, 4.0 * (ratio - 1))
        elif gas_type == "nh3":
            ratio = current / baseline_value
            return max(0, 5.0 * (ratio - 1))
        else:
            return 0.0

    def update_led(self, no2_ppm: float, co_ppm: float, nh3_ppm: float) -> None:
        """
        Update LED color based on gas concentrations
        
        Args:
            no2_ppm (float): NO2 concentration in ppm
            co_ppm (float): CO concentration in ppm
            nh3_ppm (float): NH3 concentration in ppm
        """
        if not self.initialized or not self.gas:
            return
            
        # Red if high NO2 detected
        if no2_ppm > 0.1:  # NO2 levels above 0.1 ppm
            self.gas.set_led(255, 0, 0)
        # Yellow if high CO detected
        elif co_ppm > 5.0:  # CO levels above 5 ppm
            self.gas.set_led(255, 255, 0)
        # Purple if high NH3 detected
        elif nh3_ppm > 1.0:  # NH3 levels above 1 ppm
            self.gas.set_led(255, 0, 255)
        # Otherwise green
        else:
            self.gas.set_led(0, 255, 0)

    def read_measurement(self) -> Optional[Dict[str, Any]]:
        """
        Read measurement from the sensor
        
        Returns:
            dict: Measurement data or None if failed
        """
        if not MICS6814_AVAILABLE:
            return None
            
        if not self.initialized:
            if not self.initialize():
                return self.last_valid_reading  # Return last valid reading if available
                
        try:
            # Get all readings at once
            readings = self.gas.read_all()
            
            # Check if readings are valid
            if not self.is_valid_reading(readings):
                self.log_warning("Invalid readings detected")
                return self.last_valid_reading
            
            # Calculate approximate gas concentrations
            no2_ppm = self.calculate_ppm(readings.oxidising, self.baseline["oxidising"], "oxidising")
            co_ppm = self.calculate_ppm(readings.reducing, self.baseline["reducing"], "reducing")
            nh3_ppm = self.calculate_ppm(readings.nh3, self.baseline["nh3"], "nh3")
            
            # Get current timestamp
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Update LED based on gas concentrations
            self.update_led(no2_ppm, co_ppm, nh3_ppm)
            
            # Create data dictionary
            data = {
                "sensor": self.sensor_name,
                "timestamp": current_time,
                "raw": {
                    "oxidising": readings.oxidising,
                    "reducing": readings.reducing,
                    "nh3": readings.nh3
                },
                "ppm": {
                    "no2": no2_ppm,
                    "co": co_ppm,
                    "nh3": nh3_ppm
                }
            }
            
            # Update last valid reading
            self.last_valid_reading = data
            return data
            
        except Exception as e:
            self.log_error(f"Error reading: {e}")
            self.initialized = False
            return self.last_valid_reading

    def cleanup(self) -> None:
        """Clean up resources and properly shutdown the sensor"""
        if not MICS6814_AVAILABLE:
            return
            
        try:
            if self.gas:
                # Turn off LED before exiting
                self.gas.set_led(0, 0, 0)
                # Turn off heater to save power
                self.gas.set_heater(False)
            self.initialized = False
            self.connected = False
            self.log_info("Sensor resources cleaned up")
        except Exception as e:
            self.log_error(f"Cleanup error: {e}")
