import requests, pickle
import os
from bs4 import BeautifulSoup
from logger import logger, retry
import pytesseract
from PIL import Image
import re
import pandas as pd


pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


class TAXGAPS:
    def __init__(self, login, password):
        self.url = 'https://xn--e1afmdfmbbibuf.xn--80ai4af.xn--p1acf/'
        self.session = requests.session()
        self.logger = logger
        self.cookies()
        self.login(login, password)

    def cookies(self, types='load', path="tax_cookies.pkl"):
        if types == 'save' or not os.path.exists(path):
            self.logger.info('Save cookies')
            with open(path, 'wb') as f:
                pickle.dump(self.session.cookies, f)
        elif types == 'load':
            self.logger.info('Load cookies')
            with open(path, 'rb') as f:
                self.session.cookies.update(pickle.load(f))

    def login(self, login, password):
        r = self.session.get(self.url)

        if 'Выход' in r.text:
            self.logger.info('in tax')
            return

        page = BeautifulSoup(r.text)
        token = page.find('meta', attrs={'name': "csrf-token"})['content']

        headers = {
            'authority': self.url,
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': self.url,
            'pragma': 'no-cache',
            'referer': self.url + 'login',
            'sec-ch-ua': '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
            'x-csrf-token': token,
            'x-requested-with': 'XMLHttpRequest',
        }

        r = self.session.post(self.url + 'login', data={
            '_csrf': token,
            'Login[identifier]': login,
            'Login[password]': password,
            'Login[rememberMe]': [
                '0',
                '1',
            ],
            'Login[source]': '0',
            'ajax': 'login-form',
        }, headers=headers)
        r = r.json()

        assert r['success'], r
        self.cookies('save')
        return

    @retry(3, 5)
    def get_info_from_inn(self, inns=[]):
        r = self.session.get(self.url + 'check-inn')

        if 'ИНН контрагентов' not in r.text or 'Войти' in r.text:
            raise ValueError('Мы не попали куда нужно или не авторизованы!')

        page = BeautifulSoup(r.text)
        token = page.find('meta', attrs={'name': "csrf-token"})['content']

        captcha_src = page.find('img', attrs={'id': 'checkinnform-verifycode-image'})['src']
        captcha_src = self.url + captcha_src[1:]
        captcha_r = self.session.get(captcha_src)

        path = 'captcha.jpg'
        if os.path.exists(path):
            os.remove(path)
        open(path, 'wb').write(captcha_r.content)

        img = Image.open(path)
        img = img.resize((int(3 * s) for s in img.size))

        # Распознавание, допустимы только цифры
        config = r'tessedit_char_whitelist=0123456789'
        captcha = pytesseract.image_to_string(img, config=config)
        captcha = ''.join(re.findall(r'\d+', captcha))

        r = self.session.post(self.url + 'check-inn', data={
            '_csrf': token,
            'CheckInnForm[inn]': '\n'.join([str(inn) for inn in inns]),
            'CheckInnForm[verifyCode]': captcha,
        })
        assert 'Неправильный проверочный код.' not in r.text

        page = BeautifulSoup(r.text)
        rows = [
            {table.find('th').get_text(): table.find('td').get_text(separator='\n')
             for table in row.findAll('table', attrs={'class': 'table detail-view organistaion-shortinfo-table'})
             }
            for row in page.findAll('div', attrs={'class': 'row organisation-result-wrap'})
        ]
        df = pd.DataFrame(rows)
        df.drop_duplicates(inplace=True)

        return df.reset_index(drop=True)


if __name__ == '__main__':
    tax = TAXGAPS('Сюда логин', 'Сюда пароль')
    df = tax.get_info_from_inn(inns=[123, 345, 678, 90])
    