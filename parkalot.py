import argparse
import json
import time
from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException


def debug_print(message, verbosity_level):
    if verbosity_level <= verbosity:
        print(log_prefix() + message)


def log_prefix():
    # [HH:MM:SS]
    return '[{}] '.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


def is_logged_in():
    # Check if user is logged in
    return driver.current_url != login_url


def login():
    # Logs in the user
    debug_print('Logging in...', 1)
    driver.get(url + '/#/login')
    input_email = driver.find_element_by_xpath('//input[@type="email"]')
    input_password = driver.find_element_by_xpath('//input[@type="password"]')
    button_login = driver.find_element_by_xpath('//button[text()="Login"]')

    input_email.send_keys(user)
    input_password.send_keys(password)
    button_login.click()

    try:
        alert = driver.find_element_by_xpath('//div[contains(@class, "alert-danger")]')
    except NoSuchElementException:
        # No alert -> logged in successfully
        debug_print('Logged in successfully', 1)
    else:
        debug_print('Wrong login credentials!', 0)
        debug_print('Message: {}'.format(alert.text), 1)
        driver.quit()


def refresh_if_needed():
    # Refresh page periodically (currently every hour)
    now = time.localtime()
    if now.tm_hour in [23, 0, 1] and now.tm_min == 0 and now.tm_sec == 0:
        debug_print('Refreshing page (new day)...', 1)
        driver.refresh()
    elif now.tm_hour not in [22, 23, 0] and now.tm_min == 58 and now.tm_sec == 0:
        debug_print('Refreshing page (hourly)...', 1)
        driver.refresh()


if __name__ == '__main__':
    # Handle command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('profile', type=str, help='which profile to use from config.json')
    parser.add_argument('--ignore', nargs='+', help="don't send alerts for these days")
    parser.add_argument('-v', '--verbose', action='count', help="set the verbosity of the output e.g.: -vv", default=0)
    parser.add_argument('--headless', action='store_true', help="run browser in headless mode")
    args = parser.parse_args()
    verbosity = args.verbose

    # Login credentials
    with open('config.json', 'r') as f:
        config = json.load(f)
    config = config[args.profile]
    user = config['user']
    password = config['password']
    url = config['url']
    reservation_url = url + '/#/client'
    login_url = url + '/#/login'
    # Try to reserve these spots first
    preferred_spots = config['preferred_spots']

    # Initialize webdriver
    debug_print('Starting driver...', 1)
    driver_options = webdriver.ChromeOptions()
    if args.headless:
        driver_options.add_argument('headless')
    driver_options.add_argument('user-data-dir=./chrome_profile_' + args.profile)
    driver = webdriver.Chrome(chrome_options=driver_options)
    debug_print('Getting page...', 1)
    driver.get(reservation_url)
    driver.implicitly_wait(5)

    # Start the main loop
    try:
        while True:
            if driver.current_url != reservation_url:
                driver.get(reservation_url)

            # Refresh the page periodically to prevent session expiration
            refresh_if_needed()

            # Additional check for session expiration
            if not is_logged_in():
                login()

            # Here's where the magic happens
            try:
                debug_print('Looking for a reserve button', 2)
                btn = driver.find_element_by_xpath('.//button[contains(text(), "Reserve")]')
                debug_print('Found a spot, reserving', 1)
                btn.click()
            except (NoSuchElementException, StaleElementReferenceException):
                debug_print('Not found, trying again', 2)
                pass

    except KeyboardInterrupt:
        pass
    finally:
        debug_print('Closing driver...', 1)
        driver.quit()
