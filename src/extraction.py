import requests
from playwright.async_api import async_playwright
from playwright._impl._errors import TimeoutError
from bs4 import BeautifulSoup as bs
import tika
import os
import re
import sys
from time import sleep
from urllib.parse import quote
from tika import parser
from threading import Event

def get_base_path():
    """Get the base path for files, accounting for PyInstaller bundle"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_files_path(*path_parts):
    """Get the correct path to files directory"""
    base = get_base_path()
    return os.path.join(base, "files", *path_parts)

_log_signal_emitter = None
_browser_initialized = False

def set_log_emitter(emitter):
    """Set the log signal emitter for cross-module logging"""
    global _log_signal_emitter
    _log_signal_emitter = emitter

def log_print(*args, **kwargs):
    """Enhanced print function that also sends to log window"""
    import sys
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
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

eve_sig = Event()
browser_ready = Event()  # Signal when browser is initialized
empty_domains = Event()
timeout_event = Event()  # Signal when timeout occurs
import datetime
today = datetime.datetime.now()
valdict = {9999: "ARAI - AIS"}
inv_valdict = {"ARAI - AIS": 9999}
base_url = None
dwnld_count = 0
mList_input = [133, 9, 397, 70, 55, 34, 37, 378, 12, 6, 508, 28, 83, 9999]
kwList = [
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

def pattern_matcher(bstring, patterns=kwList):
    count = 0
    for pattern in patterns:
        if (pattern[1] and re.search(pattern[0], bstring)) or ((not pattern[1]) and re.search(re.escape(pattern[0]), bstring, re.IGNORECASE)):
            count += 1
            print(f"Matched keyword: {pattern[0]}")
    return count

def clean_text(text):
    text = re.sub(r'[^\x00-\x7F]', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'^\s*$', '', text, flags=re.MULTILINE)
    text = text.strip()
    return text

def relevancy_check(file_buffer, gid, keywords = kwList):
    parsed = parser.from_buffer(file_buffer)
    all_text = clean_text(parsed["content"])
    with open(f"{gid}_parsed.txt", "w") as parsed_file:
        parsed_file.write(all_text)
    matched_keywords_count = pattern_matcher(all_text, keywords)

    if matched_keywords_count > 0:
        print(f"{gid} is relevant as {matched_keywords_count} keywords matched:")
        return True
    else:
        print(f"{gid} is not relevant")
        return False
    
async def egz_extract_defaults():
    global _browser_initialized
    
    if _browser_initialized:
        print("Browser already initialized, skipping...")
        browser_ready.set()
        return 0
    
    try:
        print("Starting browser initialization (egz)...")
        global p, browser, page, context
        
        p = await async_playwright().start()
        print("Playwright started successfully.")
        
        browser_options = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-images"
            ]
        }
        
        try:
            browser = await p.chromium.launch(channel="msedge", **browser_options)
            print("Browser launched with MS Edge successfully.")
        except Exception as e:
            print(f"Failed to launch MS Edge, trying Chrome: {e}")
            try:
                browser = await p.chromium.launch(channel="chrome", **browser_options)
                print("Browser launched with Chrome successfully.")
            except Exception as e2:
                print(f"Failed to launch Chrome, trying default Chromium: {e2}")
                browser = await p.chromium.launch(**browser_options)
                print("Browser launched with default Chromium successfully.")
        
        context = await browser.new_context(accept_downloads=True)
        print("New browser context created successfully.")

        page = await context.new_page()
        
        try:
            print("Navigating to eGazette website...")
            await page.goto("https://egazette.gov.in/", timeout=45000)
            print("Successfully navigated to eGazette website.")
        except TimeoutError:
            print("Timeout occurred while loading eGazette website")
            timeout_event.set()
            await cleanup_browser()
            return -1
        except Exception as e:
            print(f"Error navigating to eGazette website: {e}")
            timeout_event.set()
            await cleanup_browser()
            return -1
            
        print("Extracting gazettes from eGazette India...")
        
        url = page.url
        url = url.split(sep="default.aspx")[0]
        print(f"Current URL: {url}")
        global base_url
        base_url = url
        
        try:
            print("Loading search menu...")
            res = await context.request.get("{url}SearchMenu.aspx".format(url=url), headers={
                'Referer': '{base}/'.format(base=url)
            })
            body = await res.text()
            await page.set_content(body)
            await page.click('input[name="btnMinistry"]')
            await page.wait_for_selector('select[name="ddlMinistry"]', timeout=20000)
            print("Successfully loaded ministry dropdown.")
        except TimeoutError:
            print("Timeout occurred while loading ministry dropdown")
            timeout_event.set()
            await cleanup_browser()
            return -1
        except Exception as e:
            print(f"Error loading ministry dropdown: {e}")
            timeout_event.set()
            await cleanup_browser()
            return -1
            
        try:
            html = await page.content()
            sd = bs(html, 'html.parser')
            chpage = sd.find('select', {'name': 'ddlMinistry'})
            if not chpage:
                print("Could not find ministry dropdown in page content")
                await cleanup_browser()
                return -1
                
            ministry_count = 0
            for option in chpage.find_all('option'):
                if option.get('value') == "Select Ministry":
                    continue
                try:
                    value = int(option.get('value'))
                    text = option.get_text().strip()
                    if text and value:
                        valdict[value] = text
                        inv_valdict[text] = value
                        ministry_count += 1
                except (ValueError, TypeError):
                    continue
                    
            print(f"Successfully loaded {ministry_count} ministries.")
            
            if ministry_count == 0:
                print("No valid ministries found")
                await cleanup_browser()
                return -1
                
        except Exception as e:
            print(f"Error extracting ministry data: {e}")
            await cleanup_browser()
            return -1
        
        print("Browser ready! Ministries loaded.")
        _browser_initialized = True
        browser_ready.set()
        print("Waiting for extraction requests...")
        return 0
        
    except Exception as e:
        print(f"Browser initialization error (egz): {e}")
        import traceback
        traceback.print_exc()
        timeout_event.set()
        await cleanup_browser()
        return -1

async def cleanup_browser():
    """Clean up browser resources"""
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
    global dialog_handled, ministryCode
    dialog_handled = True
    emit_progress_update(valdict[ministryCode], 'completed', '0')
    await dialog.accept()
async def egz_extract_pdfs(month, year, mList, kwList):
    global dwnld_count
    dwnld_count = 0
    page.on('dialog', handle_dialog)     
    print(f"Extracting gazettes for month: {month}, year: {year}, ministries: {mList}")
    global ministryCode
    for ministryCode in mList:
        if(not eve_sig.is_set()):
            break
        if ministryCode == 9999:
            await ais_extract_pdfs()
            continue
        gid_dict = {}
        ministryCode = int(input("Enter Ministry Code: ")) if ministryCode == -1 else ministryCode
        
        ministry_name = valdict.get(ministryCode, f"Ministry {ministryCode}")
        emit_progress_update(ministry_name, 'extracting')
        
        print(f"Starting extraction with ministry code {ministryCode}...")
        if ministryCode not in valdict:
            print(f"Ministry code {ministryCode} not valid. Enter valid code!")
            #emit_progress_update(ministry_name, 'error')
            return
        try:
            await page.select_option('select[name="ddlMinistry"]', str(ministryCode), timeout=15000)
            await page.select_option('select[name="ddlmonth"]', str(month), timeout = 15000)
            await page.select_option('select[name="ddlyear"]', str(year), timeout = 15000)
            await page.click('input[name="ImgSubmitDetails"]', timeout=15000)
            print(f"Searching for gazettes under {valdict[ministryCode]} in {str(month).zfill(2)}/{year}...")
            html = None
            sd = None
            found = None
            await page.wait_for_selector('table#gvGazetteList', timeout=15000)
            html = await page.content()
            sd = bs(html, 'html.parser')
            found = sd.find('table', {'id': 'gvGazetteList'})
            if not found:
                print("No gazettes found for the given criteria.")
                #emit_progress_update(ministry_name, 'error')
                continue
            rows = found.find_all('tr')
        except TimeoutError:
            global dialog_handled
            if(dialog_handled):
                dialog_handled = False
                continue
            print(f"Timeout occurred while searching for gazette table")
            emit_progress_update(ministry_name, 'error')
            timeout_event.set()
            continue
        try:            
            await page.wait_for_selector('span#lbl_Result', timeout=10000)
        except TimeoutError:
            print(f"Timeout occurred while waiting for result label")
            emit_progress_update(ministry_name, 'error')
            timeout_event.set()
            continue
        lab = page.locator('span#lbl_Result')
        tbres = await lab.text_content()
        gcount = int(tbres.split(sep=":")[1])
        print(f"Found! {tbres}\nPrinting Gazette IDs")
        index = 0
        pg = 1
        while True:
            for i in range(1, len(rows)):
                row = rows[i]
                subj = row.find('span', {'id': re.compile(r'gvGazetteList_lbl_Subject_[0-9]+')})
                entry = row.find('span', {'id': re.compile(r'gvGazetteList_lbl_UGID_[0-9]+')})
                if not entry or not subj:
                    break
                print(f'{index} {entry.get_text()} {subj.get_text()}')
                index += 1
                gid_dict[index] = [entry.get_text(), subj.get_text()]
                if index % 15 == 0:
                    pg += 1
            if index >= gcount:
                break
            page_button = page.locator('a', has_text=f'{pg}')
            if await page_button.count() > 0:
                print(f"Clicking page button: {pg}")
                try:
                    await page_button.click(timeout=15000)
                    await page.wait_for_selector('table#gvGazetteList', timeout=10000)
                except TimeoutError:
                    print(f"Timeout occurred while navigating to page {pg}")
                    emit_progress_update(ministry_name, 'error')
                    timeout_event.set()
                    break
                html = await page.content()
                sd = bs(html, 'html.parser')
                found = sd.find('table', {'id': 'gvGazetteList'})
                if not found:
                    print("No gazettes found for the given criteria.")
                    break
                rows = found.find_all('tr')
        list_path = get_files_path(valdict[ministryCode], str(today.year), str(today.month), 'gids_list.txt')
        os.makedirs(os.path.dirname(list_path), exist_ok=True)
        
        relevant_count = 0
        with open(list_path, 'w') as f:
            for value in gid_dict.values():
                if(pattern_matcher(value[1], kwList) <= 0):
                    print(f"Gazette ID {value[0]} - {value[1]} keyword mismatch.")
                else:
                    f.write(f"1#{value[0]}\n")
                    relevant_count += 1
        
        if relevant_count > 0:
            print(f"Ministry {ministry_name}: {relevant_count} relevant files found")
            emit_progress_update(ministry_name, 'completed', f'0/{relevant_count}')
        else:
            emit_progress_update(ministry_name, 'completed', '0')
            print(f"Ministry {ministry_name}: No relevant files found")

def egz_download():
    tika.initVM()
    print("Gazette extraction completed. Now downloading PDFs...")
    filtered_gids = None
    global dwnld_count
    total_files = 0
    for ministryCode in mList_input:
        if not eve_sig.is_set():
            break
        if ministryCode == 9999:
            ais_download()
            continue
        list_path = get_files_path(valdict[ministryCode], str(today.year), str(today.month), 'gids_list.txt')
        try:
            with open(list_path, 'r') as f:
                filtered_gids = f.readlines()
        except FileNotFoundError:
            print(f"List file {list_path} not found. Skipping ministry code {valdict[ministryCode]}.")
            continue
        mincount = 0
        for gid in filtered_gids:
            if not eve_sig.is_set():
                break
            print(f"\nDownloading Gazette ID: {gid[:-1]}")
            gid_u = gid.split('#')[1].split(sep='-')[-1][:-1].strip()
            pdf_url = f'https://egazette.gov.in/WriteReadData/{today.year}/{gid_u}.pdf'
            print(f'url: {pdf_url}')
            file_path = get_files_path(valdict[ministryCode], str(today.year), str(today.month), f"{gid_u}.pdf")
            if os.path.exists(file_path):
                print(f"File {file_path} already exists, skipping download.")
                continue
            try:
                response = requests.get(pdf_url, timeout=30)
                response.raise_for_status()
            except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
                print(f"Timeout or error occurred while downloading {gid_u}: {e}")
                timeout_event.set()
                continue
            '''
            if gid.startswith('0'):
                if not relevancy_check(response.content, gid_u):
                    print(f"Skipping {gid_u} due to relevancy check failure.")
                    continue
                print(f"Relevancy check passed for {gid}.")
                continue
            '''
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(response.content)
                total_files += 1
                mincount += 1
                emit_progress_update(valdict[ministryCode], 'completed', f'{mincount}/{len(filtered_gids)}')
        if mincount > 0:            
            emit_progress_update(valdict[ministryCode], 'completed', str(mincount))
        else:
            emit_progress_update(valdict[ministryCode], 'completed', '0')
    files_path = get_files_path()
    print(f"Total {total_files} new gazettes downloaded. Files are stored in {files_path} directory")
    dwnld_count += total_files

async def ais_extract_pdfs(draft_type="draft"):
    if not eve_sig.is_set():
        print("AIS PDF extraction cancelled before starting")
        return
        
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("Booting up web driver...")
    page = await context.new_page()
    print("Extracting AIS from ARAI India...")
    emit_progress_update("ARAI - AIS", 'extracting')
    try:
        await page.goto("https://www.araiindia.com/downloads", timeout=30000)
    except TimeoutError:
        print("Timeout occurred while loading ARAI website")
        timeout_event.set()
        return
    
    if not eve_sig.is_set():
        print("AIS PDF extraction cancelled after page load")
        await page.close()
        return
        
    if(draft_type == "draft"):
        try:
            await page.click("input[id='draftAIS']")
        except TimeoutError:
            print("Timeout occurred while clicking draft AIS checkbox")
            timeout_event.set()
            return
            
    try:
        await page.wait_for_selector("table[_ngcontent-arai-c19]", timeout=15000)
    except TimeoutError:
        print("Timeout occurred while waiting for AIS table")
        timeout_event.set()
        return
    table = page.locator("table[_ngcontent-arai-c19]")
    if(not table):
        print("Table not found!!!")
        return
    rows = table.locator('tbody tr')
    try:
        await rows.last.wait_for(state='attached', timeout=10000)
    except TimeoutError:
        print("Timeout occurred while waiting for table rows to load")
        timeout_event.set()
        return    
    print(f"Found {await rows.count()} entries. Downloading PDF files...")
    emit_progress_update("ARAI - AIS", 'completed', f"0/{await rows.count()}")
    aids_list_path = get_files_path("AIS", "aids_list.txt")
    os.makedirs(os.path.dirname(aids_list_path), exist_ok=True)    
    with open(aids_list_path, 'w') as f:
        for i in range(await rows.count()):
            if not eve_sig.is_set():
                break
            row = rows.nth(i)
            code = await row.locator('td').nth(1).text_content()
            if not code:
                continue
            code = re.sub(r'[<>:"/\\\\|?*\s]', '_', code)
            dl = row.locator('td').nth(3).locator('a')
            if not dl:
                continue
            pdf_url = await dl.get_attribute('href')
            pdf_url = quote(pdf_url, safe=":/?&=%")
            print(f"Code: {pdf_url}")
            f.write(f"{code} {pdf_url}\n")
def ais_download():
    alist = []
    total_files = 0
    aids_list_path = get_files_path("AIS", "aids_list.txt")
    with open(aids_list_path, 'r') as f:
        alist = f.readlines()
    for aid in alist:
        if not eve_sig.is_set():
            break
        asp = aid.split(' ')
        code = asp[0]
        pdf_url = asp[1]
        print(f"Downloading {code} from {pdf_url}")
        file_path = get_files_path("AIS", f"{code}.pdf")
        if os.path.exists(file_path):
            print(f"File {file_path} already exists, skipping download.")
            continue
        try:
            response = requests.get(pdf_url[:-1], timeout=30)
            response.raise_for_status()
        except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
            print(f"Timeout or error occurred while downloading {code}: {e}")
            timeout_event.set()
            continue
            
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        print(response)
        with open(file_path, "wb") as f:
            f.write(response.content)
            total_files += 1
            emit_progress_update("ARAI - AIS", 'completed', f"{total_files}/{len(alist)}")
    global dwnld_count
    dwnld_count += total_files
    emit_progress_update("ARAI - AIS", 'completed', str(total_files))
    files_path = get_files_path()
    print(f"Total {total_files} new files downloaded. Files are stored in {files_path} directory")

async def extract_mids(user_domains, user_keywords):
    mList_input.clear()
    for domain in user_domains:
        mList_input.append(inv_valdict[domain])
    print(f"Ministries selected: {mList_input}")
    if not mList_input:
        print("No ministries selected. Exiting...")
        empty_domains.set()
        return -1
    if eve_sig.is_set():
        await egz_extract_pdfs(today.month, today.year, mList_input, user_keywords)
    # Don't set eve_sig here - let the GUI manage the signal state
    return 0
