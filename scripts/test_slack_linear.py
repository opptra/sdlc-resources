import os
import pytest
import requests
from unittest.mock import patch, Mock

import json
import sys
import importlib.util

# Load slack_linear module directly from file
spec = importlib.util.spec_from_file_location('slack_linear', './scripts/slack_linear.py')
slack_linear = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slack_linear)

SlackLinear = slack_linear.SlackLinear

@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv('LINEAR_API_KEY', 'fake_token')
    monkeypatch.setenv('LINEAR_TEAM_ID', 'team-id-123')

@patch('requests.post')
def test_create_linear_issue_success(mock_post):
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {
        'data': {
            'issueCreate': {
                'success': True,
                'issue': {
                    'id': 'abc123',
                    'identifier': 'ENG-100',
                    'url': 'https://linear.app/opptra/issue/ENG-100'
                }
            }
        }
    }
    mock_post.return_value = mock_response

    sl = SlackLinear()
    result = sl.create_linear_issue('Test issue', 'Details')
    assert result['success'] is True
    assert result['issue']['id'] == 'abc123'

@patch('requests.post')
def test_handle_slack_event_calls_create_issue(mock_post):
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {
        'data': {
            'issueCreate': {
                'success': True,
                'issue': {
                    'id': 'abc123',
                    'identifier': 'ENG-100',
                    'url': 'https://linear.app/opptra/issue/ENG-100'
                }
            }
        }
    }
    mock_post.return_value = mock_response

    sl = SlackLinear()
    slack_event = {'text': 'New issue from Slack'}
    result = sl.handle_slack_event(slack_event)
    assert result['success'] is True
    assert result['issue']['identifier'] == 'ENG-100'

