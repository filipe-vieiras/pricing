import os
import time
import random
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from fake_useragent import UserAgent

# Carregar variáveis de ambiente (caso precise de credenciais)
load_dotenv()

class StaysPriceMonitor:
    def __init__(self):
        self.url = "https://stays.net/precos/"
        self.data = []
        self.setup_driver()
        
    def setup_driver(self):
        """Configura o driver do Selenium com opções para evitar detecção"""
        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        
        # Descomente a linha abaixo para executar em modo headless (sem interface gráfica)
        # options.add_argument("--headless")
        
        self.driver = uc.Chrome(options=options)
        
    def login_if_needed(self):
        """Realiza login caso seja necessário"""
        try:
            # Verifica se há um formulário de login
            login_form = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form[name='login'], .login-form"))
            )
            
            # Se encontrou o formulário, tenta fazer login
            username = os.getenv("STAYS_USERNAME")
            password = os.getenv("STAYS_PASSWORD")
            
            if not username or not password:
                print("Credenciais não encontradas nas variáveis de ambiente.")
                return False
            
            # Localiza campos de login e senha (ajuste os seletores conforme necessário)
            username_field = self.driver.find_element(By.ID, "username")
            password_field = self.driver.find_element(By.ID, "password")
            
            # Preenche os campos
            username_field.send_keys(username)
            password_field.send_keys(password)
            
            # Clica no botão de login
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
            login_button.click()
            
            # Aguarda redirecionamento após login
            WebDriverWait(self.driver, 10).until(
                EC.url_changes(self.driver.current_url)
            )
            
            print("Login realizado com sucesso.")
            return True
            
        except (TimeoutException, NoSuchElementException):
            # Se não encontrou formulário de login, não é necessário fazer login
            print("Login não necessário ou elementos não encontrados.")
            return True
    
    def handle_captcha(self):
        """Verifica e tenta lidar com captchas"""
        try:
            # Verifica se há captcha (ajuste os seletores conforme necessário)
            captcha = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".g-recaptcha, .captcha, #captcha"))
            )
            
            print("Captcha detectado! Aguardando intervenção manual...")
            # Aguarda tempo para intervenção manual
            time.sleep(30)
            return True
            
        except TimeoutException:
            # Se não encontrou captcha, continua normalmente
            return False
    
    def extract_prices(self, accommodations):
        """Extrai os preços para uma configuração específica de acomodações"""
        try:
            print(f"Extraindo preços para {accommodations} acomodações...")
            
            # Localiza o campo de entrada para quantidade (qty)
            try:
                # Tenta encontrar o campo de entrada pelo ID
                qty_input = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "qty"))
                )
                
                # Se não encontrar pelo ID, tenta pela classe e nome
                if not qty_input:
                    qty_input = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "input.qty[name='quantity']"))
                    )
                
                # Limpa o campo e insere o novo valor
                qty_input.clear()
                qty_input.send_keys(str(accommodations))
                print(f"Valor {accommodations} inserido no campo de acomodações.")
                
                # Localiza e clica no botão "calcular os melhores preços"
                calculate_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'calcular os melhores preços')]"))
                )
                calculate_button.click()
                print("Botão 'calcular os melhores preços' clicado.")
                
                # Aguarda o carregamento dos resultados
                time.sleep(5)
                
            except Exception as e:
                print(f"Não foi possível definir {accommodations} acomodações ou clicar no botão de cálculo: {e}")
                return
            
            # Extrai os dados dos cards de preço com base na estrutura HTML fornecida
            try:
                # Procura por todos os elementos de plano (cada plano está em um div elementor-widget-wrap)
                plan_containers = self.driver.find_elements(By.CSS_SELECTOR, "div.elementor-widget-wrap.elementor-element-populated")
                
                print(f"Encontrados {len(plan_containers)} containers de planos.")
                
                # Se não encontrar os containers, tenta uma abordagem alternativa
                if not plan_containers:
                    print("Tentando seletores alternativos para containers de planos...")
                    plan_containers = self.driver.find_elements(By.CSS_SELECTOR, ".card, .pricing-card, .col-xl-3")
                
                # Lista de nomes de planos conhecidos
                known_plan_names = ["SUPER ANFITRIÃO", "PROFISSIONAL", "ADMINISTRADOR", "AGÊNCIA"]
                
                # Extrai os dados de cada plano
                for i, container in enumerate(plan_containers):
                    try:
                        # Verifica se este container realmente contém informações de preço
                        # Alguns containers podem ser cabeçalhos ou outros elementos
                        price_element = None
                        try:
                            price_element = container.find_element(By.CSS_SELECTOR, ".price.lead-6.fw-600.text-dark, .price")
                        except NoSuchElementException:
                            # Tenta outros seletores para preço
                            try:
                                price_element = container.find_element(By.XPATH, ".//*[contains(text(), 'R$') and contains(text(), '/mês')]")
                            except NoSuchElementException:
                                # Se não encontrar preço, pula este container
                                continue
                        
                        # Extrai o nome do plano
                        plan_name = "Plano " + str(i+1)
                        try:
                            # Tenta encontrar o título do plano
                            plan_title = container.find_element(By.CSS_SELECTOR, "h3, h4, .card-title, .plan-title")
                            plan_name = plan_title.text.strip()
                        except NoSuchElementException:
                            # Se não encontrar, usa o nome conhecido pelo índice (se disponível)
                            if i < len(known_plan_names):
                                plan_name = known_plan_names[i]
                        
                        # Extrai o preço mensal
                        price_text = "N/A"
                        try:
                            if price_element:
                                price_text = price_element.text.strip()
                                if not price_text:
                                    # Tenta extrair componentes individuais
                                    try:
                                        currency = price_element.find_element(By.CSS_SELECTOR, ".curency").text
                                        amount = price_element.find_element(By.CSS_SELECTOR, ".calendar").text
                                        period = price_element.find_element(By.CSS_SELECTOR, "small").text
                                        price_text = f"{currency} {amount}{period}"
                                    except:
                                        pass
                        except:
                            pass
                        
                        # Extrai a porcentagem
                        percentage = "N/A"
                        try:
                            percentage_element = container.find_element(By.XPATH, ".//*[contains(text(), '%') and contains(text(), 'reserva')]")
                            percentage = percentage_element.text.strip()
                        except:
                            pass
                        
                        # Extrai o preço alternativo mensal e por unidade
                        alternative_monthly_price = "N/A"
                        per_unit_price = "N/A"
                        
                        try:
                            # Procura pelo elemento fixoplan
                            fixoplan_element = container.find_element(By.CSS_SELECTOR, "[id^='fixoplan']")
                            
                            # Extrai o preço mensal alternativo
                            try:
                                base_element = fixoplan_element.find_element(By.CSS_SELECTOR, ".base")
                                alternative_monthly_price = base_element.text.strip()
                            except:
                                pass
                            
                            # Extrai o preço por unidade
                            try:
                                fixo_element = fixoplan_element.find_element(By.CSS_SELECTOR, ".fixo")
                                per_unit_price = fixo_element.text.strip()
                            except:
                                pass
                        except:
                            # Tenta encontrar os elementos diretamente
                            try:
                                base_element = container.find_element(By.CSS_SELECTOR, ".base")
                                alternative_monthly_price = base_element.text.strip()
                            except:
                                pass
                            
                            try:
                                fixo_element = container.find_element(By.CSS_SELECTOR, ".fixo")
                                per_unit_price = fixo_element.text.strip()
                            except:
                                pass
                        
                        # Adiciona os dados extraídos
                        self.data.append({
                            "accommodations": accommodations,
                            "plan_name": plan_name,
                            "price": price_text,
                            "percentage": percentage,
                            "alternative_monthly_price": alternative_monthly_price,
                            "per_unit_price": per_unit_price,
                            "date_extracted": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        
                        print(f"Extraído: {plan_name} - {price_text} - {percentage} - Alt: {alternative_monthly_price} - Por unidade: {per_unit_price}")
                        
                    except Exception as e:
                        print(f"Erro ao extrair dados do container {i+1}: {e}")
                
                print(f"Extraídos dados de {len(self.data)} planos para {accommodations} acomodações.")
                
            except Exception as e:
                print(f"Erro ao extrair os elementos de preço: {e}")
            
        except Exception as e:
            print(f"Erro ao extrair preços para {accommodations} acomodações: {e}")
            print(f"Detalhes do erro: {str(e)}")
    
    def run(self):
        """Executa o monitoramento de preços"""
        try:
            # Acessa a página
            print(f"Acessando {self.url}...")
            self.driver.get(self.url)
            
            # Aguarda o carregamento inicial da página
            time.sleep(random.uniform(3, 5))
            
            # Verifica se é necessário login
            if not self.login_if_needed():
                print("Não foi possível fazer login. Encerrando.")
                return
            
            # Verifica se há captcha
            if self.handle_captcha():
                print("Captcha tratado. Continuando...")
            
            # Extrai preços para cada configuração de acomodações
            for accommodations in [5, 20, 100]:
                # Adiciona um atraso aleatório entre as extrações para evitar bloqueios
                if accommodations != 5:  # Não precisamos de atraso para a primeira execução
                    time.sleep(random.uniform(2, 4))
                
                # Extrai os preços para a configuração atual
                self.extract_prices(accommodations)
                
                # Após cada extração, voltamos à página inicial para garantir um estado limpo
                # Isso garante que o botão será clicado novamente para cada configuração
                if accommodations != 100:  # Não precisamos recarregar após a última extração
                    print("Recarregando a página para a próxima configuração...")
                    self.driver.refresh()
                    time.sleep(3)  # Aguarda o carregamento da página
            
            # Salva os dados extraídos
            self.save_to_excel()
            
        except Exception as e:
            print(f"Erro durante a execução: {e}")
        
        finally:
            # Fecha o navegador
            self.driver.quit()
            print("Monitoramento concluído.")

    def save_to_excel(self):
        """Salva os dados extraídos em um arquivo Excel"""
        if not self.data:
            print("Nenhum dado para salvar.")
            return
        
        # Cria um DataFrame com os dados extraídos
        df = pd.DataFrame(self.data)
        
        # Define o nome do arquivo com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/Users/filipevieira/Apps/pricing3/stays_prices_{timestamp}.xlsx"
        
        # Salva o DataFrame em um arquivo Excel
        df.to_excel(filename, index=False)
        print(f"Dados salvos em {filename}")

if __name__ == "__main__":
    monitor = StaysPriceMonitor()
    monitor.run()