import requests
from playwright.async_api import async_playwright
from playwright._impl._errors import TimeoutError
from bs4 import BeautifulSoup as bs
import tika
import os
import re
from time import sleep
from urllib.parse import quote
from tika import parser
from threading import Event

# Global logging setup for cross-module logging
_log_signal_emitter = None

def set_log_emitter(emitter):
    """Set the log signal emitter for cross-module logging"""
    global _log_signal_emitter
    _log_signal_emitter = emitter

def log_print(*args, **kwargs):
    """Enhanced print function that also sends to log window"""
    import sys
    # Print to console as normal
    print(*args, **kwargs)
    
    # Also send to log window if emitter is set
    if _log_signal_emitter:
        message = ' '.join(str(arg) for arg in args)
        _log_signal_emitter.log_message.emit(message)

os.chdir(os.path.dirname(os.path.abspath(__file__)))

eve_sig = Event()
browser_ready = Event()  # Signal when browser is initialized
empty_domains = Event()
timeout_event = Event()  # Signal when timeout occurs
import datetime
today = datetime.datetime.now()
valdict = {}
inv_valdict = {}
base_url = None
dwnld_count = 0
mList_input = [133, 9, 397, 70, 55, 34, 37, 378, 12, 6, 508, 28, 83]
kwList = [
  ['CMVR 1989', True],
  ['Motor Vehicle Act 1988', True],
  ['Draft Rules', False],
  ['Amended', False],
  ['Final Draft', False],
  ['Trucks', False],
  ['Vehicle', False],
  ['Road Automobiles', False],
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
    # Remove multiple spaces, newlines, and empty lines
    text = re.sub(r'[^\x00-\x7F]', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'^\s*$', '', text, flags=re.MULTILINE)
    text = text.strip()
    return text

def relevancy_check(file_buffer, gid, keywords = kwList):
    parsed = parser.from_buffer(file_buffer)
    all_text = clean_text(parsed["content"])
    #print(parsed["content"])
    with open(f"{gid}_parsed.txt", "w") as parsed_file:
        parsed_file.write(all_text)
    #print(parsed["metadata"])
    # all_text = extract_text_from_pdf(pdf_file)
    matched_keywords_count = pattern_matcher(all_text, keywords)

    if matched_keywords_count > 0:
        print(f"{gid} is relevant as {matched_keywords_count} keywords matched:")
        #print(f"The matched keywords are: {matched_keywords}")
        return True
    else:
        print(f"{gid} is not relevant")
        return False
    
async def egz_extract_defaults():
    try:
        print("Starting browser initialization...")
        global p, browser, page, context
        p = await async_playwright().start()
        browser = await p.chromium.launch(channel="msedge", headless=False)  
        context = await browser.new_context(accept_downloads=True)
    
        page = await context.new_page()
        try:
            await page.goto("https://egazette.gov.in/", timeout=30000)
        except TimeoutError:
            print("Timeout occurred while loading eGazette website")
            timeout_event.set()
            browser_ready.set()
            return None
            
        print("Extracting gazettes from eGazette India...")
        
        url = page.url
        url = url.split(sep="default.aspx")[0]
        print(f"Current URL: {url}")
        global base_url
        base_url = url
        try:
            res = await context.request.get("{url}SearchMenu.aspx".format(url=url), headers={
                'Referer': '{base}/'.format(base=url)
            })
            body = await res.text()
            await page.set_content(body)
            await page.click('input[name="btnMinistry"]')
            await page.wait_for_selector('select[name="ddlMinistry"]', timeout=15000)
        except TimeoutError:
            print("Timeout occurred while loading ministry dropdown")
            timeout_event.set()
            browser_ready.set()
            return None
            
        html = await page.content()
        sd = bs(html, 'html.parser')
        chpage = sd.find('select', {'name': 'ddlMinistry'})
        if not chpage:
            return page
        for option in chpage.find_all('option'):
            if option.get('value') == "Select Ministry":
                continue
            valdict[int(option.get('value'))] = option.get_text()
            inv_valdict[option.get_text()] = int(option.get('value'))
        print("Browser ready! Ministries loaded.")
        # Signal that browser is ready
        browser_ready.set()
        print("Waiting for extraction requests...")   
    except Exception as e:
        print(f"Browser initialization error: {e}")
        timeout_event.set()
        browser_ready.set()  # Set even on error to prevent hanging
        return None
async def handle_dialog(dialog):
    print(dialog.message)
    global dialog_handled
    dialog_handled = True
    await dialog.accept() 
async def egz_extract_pdfs(month, year, mList, kwList):
    page.on('dialog', handle_dialog)        
    print(f"Extracting gazettes for month: {month}, year: {year}, ministries: {mList}")
    for ministryCode in mList:
        if(not eve_sig.is_set()):
            break
        gid_dict = {}
        ministryCode = int(input("Enter Ministry Code: ")) if ministryCode == -1 else ministryCode
        print(f"Starting extraction with ministry code {ministryCode}...")
        if ministryCode not in valdict:
            print(f"Ministry code {ministryCode} not valid. Enter valid code!")
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
                continue
            rows = found.find_all('tr')
        except TimeoutError:
            global dialog_handled
            if(dialog_handled):
                dialog_handled = False
                continue
            print(f"Timeout occurred while searching for gazette table")
            timeout_event.set()
            continue
        try:
            await page.wait_for_selector('span#lbl_Result', timeout=10000)
        except TimeoutError:
            print(f"Timeout occurred while waiting for result label")
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
                    timeout_event.set()
                    break
                html = await page.content()
                sd = bs(html, 'html.parser')
                found = sd.find('table', {'id': 'gvGazetteList'})
                if not found:
                    print("No gazettes found for the given criteria.")
                    break
                rows = found.find_all('tr')
        list_path = f'../files/{valdict[ministryCode]}/{today.year}/{today.month}/gids_list.txt'
        os.makedirs(os.path.dirname(list_path), exist_ok=True)
        with open(list_path, 'w') as f:
            for value in gid_dict.values():
                if(pattern_matcher(value[1], kwList) <= 0):
                    print(f"Gazette ID {value[0]} - {value[1]} keyword mismatch.")
                    f.write(f"0#{value[0]}\n")
                f.write(f"1#{value[0]}\n")

def egz_download():
    tika.initVM()
    print("Gazette extraction completed. Now downloading PDFs...")
    filtered_gids = None
    global dwnld_count
    total_files = 0
    for ministryCode in mList_input:
        list_path = f'../files/{valdict[ministryCode]}/{today.year}/{today.month}/gids_list.txt'
        try:
            with open(list_path, 'r') as f:
                filtered_gids = f.readlines()
        except FileNotFoundError:
            print(f"List file {list_path} not found. Skipping ministry code {valdict[ministryCode]}.")
            continue
        for gid in filtered_gids:
            print(f"\nDownloading Gazette ID: {gid[:-1]}")
            gid_u = gid.split('#')[1].split(sep='-')[-1][:-1].strip()
            pdf_url = f'https://egazette.gov.in/WriteReadData/{today.year}/{gid_u}.pdf'
            print(f'url: {pdf_url}')
            file_path = f"../files/{valdict[ministryCode]}/{today.year}/{today.month}/{gid_u}.pdf"
            if os.path.exists(file_path):
                print(f"File {file_path} already exists, skipping download.")
                continue
            try:
                response = requests.get(pdf_url, timeout=30)
                response.raise_for_status()  # Raise an exception for bad status codes
            except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
                print(f"Timeout or error occurred while downloading {gid_u}: {e}")
                timeout_event.set()
                continue
                
            if gid.startswith('0'):
                '''
                if not relevancy_check(response.content, gid_u):
                    print(f"Skipping {gid_u} due to relevancy check failure.")
                    continue
                '''
                print(f"Relevancy check passed for {gid}.")
                continue
            else:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "wb") as f:
                    f.write(response.content)
                    total_files += 1
    print(f"Total {total_files} new gazettes downloaded. Files are stored in ../files/ directory")
    dwnld_count = total_files

async def ais_extract_pdfs(draft_type="draft"):
    # Check if extraction was cancelled before starting
    if not eve_sig.is_set():
        print("AIS PDF extraction cancelled before starting")
        return
        
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("Booting up web driver...")
    page = await context.new_page()
    print("Extracting AIS from ARAI India...")
    try:
        await page.goto("https://www.araiindia.com/downloads", timeout=30000)
    except TimeoutError:
        print("Timeout occurred while loading ARAI website")
        timeout_event.set()
        return
    
    # Check for cancellation after page load
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
    os.makedirs(os.path.dirname(f"../files/AIS/aids_list.txt"), exist_ok=True)    
    with open (f"../files/AIS/aids_list.txt", 'w') as f:
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
    with open(f"../files/AIS/aids_list.txt", 'r') as f:
        alist = f.readlines()
    for aid in alist:
        if not eve_sig.is_set():
            break
        asp = aid.split(' ')
        code = asp[0]
        pdf_url = asp[1]
        print(f"Downloading {code} from {pdf_url}")
        file_path = f"../files/AIS/{code}.pdf"
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
    dwnld_count += total_files
    print(f"Total {total_files} new files downloaded. Files are stored in ../files/ directory")

async def extract_mids(page, user_domains, user_keywords):
    mList_input.clear()
    for domain in user_domains:
        mList_input.append(inv_valdict[domain])
    print(f"Ministries selected: {mList_input}")
    if not mList_input:
        print("No ministries selected. Exiting...")
        empty_domains.set()
        return -1
    await egz_extract_pdfs(today.month, today.year, mList_input, user_keywords)
    await ais_extract_pdfs()
    eve_sig.set()
    return 0
'''
try:
    import datetime
    today = datetime.datetime.now()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("Booting up web driver...")
    p = sync_playwright().start()
    browser = p.chromium.launch(channel="msedge", headless=True)  
    context = browser.new_context(accept_downloads=True)
    page = egz_extract_defaults(context)
    ministries_list = list(valdict.values())
    #print(f"Ministries found: {ministries_list}")
    app = QApplication(sys.argv)
    print(f"keywords: {[i[0] for i in kwList]}")
    #sleep(60)
    window = HomePage([valdict[i] for i in mList_input], ministries_list, Keywords= [i[0] for i in kwList])
    window.show()
    window.start_button.clicked.connect(lambda: extract_mids(window, page, window.section1.frame.get_items(), [[i, False] for i in window.section2.frame.get_items()]))
    #ais_extract_pdf(context, draft_type="draft")
    sys.exit(app.exec())
    #egz_extract_pdfs(today.month, today.year, mList, kwList)
    #ais_extract_pdf(today)
except KeyboardInterrupt:
    print("Process interrupted by user.")
    browser.close()
    p.stop()
    sys.exit(app.exec())
'''
'''
try:
    import datetime
    today = datetime.datetime.now()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("Booting up web driver...")
    p = sync_playwright().start()
    browser = p.chromium.launch(channel="msedge", headless=True)  
    context = browser.new_context(accept_downloads=True)
    page = egz_extract_defaults(context)
    ministries_list = list(valdict.values())
    #print(f"Ministries found: {ministries_list}")
    app = QApplication(sys.argv)
    print(f"keywords: {[i[0] for i in kwList]}")
    #sleep(60)
    window = HomePage([valdict[i] for i in mList_input], ministries_list, Keywords= [i[0] for i in kwList])
    window.show()
    window.start_button.clicked.connect(lambda: extract_mids(window, page, window.section1.frame.get_items(), [[i, False] for i in window.section2.frame.get_items()]))
    #ais_extract_pdf(context, draft_type="draft")
    sys.exit(app.exec())
    #egz_extract_pdfs(today.month, today.year, mList, kwList)
    #ais_extract_pdf(today)
except KeyboardInterrupt:
    print("Process interrupted by user.")
    browser.close()
    p.stop()
    sys.exit(app.exec())
'''
