import argparse
import json
import time
from datetime import date, datetime, timedelta

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException


class Day:
    free_spots, name, btn_reserve, btn_release, status_message, date, is_today, is_queue_active = [None] * 8

    def __init__(self, day_web_element, idx):
        self.date = (date.today() + timedelta(days=idx)).strftime('%Y-%m-%d')
        self.is_today = (idx == 0)

        try:
            self.free_spots = int(day_web_element.find_element_by_xpath('.//span[contains(@class,"_600")]').text.split(' ')[0])
        except (ValueError, NoSuchElementException, StaleElementReferenceException):
            pass

        try:
            self.name = day_web_element.find_element_by_xpath('.//span[@class="pull-left _300"]/span').text.lower()
        except (ValueError, NoSuchElementException, StaleElementReferenceException):
            pass

        try:
            self.btn_reserve = day_web_element.find_element_by_xpath('.//button[contains(text(), "Reserve")]')
        except (ValueError, NoSuchElementException, StaleElementReferenceException):
            pass

        try:
            self.btn_release = day_web_element.find_element_by_xpath('.//button[contains(text(), "Release")]')
        except (ValueError, NoSuchElementException, StaleElementReferenceException):
            pass

        try:
            msg = day_web_element.find_element_by_xpath('.//div[contains(@class, "r-b box-header p-x-md p-y-sm yellow-300")]').text
            if msg[0] == '':
                msg = msg[1:]
            self.status_message = msg
        except (ValueError, NoSuchElementException, StaleElementReferenceException):
            pass

        try:
            day_web_element.find_element_by_xpath('.//div[@class="modal-footer"]')
            self.is_queue_active = True
        except (ValueError, NoSuchElementException, StaleElementReferenceException):
            self.is_queue_active = False

    def __str__(self):
        return self.name + ' (' + self.date + '): ' + self.status

    @property
    def status(self):
        st = 'unavailable'

        if self.btn_release:
            st = 'reserved'

        if self.btn_reserve:
            st = 'free'

        if self.status_message:
            st += ' - ' + self.status_message

        return st

    @property
    def reservable(self):
        # don't reserve when already reserved
        if not self.btn_reserve:
            return False
        # when ignored don't reserve
        if self.ignored:
            return False
        # when the spot is for today and it's over 11:00 don't reserve
        if self.is_today and time.localtime().tm_hour >= 11:
            return False
        # don't reserve until the queue dialog is active

        # can be reserved in any other cases
        return True

    @property
    def releasable(self):
        # don't release if it's not reserved
        if not self.btn_release:
            return False
        # release if it's ignored
        if self.ignored:
            return True
        # when the spot is for today and it's over 19:00 release
        if self.is_today and time.localtime().tm_hour >= 19:
            return True
        # don't do anything in any other cases
        return False

    @property
    def ignored(self):
        return False

    def reserve(self):
        try:
            self.btn_reserve.click()
        except (ValueError, NoSuchElementException, StaleElementReferenceException):
            pass

    def release(self):
        try:
            self.btn_release.click()
        except (ValueError, NoSuchElementException, StaleElementReferenceException):
            pass


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


def get_days():
    # Get the days that where there are available spots for reservation
    ds = []
    for idx, day_web_element in enumerate(driver.find_elements_by_xpath('//div[@class="box-color m-t-md sharp-shadow dark r m-l m-r"]')):
        day = Day(day_web_element, idx)
        ds.append(day)
    return ds


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

    # Initialize webdriver
    debug_print('Starting driver...', 1)
    driver_options = webdriver.ChromeOptions()
    if args.headless:
        driver_options.add_argument('headless')
    driver_options.add_argument('user-data-dir=./chrome_profile_' + args.profile)
    driver = webdriver.Chrome(chrome_options=driver_options)
    debug_print('Getting page...', 1)
    driver.get(reservation_url)
    debug_print('Done', 1)

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
            days = get_days()
            for d in days:
                if d.reservable:
                    debug_print('{} ({}) is reservable, reserving...'.format(d.name, d.date), 1)
                    d.reserve()
                    debug_print('Done', 1)
                if d.releasable:
                    debug_print('{} ({}) is releasable, releasing...'.format(d.name, d.date), 1)
                    d.release()
                    debug_print('Done', 1)

            # Sleep the main loop for a second to avoid being a resource hog
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        debug_print('Closing driver...', 1)
        driver.quit()
