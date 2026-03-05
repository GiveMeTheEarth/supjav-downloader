import requests
import re
import subprocess
import os
import concurrent.futures
import time
import sys
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from seleniumbase import SB
import demjson3

from SegmentsDownload import Downloader

class supjav:
    def __init__(self):
        self.download_failed = False
        self.session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
        }
        self.session.headers.update(headers)

    def verify_success(self, sb):
        sb.assert_element('img[alt="Logo Assembly"]', timeout=4)
        sb.sleep(3)

    def get_safe_title(self, html, max_length=100):
        soup = BeautifulSoup(html, "html.parser")
        if soup is None: 
            raise ValueError("soup is None.")
        title = soup.find("h1")
        if title is None:
            raise ValueError("check the url!")
        if max_length:
            return re.sub(r'[\\/*?:"<>|\'() ]', '_', title.text)[:max_length]
        return re.sub(r'[\\/*?:"<>|\'() ]', '_', title.text)

    def is_page_loaded(self, sb) -> bool:
        return (
            sb.is_element_present("video") or
            sb.is_element_present("meta[property='og:title']") or
            sb.is_element_present("h1") or
            "supjav.com" in sb.get_current_url()
        )

    def is_captcha_page(self, sb) -> bool:
        return (
            sb.is_element_present('input[value*="Verify"]') or
            sb.is_text_visible("Checking your browser") or
            sb.is_text_visible("Verify you are human")
        )

    def complete_browser_process(self, url):
        html = None
        with SB(uc=True) as sb:
            print("open", flush=True)
            sb.uc_open_with_reconnect(url, 3)

            if self.is_captcha_page(sb):
                print("captcha loaded")
                if sb.is_element_visible('input[value*="Verify"]'):
                    sb.uc_click('input[value*="Verify"]')
                else:
                    sb.uc_gui_click_captcha()

                sb.sleep(3)

            if self.is_page_loaded(sb):
                print("page loaded")
                html = sb.get_page_source()
            else:
                print("page not loaded")
            if html and self.click_video_button(sb):
                if sb.wait_for_ready_state_complete():
                    iframe = sb.find_element("iframe#video")
                    sb.switch_to_frame(iframe)
                    inner_iframe = sb.find_element("iframe")
                    sb.switch_to_frame(inner_iframe)

                    iframe_html = sb.get_page_source()
                    return html, iframe_html

            raise Exception("CAPTCHA not bypassed or page not loaded")
        
    def click_video_button(self, sb):
        print("click video button")
        sel = "div#vserver.play-button"
        if sb.is_element_visible(sel):
            sb.uc_click(sel)
            sb.sleep(2)
            print("click complete")
            return True
    
    def get_master_url(self, html):
        soup = BeautifulSoup(html, "html.parser")
        body = soup.body
        if not body:
            return None

        for script in body.find_all("script"):
            code = script.get_text().lstrip()
            if code.startswith("const isMobile"):
                pattern = re.compile(
                    r"var\s+urlPlay\s*=\s*['\"]([^'\"]+)['\"]"
                )
                match = pattern.search(code)
                if match:
                    master_url = match.group(1)
                    print(f"master url: {master_url}")
                    return master_url
        return None
    
    def get_video_index(self, url):
        res = self.session.get(url)
        if res.status_code == 200:
            lines = res.text.strip().splitlines()
            best = {
                "width": 0,
                "height": 0,
                "url": None
            }

            for i in range(len(lines)):
                line = lines[i]

                if line.startswith("#EXT-X-STREAM-INF"):
                    # RESOLUTION=1920x1080 を抜く
                    m = re.search(r"RESOLUTION=(\d+)x(\d+)", line)
                    if not m:
                        continue

                    width = int(m.group(1))
                    height = int(m.group(2))

                    # 次の行が URL
                    if i + 1 < len(lines):
                        url = lines[i + 1].strip()

                        if height > best["height"]:
                            best["height"] = height
                            best["width"] = width
                            best["url"] = url

            print(f"resolution: width={best["width"]}, height={best["height"]}")
            print(f"index url: {best["url"]}")
            return best["url"]

    def get_video_urls(self, index_url):
        res = self.session.get(index_url)
        if res.status_code == 200:
            urls = re.findall(r'https?://[^\s]+', res.text)
            return urls
        return []
    
    def run(url, path):
        app = supjav()
        html, iframe_html = app.complete_browser_process(url)
        master_url = app.get_master_url(iframe_html)
        index_url = app.get_video_index(master_url)
        urls = app.get_video_urls(index_url)
        title = app.get_safe_title(html)
        downloader = Downloader()
        downloader.get_video(urls, path, title)