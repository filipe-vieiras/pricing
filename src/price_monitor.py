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
    
    def extract_prices(self, accommodations, max_retries=3):
        """Extrai os preços para uma configuração específica de acomodações"""
        retries = 0
        while retries < max_retries:
            try:
                print(f"Extraindo preços para {accommodations} acomodações (tentativa {retries+1}/{max_retries})...")
                
                # Verifica se o driver ainda está ativo
                try:
                    # Tenta acessar o título da página para verificar se a sessão está ativa
                    self.driver.title
                except Exception as e:
                    print(f"Sessão do navegador perdida: {e}")
                    print("Reiniciando o navegador...")
                    self.setup_driver()
                    self.driver.get(self.url)
                    time.sleep(5)
                    self.login_if_needed()
                    
                # Localiza o campo de entrada para quantidade (qty)
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
                
                # MELHORIA 1: Aguarda o carregamento dos resultados de forma mais robusta
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".price"))
                    )
                    time.sleep(2)  # Pequeno atraso adicional para garantir carregamento completo
                except TimeoutException:
                    print("Timeout esperando pelos resultados de preço.")
                    # Continua mesmo assim, talvez os elementos estejam presentes mas não detectados
                
                # Extrai os dados dos cards de preço com base na estrutura HTML fornecida
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
                valid_data = []
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
                        
                        # Pula entradas com "Plano 12" ou outros planos genéricos não desejados
                        if plan_name == "Plano 12" or (plan_name.startswith("Plano ") and int(plan_name.split()[1]) > 4):
                            continue
                        
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
                        
                        # Se não encontrou um preço válido, pula este container
                        if price_text == "N/A" or not price_text:
                            continue
                        
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
                        
                        # Adiciona os dados extraídos à lista temporária
                        valid_data.append({
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
                
                # CORREÇÃO: Movido para fora do loop de containers
                # Adiciona apenas os dados válidos à lista principal
                self.data.extend(valid_data)
                print(f"Extraídos dados de {len(valid_data)} planos válidos para {accommodations} acomodações.")
                
                # MELHORIA 2: Verifica se dados foram coletados antes de prosseguir
                if not valid_data:
                    print(f"Nenhum dado válido encontrado para {accommodations} acomodações. Tentando novamente...")
                    retries += 1
                    continue
                
                # Se chegou até aqui sem erros, sai do loop de tentativas
                return
                
            except Exception as e:
                print(f"Erro na tentativa {retries+1}: {e}")
                retries += 1
                if retries < max_retries:
                    print(f"Tentando novamente em 10 segundos...")
                    time.sleep(10)
                    # Recarrega a página para tentar novamente
                    try:
                        self.driver.refresh()
                        time.sleep(5)
                    except:
                        # Se falhar ao recarregar, tenta reiniciar o navegador
                        print("Falha ao recarregar. Reiniciando o navegador...")
                        try:
                            self.driver.quit()
                        except:
                            pass
                        self.setup_driver()
                        self.driver.get(self.url)
                        time.sleep(5)
                        self.login_if_needed()
                else:
                    print(f"Número máximo de tentativas atingido para {accommodations} acomodações.")
                    return
        
        # REMOVER ESTE BLOCO DUPLICADO:
        # except Exception as e:
        #     print(f"Erro crítico ao extrair preços para {accommodations} acomodações: {e}")
        #     retries += 1
        #     if retries < max_retries:
        #         print("Tentando reiniciar o navegador...")
        #         try:
        #             self.driver.quit()
        #         except:
        #             pass
        #         self.setup_driver()
        #         self.driver.get(self.url)
        #         time.sleep(5)
        #         self.login_if_needed()
        #     else:
        #         print(f"Falha após {max_retries} tentativas. Pulando {accommodations} acomodações.")
        #         return

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
            
            # Define o intervalo de acomodações para extrair (de 5 a 199)
            accommodation_values = list(range(5, 200))
            
            # Comentando a linha abaixo para usar todos os valores de 5 a 199
            # accommodation_values = list(range(5, 200, 5))  # Usando passo de 5 para reduzir o número de requisições
            
            # Salva o último valor processado para permitir retomada
            last_processed_index = 0
            
            # Extrai preços para cada configuração de acomodações
            for i, accommodations in enumerate(accommodation_values):
                # Pula valores já processados em caso de retomada
                if i < last_processed_index:
                    print(f"Pulando {accommodations} acomodações (já processado)...")
                    continue
                
                # Adiciona um atraso aleatório entre as extrações para evitar bloqueios
                if i > 0:  # Não precisamos de atraso para a primeira execução
                    time.sleep(random.uniform(2, 4))
                
                # Extrai os preços para a configuração atual
                self.extract_prices(accommodations)
                
                # Atualiza o último valor processado
                last_processed_index = i + 1
                
                # Após cada extração, voltamos à página inicial para garantir um estado limpo
                if accommodations != accommodation_values[-1]:  # Não precisamos recarregar após a última extração
                    print("Recarregando a página para a próxima configuração...")
                    try:
                        self.driver.refresh()
                        time.sleep(3)  # Aguarda o carregamento da página
                    except Exception as e:
                        print(f"Erro ao recarregar a página: {e}")
                        print("Tentando reiniciar o navegador...")
                        try:
                            self.driver.quit()
                        except:
                            pass
                        self.setup_driver()
                        self.driver.get(self.url)
                        time.sleep(5)
                        self.login_if_needed()
                
                # Salvar dados parciais a cada 5 extrações para evitar perda de dados
                if i > 0 and i % 5 == 0:
                    print(f"Salvando dados parciais após {i+1} extrações...")
                    self.save_to_excel(partial=True)
            
            # Salva os dados extraídos
            self.save_to_excel()
            
        except Exception as e:
            print(f"Erro durante a execução: {e}")
            # Tenta salvar os dados coletados até o momento em caso de erro
            if self.data:
                print("Salvando dados coletados até o momento...")
                self.save_to_excel(error=True)
        
        finally:
            # Fecha o navegador
            try:
                self.driver.quit()
            except:
                pass
            print("Monitoramento concluído.")

    def save_to_excel(self, partial=False, error=False):
        """Salva os dados extraídos em um arquivo Excel"""
        if not self.data:
            print("Nenhum dado para salvar.")
            return
        
        # Cria um DataFrame com os dados extraídos
        df = pd.DataFrame(self.data)
        
        # Define o nome do arquivo com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_prefix = "stays_prices"
        if partial:
            filename_prefix += "_partial"
        if error:
            filename_prefix += "_error"
        
        filename = f"/Users/filipevieira/Apps/pricing3/{filename_prefix}_{timestamp}.xlsx"
        
        # Salva o DataFrame em um arquivo Excel
        df.to_excel(filename, index=False)
        print(f"Dados salvos em {filename}")

if __name__ == "__main__":
    monitor = StaysPriceMonitor()
    monitor.run()