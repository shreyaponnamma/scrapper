import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import time
import os
import re
from dateutil import parser
from datetime import datetime

BASE_URL = "https://space.oscar.wmo.int"
SATELLITES_URL = f"{BASE_URL}/satellites"

async def get_satellite_links(page):
    print(f"Fetching full satellite list from {SATELLITES_URL}...")
    
    # Catch browser console logs
    page.on("console", lambda msg: print(f"  [Browser] {msg.text}"))
    
    await page.goto(SATELLITES_URL, wait_until="networkidle", timeout=120000)
    
    print("Waiting for satellite table to initialize...")
    try:
        await page.wait_for_selector(".dataTables_scrollBody", timeout=45000)
    except Exception as e:
        print(f"Warning: .dataTables_scrollBody not found. Proceeding with fallback.")
    
    print("Capturing all satellites via persistent scrolling...")
    
    links_data = await page.evaluate("""
        async () => {
            const collected = new Map();
            let totalTarget = 0;
            const infoEl = document.querySelector('.dataTables_info');
            if (infoEl) {
                const match = infoEl.innerText.match(/of ([\\d,]+) entries/);
                if (match) totalTarget = parseInt(match[1].replace(/,/g, ''));
            }
            console.log('Target count detected:', totalTarget);
            
            const scrollBody = document.querySelector('.dataTables_scrollBody');
            if (!scrollBody) {
                console.log('No scroll body found!');
                return [];
            }
            
            let stagnationCount = 0;
            const maxStagnation = 80; 
            let lastReportedSize = 0;
            
            let lastCollectedSize = -1;
            while (stagnationCount < maxStagnation) {
                const currentLinks = Array.from(document.querySelectorAll('a[href*="/satellites/view/"]'));
                let foundNew = false;
                
                currentLinks.forEach(a => {
                    const href = a.href;
                    if (href && !collected.has(href)) {
                        collected.set(href, {acronym: a.innerText.trim(), href: href});
                        foundNew = true;
                    }
                });
                
                if (foundNew) {
                    stagnationCount = 0;
                    console.log('Progress: ' + collected.size + ' / ' + totalTarget);
                    lastReportedSize = collected.size;
                } else {
                    stagnationCount++;
                }
                
                if (totalTarget > 0 && collected.size >= totalTarget) break;
                
                // Controlled scroll
                scrollBody.scrollTop += 400; 
                
                await new Promise(r => setTimeout(r, 800));
                
                if (stagnationCount > 0 && stagnationCount % 5 === 0) {
                    console.log('Searching... (scrolled to ' + scrollBody.scrollTop + ')');
                    scrollBody.scrollTop += 600;
                }
                
                if (scrollBody.scrollTop + scrollBody.clientHeight >= scrollBody.scrollHeight) {
                    // We hit the end of the scrollable area
                    if (stagnationCount > 30) break; // Give it some time to load more
                }
            }
            console.log('Final link collection count: ' + collected.size);
            return Array.from(collected.values());
        }
    """)
    
    print(f"Extraction complete. Found {len(links_data)} unique satellites.")
    if len(links_data) < 1000:
        print("Warning: Count is lower than expected 1000+. Scrolling might have skipped some.")
    return links_data

async def get_oscar_details(page, legend_text):
    """
    Robustly extracts all key-value pairs from a fieldset.
    """
    return await page.evaluate(f"""
        (targetLegend) => {{
            const legends = Array.from(document.querySelectorAll('legend'));
            const l = legends.find(el => el.innerText.toLowerCase().includes(targetLegend.toLowerCase()));
            if (!l) return {{}};
            
            const fieldset = l.parentElement;
            const results = {{}};
            
            // Standard table structure
            const rows = Array.from(fieldset.querySelectorAll('tr'));
            rows.forEach(tr => {{
                const cells = Array.from(tr.querySelectorAll('td, th'));
                for (let i = 0; i < cells.length - 1; i += 2) {{
                    const label = cells[i].innerText.replace(/\\u00A0/g, ' ').trim().replace(/:$/, '');
                    const value = cells[i+1].innerText.trim();
                    if (label && value && label.length < 50) {{
                        results[label] = value;
                    }}
                }}
            }});
            
            // Fallback for definition lists
            if (Object.keys(results).length === 0) {{
                const dts = Array.from(fieldset.querySelectorAll('dt'));
                dts.forEach(dt => {{
                    const label = dt.innerText.replace(/\\u00A0/g, ' ').trim().replace(/:$/, '');
                    const dd = dt.nextElementSibling;
                    if (dd && label.length < 50) {{
                        results[label] = dd.innerText.trim();
                    }}
                }});
            }}
            
            return results;
        }}
    """, legend_text)

async def get_satellite_details(browser, sat_info):
    page = await browser.new_page()
    try:
        await page.goto(sat_info['href'], wait_until="networkidle", timeout=60000)
        
        raw = await get_oscar_details(page, 'Satellite details')
        
        details = {
            'Sat_URL': sat_info['href'],
            'Sat_Acronym': raw.get('Acronym', sat_info['acronym']),
            'Sat_Full_Name': raw.get('Full name', raw.get('Full Name', 'N/A')),
            'Sat_Agency': raw.get('Space agency', raw.get('Space Agency', 'N/A')),
            'Sat_Status': raw.get('Status', 'N/A'),
            'Sat_Launch': raw.get('Launch', 'N/A'),
            'Sat_EOL': raw.get('EOL', 'N/A'),
            'Sat_Altitude': raw.get('Altitude', 'N/A')
        }
        
        # Exclusion Filters
        status_low = details['Sat_Status'].lower()
        excluded_statuses = ['lost at launch', 'cancelled', 'inactive', 'considered', 'planned', 'presumed inactive', 'presumable inactive']
        if any(f in status_low for f in excluded_statuses):
            return None, []
            
        # Launch Date Filter
        try:
            launch_date_str = details['Sat_Launch'].strip()
            if launch_date_str and launch_date_str != 'N/A':
                # Try to extract just the year or full date
                launch_date = parser.parse(launch_date_str, fuzzy=True)
                if launch_date > datetime.now():
                    return None, []
        except:
            pass

        inst_urls = await page.evaluate("""
            () => Array.from(new Set(Array.from(document.querySelectorAll('a[href*="/instruments/view/"]')).map(a => a.href)))
        """)
        
        return details, inst_urls
    except Exception as e:
        print(f"  Error on {sat_info['href']}: {e}")
        return None, []
    finally:
        await page.close()

async def get_instrument_details(browser, inst_url):
    page = await browser.new_page()
    try:
        await page.goto(inst_url, wait_until="networkidle", timeout=60000)
        
        raw_basic = await get_oscar_details(page, 'Instrument details')
        
        basic = {
            'Inst_Acronym': raw_basic.get('Acronym', 'N/A'),
            'Inst_Full_Name': raw_basic.get('Full name', raw_basic.get('Full Name', 'N/A')),
            'Inst_Description': raw_basic.get('Short description', raw_basic.get('Short Description', 'N/A')),
            'Inst_Scanning': raw_basic.get('Scanning Technique', 'N/A'),
            'Inst_Resolution': raw_basic.get('Resolution', 'N/A')
        }
        
        chars = await page.evaluate("""
            () => {
                const tables = Array.from(document.querySelectorAll('table'));
                const legends = Array.from(document.querySelectorAll('legend'));
                const legend = legends.find(l => l.innerText.toLowerCase().includes('detailed characteristics'));
                if (!legend) return [];
                const fieldset = legend.parentElement;
                const table = fieldset.querySelector('table');
                if (!table) return [];
                const rows = Array.from(table.querySelectorAll('tr'));
                if (rows.length < 1) return [];
                let headers = [];
                const thead = table.querySelector('thead');
                if (thead) {
                    headers = Array.from(thead.querySelectorAll('th, td')).map(h => h.innerText.trim());
                } else {
                    headers = Array.from(rows[0].querySelectorAll('th, td')).map(h => h.innerText.trim());
                }
                const dataRows = (thead) ? Array.from(table.querySelectorAll('tbody tr')) : rows.slice(1);
                return dataRows.map(tr => {
                    const r = {}; 
                    const cells = Array.from(tr.querySelectorAll('td'));
                    headers.forEach((h, i) => { 
                        if (h && cells[i]) {
                             const key = h.replace(/\\u00A0/g, ' ').replace(/\\s+/g, '_').toLowerCase();
                             r[key] = cells[i].innerText.trim(); 
                        }
                    });
                    return r;
                }).filter(r => Object.keys(r).length > 0);
            }
        """)
        return basic, chars
    except:
        return None, []
    finally:
        await page.close()

async def main():
    print("Starting Full WMO OSCAR Final Scraper (1000+ satellites)...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        list_page = await browser.new_page()
        
        links = await get_satellite_links(list_page)
        await list_page.close()
        
        if not links:
            print("No links found."); await browser.close(); return
            
        all_rows = []
        valid_count = 0
        output_file = "../raw_data/oscar_satellite_data_full_perfection.xlsx"
        
        print(f"Collected {len(links)} satellites. Starting production extraction...")
        
        # We use a semaphore to limit concurrency so we don't overwhelm the site
        sem = asyncio.Semaphore(5) 

        async def process_satellite(sat_info, index):
            nonlocal valid_count
            async with sem:
                print(f"[{index+1}/{len(links)}] Investigating: {sat_info['acronym']}")
                details, inst_urls = await get_satellite_details(browser, sat_info)
                if not details: 
                    return []
                
                sat_rows = []
                if not inst_urls:
                    sat_rows.append(details)
                else:
                    for inst_url in inst_urls:
                        basic, chars = await get_instrument_details(browser, inst_url)
                        if not basic: 
                            sat_rows.append(details.copy())
                            continue
                        
                        # Instrument Keyword Filter (Description Only)
                        inst_desc = basic.get('Inst_Description', '').lower()
                        if 'solar' in inst_desc or 'magnetosphere' in inst_desc:
                            continue 
                        
                        if not chars:
                            row = details.copy(); row.update(basic); sat_rows.append(row)
                        else:
                            for char_row in chars:
                                row = details.copy(); row.update(basic); row.update(char_row); sat_rows.append(row)
                
                if sat_rows:
                    valid_count += 1
                return sat_rows

        # Process in batches to allow periodic saving
        batch_size = 20
        for i in range(0, len(links), batch_size):
            batch = links[i:i+batch_size]
            tasks = [process_satellite(sat, i + j) for j, sat in enumerate(batch)]
            results = await asyncio.gather(*tasks)
            
            for res in results:
                if res:
                    all_rows.extend(res)
            
            print(f"--- PROGRESS SAVED (Sats processed: {i+len(batch)}/{len(links)}, Valid: {valid_count}) ---")
            pd.DataFrame(all_rows).to_excel(output_file, index=False)
        
        await browser.close()
        print(f"Extraction complete. Data saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
