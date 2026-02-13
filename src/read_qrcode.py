from pyzbar.pyzbar import decode
from PIL import Image
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd


class ReadQrcode:
    def __init__(self):
        self.image_folder = "images"
        self.image_name = "4929540085854702461.jpg"
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    
    def read_qrcode(self, image_path):
        result = decode(Image.open(os.path.join(self.image_folder, self.image_name)))
        url = result[0].data.decode('utf-8')
        #URL teste
        #url2 = 'file:///C:/Users/Fabio/Documents/github/chatbot-telegram/DOCUMENTO%20AUXILIAR%20DA%20NOTA%20FISCAL%20DE%20CONSUMIDOR%20ELETR%C3%94NICA.html'
        return url

    def extract_nf_data(self, image_path):
        """Método principal para extrair dados da NF"""
        try:
            url = self.read_qrcode(image_path)

            if not url:
                print("Não foi possível ler o QR Code")
                return None

            options = Options()
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--user-agent=' + self.user_agent)
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-setuid-sandbox')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--memory-pressure-off')
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--disable-features=site-per-process')
            options.add_argument('--incognito')
            options.add_argument('--headless')
            options.add_argument('--disable-features=IsolateOrigins')

        

            driver = webdriver.Chrome(options=options)
            driver.get(url)

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "tabResult"))
            )
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            return self.extract_data_from_soup(soup)

        except Exception as e:
            print(f"Erro ao extrair dados da NF: {str(e)}")
            return None
        finally:
            if 'driver' in locals():
                driver.quit()

    def extract_data_from_soup(self, soup):
        """Método para extrair dados da NF a partir do BeautifulSoup"""
        #Shop info
        header = soup.find('div', {'class': 'txtCenter'})
        divs = header.find_all('div')
        
        #Items
        items = {}

        span_descricao = [i.text.strip() for i in soup.find_all('span', {'class': 'txtTit'}) if i.text.strip()]
        span_codigo = [i.text.split(':')[1].split(')')[0].strip() for i in soup.find_all('span', {'class': 'RCod'}) if i.text.strip()]
        span_quantidade = [i.text.strip().split(':')[1].strip() for i in soup.find_all('span', {'class': 'Rqtd'}) if i.text.strip()]
        span_unidade = [i.text.split(':')[1].strip() for i in soup.find_all('span', {'class': 'RUN'}) if i.text.strip()]
        span_valor_unitario = [i.text.strip().split(':')[1].strip() for i in soup.find_all('span', {'class': 'RvlUnit'}) if i.text.strip()]
        span_valor_total = [i.text.strip() for i in soup.find_all('span', {'class': 'valor'}) if i.text.strip()]

        for i in range(len(span_descricao)):
            items[str(i)] = {
                'descricao': span_descricao[i] if i < len(span_descricao) else '',
                'codigo': span_codigo[i] if i < len(span_codigo) else '',
                'quantidade': span_quantidade[i] if i < len(span_quantidade) else '',
                'unidade': span_unidade[i] if i < len(span_unidade) else '',
                'valor_unitario': span_valor_unitario[i] if i < len(span_valor_unitario) else '',
                'valor_total': span_valor_total[i] if i < len(span_valor_total) else '',
            }

        # Resumo da nota
        quantidade_itens = soup.find('span', {'class': 'totalNumb'})
        valor_total = soup.find('span', {'class': 'txtTit'})
        descontos = soup.find('span', {'class': 'txtTit'})
        valor_a_pagar = soup.find('span', {'class': 'txtTit'})
        valor_pago = soup.find('span', {'class': 'txtTit'})
        forma_pagamento = soup.find('span', {'class': 'txtTit'})
        impostos_totais = "a"


        return {
            'shop_info': {
                "loja": divs[0].text.strip(),
                "cnpj": divs[1].text.strip().split(':')[1].strip(),
                "endereco": divs[2].text.strip().replace('\n', '').replace('\t', ''),
            },
            'items': items
        }
    