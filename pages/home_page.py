from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

class HomePage:
    """Page Object Model class for the 'Home' page."""

    def __init__(self, page: Page):
        """
        Constructor to initialize the Playwright page object
        and define all necessary locators.
        """
        self.page = page

        # ===== Locators =====
        # Use more robust/fallback selectors for default OpenCart markup
        self.lnk_my_account = page.locator('span:has-text("My Account")')  # primary
        self.lnk_my_account_fallback = page.locator('a[title="My Account"]')  # fallback

        self.lnk_register = page.locator('a:has-text("Register")')
        self.lnk_login = page.locator('a:has-text("Login")')

        # Search: try placeholder, then id-based container
        self.txt_search_box = page.locator('input[placeholder="Search"]')
        self.txt_search_box_fallback = page.locator('#search input[type="text"]')

        self.btn_search = page.locator('#search button[type="button"]')
        self.logo = page.locator('#logo')  # useful to wait for page to load

    # ===== Helper / Wait Methods =====

    def wait_for_page(self, timeout: int = 5000) -> None:
        """Wait until a key element is visible to consider the page loaded."""
        try:
            # prefer logo, fallback to search box
            self.logo.wait_for(state='visible', timeout=timeout)
        except PlaywrightTimeoutError:
            # last resort: wait for search box or my account link
            try:
                self.txt_search_box.wait_for(state='visible', timeout=1000)
            except PlaywrightTimeoutError:
                self.lnk_my_account.wait_for(state='visible', timeout=1000)

    def is_loaded(self) -> bool:
        """Return True if the home page appears to be loaded."""
        try:
            return self.logo.is_visible() or self.txt_search_box.is_visible() or self.lnk_my_account.is_visible()
        except Exception:
            return False

    # ===== Action Methods =====

    def get_home_page_title(self) -> str:
        """Return the title of the Home Page."""
        return self.page.title()

    def click_my_account(self):
        """Click on the 'My Account' link (use fallback if needed)."""
        try:
            if self.lnk_my_account.is_visible():
                self.lnk_my_account.click()
            else:
                self.lnk_my_account_fallback.click()
        except Exception as e:
            print(f"Exception in click_my_account: {e}")
            raise

    def click_register(self):
        """Click on the 'Register' link under My Account."""
        try:
            self.lnk_register.click()
        except Exception as e:
            print(f"Exception in click_register: {e}")
            raise

    def click_login(self):
        """Click on the 'Login' link under My Account."""
        try:
            self.lnk_login.click()
        except Exception as e:
            print(f"Exception in click_login: {e}")
            raise

    def enter_product_name(self, product_name: str):
        """Enter the product name into the search input box (use fallback if required)."""
        try:
            if self.txt_search_box.is_visible():
                self.txt_search_box.fill(product_name)
            else:
                self.txt_search_box_fallback.fill(product_name)
        except Exception as e:
            print(f"Exception in enter_product_name('{product_name}'): {e}")
            raise

    def click_search(self):
        """Click on the search button to initiate the product search."""
        try:
            self.btn_search.click()
        except Exception as e:
            print(f"Exception in click_search: {e}")
            raise

    def search_product(self, product_name: str):
        """Convenience method: enter product name and click search."""
        self.enter_product_name(product_name)
        self.click_search()
