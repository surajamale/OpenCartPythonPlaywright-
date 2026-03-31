import pytest
import allure
from pathlib import Path
from playwright.sync_api import expect

# ----------------------------------------------------------------------------
# STEP 1: CONFIGURATION AND OPTION HANDLING
# ----------------------------------------------------------------------------

# get configuration value


def get_config_value(config, option_name, default=None):
    """
    Safely retrieve an option from pytest config.
    Tries several name variants and falls back to pytest.ini or a default.
    """
    try:
        # Try exact name as provided (pytest stores options without leading dashes)
        return config.getoption(option_name)
    except Exception:
        # Try underscore/dash variants
        alt = option_name.replace("-", "_")
        try:
            return config.getoption(alt)
        except Exception:
            # Fallback to ini or provided default
            try:
                ini = config.getini(option_name)
                if ini:
                    return ini
            except Exception:
                pass
            return default

def _option_truthy(config, *names):
    """Return True if any of the provided option names resolve to a truthy value."""
    for name in names:
        val = get_config_value(config, name, default=None)
        if val in (True, "on", "true", "True", "1"):
            return True
    return False

# ----------------------------------------------------------------------------
# STEP 2: TEST HOOKS
# ----------------------------------------------------------------------------

# Keep hook to capture screenshots (uses Playwright page fixture provided by plugin)
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Pytest hook to capture screenshots on test failure and attach them to Allure reports.
    Also stores the 'call' report on the item as 'rep_call' so fixtures can know the test outcome.
    """
    outcome = yield
    report = outcome.get_result()

    # Always store the call-phase report so fixtures can check outcome after test finishes
    if report.when == "call":
        setattr(item, "rep_call", report)

    if report.when == "call" and report.failed:
        # Check common option names for screenshot-on-failure
        if _option_truthy(item.config, "screenshot-on-failure", "screenshot_on_failure", "screenshot"):
            page = item.funcargs.get("page")
            if page:
                screenshot_path = Path("screenshots") / f"{item.name}.png"
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    # Store a locator first and use expect() to wait for visibility.
                    # Prefer a logo element if present, otherwise fall back to body.
                    try:
                        locator = page.locator("#logo")
                        expect(locator).to_be_visible(timeout=2000)
                    except Exception:
                        try:
                            locator = page.locator("body")
                            expect(locator).to_be_visible(timeout=2000)
                        except Exception:
                            # If even the fallback fails, continue to attempt a screenshot anyway.
                            pass

                    page.screenshot(path=str(screenshot_path))
                    with open(screenshot_path, "rb") as f:
                        allure.attach(f.read(), name=f"{item.name}_screenshot", attachment_type=allure.attachment_type.PNG)
                except Exception:
                    # best-effort only
                    pass

# ----------------------------------------------------------------------------
# STEP 3: FIXTURE 1 - BROWSER CONTEXT CUSTOMIZATION
# ----------------------------------------------------------------------------

# Browser/context customization hook for pytest-playwright
@pytest.fixture(scope="function")
def browser_context_args(request):
    """
    Return kwargs for browser.new_context used by pytest-playwright.
    Do not attempt to launch browsers here — pytest-playwright handles that.
    """
    cfg = request.config
    args = {}

    # Video recording: check common option names (pytest-playwright may expose --video)
    if _option_truthy(cfg, "video", "record-video", "record_video"):
        args["record_video_dir"] = "reports/videos"

    # Extra args: example to set viewport or user agent could be added here
    # args["viewport"] = {"width": 1280, "height": 720}

    return args

# ----------------------------------------------------------------------------
# STEP 4: FIXTURE 2 - PAGE CREATION AND TEST ARTIFACT MANAGEMENT
# ----------------------------------------------------------------------------
@pytest.fixture(scope="function")
def page(request, browser):
    """
    Create a browser context and page using the pytest-playwright 'browser' fixture.
    This replaces the previous dependency on a non-existent 'browser_context' fixture.
    The fixture honors browser_context_args (if present), starts/stops tracing on the context,
    navigates to base_url, and attaches artifacts on failure.
    """
    base_url = get_config_value(request.config, "base_url", "http://localhost/opencart/upload/")
    tracing_enabled = _option_truthy(request.config, "trace", "tracing", "pw-trace")
    screenshot_opt = get_config_value(request.config, "screenshot", None) or get_config_value(request.config, "screenshot-on-failure", None)
    # video option not used directly here; browser_context_args may have set record_video_dir
    # video_opt = get_config_value(request.config, "video", None)

    # Obtain browser_context_args fixture value if present
    try:
        ctx_args = request.getfixturevalue("browser_context_args") or {}
    except Exception:
        ctx_args = {}

    # Create a new context and page under control of this fixture
    context = browser.new_context(**ctx_args)

    if tracing_enabled:
        try:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
        except Exception:
            # ignore if tracing not supported
            pass

    pg = context.new_page()
    pg.goto(base_url)

    yield pg

    # After test cleanup / artifact handling
    test_name = request.node.name
    test_failed = getattr(request.node, "rep_call", None) and request.node.rep_call.failed

    # Stop tracing and save if enabled
    if tracing_enabled:
        try:
            trace_path = Path(f"reports/traces/{test_name}_trace.zip")
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            context.tracing.stop(path=str(trace_path))
            if test_failed and trace_path.exists():
                allure.attach.file(str(trace_path), name=f"{test_name}_trace", attachment_type=allure.attachment_type.ZIP)
        except Exception:
            pass

    # Screenshot on failure (when requested)
    if test_failed and (screenshot_opt in ["on", "only-on-failure", True, "true", "on"]):
        screenshot_path = Path(f"reports/screenshots/{test_name}.png")
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            pg.screenshot(path=str(screenshot_path))
            allure.attach.file(str(screenshot_path), name=f"{test_name}_screenshot", attachment_type=allure.attachment_type.PNG)
        except Exception:
            pass

    # Video attachment when available and requested
    if test_failed and _option_truthy(request.config, "video", "record-video", "record_video"):
        try:
            video = getattr(pg, "video", None)
            video_path = video.path() if video else None
            if video_path and Path(video_path).exists():
                allure.attach.file(video_path, name=f"{test_name}_video", attachment_type=allure.attachment_type.WEBM)
        except Exception:
            pass

    # Ensure context is closed
    try:
        context.close()
    except Exception:
        pass
