"""Integration tests for the single page front end."""

import os
import shlex
import shutil
import subprocess
import tempfile
import time

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sites.models import Site
from django.test import LiveServerTestCase

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions

from email_user.tests.factories import EmailUserFactory
from services.models import Service
from services.tests.factories import ProviderTypeFactory, ServiceFactory


class FrontEndTestCase(LiveServerTestCase):
    """End to end testing with selenium and express server."""

    @classmethod
    def setUpClass(cls):
        cls.log_dir = tempfile.mkdtemp()
        cls.log_file, cls.log_file_name = tempfile.mkstemp(dir=cls.log_dir)
        cls.express_url = 'http://localhost:9000/'
        cls.express = subprocess.Popen(
            shlex.split('gulp startExpress --config test --port 9000 --fast'),
            cwd=settings.PROJECT_ROOT, stdout=cls.log_file, stderr=cls.log_file)
        # Wait for server to be available
        time.sleep(1.5)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.express.terminate()
        super().tearDownClass()
        shutil.rmtree(cls.log_dir)

    def setUp(self):
        self.browser = webdriver.PhantomJS()
        # Set desktop size
        self.browser.set_window_size(1280, 600)
        # Django prior to 1.8 doesn't create the default site with the correct pk
        # See https://code.djangoproject.com/ticket/23945
        defaults = {
            'domain':  'example.com',
            'name': 'example.com',
        }
        Site.objects.get_or_create(pk=settings.SITE_ID, defaults=defaults)

    def tearDown(self):
        self.browser.quit()
        self.clear_storage()

    def assertHashLocation(self, expected):
        """Assert current URL hash."""

        current = urlparse(self.browser.current_url)
        self.assertEqual(current.fragment, expected)

    def clear_storage(self):
        """Clear all browser local storage."""
        # PhantomJS does not respect the --local-storage-path option
        # See https://github.com/ariya/phantomjs/issues/11596
        # Files are stored in ~/.qws/share/data/Ofi Labs/PhantomJS
        storage_path = os.path.expanduser('~/.qws/share/data/Ofi Labs/PhantomJS')
        full_path = os.path.join(storage_path, 'http_localhost_9000.localstorage')
        if os.path.exists(full_path):
            os.remove(full_path)

    def set_language(self, language='en'):
        """Helper to set language choice in the browser."""

        self.browser.get(self.express_url)
        form = self.wait_for_element('language-toggle')
        button = form.find_element_by_css_selector('[data-lang="%s"]' % language)
        button.click()

    def wait_for_element(self, selector, match=By.ID, timeout=2):
        return WebDriverWait(self.browser, timeout).until(
            expected_conditions.visibility_of_element_located((match, selector))
        )

    def wait_for_page_title_contains(self, title, timeout=2):
        return WebDriverWait(self.browser, timeout).until(
            expected_conditions.text_to_be_present_in_element(
                (By.CLASS_NAME, 'page-title'), title)
        )

    def wait_for_landing_page(self, timeout=2):
        return self.wait_for_element('landing-img', By.CLASS_NAME, timeout)

    def submit_form(self, form, data, button_class='submit'):
        for name, value in data.items():
            element = form.find_element_by_name(name)
            if element.tag_name.lower() == 'select':
                select = Select(element)
                select.select_by_visible_text(value)
            else:
                element.send_keys(value)
        form.find_element_by_class_name(button_class).click()

    def test_get_homepage(self):
        """Load the homepage."""

        self.browser.get(self.express_url)
        form = self.wait_for_element('language-toggle')
        self.assertTrue(form.is_displayed(), 'Language form should be visible.')

    def test_select_language(self):
        """Select user language."""

        self.set_language('fr')
        menu = self.wait_for_element('menu')
        language = menu.find_element_by_class_name('menu-item-language')
        self.assertEqual(language.text, 'Changer de langue', 'Menu should now be French')

    def test_login(self):
        """Login an existing user."""

        user = EmailUserFactory(password='abc123')
        self.set_language()
        menu = self.wait_for_element('menu')
        login = menu.find_elements_by_link_text('Login')[0]
        login.click()
        form = self.wait_for_element('form-login', match=By.CLASS_NAME)
        self.assertHashLocation('/login')
        data = {
            'email': user.email,
            'password': 'abc123',
        }
        self.submit_form(form, data)
        self.wait_for_element('services')
        self.assertHashLocation('/manage/service-list')

    def test_register(self):
        """Register for a new site account."""

        provider_type = ProviderTypeFactory()
        self.set_language()
        menu = self.wait_for_element('menu')
        registration = menu.find_elements_by_link_text('Provider Registration')[0]
        registration.click()
        form = self.wait_for_element('provider-form')
        self.assertHashLocation('/register')
        data = {
            'name': 'Joe Provider',
            'phone_number': '12-345678',
            'description': 'Test provider',
            'focal_point_name': 'John Doe',
            'focal_point_phone_number': '87-654321',
            'address': '1313 Mockingbird Lane, Beirut, Lebanon',
            'email': 'fred@example.com',
            'password1': 'foobar',
            'password2': 'foobar',
            'number_of_monthly_beneficiaries': '37',
            'type': provider_type.name,
        }
        self.submit_form(form, data, button_class='form-btn-submit')

        self.wait_for_page_title_contains('Submitted Successfully', timeout=5)
        self.assertHashLocation('/register/confirm')

    def test_duplicate_registration(self):
        """Notify user of attempted duplicate registration."""

        user = EmailUserFactory(password='abc123')
        provider_type = ProviderTypeFactory()
        self.set_language()
        menu = self.wait_for_element('menu')
        registration = menu.find_elements_by_link_text('Provider Registration')[0]
        registration.click()
        form = self.wait_for_element('provider-form')
        self.assertHashLocation('/register')
        data = {
            'name': 'Joe Provider',
            'phone_number': '12-345678',
            'description': 'Test provider',
            'focal_point_name': 'John Doe',
            'focal_point_phone_number': '87-654321',
            'address': '1313 Mockingbird Lane, Beirut, Lebanon',
            'email': user.email,
            'password1': 'foobar',
            'password2': 'foobar',
            'number_of_monthly_beneficiaries': '37',
            'type': provider_type.name,
        }
        self.submit_form(form, data, button_class='form-btn-submit')
        error = self.wait_for_element('label[for="id_email"] .error', match=By.CSS_SELECTOR)
        self.assertIn('email already exists', error.text)

    def test_confirm_registration(self):
        """New user activating their registration."""

        EmailUserFactory(
            password='abc123', is_active=False, activation_key='1234567890')
        self.set_language()
        self.browser.get(self.express_url + '#/register/verify/1234567890')
        self.wait_for_landing_page(timeout=5)

    def test_invalid_activation(self):
        """Show message for invalid activation code."""

        self.set_language()
        self.browser.get(self.express_url + '#/register/verify/1234567890')
        self.wait_for_page_title_contains('Your account activation Failed.', timeout=5)

    def test_text_list_search(self):
        """Find services by text based search."""

        service = ServiceFactory(status=Service.STATUS_CURRENT)
        self.set_language()
        menu = self.wait_for_element('menu')
        search = menu.find_elements_by_link_text('Search')[0]
        search.click()
        form = self.wait_for_element('search_controls')
        self.assertHashLocation('/search')
        form.find_element_by_name('filtered-search').send_keys(
            service.provider.name_en[:5])
        # Results are updated automatically as search characters are entered
        # Wait a sec to make sure we have the final results
        time.sleep(1)
        result = self.wait_for_element('.search-result-list > li', match=By.CSS_SELECTOR)
        name = result.find_element_by_class_name('name')
        self.assertEqual(name.text, service.name_en)

    def test_filtered_list_search(self):
        """Find services by type."""

        service = ServiceFactory(status=Service.STATUS_CURRENT)
        self.set_language()
        menu = self.wait_for_element('menu')
        search = menu.find_elements_by_link_text('Search')[0]
        search.click()
        form = self.wait_for_element('search_controls')
        self.assertHashLocation('/search')
        Select(form.find_element_by_name('type')).select_by_visible_text(
            service.type.name_en)
        controls = self.wait_for_element('map-toggle', match=By.CLASS_NAME)
        controls.find_element_by_name('map-toggle-list').click()
        result = self.wait_for_element('.search-result-list > li', match=By.CSS_SELECTOR)
        name = result.find_element_by_class_name('name')
        self.assertEqual(name.text, service.name_en)

    def test_localized_search(self):
        """Search options and results should be localized."""

        service = ServiceFactory(status=Service.STATUS_CURRENT)
        self.set_language('fr')
        menu = self.wait_for_element('menu')
        search = menu.find_elements_by_link_text('Recherche')[0]
        search.click()
        form = self.wait_for_element('search_controls')
        self.assertHashLocation('/search')
        Select(form.find_element_by_name('type')).select_by_visible_text(
            service.type.name_fr)
        controls = self.wait_for_element('map-toggle', match=By.CLASS_NAME)
        controls.find_element_by_name('map-toggle-list').click()
        try:
            result = self.wait_for_element('.search-result-list > li', match=By.CSS_SELECTOR)
            name = result.find_element_by_class_name('name')
            name_text = name.text
        except StaleElementReferenceException:
            # Hit a race where we got a search element but then the page replaced it
            result = self.wait_for_element('.search-result-list > li', match=By.CSS_SELECTOR)
            name = result.find_element_by_class_name('name')
            name_text = name.text
        self.assertEqual(name_text, service.name_fr)
