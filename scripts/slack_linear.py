import os
import requests

LINEAR_API_URL = 'https://api.linear.app/graphql'

class SlackLinear:
    def __init__(self):
        self.linear_token = os.getenv('LINEAR_API_KEY')
        self.headers = {
            'Authorization': f'Bearer {self.linear_token}',
            'Content-Type': 'application/json'
        }
        self.linear_team_id = os.getenv('LINEAR_TEAM_ID')  # Needed for issue creation

    def create_linear_issue(self, title: str, description: str = '') -> dict:
        query = '''
          mutation IssueCreate(: IssueCreateInput!) {
            issueCreate(input: ) {
              success
              issue {
                id
                identifier
                url
              }
            }
          }
        '''
        variables = {
            'input': {
                'teamId': self.linear_team_id,
                'title': title,
                'description': description
            }
        }
        payload = {
            'query': query,
            'variables': variables
        }
        response = requests.post(LINEAR_API_URL, json=payload, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        return data['data']['issueCreate']

    def handle_slack_event(self, slack_event: dict) -> dict:
        # This is a stub method to simulate parsing Slack event text for issue creation
        text = slack_event.get('text', '')
        # For simplicity, we treat the whole text as title
        created_issue = self.create_linear_issue(title=text)
        return created_issue

# Example CLI usage (basic)
if __name__ == '__main__':
    import sys
    import json

    if len(sys.argv) < 2:
        print('Usage: python scripts/slack_linear.py \'{"text": "issue title"}\'')
        sys.exit(1)

    event = json.loads(sys.argv[1])
    sl = SlackLinear()
    result = sl.handle_slack_event(event)
    print(json.dumps(result, indent=2))

