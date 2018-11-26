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
    try:
        # Search for the user email
        # (it's located on the left panel if the user is logged in)
        driver.find_element_by_xpath('//span[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{}")]'.format(user.lower()))
        debug_print('Already logged in', 2)
        return True
    except NoSuchElementException:
        debug_print('Not logged in', 1)
    return False


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


def get_green_days(ignored_days):
    # Get the days that where there are available spots for reservation
    days = []
    for day in driver.find_elements_by_xpath('//div[@class="box-color m-t-md sharp-shadow dark r m-l m-r"]'):
        # The status is either "<n> spots available" or "No spots available" or "<building>  <spot>"
        #  so the first word is only a valid integer when there are spots available
        #  (that are not already booked by you) so we use this as a check.
        try:
            free_spots = int(day.find_element_by_xpath('.//span[contains(@class,"_600")]').text.split(' ')[0])
            day_name = day.find_element_by_xpath('.//span[@class="pull-left _300"]/span').text.lower()

            # Don't send alert for ignored days if any is given
            if not (ignored_days and day_name in ignored_days):
                days.append({
                    'name': day_name,
                    'free_spots': free_spots,
                    'btn_more': day.find_element_by_xpath('.//button[contains(text(), "More")]'),
                    'btn_reserve': day.find_element_by_xpath('.//button[contains(text(), "Reserve")]'),
                })
                debug_print('{} spot(s) found for {}!'.format(free_spots, day_name), 1)
        except (ValueError, NoSuchElementException, StaleElementReferenceException):
            pass
    return days


def get_free_spots():
    # Cycle through the day boxes and collect those that have the 'Available' status message
    free_spots = []
    for spot in driver.find_elements_by_xpath('//div[@class="box"]'):
        try:
            spot_number = ' '.join(spot.find_element_by_xpath('.//h3[@class="text-ellipsis"]').text.split())
            if 'Available' in spot.get_attribute('innerHTML'):
                debug_print('{}: FREE'.format(spot_number), 2)
                free_spots.append({
                    'number': spot_number,
                    'btn_reserve': spot.find_element_by_xpath('.//button[contains(text(), "Reserve")]'),
                })
            else:
                debug_print('{}: OCCUPIED'.format(spot_number), 2)
        except StaleElementReferenceException:
            pass

    # Sort the results by the 'number' attribute before returning
    return sorted(free_spots, key=lambda k: k['number'])


def get_spot_by_number(spot_number, available_spots):
    # Check if spot number is in the available_spots list
    # returns the spot object or 'None' if it's not in the list
    for spot in available_spots:
        if spot['number'] == spot_number:
            return spot
    return None


def do_reservation(btn_reserve):
    # Clicks the provided 'Reserve' button. Waits for confirmation
    time.sleep(1)
    btn_reserve.click()
    debug_print('Waiting for reservation confirmation...', 2)
    try:
        driver.find_element_by_xpath('//div[contains(@class, "snackbar") and text() = "Successfully reserved"]')
        debug_print('Reservation confirmed', 1)
    except NoSuchElementException:
        debug_print('Captcha, refreshing', 1)
        refresh_page()


def reserve_spot(day):
    # Reverse a spot on a given day
    # In case multiple spots are available, it tries to reserve one from the preferred list
    debug_print('Reserving spot...', 1)

    if day['free_spots'] <= 0:
        # Do nothing if there aren't any free spots
        debug_print('No free spots, skipping', 1)
        return
    elif day['free_spots'] == 1:
        # If there's only one free spot simply reserve it
        debug_print('Only one spot available, reserving that one', 1)
        do_reservation(day['btn_reserve'])
        return
    else:
        # If there are multiple free spots, try to reserve the preferred ones first
        debug_print('Multiple spots are available, trying to reserve a preferred one', 1)
        original_url = driver.current_url
        day['btn_more'].click()
        free_spots = get_free_spots()
        for ps in preferred_spots:
            spot = get_spot_by_number(ps, free_spots)
            if spot:
                debug_print('Preferred spot {} is free, reserving'.format(ps), 1)
                do_reservation(spot['btn_reserve'])
                get_page(original_url)
                return
            else:
                debug_print('Preferred spot {} is not free, skipping'.format(ps), 1)

        # If none of the preferred spaces are available simply reserve the first one available
        if len(free_spots) > 0:
            do_reservation(free_spots[0]['btn_reserve'])
        get_page(original_url)


def refresh_if_needed():
    # Refresh page periodically (currently every hour)
    now = time.localtime()
    if now.tm_hour in [23, 0, 1] and now.tm_min == 0 and now.tm_sec == 0:
        debug_print('Refreshing page (new day)...', 1)
        refresh_page()
    elif now.tm_hour not in [22, 23, 0] and now.tm_min == 58 and now.tm_sec == 0:
        debug_print('Refreshing page (hourly)...', 1)
        refresh_page()


def get_page(page_url):
    driver.get(page_url)
    time.sleep(1)


def refresh_page():
    driver.refresh()
    time.sleep(1)


if __name__ == '__main__':
    # Handle command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('config_section', type=str, help='which section to use from config.ini')
    parser.add_argument('--ignore', nargs='+', help="don't send alerts for these days")
    parser.add_argument('-v', '--verbose', action='count', help="set the verbosity of the output e.g.: -vv", default=0)
    parser.add_argument('--headless', action='store_true', help="run browser in headless mode")
    args = parser.parse_args()
    verbosity = args.verbose

    # Login credentials
    with open('config.json', 'r') as f:
        config = json.load(f)
    config = config[args.config_section]
    user = config['user']
    password = config['password']
    url = config['url']
    # Try to reserve these spots first
    preferred_spots = config['preferred_spots']

    # Initialize webdriver
    debug_print('Starting driver...', 1)
    driver_options = webdriver.ChromeOptions()
    if args.headless:
        driver_options.add_argument('headless')
    driver_options.add_argument('user-data-dir=./chrome_profile')
    driver = webdriver.Chrome(chrome_options=driver_options)
    debug_print('Getting page...', 1)
    get_page(url + '/#/client')
    driver.implicitly_wait(5)

    # Start the main loop
    try:
        while True:
            # Refresh the page periodically to prevent session expiration
            refresh_if_needed()

            # Additional check for session expiration
            if not is_logged_in():
                login()

            # Here's where the magic happens
            green_days = get_green_days(args.ignore)
            for green_day in green_days:
                reserve_spot(green_day)

            # Sleep the main loop for a second to avoid being a resource hog
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        debug_print('Closing driver...', 1)
        driver.quit()
