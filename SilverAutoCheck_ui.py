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
from threading import Thread
import pytz

# Page configuration
st.set_page_config(
    page_title="NSE Silver Option Chain Monitor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS (optimized)
st.markdown("""
    <style>
    .main > div { padding: 0.5rem; }
    .main-header {
        background: linear-gradient(135deg, #1e3c72, #2a5298);
        color: white; padding: 1rem; border-radius: 8px;
        text-align: center; margin-bottom: 1rem;
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; }
    .main-header p { margin: 0.3rem 0 0 0; opacity: 0.9; }
    .status-success { color: #28a745; font-weight: bold; }
    .status-error { color: #dc3545; font-weight: bold; }
    .stProgress > div > div > div > div { background-color: #2a5298; }
    .block-container { padding: 0.5rem; }
    </style>
""", unsafe_allow_html=True)

class NSEOptionChainStreamlit:
    def __init__(self):
        """Initialize the NSE Option Chain Monitor"""
        self.commodity_symbol = "SILVER"
        self.wait_timeout = 15  # Reduced timeout
        self.strike_file_path = "/opt/render/project/src/SilverStrikes.txt"  # Updated for Render
        
        # Initialize session state
        self._initialize_session_state()
        
        # Load data from session state
        self.ce_strikes = st.session_state.ce_strikes
        self.pe_strikes = st.session_state.pe_strikes
        self.driver = None
        self.wait = None
    
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
            'refresh_interval': 300,
            'next_refresh_time': None,
            'is_fetching': False,
            'driver_initialized': False,
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def get_ist_time(self):
        """Get current IST time"""
        ist = pytz.timezone('Asia/Kolkata')
        return datetime.now(ist)
    
    def load_strikes_from_file(self, file_path=None):
        """Load CE and PE strikes from the specified file (optimized)"""
        try:
            file_path = file_path or st.session_state.selected_file_path
            
            if not os.path.exists(file_path):
                st.error(f"❌ Strike file not found: {file_path}")
                return False
            
            with open(file_path, 'r') as file:
                content = file.read()
            
            # Simplified regex patterns
            ce_match = re.search(r'CE.*?=.*?\[(.*?)\]', content, re.IGNORECASE | re.DOTALL)
            pe_match = re.search(r'PE.*?=.*?\[(.*?)\]', content, re.IGNORECASE | re.DOTALL)
            
            if not ce_match or not pe_match:
                st.error("❌ Could not find CE/PE STRIKE data in file")
                return False
            
            # Extract strikes
            ce_strikes_raw = re.findall(r"['\"]([^'\"]+)['\"]", ce_match.group(1))
            pe_strikes_raw = re.findall(r"['\"]([^'\"]+)['\"]", pe_match.group(1))
            
            # Process strikes
            st.session_state.ce_strikes = [s + '.00' if not s.endswith('.00') else s for s in ce_strikes_raw]
            st.session_state.pe_strikes = [s + '.00' if not s.endswith('.00') else s for s in pe_strikes_raw]
            
            self.ce_strikes = st.session_state.ce_strikes
            self.pe_strikes = st.session_state.pe_strikes
            st.session_state.strikes_loaded = True
            
            st.success(f"✅ Loaded {len(st.session_state.ce_strikes)} CE + {len(st.session_state.pe_strikes)} PE strikes!")
            return True
            
        except Exception as e:
            st.error(f"❌ Error loading strikes: {e}")
            return False
    
    def setup_driver(self):
        """Setup Chrome WebDriver with optimized options for Render"""
        if st.session_state.driver_initialized:
            return True
            
        chrome_options = Options()
        
        # Render-specific optimizations
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--disable-javascript")  # Disable JS if not needed
        chrome_options.add_argument("--disable-css")  # Disable CSS loading
        chrome_options.add_argument("--memory-pressure-off")
        chrome_options.add_argument("--aggressive-cache-discard")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-client-side-phishing-detection")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Linux; Chrome/91.0)")
        
        # Set window size smaller for faster rendering
        chrome_options.add_argument("--window-size=1024,768")
        
        try:
            # Use chromedriver from PATH (installed via build.sh)
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, self.wait_timeout)
            st.session_state.driver_initialized = True
            return True
        except Exception as e:
            st.error(f"Failed to setup WebDriver: {e}")
            return False
    
    def navigate_and_setup(self):
        """Navigate to NSE and setup commodities page (optimized)"""
        try:
            # Use direct URL for faster access
            self.driver.get("https://www.nseindia.com/option-chain")
            
            # Reduced wait times
            time.sleep(2)
            
            # Click commodities tab with retry
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    commodities_tab = self.wait.until(EC.element_to_be_clickable((By.ID, "goldmChain")))
                    self.driver.execute_script("arguments[0].click();", commodities_tab)
                    time.sleep(1)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(1)
            
            return True
        except Exception as e:
            st.error(f"Navigation failed: {e}")
            return False
    
    def select_commodity_and_expiry(self):
        """Select commodity and expiry (optimized)"""
        try:
            # Select commodity with shorter wait
            dropdown = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "goldmSelect"))
            )
            Select(dropdown).select_by_value(self.commodity_symbol)
            time.sleep(1)
            
            # Select expiry
            if st.session_state.selected_expiry_date:
                expiry_dropdown = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "goldmExpirySelect"))
                )
                Select(expiry_dropdown).select_by_value(st.session_state.selected_expiry_date)
                time.sleep(1)
                return True
            else:
                # Select first available expiry
                expiry_dropdown = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "goldmExpirySelect"))
                )
                select_expiry = Select(expiry_dropdown)
                if len(select_expiry.options) > 1:
                    select_expiry.select_by_index(1)  # Select first non-default option
                    st.session_state.selected_expiry_date = select_expiry.options[1].get_attribute("value")
                time.sleep(1)
                return True
                
        except Exception as e:
            st.error(f"Selection failed: {e}")
            return False
    
    def fetch_available_expiry_dates(self):
        """Fetch available expiry dates (optimized with threading)"""
        def fetch_expiry_thread():
            try:
                if not self.setup_driver():
                    return False
                
                if not self.navigate_and_setup():
                    return False
                
                # Select commodity first
                dropdown = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "goldmSelect"))
                )
                Select(dropdown).select_by_value(self.commodity_symbol)
                time.sleep(1)
                
                # Get expiry options
                expiry_dropdown = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "goldmExpirySelect"))
                )
                select_expiry = Select(expiry_dropdown)
                
                expiry_dates = []
                for option in select_expiry.options[1:]:  # Skip first "Select" option
                    expiry_value = option.get_attribute("value")
                    if expiry_value:
                        expiry_dates.append(expiry_value)
                
                if expiry_dates:
                    st.session_state.available_expiry_dates = expiry_dates
                    if not st.session_state.selected_expiry_date:
                        st.session_state.selected_expiry_date = expiry_dates[0]
                    st.session_state.expiry_fetch_success = True
                else:
                    st.session_state.expiry_fetch_success = False
                    
            except Exception as e:
                st.session_state.expiry_fetch_error = str(e)
                st.session_state.expiry_fetch_success = False
            finally:
                if self.driver:
                    try:
                        self.driver.quit()
                        st.session_state.driver_initialized = False
                    except:
                        pass
        
        # Initialize status variables
        st.session_state.expiry_fetch_success = None
        st.session_state.expiry_fetch_error = None
        
        # Run in separate thread for better UI responsiveness
        thread = Thread(target=fetch_expiry_thread)
        thread.start()
        
        # Show progress while waiting
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i in range(20):  # 10 seconds maximum wait
            if st.session_state.expiry_fetch_success is not None:
                break
            progress_bar.progress((i + 1) / 20)
            status_text.text(f"Fetching expiry dates... {i+1}/20")
            time.sleep(0.5)
        
        thread.join(timeout=5)  # Wait max 5 more seconds
        
        progress_bar.empty()
        status_text.empty()
        
        if st.session_state.expiry_fetch_success:
            return True
        else:
            error_msg = getattr(st.session_state, 'expiry_fetch_error', 'Unknown error')
            st.error(f"Failed to fetch expiry dates: {error_msg}")
            return False
    
    def extract_option_data(self):
        """Extract option chain data (optimized)"""
        try:
            # Use faster element location
            table = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "optionChainTable-goldm"))
            )
            
            # Get all rows at once
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            all_strikes_data = {}
            
            # Process rows in batches for better performance
            for row in rows[1:]:  # Skip header row
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 21:
                    try:
                        strike_text = cells[10].text.strip()
                        if strike_text and strike_text != "-" and "," in strike_text:
                            # Extract data more efficiently
                            strike_data = {
                                'Strike': strike_text,
                                'CE_Volume': cells[2].text.strip() or "NA",
                                'CE_Bid_Qty': cells[6].text.strip() or "NA",
                                'CE_Bid': cells[7].text.strip() or "NA",
                                'CE_Ask': cells[8].text.strip() or "NA",
                                'CE_Ask_Qty': cells[9].text.strip() or "NA",
                                'PE_Bid_Qty': cells[11].text.strip() or "NA",
                                'PE_Bid': cells[12].text.strip() or "NA",
                                'PE_Ask': cells[13].text.strip() or "NA",
                                'PE_Ask_Qty': cells[14].text.strip() or "NA",
                                'PE_Volume': cells[18].text.strip() or "NA"
                            }
                            all_strikes_data[strike_text] = strike_data
                    except:
                        continue  # Skip problematic rows
            
            return all_strikes_data
            
        except Exception as e:
            st.error(f"Error extracting data: {e}")
            return {}
    
    def fetch_data(self):
        """Main data fetching function (optimized)"""
        if not st.session_state.strikes_loaded:
            st.error("❌ Please load strikes first!")
            return False
        
        st.session_state.is_fetching = True
        
        with st.spinner("🔄 Fetching data..."):
            try:
                if not self.setup_driver():
                    return False
                
                if not self.navigate_and_setup():
                    return False
                
                if not self.select_commodity_and_expiry():
                    return False
                
                # Wait for data with shorter timeout
                WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
                )
                time.sleep(2)  # Reduced wait time
                
                # Extract data
                all_data = self.extract_option_data()
                
                if all_data:
                    current_time = self.get_ist_time()
                    st.session_state.option_data = all_data
                    st.session_state.last_fetch_time = current_time
                    st.session_state.refresh_counter += 1
                    
                    if st.session_state.auto_refresh:
                        st.session_state.next_refresh_time = current_time + timedelta(seconds=st.session_state.refresh_interval)
                    
                    st.success("✅ Data fetched successfully!")
                    return True
                else:
                    st.error("❌ No data retrieved")
                    return False
                    
            except Exception as e:
                st.error(f"❌ Fetch failed: {e}")
                return False
            finally:
                st.session_state.is_fetching = False
                if self.driver:
                    try:
                        self.driver.quit()
                        st.session_state.driver_initialized = False
                    except:
                        pass
    
    def get_time_info(self):
        """Get time information for display (using IST)"""
        current_time = self.get_ist_time()
        
        if not st.session_state.last_fetch_time:
            return {
                'last_update': 'Never',
                'current_time': current_time.strftime('%H:%M:%S'),
                'time_ago': 'No data fetched yet',
                'minutes_ago': 0,
                'seconds_until_refresh': 0,
                'progress': 0,
                'should_refresh': False
            }
        
        # Convert to IST if needed
        last_fetch = st.session_state.last_fetch_time
        if last_fetch.tzinfo is None:
            ist = pytz.timezone('Asia/Kolkata')
            last_fetch = ist.localize(last_fetch)
        
        time_diff = current_time - last_fetch
        total_seconds = int(time_diff.total_seconds())
        minutes_ago = total_seconds // 60
        seconds_ago = total_seconds % 60
        
        # Calculate refresh timing
        should_refresh = False
        seconds_until_refresh = 0
        progress = 0
        
        if st.session_state.auto_refresh:
            if st.session_state.next_refresh_time:
                next_refresh = st.session_state.next_refresh_time
                if next_refresh.tzinfo is None:
                    ist = pytz.timezone('Asia/Kolkata')
                    next_refresh = ist.localize(next_refresh)
                
                time_until_refresh = next_refresh - current_time
                seconds_until_refresh = max(0, int(time_until_refresh.total_seconds()))
                should_refresh = seconds_until_refresh <= 0 and not st.session_state.is_fetching
                progress = min(1.0, (st.session_state.refresh_interval - seconds_until_refresh) / st.session_state.refresh_interval)
            else:
                should_refresh = total_seconds >= st.session_state.refresh_interval and not st.session_state.is_fetching
                progress = min(1.0, total_seconds / st.session_state.refresh_interval)
        
        # Format time ago string
        if minutes_ago == 0:
            time_ago = f"{seconds_ago} seconds ago"
        else:
            time_ago = f"{minutes_ago}m {seconds_ago}s ago"
        
        return {
            'last_update': last_fetch.strftime('%H:%M:%S'),
            'current_time': current_time.strftime('%H:%M:%S'),
            'time_ago': time_ago,
            'minutes_ago': minutes_ago,
            'seconds_until_refresh': seconds_until_refresh,
            'progress': progress,
            'should_refresh': should_refresh
        }
    
    def find_matching_strike(self, target_strike, available_strikes):
        """Find matching strike (optimized)"""
        # Direct match first
        if target_strike in available_strikes:
            return target_strike
        
        # Clean and compare
        target_clean = target_strike.replace(',', '').replace('.00', '')
        
        for strike in available_strikes:
            strike_clean = strike.replace(',', '').replace('.00', '')
            if target_clean == strike_clean:
                return strike
        
        return None
    
    def format_strike_for_display(self, strike):
        """Format strike price for display"""
        try:
            cleaned = strike.replace(".00", "").replace(",", "")
            return f"{int(cleaned):,}"
        except:
            return strike
    
    def render_sidebar(self):
        """Render the sidebar configuration (optimized)"""
        with st.sidebar:
            st.header("⚙️ Configuration")
            
            # Step 1: Expiry Date Section
            st.subheader("📅 Step 1: Expiry Selection")
            
            if st.button("🔍 Fetch Expiry Dates", use_container_width=True, type="primary"):
                success = self.fetch_available_expiry_dates()
                if success:
                    st.success(f"✅ Found {len(st.session_state.available_expiry_dates)} dates")
                    st.rerun()
            
            if st.session_state.available_expiry_dates:
                st.session_state.selected_expiry_date = st.selectbox(
                    "📅 Select Expiry",
                    options=st.session_state.available_expiry_dates,
                    index=st.session_state.available_expiry_dates.index(st.session_state.selected_expiry_date) 
                        if st.session_state.selected_expiry_date in st.session_state.available_expiry_dates else 0
                )
                st.success(f"📅 Selected: {st.session_state.selected_expiry_date}")
            else:
                st.warning("⚠️ Please fetch expiry dates first")
            
            st.divider()
            
            # Step 2: Strike File Section
            st.subheader("📁 Step 2: Strike File")
            
            uploaded_file = st.file_uploader("📁 Upload Strike File", type=['txt'])
            
            if uploaded_file is not None:
                # Save uploaded file
                temp_path = f"/tmp/{uploaded_file.name}"
                try:
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.session_state.selected_file_path = temp_path
                    st.success(f"✅ File uploaded: {uploaded_file.name}")
                except Exception as e:
                    st.error(f"❌ Upload failed: {e}")
            
            load_disabled = not st.session_state.selected_expiry_date
            if st.button("📁 Load Strikes", type="secondary", use_container_width=True, disabled=load_disabled):
                if st.session_state.selected_expiry_date:
                    success = self.load_strikes_from_file()
                    if success:
                        st.rerun()
                else:
                    st.warning("⚠️ Select expiry date first!")
            
            if st.session_state.strikes_loaded:
                st.success(f"✅ Loaded: {len(st.session_state.ce_strikes)} CE, {len(st.session_state.pe_strikes)} PE")
            
            st.divider()
            
            # Step 3: Data Refresh
            st.subheader("🔄 Step 3: Data Refresh")
            
            st.session_state.auto_refresh = st.checkbox(
                "Auto Refresh (5 min)", 
                value=st.session_state.auto_refresh
            )
            
            refresh_disabled = not (st.session_state.strikes_loaded and st.session_state.selected_expiry_date)
            
            if st.button("🔄 Refresh Now", type="secondary", use_container_width=True, disabled=refresh_disabled):
                success = self.fetch_data()
                if success:
                    st.rerun()
            
            st.divider()
            
            # Status
            st.subheader("📊 Status")
            time_info = self.get_time_info()
            
            st.write(f"**Current Time (IST):** {time_info['current_time']}")
            st.write(f"**Last Update:** {time_info['last_update']}")
            st.write(f"**Updated:** {time_info['time_ago']}")
            
            if st.session_state.auto_refresh and st.session_state.last_fetch_time:
                if time_info['seconds_until_refresh'] > 0:
                    minutes_left = time_info['seconds_until_refresh'] // 60
                    seconds_left = time_info['seconds_until_refresh'] % 60
                    st.write(f"**Next Refresh:** {minutes_left}:{seconds_left:02d}")
                    st.progress(time_info['progress'])
                else:
                    st.write("**Status:** 🔄 Refreshing...")
                    st.progress(1.0)
            else:
                st.write("**Status:** 📊 Manual mode")
            
            st.caption(f"Refreshes: {st.session_state.refresh_counter}")
    
    def prepare_display_data(self):
        """Prepare data for display (optimized)"""
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
                    'Status': 'Found'
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
                    'Status': 'Not Found'
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
                    'Status': 'Found'
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
                    'Status': 'Not Found'
                })
        
        return display_data, matches_found
    
    def render_data_tables(self, df):
        """Render data tables (simplified)"""
        # Show not found strikes
        not_found = df[df['Status'] == 'Not Found']
        if len(not_found) > 0:
            st.warning(f"⚠️ {len(not_found)} strikes not found")
        
        # Split CE and PE
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📞 CE Options")
            ce_df = df[df['Type'] == 'CE'].drop(['Type', 'Status'], axis=1)
            if len(ce_df) > 0:
                st.dataframe(ce_df, use_container_width=True, hide_index=True)
            else:
                st.info("No CE data")
        
        with col2:
            st.subheader("📉 PE Options")
            pe_df = df[df['Type'] == 'PE'].drop(['Type', 'Status'], axis=1)
            if len(pe_df) > 0:
                st.dataframe(pe_df, use_container_width=True, hide_index=True)
            else:
                st.info("No PE data")
    
    def display_main_content(self):
        """Display main content"""
        if not st.session_state.strikes_loaded:
            st.info("📋 **Load strikes file first using the sidebar.**")
            return
        
        if st.session_state.option_data:
            self.display_option_data()
        else:
            st.info("📊 **Click 'Refresh Now' to fetch data.**")
    
    def display_option_data(self):
        """Display option chain data"""
        display_data, matches_found = self.prepare_display_data()
        
        if not display_data:
            st.warning("⚠️ No data to display")
            return
        
        total_strikes = len(st.session_state.ce_strikes) + len(st.session_state.pe_strikes)
        st.info(f"📊 **Matches:** {matches_found}/{total_strikes}")
        
        df = pd.DataFrame(display_data)
        
        # Quick metrics
        col1, col2, col3, col4 = st.columns(4)
        
        ce_data = df[df['Type'] == 'CE']
        pe_data = df[df['Type'] == 'PE']
        
        ce_available = len(ce_data[(ce_data['Bid'] != 'NA') & (ce_data['Ask'] != 'NA')])
        pe_available = len(pe_data[(pe_data['Bid'] != 'NA') & (pe_data['Ask'] != 'NA')])
        
        with col1:
            st.metric("CE Bid/Ask", f"{ce_available}/{len(ce_data)}")
        with col2:
            st.metric("PE Bid/Ask", f"{pe_available}/{len(pe_data)}")
        with col3:
            st.metric("CE Volume", len(ce_data[ce_data['Volume'] != 'NA']))
        with col4:
            st.metric("PE Volume", len(pe_data[pe_data['Volume'] != 'NA']))
        
        # Expiry info
        if st.session_state.selected_expiry_date:
            st.info(f"📅 **Expiry:** {st.session_state.selected_expiry_date}")
        
        # Data tables
        self.render_data_tables(df)
    
    def handle_auto_refresh(self):
        """Handle auto-refresh logic (optimized)"""
        if (st.session_state.auto_refresh and 
            st.session_state.last_fetch_time and 
            st.session_state.strikes_loaded and
            not st.session_state.is_fetching):
            
            current_time = self.get_ist_time()
            
            # Initialize next refresh time if not set
            if not st.session_state.next_refresh_time:
                st.session_state.next_refresh_time = current_time + timedelta(seconds=st.session_state.refresh_interval)
            
            # Check if it's time to refresh
            next_refresh = st.session_state.next_refresh_time
            if next_refresh.tzinfo is None:
                ist = pytz.timezone('Asia/Kolkata')
                next_refresh = ist.localize(next_refresh)
            
            if current_time >= next_refresh:
                st.session_state.is_fetching = True
                try:
                    success = self.fetch_data()
                    if success:
                        st.session_state.next_refresh_time = self.get_ist_time() + timedelta(seconds=st.session_state.refresh_interval)
                        st.rerun()
                finally:
                    st.session_state.is_fetching = False
    
    def run(self):
        """Main application entry point"""
        # Header
        st.markdown("""
            <div class="main-header">
                <h1>📈 NSE Silver Option Chain Monitor</h1>
                <p>Real-time monitoring with auto-refresh (IST timezone)</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Handle auto-refresh
        self.handle_auto_refresh()
        
        # Render sidebar
        self.render_sidebar()
        
        # Display main content
        self.display_main_content()
        
        # Auto-refresh indicator
        if st.session_state.auto_refresh and st.session_state.last_fetch_time:
            time_info = self.get_time_info()
            if time_info['seconds_until_refresh'] > 0:
                minutes = time_info['seconds_until_refresh'] // 60
                seconds = time_info['seconds_until_refresh'] % 60
                st.success(f"✅ Auto-refresh enabled | Next refresh in {minutes}:{seconds:02d}")
            else:
                st.warning("🔄 Auto-refresh - preparing to refresh...")
        
        # Force rerun for real-time updates (with longer interval to reduce load)
        if st.session_state.auto_refresh:
            time.sleep(2)  # Longer delay to reduce server load
            st.rerun()

# Main function
def main():
    """Main application function"""
    try:
        nse_app = NSEOptionChainStreamlit()
        nse_app.run()
    except Exception as e:
        st.error(f"Application error: {e}")
        st.info("Please refresh the page to restart the application.")

if __name__ == "__main__":
    main()
