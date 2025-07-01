from requests import get
from requests.exceptions import Timeout, RequestException
from playwright.async_api import async_playwright
from playwright._impl._errors import TimeoutError
from bs4 import BeautifulSoup as bs
from os import chdir, makedirs
from os.path import dirname, join, abspath, exists
from re import search, escape, IGNORECASE, sub, compile, MULTILINE
import sys
from urllib.parse import quote
from threading import Event

def get_base_path():
    """Get the base path for files, accounting for PyInstaller bundle"""
    if getattr(sys, 'frozen', False):
        return dirname(sys.executable)
    else:
        return dirname(abspath(__file__))

def get_files_path(*path_parts):
    """Get the correct path to files directory"""
    base = get_base_path()
    return join(base, "files", *path_parts)

_log_signal_emitter = None
ht_parser = 'html.parser'

def set_log_emitter(emitter):
    """Set the log signal emitter for cross-module logging"""
    global _log_signal_emitter
    _log_signal_emitter = emitter

def log_print(*args, **kwargs):
    """Enhanced print function that also sends to log window"""
    print(*args, **kwargs)
    
    if _log_signal_emitter:
        message = ' '.join(str(arg) for arg in args)
        _log_signal_emitter.log_message.emit(message)

def emit_progress_update(ministry_name, status, count="-"):
    """Emit progress update signal for GUI color changes"""
    if _log_signal_emitter:
        _log_signal_emitter.progress_update.emit(ministry_name,  status, count)

base_path = get_base_path()
if getattr(sys, 'frozen', False):
    print(f"Running as PyInstaller bundle, base path: {base_path}")
else:
    chdir(dirname(abspath(__file__)))

eve_sig = Event()
browser_ready = Event()  # Signal when browser is initialized
empty_domains = Event()
timeout_event = Event()  # Signal when timeout occurs
import datetime
today = datetime.datetime.now()
valdict = {9999: "ARAI - AIS - draft", 9998: "ARAI - AIS - published"}
inv_valdict = {"ARAI - AIS - draft": 9999, "ARAI - AIS - published": 9998}
base_url = None
mlist_input = [9999, 9998, 133, 9, 397, 70, 55, 34, 37, 378, 12, 6, 508, 28, 83]
kwlist = [
  ['CMVR 1989', True],
  ['Motor Vehicle Act 1988', True],
  ['Draft Rules', False],
  ['Amended', False],
  ['Final Draft', False],
  ['Truck', False],
  ['Vehicle', False],
  ['Road', False],
  ['Automobile', False],
  ['M category', True],
  ['N category', True],
  ['Wheel Rim', False],
  ['Battery', False],
  ['Waste Management', False],
  ['Steel', False],
  ['Brake system', False],
  ['Emission', False],
  ['AdBlue', True],
  ['Urea', False],
  ['Smoke', False],
  ['Pollution', False],
  ['Tires', False],
  ['Electric', False],
  ['EV', True],
  ['PM', True],
  ['Type Approval', False],
  ['Registration', False],
  ['Safety', False],
  ['Compliance', False],
  ['Fire', False],
  ['Air Conditioning', False],
  ['Light', False],
  ['Diesel', False],
  ['Fuel', False],
  ['Coal', False],
  ['Mines', False],
  ['Hydrogen', False],
  ['Alternate Fuel', False],
  ['Test', False]
]

def pattern_matcher(bstring, patterns=kwlist):
    count = 0
    for pattern in patterns:
        if pattern[1]:
            match = search(escape(pattern[0]), bstring)
            if match:
                count += 1
                print(f"Matched keyword: {pattern[0]} in {match.group(0)}")
        else:
            match = search(escape(pattern[0]), bstring, IGNORECASE)
            if match:
                count += 1
                print(f"Matched keyword: {pattern[0]} in {match.group(0)}")
    return count

def clean_text(text):
    text = sub(r'[^\x00-\x7F]', '', text)
    text = sub(r'\s+', ' ', text)
    text = sub(r'^\s*$', '', text, flags=MULTILINE)
    text = text.strip()
    return text

async def browser_init():
    try:
        print("Starting browser initialization (egz)...")
        global p, browser, page, context
        p = await async_playwright().start()
        browser = await p.chromium.launch(channel="msedge", headless=True, args = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--disable-extensions", "--disable-plugins", "--disable-images"]) 
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
    except Exception as e:
        print(f"Error during browser initialization: {e}")
        timeout_event.set()
        await cleanup_browser()
        return -1

async def egz_extract_defaults():
    print("Starting data initialization (egz)...")
    try:
        await browser_init()
        global page
        await page.goto("https://egazette.gov.in/", timeout=45000)
        print("Successfully navigated to eGazette website.")
        global base_url
        base_url = page.url.split(sep="default.aspx")[0]
        print(f"Current URL: {base_url}\nLoading search menu...")
        res = await context.request.get("{url}SearchMenu.aspx".format(url=base_url), headers={
            'Referer': '{base}/'.format(base=base_url)
        })
        await page.set_content(await res.text())
        await page.click('input[name="btnMinistry"]')
        await page.wait_for_selector('select[name="ddlMinistry"]', timeout=20000)
        chpage = bs(await page.content(), ht_parser).find('select', {'name': 'ddlMinistry'})
        if not chpage:
            print("Could not find ministry dropdown in page content")
            await cleanup_browser()
            return -1
        ministry_count = 0
        for option in chpage.find_all('option')[1:]:
            value = int(option.get('value'))
            text = option.get_text().strip()
            if text and value:
                valdict[value] = text
                inv_valdict[text] = value
                ministry_count += 1    
        print(f"Successfully loaded {ministry_count} ministries.")
        
        if ministry_count == 0:
            print("No valid ministries found")
            await cleanup_browser()
            return -1
        
    except TimeoutError:
        print("Timeout occurred while extracting defaults.")
        timeout_event.set()
        await cleanup_browser()
        return -1
    
    except Exception as e:
        print(f"Data initialization error (egz): {e}")
        import traceback
        traceback.print_exc()
        timeout_event.set()
        await cleanup_browser()
        return -1
    print("Browser ready! Ministries loaded.")
    browser_ready.set()
    print("Waiting for extraction requests...")
    return 0

async def cleanup_browser():
    try:
        if 'browser' in globals() and browser:
            await browser.close()
            print("Browser closed.")
    except Exception as e:
        print(f"Error closing browser: {e}")
    
    try:
        if 'p' in globals() and p:
            await p.stop()
            print("Playwright stopped.")
    except Exception as e:
        print(f"Error stopping Playwright: {e}")

async def handle_dialog(dialog):
    print(dialog.message)
    global dialog_handled, mcode
    dialog_handled = True
    emit_progress_update(valdict[mcode], 'completed', '0')
    await dialog.accept()
    
async def egz_extract_pdfs(mlist, kwlist):
    """Main extraction function with reduced complexity"""
    global dwnld_count, page
    dwnld_count = 0
    page.on('dialog', handle_dialog)     
    print(f"Extracting gazettes for month: {today.month}, year: {today.year}, ministries: {mlist}")
    global mcode
    for mcode in mlist:
        if not eve_sig.is_set():
            break
            
        if mcode == 9999:
            await ais_extract_pdfs()
            continue    
        if mcode == 9998:
            await ais_extract_pdfs('published')
            continue
        
        await _process_ministry(mcode, kwlist)

async def _process_ministry(mcode, kwlist):
    """Process a single ministry - reduces nesting"""
    ministry_name = valdict.get(mcode, f"Ministry {mcode}")
    emit_progress_update(ministry_name, 'extracting')
        
    try:
        await page.select_option('select[name="ddlMinistry"]', str(mcode), timeout=15000)
        await page.select_option('select[name="ddlmonth"]', 'June', timeout=15000)
        await page.click('input[name="ImgSubmitDetails"]', timeout=15000)
        gazette_data = await _extract_gazette_data(ministry_name)
        if gazette_data:
            print(gazette_data)
            await _process_gazette_pages(gazette_data, ministry_name)
            _save_filtered_results(mcode, gazette_data['gid_dict'], kwlist, ministry_name)
    except Exception as e:
        print(f"Error processing ministry {ministry_name}: {e}")
        emit_progress_update(ministry_name, 'error')

async def _extract_gazette_data(ministry_name):
    """Extract initial gazette data and count"""
    try:
        await page.wait_for_selector('table#gvGazetteList', timeout=15000)
        
        # Get total count
        await page.wait_for_selector('span#lbl_Result', timeout=10000)
        lab = page.locator('span#lbl_Result')
        tbres = await lab.text_content()
        gcount = int(tbres.split(sep=":")[1])
        
        print(f"Found! {tbres}")
        
        # Get initial table
        html = await page.content()
        sd = bs(html, ht_parser)
        found = sd.find('table', {'id': 'gvGazetteList'})
        
        if not found:
            print("No gazettes found for the given criteria.")
            return None
            
        return {
            'gcount': gcount,
            'rows': found.find_all('tr'),
            'gid_dict': {},
            'index': 0,
            'page_num': 1
        }
        
    except TimeoutError:
        return _handle_dialog_or_timeout(ministry_name)

def _handle_dialog_or_timeout(ministry_name):
    """Handle dialog or timeout scenarios"""
    global dialog_handled
    if dialog_handled:
        dialog_handled = False
        return None
    
    print("Timeout occurred while searching for gazette table")
    emit_progress_update(ministry_name, 'error')
    timeout_event.set()
    return None

async def _process_gazette_pages(gazette_data, ministry_name):
    """Process all pages of gazette results"""
    while gazette_data['index'] < gazette_data['gcount']:
        _extract_rows_data(gazette_data)
        
        if gazette_data['index'] >= gazette_data['gcount']:
            break
            
        # Navigate to next page if needed
        if not await _navigate_next_page(gazette_data, ministry_name):
            break

def _extract_rows_data(gazette_data):
    """Extract data from current page rows"""
    rows = gazette_data['rows']
    
    for i in range(1, len(rows)):
        row = rows[i]
        
        """Extract entry data from a single row"""
        subj = row.find('span', {'id': compile(r'gvGazetteList_lbl_Subject_[\d]+')})
        entry = row.find('span', {'id': compile(r'gvGazetteList_lbl_UGID_[\d]+')})
        
        if not entry or not subj:
            return None
            
        entry_text = entry.get_text()
        subj_text = subj.get_text()
        
        print(f"{gazette_data['index']} {entry_text} {subj_text}")
        entry_data = [entry_text, subj_text]
        
        if not entry_data:
            break
            
        gazette_data['index'] += 1
        gazette_data['gid_dict'][gazette_data['index']] = entry_data
        
        if gazette_data['index'] % 15 == 0:
            gazette_data['page_num'] += 1

async def _navigate_next_page(gazette_data, ministry_name):
    """Navigate to next page of results"""
    page_num = gazette_data['page_num']
    page_button = page.locator('a', has_text=f'{page_num}')
    
    if await page_button.count() == 0:
        return False
        
    try:
        print(f"Clicking page button: {page_num}")
        await page_button.click(timeout=15000)
        await page.wait_for_selector('table#gvGazetteList', timeout=10000)
        
        # Update rows for next iteration
        html = await page.content()
        sd = bs(html, ht_parser)
        found = sd.find('table', {'id': 'gvGazetteList'})
        
        if not found:
            print("No gazettes found for the given criteria.")
            return False
            
        gazette_data['rows'] = found.find_all('tr')
        return True
        
    except TimeoutError:
        print(f"Timeout occurred while navigating to page {page_num}")
        emit_progress_update(ministry_name, 'error')
        timeout_event.set()
        return False

def _save_filtered_results(mcode, gid_dict, kwlist, ministry_name):
    """Save filtered results to file"""
    list_path = get_files_path(valdict[mcode], str(today.year), str(today.month), 'gids_list.txt')
    makedirs(dirname(list_path), exist_ok=True)
    
    relevant_count = 0
    with open(list_path, 'w') as f:
        for value in gid_dict.values():
            if pattern_matcher(value[1], kwlist) > 0:
                f.write(f"1#{value[0]}\n")
                relevant_count += 1
            else:
                print(f"Gazette ID {value[0]} - {value[1]} keyword mismatch.")
    if relevant_count > 0:
        print(f"Ministry {ministry_name}: {relevant_count} new relevant files found")
        emit_progress_update(ministry_name, 'completed', f'0/{relevant_count}')
    else:
        emit_progress_update(ministry_name, 'completed', '0')
        print(f"Ministry {ministry_name}: No new relevant files found")
    
def egz_download():
    print("Gazette extraction completed. Now downloading PDFs...")
    filtered_gids = []
    global dwnld_count
    total_files = 0
    global mcode
    for mcode in mlist_input:
        if not eve_sig.is_set():
            break
        print(f"\nProcessing ministry code: {mcode} - {valdict[mcode]}")
        if mcode == 9999 or mcode == 9998:
            ais_download(mcode)
            continue
        list_path = get_files_path(valdict[mcode], str(today.year), str(today.month), 'gids_list.txt')
        try:
            with open(list_path, 'r') as f:
                filtered_gids = f.readlines()
        except FileNotFoundError:
            print(f"List file {list_path} not found. Skipping ministry code {valdict[mcode]}.")
            continue
        mincount = 0
        for gid in filtered_gids:
            if not eve_sig.is_set():
                break
            print(f"\nDownloading Gazette ID: {gid[:-1]}")
            gid_u = gid.split('#')[1].split(sep='-')[-1][:-1].strip()
            pdf_url = f'https://egazette.gov.in/WriteReadData/{today.year}/{gid_u}.pdf'
            print(f'url: {pdf_url}')
            file_path = get_files_path(valdict[mcode], str(today.year), str(today.month), f"{gid_u}.pdf")
            if exists(file_path):
                print(f"File {file_path} already exists, skipping download.")
                continue
            response = get(pdf_url, timeout=30)
            response.raise_for_status()
            makedirs(dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(response.content)
                mincount += 1
                emit_progress_update(valdict[mcode], 'completed', f'{mincount}/{len(filtered_gids)}')
        total_files += mincount
        emit_progress_update(valdict[mcode], 'completed', str(mincount))
    files_path = get_files_path()
    dwnld_count += total_files
    print(f"Total {total_files} new gazettes downloaded. Files are stored in {files_path} directory")
    
async def ais_extract_pdfs(draft_type="draft"):
    aistype = 9999 if draft_type == "draft" else 9998
    page = await context.new_page()
    print("Extracting AIS from ARAI India...")
    emit_progress_update(valdict[aistype], 'extracting')
    try:
        await page.goto("https://www.araiindia.com/downloads", timeout=30000)
        if(draft_type == "draft"):
            await page.click("input[id='draftAIS']")
        await page.wait_for_selector("table[_ngcontent-arai-c19]", timeout=15000)
        table = page.locator("table[_ngcontent-arai-c19]")
        if(not table):
            print("Table not found!!!")
            return
        rows = table.locator('tbody tr')
        await rows.last.wait_for(state='attached', timeout=10000)
    except TimeoutError:
        print("Timeout occurred while waiting for table rows to load")
        timeout_event.set()
        return    
    print(f"Found {await rows.count()} entries. Downloading PDF files...")
    emit_progress_update(valdict[aistype], 'completed', f"0/{await rows.count()}")
    aids_list_path = get_files_path(valdict[aistype], "aids_list.txt")
    makedirs(dirname(aids_list_path), exist_ok=True)    
    with open(aids_list_path, 'w') as f:
        for i in range(await rows.count()):
            if not eve_sig.is_set():
                break
            row = rows.nth(i)
            code = await row.locator('td').nth(1).text_content()
            if not code:
                continue
            code = sub(r'[<>:"/\\|?*\s]', '_', code)
            dl = row.locator('td').nth(3).locator('a')
            if not dl:
                continue
            pdf_url = await dl.get_attribute('href')
            pdf_url = quote(pdf_url, safe=":/?&=%")
            print(f"Code: {pdf_url}")
            f.write(f"{code} {pdf_url}\n")
def ais_download(aistype):
    alist = []
    global dwnld_count
    total_files = 0
    aids_list_path = get_files_path(valdict[aistype], "aids_list.txt")
    with open(aids_list_path, 'r') as f:
        alist = f.readlines()
    for aid in alist:
        if not eve_sig.is_set():
            break
        asp = aid.split(' ')
        code = asp[0]
        pdf_url = asp[1]
        print(f"Downloading {code} from {pdf_url}")
        file_path = get_files_path(valdict[aistype], f"{code}.{pdf_url.split('.')[-1][:-1]}")
        if exists(file_path):
            print(f"File {file_path} already exists, skipping download.")
            continue
        response = get(pdf_url[:-1], timeout=30)
        response.raise_for_status()
            
        makedirs(dirname(file_path), exist_ok=True)
        print(response)
        with open(file_path, "wb") as f:
            f.write(response.content)
            total_files += 1
            emit_progress_update(valdict[aistype], 'completed', f"{total_files}/{len(alist)}")
    emit_progress_update(valdict[aistype], 'completed', str(total_files))
    files_path = get_files_path()
    dwnld_count += total_files
    print(f"Total {total_files} new files downloaded. Files are stored in {files_path} directory")

async def extract_mids(user_domains, user_keywords):
    mlist_input.clear()
    for domain in user_domains:
        mlist_input.append(inv_valdict[domain])
    print(f"Ministries selected: {mlist_input}")
    if not mlist_input:
        print("No ministries selected. Exiting...")
        empty_domains.set()
        return -1
    if eve_sig.is_set():
        await egz_extract_pdfs(mlist_input, user_keywords)
    # Don't set eve_sig here - let the GUI manage the signal state
    return 0
