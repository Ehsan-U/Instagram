import re
import sys
import time
from playwright._impl._api_types import TimeoutError
from playwright.sync_api import sync_playwright
import requests
import csv
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
import os
import json
from traceback import print_exc
import requests_cache
import copy
import pandas as pd
from playwright_stealth import stealth_sync


class LoginError(Exception):
    pass



class Instagram():
    headers = {
        # "Cookie": "datr=l9z6YyaU5VkGygR8pQyKS3kU; ig_nrcb=1; mid=Y_rcnQALAAEcNMJRyVn4AS5G8O9L; ig_did=18F74B00-A5B1-42FB-AB62-923A65AAB7DE; csrftoken=9ld9e7dnDwFDexgl3wtwIEcuTzu4cahA; ds_user_id=58392475638; sessionid=58392475638%3Av2dAD9D2wg91pE%3A18%3AAYfp7teywwiBnP15x4Dw_7IPvI9Bz2aQxGhBKJyeHA; rur=\"CLN\\05458392475638\\0541708923924:01f7fc7c59553ab557798b3d4e341a907218a6e31a33df2b9b9c50e40916b7dd1b9bc485\"", 
        # "Sec-Ch-Ua": "\"Chromium\";v=\"109\", \"Not_A Brand\";v=\"99\"", 
        # "X-Csrftoken": "9ld9e7dnDwFDexgl3wtwIEcuTzu4cahA", 
        "Accept": "*/*", 
        "X-Requested-With": "XMLHttpRequest", 
        # "X-Ig-App-Id": "936619743392459", 
        # "Sec-Ch-Ua-Platform": "\"Windows\"", 
        # "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.5414.120 Safari/537.36", 
        "Referer": "https://www.instagram.com/", 
        # "Sec-Fetch-Site": "same-origin", 
        # "Sec-Fetch-Dest": "empty", 
        "Host": "www.instagram.com", 
        "Accept-Encoding": "gzip, deflate", 
        # "Viewport-Width": "1680", 
        # "Sec-Fetch-Mode": "cors", 
        "Accept-Language": "en-US,en;q=0.9", 
        # "Sec-Ch-Ua-Mobile": "?0", 
        # "Sec-Ch-Prefers-Color-Scheme": "light", 
    }
    # session = requests_cache.CachedSession('cache')
    start_url = 'https://www.instagram.com/accounts/login/'



    def init_playwright(self):
        self.play = sync_playwright().start()
        self.page = self.play.chromium.launch(headless=False,channel="chrome").new_context().new_page()
        stealth_sync(self.page)

    def init_writer(self):
        self.file = open('results.csv', 'w', newline='', encoding='utf8')
        self.writer = csv.writer(self.file)
        self.writer.writerow(['Image', 'Username', 'Full_Name','Followers','Following','Posts','Email','Phone','City','Bio'])


    def reshape_cookies(self, cookies):
        if cookies:
            request_cookies = {}
            for cookie in cookies:
                name = cookie['name']
                del cookie['name']
                value = cookie['value']
                del cookie['value']
                cookie[name] = value
                request_cookies.update(cookie)
            request_cookies = {k:str(v) for k,v in request_cookies.items()}
            return request_cookies
        else:
            return None
    

    def load_locations(self):
        df = pd.read_excel('locations.xlsx')
        locations = df.location.values
        return locations


    def load_config(self):
        with open('config.json', 'r') as f:
            config = json.load(f)
        self.insta_user = config.get('credentials').get('instagram').get('username')
        self.insta_pass = config.get('credentials').get('instagram').get('password')
        self.gmail_user = config.get('credentials').get('gmail').get('username')
        self.gmail_pass = config.get('credentials').get('gmail').get('password')


    def load_cookies(self):
        if os.path.exists("./cookies.json"):
            with open("cookies.json", 'r') as f:
                data = json.load(f)
            cookies = data.get("cookies")
            app_id = data.get('app_id')
            self.cookies = self.reshape_cookies(copy.deepcopy(cookies))
            self.headers['X-Csrftoken'] = self.get_csrf(copy.deepcopy(cookies))
            self.headers['X-Ig-App-Id'] = app_id
            self.logged_in = True
            return True
        else:
            return False
        

    def save_cookies(self, cookies):
        with open("cookies.json", 'w') as f:
            json.dump(cookies, f)
            print(" [+] cookies saved!")


    @staticmethod
    def get_csrf(cookies):
        for cookie in cookies:
            if 'csrftoken' in cookie.get('name'):
                return cookie.get('value')


    def parse_user(self, response):
        if response:
            try:
                username = response.get("user").get("username")
                item = dict(
                    profile = response.get("user").get("profile_pic_url"),
                    username = username,
                    full_name = response.get("user").get("full_name"),
                    followers = response.get("user").get("follower_count"),
                    following = response.get("user").get("following_count"),
                    posts = response.get("user").get("media_count"),
                    email = response.get("user").get("public_email"),
                    phone = response.get("user").get("contact_phone_number"),
                    city = response.get("user").get("city_name"),
                    bio = response.get("user").get("biography")
                )
                self.writer.writerow(item.values())
                self.counter +=1
                print(f"\r [+] Records extracted: {self.counter}",end='')
            except Exception:
                print_exc()


    def parse_location(self, response):
        if response:
            user_ids = set(re.findall('(?:"user_id": ")(.*?)(?:")', json.dumps(response)))
            for user_id in user_ids:
                url = f"https://www.instagram.com:443/api/v1/users/{user_id}/info/"
                self.start_request(url, callback=self.parse_user, cookies=self.cookies, cached=True)
            

    def start_request(self, url=None, callback=None, cookies=None, cached=None):
        try:
            if cached:
                response = self.c_session.get(url, headers=self.headers, cookies=cookies).json()
            else:
                response = self.session.get(url, headers=self.headers, cookies=cookies).json()
        except Exception:
            print_exc()
            response = None
        else:
            callback(response)


    def login(self):
        self.load_config()
        self.init_playwright()
        try:
            self.page.goto(self.start_url)
            self.page.wait_for_selector("//input[@name='username']")
            self.page.locator("//input[@name='username']").type(self.insta_user, delay=0.2)
            self.page.locator("//input[@name='password']").type(self.insta_pass, delay=0.2)
            self.page.locator("//button[@type='submit']").click()
            self.page.wait_for_selector("//input[@name='username']", state="detached")
            self.page.wait_for_selector("//img[contains(@alt, 'profile')]")
        except TimeoutError:
            pass
        else:
            cookies = self.page.context.cookies()
            self.cookies = self.reshape_cookies(copy.deepcopy(cookies))
            app_id = re.search(r'(?:X-IG-App-ID"\:")(.*?)(?:")', self.page.content()).group(1)
            self.headers['X-Ig-App-Id'] = app_id.strip()
            self.headers['X-Csrftoken'] = self.get_csrf(copy.deepcopy(cookies))
            config = {
                'app_id': app_id,
                'cookies': copy.deepcopy(cookies),
            }
            self.save_cookies(config)
            self.logged_in = True
        finally:
            self.play.stop()
    

    def main(self):
        self.logged_in = False
        self.counter = 0
        self.err_counter = 1
        self.login_retry = 0
        self.session = requests.Session()
        self.c_session = requests_cache.CachedSession('cache')
        self.init_writer()
        if not self.load_cookies():
            self.login()
        if self.logged_in:
            locations = self.load_locations()
            for n,location in enumerate(locations, start=1):
                location_id = re.search('(?:locations/)(.*?)(?:/)', location).group(1)
                url = f"https://www.instagram.com/api/v1/locations/web_info/?location_id={location_id}"
                try:
                    self.start_request(url, callback=self.parse_location, cookies=self.cookies)
                except KeyboardInterrupt:
                    break
        self.file.close()
        print(f" [+] Finished")
        self.send_email()
        print(f" [+] Done")


    def send_email(self, subject='Alert', body='Completed', attachment='results.csv'):
        print(f" [+] Sending email")
        self.load_config()
        sender = "au85265@gmail.com"
        reciever = "au85265@gmail.com"
        msg = MIMEMultipart(body)
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = reciever
        with open(attachment, 'rb') as f:
            if self.counter:
                part = MIMEApplication(f.read(), Name='results.csv')
                part['Content-Disposition'] = f'attachment; filename="{part.get_filename()}"'
                msg.attach(part)
        smtp_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        smtp_server.login(self.gmail_user, self.gmail_pass)
        smtp_server.sendmail(sender, reciever, msg.as_string())
        smtp_server.quit()

i = Instagram()
i.main()