import time
import csv
import os
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crash_updater.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OptimizedCrashUpdater:
    def __init__(self, url="https://1xbet.com/en/allgamesentrance/crash", csv_file="1XBetCrash.csv"):
        self.url = url
        self.csv_file = csv_file
        self.driver = None
        self.wait = None
        self.last_multiplier = None
        self.data_buffer = []
        self.buffer_size = 10  # Write to CSV every 10 entries
        
    def _setup_chrome_options(self):
        """Configure optimized Chrome options for performance"""
        chrome_options = Options()
        
        # Performance optimizations
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')  # Don't load images
        chrome_options.add_argument('--disable-javascript')  # Disable JS if not needed
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        
        # Memory optimizations
        chrome_options.add_argument('--memory-pressure-off')
        chrome_options.add_argument('--max_old_space_size=4096')
        
        # Network optimizations
        chrome_options.add_argument('--aggressive-cache-discard')
        chrome_options.add_argument('--disable-background-networking')
        
        # Window size optimization
        chrome_options.add_argument('--window-size=1024,768')
        
        # Additional performance preferences
        prefs = {
            "profile.default_content_setting_values": {
                "images": 2,  # Block images
                "plugins": 2,  # Block plugins
                "popups": 2,  # Block popups
                "geolocation": 2,  # Block location sharing
                "notifications": 2,  # Block notifications
                "media_stream": 2,  # Block media stream
            },
            "profile.managed_default_content_settings": {
                "images": 2
            }
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        return chrome_options
    
    def _initialize_driver(self):
        """Initialize Chrome driver with optimizations"""
        try:
            chrome_options = self._setup_chrome_options()
            service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, timeout=10)
            
            # Set page load timeout
            self.driver.set_page_load_timeout(30)
            
            logger.info("Chrome driver initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver: {e}")
            raise
    
    def _ensure_csv_header(self):
        """Ensure CSV file has proper header"""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['Time', 'Number of players', 'Total bets', 'Multiplier'])
                logger.info(f"Created new CSV file: {self.csv_file}")
    
    def _append_to_csv(self, data_rows):
        """Efficiently append multiple rows to CSV"""
        try:
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerows(data_rows)
            logger.info(f"Appended {len(data_rows)} rows to CSV")
        except Exception as e:
            logger.error(f"Error writing to CSV: {e}")
    
    def _extract_game_data(self):
        """Extract multiplier and related game data efficiently"""
        try:
            # Wait for multiplier element to be present
            multiplier_element = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.c-events-table__multiplier'))
            )
            
            # Wait for element to be visible
            self.wait.until(EC.visibility_of(multiplier_element))
            
            # Extract multiplier value
            multiplier_text = multiplier_element.text.strip()
            if multiplier_text.startswith('x'):
                multiplier = float(multiplier_text[1:])
            else:
                multiplier = float(multiplier_text)
            
            # Only process if it's a new multiplier
            if multiplier == self.last_multiplier:
                return None
                
            self.last_multiplier = multiplier
            
            # Try to extract additional game data (with fallbacks)
            try:
                players_element = self.driver.find_element(By.CSS_SELECTOR, '.players-count')
                players = int(players_element.text.replace(',', ''))
            except:
                players = 0  # Fallback value
            
            try:
                bets_element = self.driver.find_element(By.CSS_SELECTOR, '.total-bets')
                bets_text = bets_element.text.replace(',', '').replace('$', '').replace('€', '')
                total_bets = float(bets_text)
            except:
                total_bets = 0.0  # Fallback value
            
            # Current time
            current_time = datetime.now().strftime('%H:%M')
            
            return [current_time, players, total_bets, multiplier]
            
        except TimeoutException:
            logger.warning("Timeout waiting for multiplier element")
            return None
        except Exception as e:
            logger.error(f"Error extracting game data: {e}")
            return None
    
    def _reconnect_if_needed(self):
        """Reconnect driver if connection is lost"""
        try:
            # Test if driver is still responsive
            self.driver.current_url
        except WebDriverException:
            logger.warning("Driver connection lost, reconnecting...")
            try:
                self.driver.quit()
            except:
                pass
            self._initialize_driver()
            return True
        return False
    
    def start_monitoring(self, max_retries=5):
        """Start monitoring with improved error handling and efficiency"""
        logger.info("Starting crash game monitoring...")
        
        # Initialize driver and CSV
        self._initialize_driver()
        self._ensure_csv_header()
        
        retry_count = 0
        consecutive_errors = 0
        
        try:
            while retry_count < max_retries:
                try:
                    # Navigate to the website
                    logger.info(f"Navigating to: {self.url}")
                    self.driver.get(self.url)
                    
                    # Reset error counters on successful page load
                    consecutive_errors = 0
                    
                    while True:
                        # Extract game data
                        game_data = self._extract_game_data()
                        
                        if game_data:
                            logger.info(f"New data: {game_data}")
                            self.data_buffer.append(game_data)
                            
                            # Write buffer to CSV when full
                            if len(self.data_buffer) >= self.buffer_size:
                                self._append_to_csv(self.data_buffer)
                                self.data_buffer.clear()
                        
                        # Short sleep to prevent excessive CPU usage
                        time.sleep(0.5)
                        
                except TimeoutException:
                    consecutive_errors += 1
                    logger.warning(f"Page load timeout (attempt {consecutive_errors})")
                    
                    if consecutive_errors >= 3:
                        if self._reconnect_if_needed():
                            consecutive_errors = 0
                        else:
                            break
                            
                except WebDriverException as e:
                    logger.error(f"WebDriver error: {e}")
                    self._reconnect_if_needed()
                    retry_count += 1
                    time.sleep(5)  # Wait before retry
                    
                except KeyboardInterrupt:
                    logger.info("Monitoring stopped by user")
                    break
                    
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    retry_count += 1
                    time.sleep(5)
                    
        finally:
            # Write any remaining buffer data
            if self.data_buffer:
                self._append_to_csv(self.data_buffer)
                logger.info(f"Wrote final {len(self.data_buffer)} buffered entries")
            
            # Clean up
            try:
                if self.driver:
                    self.driver.quit()
                    logger.info("Driver closed successfully")
            except Exception as e:
                logger.error(f"Error closing driver: {e}")

def main():
    """Main function with configuration"""
    updater = OptimizedCrashUpdater()
    
    try:
        updater.start_monitoring(max_retries=10)
    except KeyboardInterrupt:
        logger.info("Script terminated by user")
    except Exception as e:
        logger.error(f"Script failed: {e}")
        raise

if __name__ == "__main__":
    main()
