import asyncio
from playwright.async_api import async_playwright
import pandas as pd
from datetime import datetime
import time
import os
import re
from dateutil import parser

BASE_URL = "https://database.eohandbook.com/database/"
INDEX_URL = f"{BASE_URL}missionindex.aspx"

async def get_mission_links(page):
    print(f"Fetching mission index from {INDEX_URL}...")
    await page.goto(INDEX_URL, wait_until="networkidle", timeout=90000)
    await page.wait_for_selector("a[href*='missionID=']", timeout=30000)
    
    links = await page.eval_on_selector_all("a[href*='missionID=']", """
        els => els.map(a => ({
            name: a.innerText.trim(),
            href: a.href,
            mission_id: a.href.split('missionID=')[1].split('&')[0]
        }))
    """)
    
    unique_links = {}
    for link in links:
        if link['href'] not in unique_links:
            unique_links[link['href']] = link
            
    print(f"Found {len(unique_links)} unique missions.")
    return list(unique_links.values())

async def extract_field_value(page, label_text):
    """
    Robust extraction using XPath to find the sibling div of a label.
    """
    try:
        value = await page.evaluate(f"""
            (labelStr) => {{
                const xpath = `//div[normalize-space()='${{labelStr}}']/following-sibling::div[1]`;
                const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                if (result) return result.innerText.trim();
                
                const xpath2 = `//div[normalize-space()='${{labelStr}}:']/following-sibling::div[1]`;
                const result2 = document.evaluate(xpath2, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                if (result2) return result2.innerText.trim();
 
                const xpath3 = `//div[.//text()[normalize-space()='${{labelStr}}']]/following-sibling::div[1]`;
                const result3 = document.evaluate(xpath3, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                if (result3) return result3.innerText.trim();
 
                const divs = Array.from(document.querySelectorAll('div, td'));
                const target = divs.find(d => {{
                    const t = d.innerText.trim().toLowerCase();
                    return t === labelStr.toLowerCase() || t === (labelStr.toLowerCase() + ':');
                }});
                if (target) {{
                    const next = target.nextElementSibling;
                    if (next) return next.innerText.trim();
                }}
                return "";
            }}
        """, label_text)
        return value if value else "N/A"
    except Exception:
        return "N/A"

async def get_mission_details(browser, mission_url):
    page = await browser.new_page()
    try:
        await page.goto(mission_url, wait_until="networkidle", timeout=60000)
        details = {}
        h3 = await page.query_selector('h3')
        details['Satellite Full Name'] = (await h3.inner_text()).strip() if h3 else "Unknown"
        details['Mission Agencies'] = await extract_field_value(page, 'Mission Agencies')
        details['Mission Status'] = await extract_field_value(page, 'Mission Status')
        details['Launch Date'] = await extract_field_value(page, 'Launch Date')
        details['EOL Date'] = await extract_field_value(page, 'EOL Date')
        details['Orbit Altitude'] = await extract_field_value(page, 'Orbit Altitude')
        details['NORAD Catalog #'] = await extract_field_value(page, 'NORAD Catalog #')
        details['International Designator'] = await extract_field_value(page, 'International Designator')
        
        # Filtering logic
        status = details['Mission Status'].lower()
        forbidden_statuses = ['planned', 'cancelled', 'mission complete', 'completed', 'complete']
        if any(s in status for s in forbidden_statuses if s):
            return None, []
        
        instrument_urls = await page.eval_on_selector_all("a[href*='instrumentsummary.aspx']", "els => els.map(a => a.href)")
        instrument_urls = list(set(instrument_urls))
        return details, instrument_urls
    except Exception as e:
        return None, []
    finally:
        await page.close()

async def get_instrument_details(browser, instrument_url):
    page = await browser.new_page()
    try:
        await page.goto(instrument_url, wait_until="networkidle", timeout=60000)
        details = {}
        h3 = await page.query_selector('h3')
        details['Instrument Full Name'] = (await h3.inner_text()).strip() if h3 else "Unknown"
        details['Resolution'] = await extract_field_value(page, 'Resolution')
        details['Swath'] = await extract_field_value(page, 'Swath')
        details['Accuracy'] = await extract_field_value(page, 'Accuracy')
        details['Waveband'] = await extract_field_value(page, 'Waveband')
        return details
    except:
        return None
    finally:
        await page.close()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        missions = await get_mission_links(page)
        all_data = []
        for i, m_link in enumerate(missions):
            print(f"[{i+1}/{len(missions)}] Checking: {m_link['name']}")
            details, inst_urls = await get_mission_details(browser, m_link['href'])
            if not details: continue
            if not inst_urls:
                row = details.copy(); row.update({'Instrument Full Name': 'None Listed'})
                all_data.append(row)
            else:
                for inst_url in inst_urls:
                    inst_details = await get_instrument_details(browser, inst_url)
                    if inst_details:
                        row = details.copy(); row.update(inst_details); all_data.append(row)
            if (i + 1) % 20 == 0:
                pd.DataFrame(all_data).to_excel("satellite_data_full.xlsx", index=False)
        pd.DataFrame(all_data).to_excel("satellite_data_full.xlsx", index=False)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
