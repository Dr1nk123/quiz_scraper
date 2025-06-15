from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import json
import os
from dotenv import load_dotenv
import difflib
from concurrent.futures import ThreadPoolExecutor
import threading
from queue import Queue
import traceback
from urllib.parse import urlparse, parse_qs

def setup_chrome():
    try:
        print("设置Chrome浏览器...")
        chrome_options = Options()
        
        # 设置Chrome路径
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(chrome_path):
            chrome_options.binary_location = chrome_path
        
        # 添加必要的选项
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--ignore-ssl-errors')
        chrome_options.add_argument('--allow-insecure-localhost')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        # 使用本地的ChromeDriver
        chromedriver_path = os.path.join(os.path.dirname(__file__), "chromedriver.exe")
        if not os.path.exists(chromedriver_path):
            print(f"错误：未找到ChromeDriver，请确保{chromedriver_path}文件存在")
            return None
            
        print(f"使用ChromeDriver: {chromedriver_path}")
        service = Service(chromedriver_path)
        
        print("创建Chrome实例...")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # 设置页面加载超时
        driver.set_page_load_timeout(30)
        # 设置脚本执行超时
        driver.set_script_timeout(30)
        
        print("Chrome实例创建成功！")
        return driver
    except Exception as e:
        print(f"设置Chrome时出错: {str(e)}")
        print("请确保：")
        print("1. Chrome浏览器已正确安装")
        print("2. Chrome浏览器版本与ChromeDriver版本匹配")
        print("3. chromedriver.exe 文件存在于程序同目录下")
        return None

def login_to_site(driver, username, password):
    if not driver:
        return False
        
    try:
        print("正在访问登录页面...")
        driver.get("输入你的登录页面") # 这边输入网站登录页面的重定向
        
        # 等待页面加载完成
        print("等待页面加载...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(3)  # 额外等待
        
        # 保存页面源码以供调试
        with open("login_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("已保存登录页面源码到 login_page.html")
        
        # 注入JSEncrypt库
        jsencrypt_script = """
        var script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jsencrypt/3.2.1/jsencrypt.min.js';
        document.head.appendChild(script);
        """
        driver.execute_script(jsencrypt_script)
        print("注入JSEncrypt库")
        time.sleep(3)  # 等待库加载
        
        # 获取加密盐值
        salt = driver.find_element(By.ID, "pwdEncryptSalt").get_attribute("value")
        print(f"获取到密码加密盐值: {salt}")
        
        # 执行密码加密的JavaScript代码
        encrypt_script = """
        function encryptPassword(password, salt) {
            var encrypt = new JSEncrypt();
            encrypt.setPublicKey('MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCxbNYHkL0pOKXJWUDb9E+Y4TXekr3S9k8Pu5zcG3wXZXVxvk1kPqDDn9+f4O8wZOqKnV6GVXlkX+WxvB6qn0UVFJSVXRktjQcTs7KqvS2SXqk3HtxSmGEJjF6X1gVn4qhRX8XOI1DNj4KXqhC5tIwqnr8N9PFPrGHD5EZGgQpOBQIDAQAB');
            var encrypted = encrypt.encrypt(password + salt);
            return encrypted;
        }
        return encryptPassword(arguments[0], arguments[1]);
        """
        encrypted_password = driver.execute_script(encrypt_script, password, salt)
        print("密码加密完成")
        
        def find_and_fill_element(by, value, input_value, description):
            try:
                print(f"查找{description}...")
                element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((by, value))
                )
                print(f"清除{description}现有内容...")
                driver.execute_script("arguments[0].value = ''", element)
                time.sleep(1)
                print(f"输入{description}...")
                driver.execute_script("arguments[0].value = arguments[1]", element, input_value)
                time.sleep(1)
                return True
            except Exception as e:
                print(f"处理{description}时出错: {str(e)}")
                return False
        
        # 尝试填写用户名
        if not find_and_fill_element(By.ID, "username", username, "用户名"):
            if not find_and_fill_element(By.NAME, "username", username, "用户名"):
                print("无法找到用户名输入框")
                return False
        
        # 填写明文密码到显示框
        if not find_and_fill_element(By.NAME, "passwordText", password, "明文密码"):
            print("无法找到明文密码输入框")
            return False
            
        # 填写加密后的密码到隐藏框
        if not find_and_fill_element(By.NAME, "password", encrypted_password, "加密密码"):
            print("无法找到加密密码输入框")
            return False
        
        print("查找登录按钮...")
        login_button = None
        button_locators = [
            (By.ID, "login_submit"),
            (By.CLASS_NAME, "auth_login_btn"),
            (By.NAME, "submit"),
            (By.XPATH, "//button[@type='submit']"),
            (By.XPATH, "//input[@type='submit']"),
            (By.XPATH, "//button[contains(text(), '登录')]"),
            (By.XPATH, "//a[contains(@class, 'login-btn')]")
        ]
        
        for locator in button_locators:
            try:
                login_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable(locator)
                )
                print(f"找到登录按钮: {locator}")
                break
            except:
                continue
        
        if not login_button:
            print("无法找到登录按钮")
            return False
        
        print("点击登录按钮...")
        try:
            login_button.click()
        except:
            try:
                driver.execute_script("arguments[0].click();", login_button)
            except Exception as e:
                print(f"点击登录按钮时出错: {str(e)}")
                return False
        
        # 等待登录完成并重定向
        print("等待登录完成和重定向...")
        time.sleep(15)  # 给足够的时间进行登录和重定向
        
        # 检查登录状态
        current_url = driver.current_url
        print(f"当前URL: {current_url}")
        
        if "输入URL" in current_url and "login" not in current_url.lower():# 这边添加一个判断条件，判断是否登录成功 URL输入网页登录成功的URL
            print("登录成功！")
            return True
        else:
            print("登录失败：未能成功重定向到目标页面")
            print("当前页面标题:", driver.title)
            print("页面源码已保存，请检查登录页面的具体问题")
            return False
            
    except Exception as e:
        print(f"登录过程中出错: {str(e)}")
        print("当前页面标题:", driver.title)
        print("当前URL:", driver.current_url)
        return False

def wait_and_find_element(driver, by, value, timeout=10):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except:
        return None

def wait_and_find_elements(driver, by, value, timeout=10):
    try:
        elements = WebDriverWait(driver, timeout).until(
            EC.presence_of_all_elements_located((by, value))
        )
        return elements
    except:
        return []
        
def get_quiz_id_from_url(url):
    """从URL中提取quiz id"""
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        quiz_id = query_params.get('id', ['unknown'])[0]
        return quiz_id
    except:
        return 'unknown'

def get_file_names(quiz_id):
    """根据quiz id生成对应的文件名"""
    json_file = f"quiz_bank_{quiz_id}.json"
    txt_file = f"quiz_bank_{quiz_id}.txt"
    return json_file, txt_file

def load_existing_questions(quiz_id):
    """从文件加载已存在的题库"""
    json_file, _ = get_file_names(quiz_id)
    try:
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                questions = json.load(f)
            print(f"从 {json_file} 加载了 {len(questions)} 个已存在的题目")
            return questions
        else:
            print(f"题库文件 {json_file} 不存在，将创建新题库")
            return []
    except Exception as e:
        print(f"加载题库时出错: {str(e)}")
        return []

def save_questions(questions, quiz_id):
    """保存题目到对应的文件"""
    json_file, txt_file = get_file_names(quiz_id)
    try:
        print(f"保存 {len(questions)} 个题目到 {json_file}")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        
        # 同时保存一个可读的文本版本
        print(f"保存可读版本到 {txt_file}")
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"测验ID: {quiz_id}\n")
            f.write("="*50 + "\n\n")
            for i, q in enumerate(questions, 1):
                f.write(f"题目 {i}：{q['question_text']}\n")
                f.write("选项：\n")
                for j, opt in enumerate(q['options'], 1):
                    f.write(f"  {j}. {opt}\n")
                f.write(f"答案：{q['correct_answer']}\n")
                f.write("\n" + "="*50 + "\n\n")
        print("保存完成！")
        return True
    except Exception as e:
        print(f"保存题目时出错: {str(e)}")
        return False

def is_question_exists(question, existing_questions):
    """检查题目是否已存在"""
    for existing_q in existing_questions:
        # 检查题目文本是否完全相同
        if question["question_text"] == existing_q["question_text"]:
            return True
        # 如果题目文本相似度很高（比如只是标点符号或空格不同），也认为是重复
        similarity = difflib.SequenceMatcher(None, 
            question["question_text"].replace(" ", "").replace("　", ""), 
            existing_q["question_text"].replace(" ", "").replace("　", "")
        ).ratio()
        if similarity > 0.95:  # 95%相似度
            return True
    return False

def create_driver():
    """创建一个新的WebDriver实例"""
    try:
        chrome_options = Options()
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(chrome_path):
            chrome_options.binary_location = chrome_path
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--ignore-ssl-errors')
        chrome_options.add_argument('--allow-insecure-localhost')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        chromedriver_path = os.path.join(os.path.dirname(__file__), "chromedriver.exe")
        if not os.path.exists(chromedriver_path):
            print(f"错误：未找到ChromeDriver，请确保{chromedriver_path}文件存在")
            return None
            
        service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.set_script_timeout(30)
        return driver
    except Exception as e:
        print(f"创建Chrome实例时出错: {str(e)}")
        return None

def process_review_link(driver, href, existing_questions, result_queue):
    """处理单个回顾链接的函数，用于多线程"""
    questions = []
    try:
        print(f"访问回顾链接: {href}")
        driver.get(href)
        time.sleep(2)  # 减少等待时间
        
        # 获取这次考试的所有题目
        while True:
            try:
                # 获取当前页面的题目
                all_questions = wait_and_find_elements(driver, By.CLASS_NAME, "que")
                for question in all_questions:
                    try:
                        # 获取题目文本
                        question_text = question.find_element(By.CLASS_NAME, "qtext").text.strip()
                        
                        # 检查是否已经存在这个题目
                        exists = False
                        for existing_q in existing_questions:
                            if existing_q["question_text"] == question_text:
                                exists = True
                                break
                                
                        if not exists:
                            # 获取所有选项
                            options = []
                            try:
                                answer_divs = question.find_elements(By.CSS_SELECTOR, ".answer .r0, .answer .r1")
                                for answer_div in answer_divs:
                                    option_text = answer_div.find_element(By.CSS_SELECTOR, ".flex-fill").text.strip()
                                    options.append(option_text)
                            except:
                                print("未找到选项")
                            
                            # 获取正确答案
                            try:
                                answer_element = question.find_element(By.CSS_SELECTOR, ".rightanswer")
                                correct_answer = answer_element.text.replace("正确答案是：", "").strip()
                            except:
                                correct_answer = "未能获取答案"
                            
                            # 保存题目和答案
                            new_question = {
                                "question_text": question_text,
                                "options": options,
                                "correct_answer": correct_answer
                            }
                            questions.append(new_question)
                            
                            print(f"发现新题目：")
                            print(f"题目：{question_text}")
                            print("选项：")
                            for j, opt in enumerate(options, 1):
                                print(f"{j}. {opt}")
                            print(f"答案：{correct_answer}")
                            print("-" * 50)
                        else:
                            print("题目已存在，跳过")
                        
                    except Exception as e:
                        print(f"获取题目和答案时出错: {str(e)}")
                        continue
                
                # 尝试找下一页按钮
                try:
                    next_page = driver.find_element(By.CSS_SELECTOR, ".mod_quiz-next-nav")
                    if not next_page:
                        print("没有更多页面")
                        break
                        
                    print("点击下一页...")
                    next_page_href = next_page.get_attribute("href")
                    if next_page_href:
                        print(f"直接访问下一页: {next_page_href}")
                        driver.get(next_page_href)
                    else:
                        driver.execute_script("arguments[0].click();", next_page)
                    time.sleep(2)  # 减少等待时间
                except:
                    print("没有下一页了")
                    break
                    
            except Exception as e:
                print(f"处理页面时出错: {str(e)}")
                break
                
    except Exception as e:
        print(f"处理回顾链接时出错: {str(e)}")
        traceback.print_exc()
    
    # 将结果放入队列
    result_queue.put(questions)

def scrape_questions(driver, username, password, quiz_url, min_reviews=10):
    if not driver:
        return []
        
    try:
        # 从URL中获取quiz id
        quiz_id = get_quiz_id_from_url(quiz_url)
        print(f"当前测验ID: {quiz_id}")
        
        # 加载已存在的题库
        existing_questions = load_existing_questions(quiz_id)
        new_questions = []
        
        print(f"访问测试页面: {quiz_url}")
        driver.get(quiz_url)
        time.sleep(3)  # 减少等待时间
        
        # 首先检查是否需要重新登录
        if "login" in driver.current_url.lower():
            print("检测到需要重新登录...")
            if not login_to_site(driver, username, password):
                print("重新登录失败")
                return []
            driver.get(quiz_url)
            time.sleep(3)  # 减少等待时间
        
        attempts_count = 0
        max_attempts = 15
        
        while attempts_count < max_attempts:
            # 检查当前页面上的回顾按钮数量
            review_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), '回顾')]")
            current_reviews = len(review_buttons)
            print(f"当前有 {current_reviews} 个回顾按钮")
            
            if current_reviews >= min_reviews:
                print(f"已找到足够的回顾按钮（{current_reviews}个），开始获取题库...")
                
                # 收集所有回顾按钮的href
                review_hrefs = []
                for button in review_buttons:
                    try:
                        href = button.get_attribute('href')
                        if href:
                            review_hrefs.append(href)
                    except:
                        continue
                
                # 创建结果队列
                result_queue = Queue()
                
                # 创建线程池
                with ThreadPoolExecutor(max_workers=4) as executor:
                    # 提交任务到线程池
                    futures = []
                    for href in review_hrefs:
                        future = executor.submit(process_review_link, driver, href, existing_questions, result_queue)
                        futures.append(future)
                    
                    # 等待所有任务完成
                    for future in futures:
                        future.result()
                
                # 从队列中收集所有结果
                while not result_queue.empty():
                    questions = result_queue.get()
                    new_questions.extend(questions)
                
                print(f"\n题库收集完成！总共获取到 {len(new_questions)} 个不重复的题目")
                
                # 合并新旧题库并保存
                if new_questions:
                    all_questions = existing_questions + new_questions
                    if save_questions(all_questions, quiz_id):
                        print(f"成功保存题库！当前题库共有 {len(all_questions)} 个题目")
                    else:
                        print("保存题库失败")
                
                return new_questions
            
            # 如果回顾按钮不够，继续答题
            print(f"回顾按钮数量不足（当前{current_reviews}个，需要{min_reviews}个），继续答题...")
            try:
                # 检查页面状态并处理不同情况
                try:
                    # 首先尝试查找"继续上次考试"按钮
                    continue_button = driver.find_element(By.XPATH, "//button[contains(text(), '继续上次考试')] | //input[@value='继续上次考试']")
                    if continue_button:
                        print("发现未完成的考试，点击继续...")
                        driver.execute_script("arguments[0].click();", continue_button)
                        time.sleep(3)
                        print("成功进入考试页面")
                except:
                    print("未找到继续上次考试按钮，尝试其他按钮...")
                    # 尝试查找"重新考试测验"按钮
                    try:
                        start_button = driver.find_element(By.XPATH, "//button[contains(text(), '重新考试测验')] | //input[@value='重新考试测验']")
                        if start_button:
                            print("点击重新考试测验...")
                            driver.execute_script("arguments[0].click();", start_button)
                            time.sleep(3)
                    except:
                        print("未找到重新考试测验按钮")
                
                # 直接结束考试
                print("准备结束考试...")
                try:
                    # 尝试多种方式查找结束考试链接
                    finish_link = None
                    try:
                        finish_link = driver.find_element(By.CSS_SELECTOR, "a.endtestlink")
                    except:
                        try:
                            finish_link = driver.find_element(By.XPATH, "//a[contains(text(), '结束考试')]")
                        except:
                            try:
                                finish_link = driver.find_element(By.CSS_SELECTOR, "a[href*='summary.php']")
                            except:
                                print("未能找到结束考试链接")
                    
                    if finish_link:
                        print("找到结束考试链接，准备点击...")
                        driver.execute_script("arguments[0].click();", finish_link)
                        time.sleep(2)
                        
                        # 处理未完成提示，点击确认交卷按钮
                        try:
                            confirm_button = None
                            try:
                                confirm_button = driver.find_element(By.CSS_SELECTOR, "input[value='交卷结束考试']")
                            except:
                                try:
                                    confirm_button = driver.find_element(By.XPATH, "//button[text()='交卷结束考试']")
                                except:
                                    try:
                                        confirm_button = driver.find_element(By.XPATH, "//*[contains(text(), '交卷结束考试')]")
                                    except:
                                        print("未能找到确认交卷按钮")
                            
                            if confirm_button:
                                print("找到确认交卷按钮，准备点击...")
                                driver.execute_script("arguments[0].click();", confirm_button)
                                time.sleep(2)
                                
                                print("等待最终确认对话框...")
                                time.sleep(1)
                                
                                # 再次点击最终确认按钮
                                final_confirm = None
                                try:
                                    final_confirm = driver.find_element(By.CSS_SELECTOR, "input[value='交卷结束考试']")
                                except:
                                    try:
                                        final_confirm = driver.find_element(By.XPATH, "//button[text()='交卷结束考试']")
                                    except:
                                        try:
                                            final_confirm = driver.find_element(By.XPATH, "//*[contains(text(), '交卷结束考试')]")
                                        except:
                                            print("未能找到最终确认按钮")
                                
                                if final_confirm:
                                    print("找到最终确认按钮，准备点击...")
                                    driver.execute_script("arguments[0].click();", final_confirm)
                                    time.sleep(3)
                                    print("已完成交卷确认")
                                    
                                    # 点击返回本站首页按钮
                                    try:
                                        home_button = None
                                        try:
                                            home_button = driver.find_element(By.CSS_SELECTOR, "input[value='返回本站首页']")
                                        except:
                                            try:
                                                home_button = driver.find_element(By.XPATH, "//form[@action='../index.php']//input[@type='submit']")
                                            except:
                                                try:
                                                    home_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
                                                except:
                                                    print("未能找到返回首页按钮")
                                        
                                        if home_button:
                                            print("找到返回首页按钮，准备点击...")
                                            driver.execute_script("arguments[0].click();", home_button)
                                            time.sleep(3)
                                            
                                            # 直接访问登录页面
                                            print("访问登录页面...")
                                            driver.get("https://输入你的登录页面")#   还是一个重定向的登录页面
                                            time.sleep(3)
                                            
                                            # 重新登录
                                            print("重新登录系统...")
                                            if login_to_site(driver, username, password):
                                                print("重新登录成功，访问测试页面...")
                                                driver.get(quiz_url)
                                                time.sleep(3)
                                            else:
                                                print("重新登录失败")
                                                return []
                                        else:
                                            print("未找到返回首页按钮")
                                            return []
                                    except Exception as e:
                                        print(f"点击返回本站首页按钮时出错: {str(e)}")
                                        return []
                                else:
                                    print("未找到最终确认按钮")
                                    return []
                            else:
                                print("未找到确认交卷按钮")
                                return []
                        except Exception as e:
                            print(f"处理确认对话框时出错: {str(e)}")
                            return []
                    else:
                        print("未找到结束考试链接")
                        return []
                except Exception as e:
                    print(f"结束考试时出错: {str(e)}")
                    return []
                
            except Exception as e:
                print(f"处理考试页面时出错: {str(e)}")
                return []
            
            attempts_count += 1
            print(f"已完成第 {attempts_count} 次尝试，继续收集...")
        
        print(f"达到最大尝试次数（{max_attempts}次），但未能收集到足够的题目")
        return new_questions
        
    except Exception as e:
        print(f"抓取题目时出错: {str(e)}")
        return []

def main():
    try:
        print("开始运行爬虫程序...")
        
        # 加载环境变量
        print("读取登录信息...")
        load_dotenv("user.env")
        username = os.getenv("QUIZ_USERNAME")
        password = os.getenv("QUIZ_PASSWORD")
        
        if not username or not password:
            print("错误：未能从user.env文件中读取用户名或密码")
            print(f"实际读取到的用户名: {username}")
            print(f"实际读取到的密码: {password}")
            return
        
        print(f"从环境文件读取到的用户名: {username}")
        print(f"从环境文件读取到的密码长度: {len(password) if password else 0}")
        
        # 获取用户输入的测验ID
        print("\n请输入测验ID (例如: 2573)")
        quiz_id = input("测验ID: ").strip()
        
        # 验证ID格式
        if not quiz_id.isdigit():
            print("错误：无效的ID格式！ID必须是数字")
            return
            
        # 构造完整的URL
        quiz_url = f"https://{quiz_id}"# URL    具体的URL拼接
        print(f"将访问URL: {quiz_url}")
            
        # 获取用户指定的最小回顾数量
        while True:
            try:
                print("\n请输入需要收集的最小回顾数量（建议值：10）")
                min_reviews = int(input("回顾数量: ").strip())
                if min_reviews > 0:
                    break
                else:
                    print("错误：回顾数量必须大于0")
            except ValueError:
                print("错误：请输入一个有效的数字")
        
        # 设置Chrome
        driver = None
        try:
            driver = setup_chrome()
            if not driver:
                print("无法启动Chrome浏览器，请检查Chrome安装状态")
                return
                
            # 登录
            if login_to_site(driver, username, password):
                # 抓取题目
                new_questions = scrape_questions(driver, username, password, quiz_url, min_reviews)
                if new_questions:
                    print(f"本次运行成功获取了 {len(new_questions)} 个新题目")
                else:
                    print("本次运行未能获取到任何新题目")
            else:
                print("登录失败！请检查用户名和密码是否正确")
        except Exception as e:
            print(f"程序运行出错: {str(e)}")
            traceback.print_exc()
        finally:
            if driver:
                print("关闭浏览器...")
                print("BY.2025.5.22 版本v2.0.1 由Drink编写")
                driver.quit()
    except Exception as e:
        print(f"主程序出错: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 