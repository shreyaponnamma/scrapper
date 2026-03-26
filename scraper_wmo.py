import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import time
import os
import re

BASE_URL = "https://space.oscar.wmo.int"
SATELLITES_URL = f"{BASE_URL}/satellites"

async def get_satellite_links(page):
    print(f"Fetching full satellite list from {SATELLITES_URL}...")
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
            console.log('Target count:', totalTarget);
            
            const scrollBody = document.querySelector('.dataTables_scrollBody');
            if (!scrollBody) return [];
            
            let stagnationCount = 0;
            const maxStagnation = 40; 
            
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
                
                if (foundNew) stagnationCount = 0;
                else stagnationCount++;
                
                // If we reached the target or the bottom
                if (totalTarget > 0 && collected.size >= totalTarget) break;
                
                scrollBody.scrollTop += 800;
                await new Promise(r => setTimeout(r, 600));
                
                if (scrollBody.scrollTop + scrollBody.clientHeight >= scrollBody.scrollHeight - 10) {
                    // Quick nudge up and down to trigger any lazy loading
                    scrollBody.scrollTop -= 5;
                    await new Promise(r => setTimeout(r, 100));
                    scrollBody.scrollTop += 5;
                    await new Promise(r => setTimeout(r, 1000));
                }
            }
            
            return Array.from(collected.values());
        }
    """)
    
    print(f"Extraction complete. Found {len(links_data)} unique satellites.")
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
        
        if any(f in details['Sat_Status'].lower() for f in ['lost at launch', 'cancelled']):
            return None, []
            
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
                             const key = 'Char_' + h.replace(/\\u00A0/g, ' ').replace(/\\s+/g, '_');
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
        output_file = "oscar_satellite_data_full_perfection.xlsx"
        
        print(f"Collected {len(links)} satellites. Starting production extraction...")
        
        for i, sat_info in enumerate(links):
            print(f"[{i+1}/{len(links)}] Investigating: {sat_info['acronym']}")
            details, inst_urls = await get_satellite_details(browser, sat_info)
            if not details: continue
            
            valid_count += 1
            if not inst_urls:
                all_rows.append(details)
            else:
                for inst_url in inst_urls:
                    basic, chars = await get_instrument_details(browser, inst_url)
                    if not basic: 
                        all_rows.append(details.copy()); continue
                    if not chars:
                        row = details.copy(); row.update(basic); all_rows.append(row)
                    else:
                        for char_row in chars:
                            row = details.copy(); row.update(basic); row.update(char_row); all_rows.append(row)
            
            # Periodic save for full run
            if valid_count % 20 == 0:
                print(f"--- FULL PROGRESS SAVED (Count: {valid_count}) ---")
                pd.DataFrame(all_rows).to_excel(output_file, index=False)
        
        pd.DataFrame(all_rows).to_excel(output_file, index=False)
        await browser.close()
        print(f"Extraction complete. Data saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
