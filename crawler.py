import typing as t
import pymongo
from time import sleep
from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains


_EMAIL_USER = "study.ai_172"
_EMAIL_PASSWORD = "NextPassword172#"

_MONGO_HOST = "localhost"
_MONGO_PORT = 27017
_MONGO_DB = "gb_course"
_MONGO_COLLECTION = "emails"

_START_URL = "https://account.mail.ru/login"

_DEFAULT_PAGE_LOAD_TIMEOUT = 1.5
_DEFAULT_CONDITIONAL_TIMEOUT = 10


@dataclass
class Email:
    url: str
    subject: str
    body: str
    date: str


def _login(driver):
    driver.get(_START_URL)

    sleep(_DEFAULT_PAGE_LOAD_TIMEOUT)
    login = WebDriverWait(driver, _DEFAULT_CONDITIONAL_TIMEOUT).until(
        EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='Account name']")
        )
    )
    login.send_keys(_EMAIL_USER)
    next_btn = driver.find_element(By.XPATH, "//button[@data-test-id='next-button']")
    next_btn.click()

    sleep(_DEFAULT_PAGE_LOAD_TIMEOUT)
    password = WebDriverWait(driver, _DEFAULT_CONDITIONAL_TIMEOUT).until(
        EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Password']"))
    )
    password.send_keys(_EMAIL_PASSWORD)
    submit_btn = driver.find_element(
        By.XPATH, "//button[@data-test-id='submit-button']"
    )
    submit_btn.click()


def _iterate_over_emails(driver) -> t.Generator[Email, None, None]:
    sleep(_DEFAULT_PAGE_LOAD_TIMEOUT)

    # wait for the page to load
    WebDriverWait(driver, _DEFAULT_CONDITIONAL_TIMEOUT).until(
        EC.presence_of_element_located(
            (By.XPATH, "//div[contains(@class, 'letter-list')]")
        )
    )

    actions = ActionChains(driver)

    need_to_exit = False
    collected_emails = {}

    while not need_to_exit:
        # get all emails
        email_links = driver.find_elements(
            By.XPATH,
            "//a[contains(@class, 'js-letter-list-item') and contains(@class, 'llc_normal')]",
        )

        # iterate over emails
        is_something_new = False
        for lnk_el in email_links:
            lnk = lnk_el.get_attribute("href")

            if lnk in collected_emails:
                continue

            email = _process_email(driver, lnk)
            yield email

            is_something_new = True
            collected_emails[lnk] = email

        if is_something_new:
            actions.move_to_element(lnk_el).perform()
        else:
            need_to_exit = True


def _process_email(driver, lnk) -> Email:
    driver.execute_script(f"window.open('{lnk}')")
    driver.switch_to.window(driver.window_handles[-1])
    try:
        sleep(_DEFAULT_PAGE_LOAD_TIMEOUT)

        subject_el = WebDriverWait(driver, _DEFAULT_CONDITIONAL_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, "//h2[@class='thread-subject']"))
        )

        date_el = driver.find_element(By.XPATH, "//div[@class='letter__date']")

        body_el = driver.find_element(By.XPATH, "//div[@class='letter__body']")

        return Email(
            url=lnk, subject=subject_el.text, body=body_el.text, date=date_el.text
        )
    finally:
        driver.close()
        driver.switch_to.window(driver.window_handles[-1])


def _save_to_mongo(email_list: t.List[Email]):
    conn = pymongo.MongoClient(host=_MONGO_HOST, port=_MONGO_PORT)
    db = conn[_MONGO_DB]
    collection = db[_MONGO_COLLECTION]

    for email in email_list:
        if collection.count_documents({"_id": email.url}) > 0:
            continue
        collection.insert_one(
            {
                "_id": email.url,
                "subject": email.subject,
                "body": email.body,
                "date": email.date,
            }
        )


def main():
    driver = webdriver.Chrome()

    # perform login
    try:
        _login(driver)

        email_list = []
        for email in _iterate_over_emails(driver):
            email_list.append(email)
    finally:
        driver.close()

    _save_to_mongo(email_list)


if __name__ == "__main__":
    main()
