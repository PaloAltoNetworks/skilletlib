from skilletlib import Panoply

from pytest_mock import mocker


def test_op_valid(mocker):
    p = Panoply()
    p.xapi = mocker.MagicMock()
    p.xapi.op = mocker.MagicMock()
    p.xapi.xml_document.return_value = 'hi there'
    p.xapi.xml_result.return_value = 'Hi there'
    results = p.execute_op('show system info')
    assert results == 'Hi there'
