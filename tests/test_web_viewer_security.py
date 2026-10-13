"""Browser regression tests for untrusted values in generated click handlers.

Install the browser extra and Chromium to run:
    pip install -e '.[dev,browser]'
    python -m playwright install chromium
    pytest tests/test_web_viewer_security.py -v
"""

import json
import os
from pathlib import Path

import pytest

playwright = pytest.importorskip('playwright.sync_api')
VIEWER = Path(os.environ.get('HL7_VIEWER_PATH', Path(__file__).parents[1] / 'hl7-viewer.html'))
MESSAGE = (
    'MSH|^~\\&|TEST|LAB|TEST|LAB|202610131200||ORU^R01|TEST001|P|2.5\r'
    'PID|1||TEST123||SYNTHETIC^PATIENT\r'
    'OBX|1|ST|TEST^Test||Synthetic value\r'
)
PAYLOAD = "ST');window.__viewer_xss = true;//"


@pytest.fixture(scope='module')
def browser():
    with playwright.sync_playwright() as manager:
        options = {'headless': True}
        if os.environ.get('CHROMIUM_PATH'):
            options['executable_path'] = os.environ['CHROMIUM_PATH']
        instance = manager.chromium.launch(**options)
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(VIEWER.resolve().as_uri())
    yield page
    context.close()
    assert not errors, errors


def parse(page, message=MESSAGE):
    page.locator('#msgInput').fill(message)
    page.get_by_role('button', name='Parse', exact=True).click()
    assert page.locator('#parsedBody .field-row').count() > 0


def assert_no_execution(page):
    assert page.evaluate('window.__viewer_xss === true') is False


def test_obx_datatype_does_not_execute_code(page):
    parse(page, MESSAGE.replace('|ST|', '|' + PAYLOAD + '|'))
    page.locator('[data-field-key="OBX-5"]').click()
    page.locator('#detailPanel .dtype-link').click()
    assert_no_execution(page)
    assert page.locator('#detailPanel .dtype-link').get_attribute('data-dtype') == PAYLOAD


def test_profile_datatype_does_not_execute_code(page):
    parse(page)
    profile = {'name': 'Synthetic profile', 'segments': {'PID': {'fields': {'5': {'dt': PAYLOAD}}}}}
    page.locator('#profileFile').set_input_files({
        'name': 'synthetic.json', 'mimeType': 'application/json',
        'buffer': json.dumps(profile).encode(),
    })
    playwright.expect(page.locator('#profileName')).to_have_text('Synthetic profile')
    page.locator('[data-field-key="PID-5"]').click()
    page.locator('#detailPanel .dtype-link').click()
    assert_no_execution(page)


@pytest.mark.parametrize('selector', ['.seg-toggle', '.expand-icon'])
def test_segment_keys_do_not_execute_code(page, selector):
    # Malformed segment identifiers are still untrusted input to the viewer.
    segment = "Z',event);window.__viewer_xss = true;//"
    parse(page, MESSAGE + segment + '|A^B\r')
    if selector == '.seg-toggle':
        page.locator('#parsedBody .seg-toggle').last.click()
    else:
        page.locator('#parsedBody .field-row').last.locator('.expand-icon').click()
    assert_no_execution(page)


def test_valid_navigation_and_stop_propagation_are_preserved(page):
    parse(page)
    row = page.locator('[data-field-key="PID-5"]')
    selected_before = page.locator('#parsedBody .field-row.selected').count()
    row.locator('.expand-icon').click()
    assert page.locator('tr.comp-row[data-parent-key="PID-5"].expanded').count() > 0
    assert page.locator('#parsedBody .field-row.selected').count() == selected_before
    row.click()
    page.locator('#detailPanel .dtype-link').click()
    playwright.expect(page.locator('#detailPanel h3')).to_have_text('Data Type: XPN')
    page.locator('#detailPanel .dtype-link').first.click()
    playwright.expect(page.locator('#detailPanel h3')).to_have_text('Data Type: FN')
    page.locator('#parsedBody .seg-toggle').first.click()
    assert page.locator('#parsedBody .hidden-collapse').count() > 0
    page.locator('#parsedBody .seg-toggle').first.click()
    assert page.locator('#parsedBody .hidden-collapse').count() == 0
