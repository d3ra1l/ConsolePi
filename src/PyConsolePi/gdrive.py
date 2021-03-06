#!/etc/ConsolePi/venv/bin/python3

import os
import json
import socket
import os.path
import time

# -- google stuff --
from googleapiclient import discovery
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# -- GLOBALS --
TIMEOUT = 3   # socket timeout in seconds (for clustered/cloud setup)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.metadata']


class GoogleDrive:

    def __init__(self, log, hostname=None):
        self.log = log  # if log is not None else..
        self.hostname = socket.gethostname() if hostname is None else hostname
        self.creds = None
        self.file_id = None
        self.sheets_svc = None

    # Authenticate find file_id and build services
    def auth(self):
        if self.creds is None:
            self.creds = self.get_credentials()
        if self.file_id is None:
            self.file_id = self.get_file_id()
            if self.file_id is None:
                self.file_id = self.create_sheet()
        if self.sheets_svc is None:
            self.sheets_svc = discovery.build('sheets', 'v4', credentials=self.creds)

    # Google sheets API credentials - used to update config on Google Drive
    def get_credentials(self):
        log = self.log
        log.debug('[GDRIVE]: -->get_credentials() {}'.format(log.name))
        """
        Get credentials for google drive / sheets
        """
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        os.chdir('/etc/ConsolePi/cloud/gdrive/')
        if os.path.exists('.credentials/token.pickle'):
            with open('.credentials/token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    '.credentials/credentials.json', SCOPES)
                creds = flow.run_local_server()
            # Save the credentials for the next run
            with open('.credentials/token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        return creds

    # Google Drive Get File ID from File Name
    def get_file_id(self):
        # pylint: disable=maybe-no-member
        """
        Gets file id for ConsolePi.csv file on Google Drive
        Params: credentials object
        returns: id (or None if not found)
        """
        if self.creds is None:
            self.creds = self.get_credentials()
        
        service = discovery.build('drive', 'v3', credentials=self.creds)
        results = service.files().list(
            pageSize=10, fields="nextPageToken, files(id, name)", q="name='ConsolePi.csv'").execute()
        items = results.get('files', [])
        if not items:
            print('No files found.')
        else:
            for item in items:
                if item['name'] == 'ConsolePi.csv':
                    return item['id']

    # Create spreadsheet to store data if not found (get_file_id returns None)
    def create_sheet(self):
        # pylint: disable=maybe-no-member
        log = self.log
        service = self.sheets_svc
        log.info('[GDRIVE]: ConsolePi.csv not found on Gdrive. Creating ConsolePi.csv')
        spreadsheet = {
            'properties': {
                'title': 'ConsolePi.csv'
            }
        }
        spreadsheet = service.spreadsheets().create(body=spreadsheet,
                                                    fields='spreadsheetId').execute()
        return '{0}'.format(spreadsheet.get('spreadsheetId'))

    # Auto Resize gdrive columns to match content
    def resize_cols(self):
        # pylint: disable=maybe-no-member
        log = self.log
        service = self.sheets_svc
        body = {"requests": [{"autoResizeDimensions": {"dimensions": {"sheetId": 0, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 2}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=self.file_id,
            body=body).execute()
        log.debug('[GDRIVE]: resize_cols response: {}'.format(response))

    def update_files(self, data):
        # pylint: disable=maybe-no-member
        log = self.log
        log.debug('[GDRIVE]: -->update_files - data passed to function\n{}'.format(json.dumps(data, indent=4, sort_keys=True)))
        self.auth()
        spreadsheet_id = self.file_id
        service = self.sheets_svc

        # init remote_consoles dict, any entries in config not matching this ConsolePis hostname are added as remote ConsolePis
        value_input_option = 'USER_ENTERED'
        remote_consoles = {}
        cnt = 1
        data[self.hostname]['upd_time'] = int(time.time())  # Put timestamp (epoch) on data for this ConsolePi
        for k in data:
            found = False
            value_range_body = {
                "values": [
                    [
                        k,
                        json.dumps(data[k])
                    ]
                ]
            }

            # find out if this ConsolePi already has a row use that row in range
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id, range='A:B').execute()
            # TODO add exception catcher for HttpError 503 service currently unreachable with retries
            log.info('[GDRIVE]: Reading from Cloud Config') # .format(result.get('values')))
            if result.get('values') is not None:
                x = 1
                for row in result.get('values'):
                    if k == row[0]:  # k is hostname row[0] is column A of current row
                        cnt = x
                        found = True
                    else:
                        log.info('[GDRIVE]: {0} found on Google Drive Config'.format(row[0]))
                        remote_consoles[row[0]] = json.loads(row[1])
                        remote_consoles[row[0]]['source'] = 'cloud'
                    x += 1
                log.debug('[GDRIVE]: remote_ConsolePis Discovered from sheet: {0}, Count: {1}'.format(
                    json.dumps(remote_consoles) if len(remote_consoles) > 0 else 'None', str(len(remote_consoles))))
            range_ = 'a' + str(cnt) + ':b' + str(cnt)

            if found:
                log.info('[GDRIVE]: Updating ' + str(k) + ' data found on row ' + str(cnt) + ' of Google Drive config')
                request = service.spreadsheets().values().update(spreadsheetId=spreadsheet_id, range=range_,
                                                                 valueInputOption=value_input_option, body=value_range_body)
            else:
                log.info('[GDRIVE]: Adding ' + str(k) + ' to Google Drive Config')
                request = service.spreadsheets().values().append(spreadsheetId=spreadsheet_id, range=range_,
                                                                 valueInputOption=value_input_option, body=value_range_body)
            request.execute()
            cnt += 1
        self.resize_cols()
        return remote_consoles


if __name__ == '__main__':
    print('gdrive script is not standalone must be imported')
