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
    
    def load_page(self, url):
        html = None
        with SB(
            uc=True,
        ) as sb:
            print(f"open: {url}")
            sb.uc_open_with_reconnect(url, 3)

            try:
                # video-wrap がDOMに出たらロード完了扱い
                sb.wait_for_element_present("a.btn-server.active", timeout=30)
                print("A necessary part loaded.")
                html = sb.get_page_source()
            except Exception as e:
                print("video-wrap not loaded:", e)
                html = sb.get_page_source()

            return html

    def complete_browser_process(self, url):
        html = None
        with SB(uc=True) as sb:
            print(f"open: {url}")
            sb.uc_open_with_reconnect(url, 3)

            try:
                # video-wrap is in DOM?
                sb.wait_for_element_present("a.btn-server.active", timeout=30)
                print("A necessary part loaded.")
                html = sb.get_page_source()
            except Exception as e:
                print("video-wrap not loaded:", e)
                html = sb.get_page_source()

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
    
    def get_iframe(self, html):
        soup = BeautifulSoup(html, "html.parser")
        vurl = soup.select_one(".btn-server.active").get("data-link")
        if vurl is None:
            print("vurl is not found.")
            return None
        bg = soup.select_one("#dz_video").get("bg")
        if bg is None:
            bg = "undefined"
        
        # This is a parent iframe url. Just for your info.
        # iframe_url = "https://lk1.supremejav.com/supjav.php?l="+vurl+"&bg="+bg
        
        reversed_vurl = vurl[::-1]

        return "https://lk1.supremejav.com/supjav.php?c="+reversed_vurl+"&bg="+bg
    
    def get_inner_iframe_html(self, iframe_url):
        headers = {
            "referer": "https://supjav.com/"
        }
        res = self.session.get(iframe_url, headers=headers)
        if res.status_code == 200 and res.text != "404":
            return res.text
        return None

    
    def run(self, url, path):
        # Finally, it is now faster than before!!
        html = self.load_page(url)
        if html is None:
            raise("It seems like the url you provided is not correct.")
        inner_iframe_url = self.get_iframe(html)
        iframe_html = self.get_inner_iframe_html(inner_iframe_url)
        if iframe_html is None:
            print("The fastest way was not working. Let's use an alternative way...")
            html, iframe_html = self.complete_browser_process(url)
        master_url = self.get_master_url(iframe_html)
        index_url = self.get_video_index(master_url)
        urls = self.get_video_urls(index_url)
        title = self.get_safe_title(html)
        downloader = Downloader()
        downloader.get_video(urls, path, title)