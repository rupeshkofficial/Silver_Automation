import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import threading
import pytz

# Page configuration
st.set_page_config(
    page_title="NSE Silver Option Chain Monitor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main > div {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1e3c72, #2a5298);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 600;
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
    }
    
    .status-success {
        color: #28a745;
        font-weight: bold;
    }
    
    .status-warning {
        color: #ffc107;
        font-weight: bold;
    }
    
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
        background-color: #f0f2f6;
        border-radius: 8px 8px 0px 0px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #2a5298;
        color: white;
    }
    
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    .auto-refresh-status {
        position: fixed;
        top: 10px;
        right: 10px;
        background: rgba(42, 82, 152, 0.9);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.8rem;
        z-index: 1000;
    }
    </style>
""", unsafe_allow_html=True)

class NSEOptionChainStreamlit:
    def __init__(self):
        """Initialize the NSE Option Chain Monitor"""
        # Configuration
        self.commodity_symbol = "SILVER"
        self.wait_timeout = 20
        self.strike_file_path = "/Users/rupeshk/Desktop/Aa_Code/Silver_Automation/SilverStrikes.txt"
        
        # Initialize session state
        self._initialize_session_state()
        
        # Load data from session state
        self.ce_strikes = st.session_state.ce_strikes
        self.pe_strikes = st.session_state.pe_strikes
        self.driver = None
        self.wait = None
        self.driver_lock = threading.Lock()
    
    def _initialize_session_state(self):
        """Initialize all session state variables"""
        defaults = {
            'option_data': {},
            'last_fetch_time': None,
            'auto_refresh': False,
            'strikes_loaded': False,
            'ce_strikes': [],
            'pe_strikes': [],
            'selected_file_path': self.strike_file_path,
            'refresh_counter': 0,
            'selected_expiry_date': None,
            'available_expiry_dates': [],
            'refresh_interval': 300,  # 5 minutes in seconds
            'next_refresh_time': None,
            'is_fetching': False,
            'last_page_refresh': None,
            'driver_initialized': False
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def setup_driver_once(self):
        """Setup Chrome WebDriver only once and reuse it"""
        with self.driver_lock:
            if st.session_state.driver_initialized and self.driver:
                return True
                
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-logging")
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--silent")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--window-size=1920,1080")
            
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                self.wait = WebDriverWait(self.driver, self.wait_timeout)
                st.session_state.driver_initialized = True
                return True
            except Exception as e:
                st.error(f"Failed to setup WebDriver: {e}")
                return False
    
    def close_driver(self):
        """Close the WebDriver if it exists"""
        with self.driver_lock:
            if self.driver:
                try:
                    self.driver.quit()
                    self.driver = None
                    st.session_state.driver_initialized = False
                except:
                    pass
    
    def load_strikes_from_file(self, file_path=None):
        """Load CE and PE strikes from the specified file"""
        try:
            file_path = file_path or st.session_state.selected_file_path
            
            if not os.path.exists(file_path):
                st.error(f"❌ Strike file not found: {file_path}")
                return False
            
            with open(file_path, 'r') as file:
                content = file.read()
            
            # Parse CE strikes
            ce_patterns = [
                r"CE\s+STRIKE\s*=\s*\[(.*?)\]",
                r"CE[_ ]STRIKES?\s*=\s*\[(.*?)\]",
                r"ce\s+strike\s*=\s*\[(.*?)\]",
                r"ce[_ ]strikes?\s*=\s*\[(.*?)\]"
            ]
            
            ce_found = self._extract_strikes(content, ce_patterns, 'ce_strikes')
            pe_patterns = [
                r"PE\s+STRIKE\s*=\s*\[(.*?)\]",
                r"PE[_ ]STRIKES?\s*=\s*\[(.*?)\]",
                r"pe\s+strike\s*=\s*\[(.*?)\]",
                r"pe[_ ]strikes?\s*=\s*\[(.*?)\]"
            ]
            
            pe_found = self._extract_strikes(content, pe_patterns, 'pe_strikes')
            
            if not ce_found or not pe_found:
                if not ce_found:
                    st.error("❌ Could not find CE STRIKE data in file")
                if not pe_found:
                    st.error("❌ Could not find PE STRIKE data in file")
                return False
            
            # Update instance variables and session state
            self.ce_strikes = st.session_state.ce_strikes
            self.pe_strikes = st.session_state.pe_strikes
            st.session_state.strikes_loaded = True
            
            st.success(f"✅ Successfully loaded {len(st.session_state.ce_strikes)} CE strikes and {len(st.session_state.pe_strikes)} PE strikes!")
            return True
            
        except Exception as e:
            st.error(f"❌ Error loading strikes from file: {e}")
            return False
    
    def _extract_strikes(self, content, patterns, session_key):
        """Extract strikes using regex patterns"""
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                data = match.group(1)
                strikes_raw = re.findall(r"['\"]([^'\"]+)['\"]", data)
                
                if strikes_raw:
                    st.session_state[session_key] = []
                    for strike in strikes_raw:
                        if not strike.endswith('.00'):
                            st.session_state[session_key].append(strike + '.00')
                        else:
                            st.session_state[session_key].append(strike)
                    return True
        return False
    
    def find_matching_strike(self, target_strike, available_strikes):
        """Find matching strike from available strikes on website"""
        # First try exact match
        if target_strike in available_strikes:
            return target_strike
        
        # Try fuzzy matching with different formats
        target_clean = target_strike.replace(',', '').replace('.00', '')
        
        for strike in available_strikes:
            strike_clean = strike.replace(',', '').replace('.00', '')
            if target_clean == strike_clean:
                return strike
        
        # Try partial matching (last 5 digits for silver strikes)
        if len(target_clean) >= 5:
            target_last5 = target_clean[-5:]
            
            for strike in available_strikes:
                strike_clean = strike.replace(',', '').replace('.00', '')
                if len(strike_clean) >= 5:
                    strike_last5 = strike_clean[-5:]
                    if target_last5 == strike_last5:
                        return strike
        
        return None
    
    def format_strike_for_display(self, strike):
        """Format strike price for display"""
        try:
            cleaned = strike.replace(".00", "").replace(",", "")
            return f"{int(cleaned):,}"
        except:
            return strike
    
    def navigate_and_setup(self):
        """Navigate to NSE and setup commodities page"""
        try:
            self.driver.get("https://www.nseindia.com/option-chain")
            time.sleep(3)
            
            # Click commodities tab
            commodities_tab = self.wait.until(EC.element_to_be_clickable((By.ID, "goldmChain")))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", commodities_tab)
            time.sleep(1)
            
            try:
                commodities_tab.click()
            except:
                self.driver.execute_script("arguments[0].click();", commodities_tab)
            
            time.sleep(2)
            return True
        except Exception as e:
            st.error(f"Navigation failed: {e}")
            return False
    
    def select_commodity_and_expiry(self):
        """Select commodity and user-selected expiry date"""
        try:
            # Select commodity
            dropdown = self.wait.until(EC.presence_of_element_located((By.ID, "goldmSelect")))
            Select(dropdown).select_by_value(self.commodity_symbol)
            time.sleep(2)
            
            # Select user-chosen expiry
            if st.session_state.selected_expiry_date:
                expiry_dropdown = self.wait.until(EC.presence_of_element_located((By.ID, "goldmExpirySelect")))
                select_expiry = Select(expiry_dropdown)
                select_expiry.select_by_value(st.session_state.selected_expiry_date)
                time.sleep(2)
                return True
            else:
                # Fallback to nearest expiry if no selection
                selected_expiry = self._select_nearest_expiry()
                st.session_state.selected_expiry_date = selected_expiry
                time.sleep(2)
                return True
        except Exception as e:
            st.error(f"Commodity/Expiry selection failed: {e}")
            return False
    
    def _select_nearest_expiry(self):
        """Select the nearest (first) expiry date"""
        expiry_selectors = [
            "select[id*='expiry']", "select[id*='Expiry']", 
            "#goldmExpirySelect", "select:nth-of-type(2)"
        ]
        
        for selector in expiry_selectors:
            try:
                expiry_dropdown = self.driver.find_element(By.CSS_SELECTOR, selector)
                select_expiry = Select(expiry_dropdown)
                options = select_expiry.options[1:] if len(select_expiry.options) > 1 else select_expiry.options
                
                if options:
                    nearest_expiry = options[0]
                    nearest_expiry.click()
                    return nearest_expiry.text or nearest_expiry.get_attribute("value")
                    
            except Exception:
                continue
        
        raise Exception("Could not find or select nearest expiry")
    
    def fetch_available_expiry_dates(self):
        """Fetch available expiry dates from NSE website - optimized version"""
        try:
            if not self.setup_driver_once():
                return False
            
            if not self.navigate_and_setup():
                return False
            
            # Select commodity first to load expiry options
            dropdown = self.wait.until(EC.presence_of_element_located((By.ID, "goldmSelect")))
            Select(dropdown).select_by_value(self.commodity_symbol)
            time.sleep(2)
            
            # Get expiry dropdown options
            expiry_dropdown = self.wait.until(EC.presence_of_element_located((By.ID, "goldmExpirySelect")))
            select_expiry = Select(expiry_dropdown)
            
            # Extract all expiry options (skip first "Select" option)
            expiry_dates = []
            for option in select_expiry.options[1:]:  # Skip first "Select" option
                expiry_value = option.get_attribute("value")
                if expiry_value:
                    expiry_dates.append(expiry_value)
            
            if expiry_dates:
                st.session_state.available_expiry_dates = expiry_dates
                # Set first expiry as default if none selected
                if not st.session_state.selected_expiry_date:
                    st.session_state.selected_expiry_date = expiry_dates[0]
                return True
            else:
                st.error("No expiry dates found")
                return False
                
        except Exception as e:
            st.error(f"Error fetching expiry dates: {e}")
            return False
    
    def wait_for_data(self):
        """Wait for option chain data to load"""
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table, .option-chain-table, [class*='option']")))
            time.sleep(2)
            return True
        except Exception as e:
            st.error(f"Data loading timeout: {e}")
            return False
    
    def safe_get_text(self, cell):
        """Safely extract text from cell"""
        try:
            text = cell.text.strip()
            return text if text and text != "-" else "NA"
        except:
            return "NA"
    
    def extract_option_data(self):
        """Extract option chain data for all available strikes - optimized"""
        try:
            table = self.driver.find_element(By.ID, "optionChainTable-goldm")
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            all_strikes_data = {}
            
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 21:
                    strike_text = self.safe_get_text(cells[10])
                    if strike_text != "NA" and "," in strike_text:
                        strike_data = {
                            'Strike': strike_text,
                            'CE_Volume': self.safe_get_text(cells[2]),
                            'CE_Bid_Qty': self.safe_get_text(cells[6]),
                            'CE_Bid': self.safe_get_text(cells[7]),
                            'CE_Ask': self.safe_get_text(cells[8]),
                            'CE_Ask_Qty': self.safe_get_text(cells[9]),
                            'PE_Bid_Qty': self.safe_get_text(cells[11]),
                            'PE_Bid': self.safe_get_text(cells[12]),
                            'PE_Ask': self.safe_get_text(cells[13]),
                            'PE_Ask_Qty': self.safe_get_text(cells[14]),
                            'PE_Volume': self.safe_get_text(cells[18])
                        }
                        all_strikes_data[strike_text] = strike_data
            
            return all_strikes_data
            
        except Exception as e:
            st.error(f"Error extracting data: {e}")
            return {}
    
    def fetch_data(self):
        """Main data fetching function - optimized"""
        if not st.session_state.strikes_loaded:
            st.error("❌ Please load strikes first!")
            return False
        
        # Set fetching flag
        st.session_state.is_fetching = True
        
        with st.spinner("🔄 Fetching option chain data..."):
            try:
                if not self.setup_driver_once():
                    return False
                
                if not self.select_commodity_and_expiry():
                    return False
                
                if not self.wait_for_data():
                    return False
                
                # Extract data
                all_data = self.extract_option_data()
                
                if all_data:
                    # Use UTC time to avoid timezone issues
                    current_time = datetime.now(pytz.UTC)
                    st.session_state.option_data = all_data
                    st.session_state.last_fetch_time = current_time
                    st.session_state.refresh_counter += 1
                    
                    # Set next refresh time
                    if st.session_state.auto_refresh:
                        st.session_state.next_refresh_time = current_time + timedelta(seconds=st.session_state.refresh_interval)
                    
                    st.success("✅ Data fetched successfully!")
                    return True
                else:
                    st.error("❌ No data retrieved")
                    return False
                    
            except Exception as e:
                st.error(f"❌ Data fetch failed: {e}")
                return False
            finally:
                st.session_state.is_fetching = False
    
    def get_time_info(self):
        """Get time information for display - fixed timezone handling"""
        # Use UTC time consistently
        current_time = datetime.now(pytz.UTC)
        
        if not st.session_state.last_fetch_time:
            return {
                'last_update': 'Never',
                'current_time': current_time.astimezone(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S'),
                'time_ago': 'No data fetched yet',
                'minutes_ago': 0,
                'seconds_until_refresh': 0,
                'progress': 0,
                'should_refresh': False
            }
        
        # Ensure last_fetch_time is timezone-aware
        if st.session_state.last_fetch_time.tzinfo is None:
            last_fetch_time = st.session_state.last_fetch_time.replace(tzinfo=pytz.UTC)
        else:
            last_fetch_time = st.session_state.last_fetch_time
        
        time_diff = current_time - last_fetch_time
        total_seconds = int(time_diff.total_seconds())
        minutes_ago = total_seconds // 60
        seconds_ago = total_seconds % 60
        
        # Calculate refresh timing
        should_refresh = False
        seconds_until_refresh = 0
        progress = 0
        
        if st.session_state.auto_refresh:
            if st.session_state.next_refresh_time:
                # Ensure next_refresh_time is timezone-aware
                if st.session_state.next_refresh_time.tzinfo is None:
                    next_refresh_time = st.session_state.next_refresh_time.replace(tzinfo=pytz.UTC)
                else:
                    next_refresh_time = st.session_state.next_refresh_time
                
                time_until_refresh = next_refresh_time - current_time
                seconds_until_refresh = max(0, int(time_until_refresh.total_seconds()))
                should_refresh = seconds_until_refresh <= 0 and not st.session_state.is_fetching
                progress = min(1.0, (st.session_state.refresh_interval - seconds_until_refresh) / st.session_state.refresh_interval)
            else:
                should_refresh = total_seconds >= st.session_state.refresh_interval and not st.session_state.is_fetching
                progress = min(1.0, total_seconds / st.session_state.refresh_interval)
        
        # Format time ago string
        if minutes_ago == 0:
            time_ago = f"{seconds_ago} seconds ago"
        elif minutes_ago == 1:
            time_ago = f"1 minute {seconds_ago} seconds ago"
        else:
            time_ago = f"{minutes_ago} minutes ago"
        
        # Convert to IST for display
        last_update_ist = last_fetch_time.astimezone(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')
        current_time_ist = current_time.astimezone(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')
        
        return {
            'last_update': last_update_ist,
            'current_time': current_time_ist,
            'time_ago': time_ago,
            'minutes_ago': minutes_ago,
            'seconds_until_refresh': seconds_until_refresh,
            'progress': progress,
            'should_refresh': should_refresh
        }
    
    def render_sidebar(self):
        """Render the sidebar configuration"""
        with st.sidebar:
            st.header("⚙️ Configuration")
            
            # Step 1: Expiry Date Section (FIRST)
            st.header("📅 Step 1: Expiry Selection")
            
            # Fetch expiry dates button
            if st.button("🔍 Fetch Available Expiry Dates", use_container_width=True, type="primary"):
                with st.spinner("Fetching available expiry dates from NSE..."):
                    success = self.fetch_available_expiry_dates()
                    if success:
                        st.success(f"✅ Found {len(st.session_state.available_expiry_dates)} expiry dates")
                        st.rerun()
                    else:
                        st.error("❌ Failed to fetch expiry dates")
            
            # Show available expiry dates and selection
            if st.session_state.available_expiry_dates:
                st.info(f"📋 Available: {len(st.session_state.available_expiry_dates)} expiry dates")
                
                # Expiry date selection dropdown
                st.session_state.selected_expiry_date = st.selectbox(
                    "📅 Select Expiry Date",
                    options=st.session_state.available_expiry_dates,
                    index=st.session_state.available_expiry_dates.index(st.session_state.selected_expiry_date) 
                        if st.session_state.selected_expiry_date in st.session_state.available_expiry_dates else 0,
                    help="Select the expiry date for monitoring option data"
                )
                
                st.success(f"📅 Selected: {st.session_state.selected_expiry_date}")
            else:
                st.warning("⚠️ Please fetch expiry dates first")
            
            st.divider()
            
            # Step 2: Strike File Section (SECOND)
            st.header("📁 Step 2: Strike File")
            
            # File upload or path input
            uploaded_file = st.file_uploader(
                "📁 Upload Strike File", 
                type=['txt'], 
                help="Upload a text file containing CE STRIKE and PE STRIKE data"
            )
            
            if uploaded_file is not None:
                temp_path = f"/tmp/{uploaded_file.name}"
                try:
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.session_state.selected_file_path = temp_path
                    st.success(f"✅ File uploaded: {uploaded_file.name}")
                except Exception as e:
                    st.error(f"❌ Failed to upload file: {e}")
            else:
                st.session_state.selected_file_path = st.text_input(
                    "📂 Strike File Path", 
                    value=st.session_state.selected_file_path,
                    help="Path to the file containing CE STRIKE and PE STRIKE data"
                )
            
            # Load strikes button - disabled if no expiry selected
            load_disabled = not st.session_state.selected_expiry_date
            if st.button("📁 Load Strikes", type="secondary", use_container_width=True, disabled=load_disabled):
                if st.session_state.selected_expiry_date:
                    success = self.load_strikes_from_file()
                    if success:
                        st.rerun()
                else:
                    st.warning("⚠️ Please select expiry date first!")
            
            # Show loaded strikes status
            if st.session_state.strikes_loaded:
                st.success(f"✅ Strikes loaded: {len(st.session_state.ce_strikes)} CE, {len(st.session_state.pe_strikes)} PE")
            
            st.divider()
            
            # Step 3: Auto-refresh settings (THIRD)
            st.header("🔄 Step 3: Data Refresh")
            
            st.session_state.auto_refresh = st.checkbox(
                "Enable Auto Refresh (5 min)", 
                value=st.session_state.auto_refresh
            )
            
            # Refresh button - only enabled if both expiry and strikes are ready
            refresh_disabled = not (st.session_state.strikes_loaded and st.session_state.selected_expiry_date)
            
            if st.button("🔄 Refresh Now", type="secondary", use_container_width=True, disabled=refresh_disabled):
                if st.session_state.strikes_loaded and st.session_state.selected_expiry_date:
                    success = self.fetch_data()
                    if success:
                        st.rerun()
                else:
                    if not st.session_state.selected_expiry_date:
                        st.warning("⚠️ Please select expiry date first!")
                    elif not st.session_state.strikes_loaded:
                        st.warning("⚠️ Please load strikes first!")
            
            st.divider()
            
            # Status information with real-time updates
            st.header("📊 Status")
            
            # Create placeholders for dynamic content
            time_info = self.get_time_info()
            
            # Current time display
            current_time_placeholder = st.empty()
            current_time_placeholder.write(f"**Current Time:** {time_info['current_time']}")
            
            st.write(f"**Last Update:** {time_info['last_update']}")
            st.write(f"**Updated:** {time_info['time_ago']}")
            
            if st.session_state.auto_refresh and st.session_state.last_fetch_time:
                if time_info['seconds_until_refresh'] > 0:
                    minutes_left = time_info['seconds_until_refresh'] // 60
                    seconds_left = time_info['seconds_until_refresh'] % 60
                    st.write(f"**Next Refresh:** {minutes_left}:{seconds_left:02d}")
                    st.progress(time_info['progress'])
                    st.write(f"**Status:** ⏰ Auto-refresh in {minutes_left}:{seconds_left:02d}")
                else:
                    st.write("**Status:** 🔄 Refreshing soon...")
                    st.progress(1.0)
            else:
                st.write("**Status:** 📊 Manual refresh mode")
            
            st.caption(f"Refresh count: {st.session_state.refresh_counter}")


    def create_summary_metrics(self, filtered_data):
        """Create summary metrics"""
        ce_data = filtered_data[filtered_data['Type'] == 'CE']
        pe_data = filtered_data[filtered_data['Type'] == 'PE']
        
        # Calculate metrics
        ce_bid_ask_available = len(ce_data[(ce_data['Bid'] != 'NA') & (ce_data['Ask'] != 'NA')])
        pe_bid_ask_available = len(pe_data[(pe_data['Bid'] != 'NA') & (pe_data['Ask'] != 'NA')])
        
        ce_volume_present = len(ce_data[ce_data['Volume'] != 'NA'])
        pe_volume_present = len(pe_data[pe_data['Volume'] != 'NA'])
        
        total_ce = len(ce_data)
        total_pe = len(pe_data)
        
        return {
            'ce_bid_ask_pct': (ce_bid_ask_available / total_ce * 100) if total_ce > 0 else 0,
            'pe_bid_ask_pct': (pe_bid_ask_available / total_pe * 100) if total_pe > 0 else 0,
            'ce_volume_pct': (ce_volume_present / total_ce * 100) if total_ce > 0 else 0,
            'pe_volume_pct': (pe_volume_present / total_pe * 100) if total_pe > 0 else 0,
            'total_strikes': total_ce + total_pe
        }
    
    def prepare_display_data(self):
        """Prepare data for display"""
        all_data = st.session_state.option_data
        display_data = []
        matches_found = 0
        
        # Process CE strikes
        for strike in st.session_state.ce_strikes:
            matching_strike = self.find_matching_strike(strike, all_data.keys())
            
            if matching_strike:
                data = all_data[matching_strike]
                display_data.append({
                    'Strike': self.format_strike_for_display(strike),
                    'Type': 'CE',
                    'Volume': data['CE_Volume'],
                    'Bid_Qty': data['CE_Bid_Qty'],
                    'Bid': data['CE_Bid'],
                    'Ask': data['CE_Ask'],
                    'Ask_Qty': data['CE_Ask_Qty'],
                    'Match_Status': 'Found' if matching_strike == strike else f'Matched to {matching_strike}'
                })
                matches_found += 1
            else:
                display_data.append({
                    'Strike': self.format_strike_for_display(strike),
                    'Type': 'CE',
                    'Volume': 'NA',
                    'Bid_Qty': 'NA',
                    'Bid': 'NA',
                    'Ask': 'NA',
                    'Ask_Qty': 'NA',
                    'Match_Status': 'Not Found'
                })
        
        # Process PE strikes
        for strike in st.session_state.pe_strikes:
            matching_strike = self.find_matching_strike(strike, all_data.keys())
            
            if matching_strike:
                data = all_data[matching_strike]
                display_data.append({
                    'Strike': self.format_strike_for_display(strike),
                    'Type': 'PE',
                    'Volume': data['PE_Volume'],
                    'Bid_Qty': data['PE_Bid_Qty'],
                    'Bid': data['PE_Bid'],
                    'Ask': data['PE_Ask'],
                    'Ask_Qty': data['PE_Ask_Qty'],
                    'Match_Status': 'Found' if matching_strike == strike else f'Matched to {matching_strike}'
                })
                matches_found += 1
            else:
                display_data.append({
                    'Strike': self.format_strike_for_display(strike),
                    'Type': 'PE',
                    'Volume': 'NA',
                    'Bid_Qty': 'NA',
                    'Bid': 'NA',
                    'Ask': 'NA',
                    'Ask_Qty': 'NA',
                    'Match_Status': 'Not Found'
                })
        
        return display_data, matches_found
    
    def render_data_tables(self, df):
        """Render the data tables"""
        # Show match status summary for not found strikes only
        not_found = df[df['Match_Status'] == 'Not Found']
        if len(not_found) > 0:
            st.warning(f"⚠️ {len(not_found)} strikes not found on website:")
            not_found_strikes = not_found[['Type', 'Strike']].values.tolist()
            for type_val, strike_val in not_found_strikes:
                st.write(f"- {type_val} {strike_val}")
        
        # Split into CE and PE tables
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📞 CE (Call) Options")
            ce_df = df[df['Type'] == 'CE'].drop(['Type', 'Match_Status'], axis=1)
            if len(ce_df) > 0:
                st.dataframe(
                    ce_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Strike": st.column_config.TextColumn("Strike", width="small"),
                        "Volume": st.column_config.TextColumn("Volume", width="small"),
                        "Bid_Qty": st.column_config.TextColumn("Bid Qty", width="small"),
                        "Bid": st.column_config.TextColumn("Bid", width="small"),
                        "Ask": st.column_config.TextColumn("Ask", width="small"),
                        "Ask_Qty": st.column_config.TextColumn("Ask Qty", width="small"),
                    }
                )
            else:
                st.info("No CE data available")
        
        with col2:
            st.subheader("📉 PE (Put) Options")
            pe_df = df[df['Type'] == 'PE'].drop(['Type', 'Match_Status'], axis=1)
            if len(pe_df) > 0:
                st.dataframe(
                    pe_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Strike": st.column_config.TextColumn("Strike", width="small"),
                        "Volume": st.column_config.TextColumn("Volume", width="small"),
                        "Bid_Qty": st.column_config.TextColumn("Bid Qty", width="small"),
                        "Bid": st.column_config.TextColumn("Bid", width="small"),
                        "Ask": st.column_config.TextColumn("Ask", width="small"),
                        "Ask_Qty": st.column_config.TextColumn("Ask Qty", width="small"),
                    }
                )
            else:
                st.info("No PE data available")
    
    def create_charts(self, df):
        """Create visualization charts"""
        try:
            # Create charts with valid data only
            valid_data = df[df['Match_Status'] != 'Not Found']
            if len(valid_data) == 0:
                st.warning("⚠️ No valid data available for charts.")
                return
            
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('Bid/Ask Availability', 'Volume Distribution', 
                              'CE vs PE Comparison', 'Strike Distribution'),
                specs=[[{"type": "bar"}, {"type": "pie"}],
                       [{"type": "bar"}, {"type": "bar"}]]
            )
            
            # Chart 1: Bid/Ask availability
            ce_data = valid_data[valid_data['Type'] == 'CE']
            pe_data = valid_data[valid_data['Type'] == 'PE']
            
            ce_available = len(ce_data[(ce_data['Bid'] != 'NA') & (ce_data['Ask'] != 'NA')])
            pe_available = len(pe_data[(pe_data['Bid'] != 'NA') & (pe_data['Ask'] != 'NA')])
            
            fig.add_trace(
                go.Bar(x=['CE', 'PE'], y=[ce_available, pe_available], 
                       name='Bid/Ask Available', marker_color=['#2a5298', '#e74c3c']),
                row=1, col=1
            )
            
            # Chart 2: Volume distribution
            volume_counts = valid_data['Volume'].value_counts()
            fig.add_trace(
                go.Pie(labels=volume_counts.index, values=volume_counts.values, name="Volume"),
                row=1, col=2
            )
            
            # Chart 3: CE vs PE comparison
            ce_count = len(ce_data)
            pe_count = len(pe_data)
            
            fig.add_trace(
                go.Bar(x=['CE', 'PE'], y=[ce_count, pe_count], 
                       name='Total Strikes', marker_color=['#2a5298', '#e74c3c']),
                row=2, col=1
            )
            
            # Chart 4: Strike distribution (sample)
            sample_strikes = valid_data['Strike'].head(10).tolist()
            fig.add_trace(
                go.Bar(x=sample_strikes, y=[1]*len(sample_strikes), 
                       name='Sample Strikes', marker_color='#27ae60'),
                row=2, col=2
            )
            
            fig.update_layout(height=600, showlegend=False, title_text="Option Chain Analytics")
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error creating charts: {e}")
    
    def generate_text_report(self, df):
        """Generate text report for download"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_lines = []
        
        report_lines.append(f"NSE Silver Option Chain Report")
        report_lines.append(f"Generated: {current_time}")
        report_lines.append("="*70)
        
        # CE data
        report_lines.append("CE (CALL) OPTIONS")
        report_lines.append("-" * 70)
        report_lines.append(f"{'Strike':<12} | {'Volume':<8} | {'Bid Qty':<8} | {'Bid':<10} | {'Ask':<10} | {'Ask Qty':<8}")
        report_lines.append("-" * 70)
        
        ce_data = df[df['Type'] == 'CE']
        for _, row in ce_data.iterrows():
            line = f"{row['Strike']:<12} | {row['Volume']:<8} | {row['Bid_Qty']:<8} | {row['Bid']:<10} | {row['Ask']:<10} | {row['Ask_Qty']:<8}"
            report_lines.append(line)
        
        # PE data
        report_lines.append("\n" + "="*70)
        report_lines.append("PE (PUT) OPTIONS")
        report_lines.append("-" * 70)
        report_lines.append(f"{'Strike':<12} | {'Volume':<8} | {'Bid Qty':<8} | {'Bid':<10} | {'Ask':<10} | {'Ask Qty':<8}")
        report_lines.append("-" * 70)
        
        pe_data = df[df['Type'] == 'PE']
        for _, row in pe_data.iterrows():
            line = f"{row['Strike']:<12} | {row['Volume']:<8} | {row['Bid_Qty']:<8} | {row['Bid']:<10} | {row['Ask']:<10} | {row['Ask_Qty']:<8}"
            report_lines.append(line)
        
        # Summary
        report_lines.append("\n" + "="*70)
        report_lines.append("SUMMARY")
        report_lines.append("="*70)
        
        total_strikes = len(df)
        total_with_bid_ask = len(df[(df['Bid'] != 'NA') & (df['Ask'] != 'NA')])
        total_with_volume = len(df[df['Volume'] != 'NA'])
        
        report_lines.append(f"Total Strikes Monitored: {total_strikes}")
        report_lines.append(f"Strikes with Bid/Ask: {total_with_bid_ask}")
        report_lines.append(f"Strikes with Volume: {total_with_volume}")
        
        ce_missing_bid_ask = len(ce_data[(ce_data['Bid'] == 'NA') | (ce_data['Ask'] == 'NA')])
        pe_missing_bid_ask = len(pe_data[(pe_data['Bid'] == 'NA') | (pe_data['Ask'] == 'NA')])
        
        report_lines.append(f"\nCE Bid/Ask Available: {'YES ✅' if ce_missing_bid_ask == 0 else 'NO ❌'}")
        report_lines.append(f"PE Bid/Ask Available: {'YES ✅' if pe_missing_bid_ask == 0 else 'NO ❌'}")
        report_lines.append(f"All Volumes NA: {'YES ✅' if total_with_volume == 0 else 'NO ❌'}")
        
        return '\n'.join(report_lines)
    
    def display_main_content(self):
        """Display the main content area"""
        if not st.session_state.strikes_loaded:
            st.info("📋 **Please load the strikes file first using the sidebar.**")
            st.markdown("### Expected File Format:")
            st.code("""CE STRIKE = ['112,250', '112,750', '113,250']
PE STRIKE = ['113,750', '113,250', '112,750']""")
            return
        
        # Display data if available
        if st.session_state.option_data:
            self.display_option_data()
        else:
            st.info("📊 **Click 'Refresh Now' to fetch the latest option chain data.**")
    
    def display_option_data(self):
        """Display the fetched option chain data"""
        all_data = st.session_state.option_data
        
        if not all_data:
            st.warning("⚠️ No option chain data available.")
            return
        
        # Prepare data for display
        display_data, matches_found = self.prepare_display_data()
        
        if not display_data:
            st.warning("⚠️ No strike data could be processed.")
            return
        
        # Show match summary
        total_strikes = len(st.session_state.ce_strikes) + len(st.session_state.pe_strikes)
        st.info(f"📊 **Match Summary:** {matches_found}/{total_strikes} strikes found on website")
        
        df = pd.DataFrame(display_data)
        
        # Summary metrics
        metrics = self.create_summary_metrics(df)
        
        # Display metrics in columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("CE Bid/Ask Available", f"{metrics['ce_bid_ask_pct']:.1f}%")
        
        with col2:
            st.metric("PE Bid/Ask Available", f"{metrics['pe_bid_ask_pct']:.1f}%")
        
        with col3:
            st.metric("CE Volume Present", f"{metrics['ce_volume_pct']:.1f}%")
        
        with col4:
            st.metric("PE Volume Present", f"{metrics['pe_volume_pct']:.1f}%")
        
        # Expiry date info
        if st.session_state.selected_expiry_date:
            st.info(f"🗓️ **Selected Expiry Date:** {st.session_state.selected_expiry_date}")
        
        # Tabs for different views
        tab1, tab2 = st.tabs(["📊 Data Table", "📈 Charts"])
        
        with tab1:
            self.render_data_tables(df)
        
        with tab2:
            self.create_charts(df)
    
    def render_export_section(self):
        """Render the export/download section"""
        if st.session_state.option_data and st.session_state.strikes_loaded:
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col2:
                display_data, _ = self.prepare_display_data()
                if display_data:
                    df = pd.DataFrame(display_data)
                    report_content = self.generate_text_report(df)
                    
                    st.download_button(
                        label="📄 Download Report",
                        data=report_content,
                        file_name=f"silver_option_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
    
    def render_auto_refresh_status(self):
        """Render floating auto-refresh status"""
        if st.session_state.auto_refresh and st.session_state.last_fetch_time:
            current_time = datetime.now(pytz.UTC)
            
            if st.session_state.next_refresh_time:
                # Ensure next_refresh_time is timezone-aware
                if st.session_state.next_refresh_time.tzinfo is None:
                    next_refresh_time = st.session_state.next_refresh_time.replace(tzinfo=pytz.UTC)
                else:
                    next_refresh_time = st.session_state.next_refresh_time
                
                seconds_left = (next_refresh_time - current_time).total_seconds()
                if seconds_left > 0:
                    minutes = int(seconds_left // 60)
                    seconds = int(seconds_left % 60)
                    progress = 1 - (seconds_left / st.session_state.refresh_interval)
                    
                    st.markdown(
                        f'<div class="auto-refresh-status">⏰ Next refresh in {minutes}:{seconds:02d}</div>',
                        unsafe_allow_html=True
                    )
                    
                    # Update progress bar in sidebar
                    with st.sidebar:
                        st.progress(progress)
                else:
                    st.markdown(
                        '<div class="auto-refresh-status">🔄 Refreshing data...</div>',
                        unsafe_allow_html=True
                    )
    
    def handle_auto_refresh(self):
        """Handle auto-refresh logic"""
        if (st.session_state.auto_refresh and 
            st.session_state.last_fetch_time and 
            st.session_state.strikes_loaded and
            not st.session_state.is_fetching):
            
            current_time = datetime.now(pytz.UTC)
            
            # Initialize next refresh time if not set
            if not st.session_state.next_refresh_time:
                st.session_state.next_refresh_time = current_time + timedelta(seconds=st.session_state.refresh_interval)
            
            # Check if it's time to refresh
            if current_time >= st.session_state.next_refresh_time:
                st.session_state.is_fetching = True
                try:
                    success = self.fetch_data()
                    if success:
                        st.session_state.next_refresh_time = datetime.now(pytz.UTC) + timedelta(seconds=st.session_state.refresh_interval)
                        st.session_state.refresh_counter += 1
                        st.session_state.last_fetch_time = datetime.now(pytz.UTC)
                finally:
                    st.session_state.is_fetching = False
    
    def render_status_footer(self):
        """Render the status footer with real-time updates"""
        if st.session_state.auto_refresh:
            current_time = datetime.now(pytz.UTC)
            
            if st.session_state.last_fetch_time:
                # Ensure last_fetch_time is timezone-aware
                if st.session_state.last_fetch_time.tzinfo is None:
                    last_fetch_time = st.session_state.last_fetch_time.replace(tzinfo=pytz.UTC)
                else:
                    last_fetch_time = st.session_state.last_fetch_time
                
                time_since_update = current_time - last_fetch_time
                minutes = int(time_since_update.total_seconds() // 60)
                seconds = int(time_since_update.total_seconds() % 60)
                
                if st.session_state.next_refresh_time:
                    # Ensure next_refresh_time is timezone-aware
                    if st.session_state.next_refresh_time.tzinfo is None:
                        next_refresh_time = st.session_state.next_refresh_time.replace(tzinfo=pytz.UTC)
                    else:
                        next_refresh_time = st.session_state.next_refresh_time
                    
                    time_until_refresh = next_refresh_time - current_time
                    if time_until_refresh.total_seconds() > 0:
                        refresh_min = int(time_until_refresh.total_seconds() // 60)
                        refresh_sec = int(time_until_refresh.total_seconds() % 60)
                        st.success(f"✅ Auto-refresh enabled | Last update: {minutes}m {seconds}s ago | Next refresh in {refresh_min}m {refresh_sec}s")
                    else:
                        st.warning("🔄 Auto-refresh enabled - Refreshing now...")
                else:
                    st.info(f"⏳ Auto-refresh enabled | Last update: {minutes}m {seconds}s ago")
            else:
                st.info("⏳ Auto-refresh enabled - Waiting for first data fetch...")
            
            st.caption(f"Total refreshes: {st.session_state.refresh_counter}")
    
    def run(self):
        """Main application entry point"""
        # Header
        st.markdown("""
            <div class="main-header">
                <h1>📈 NSE Silver Option Chain Monitor</h1>
                <p>Real-time monitoring with auto-refresh functionality</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Handle auto-refresh
        self.handle_auto_refresh()
        
        # Render floating auto-refresh status
        self.render_auto_refresh_status()
        
        # Render sidebar
        self.render_sidebar()
        
        # Display main content
        self.display_main_content()
        
        # Export functionality
        self.render_export_section()
        
        # Status footer
        self.render_status_footer()
        
        # Force a rerun for real-time updates if auto-refresh is enabled
        if st.session_state.auto_refresh:
            time.sleep(1)  # Small delay to prevent excessive reruns
            st.rerun()

# Main function
def main():
    """Main application function"""
    nse_app = NSEOptionChainStreamlit()
    nse_app.run()

if __name__ == "__main__":
    main()
