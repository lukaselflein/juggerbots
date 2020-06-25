
import argparse
import logging
import json 
import time
import os
import re
import pandas as pd
import pickle
import telegram

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


class GoogleSheet:
    """A google spreadsheet.
    The content is treated as a list of lists.
    Casting to pandas dataframes happens outside."""

    def __init__(self, sheet_id, sheet_range):
        """Handle login and default parameters."""
        creds = self.auth()
        service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
        self.sheet = service.spreadsheets()
        self.sheet_id = sheet_id
        self.sheet_range = sheet_range

    def auth(self):
        """Logs in to the Google API.
        The `credentials.json` secret file stores login information.
        Saves an access token in `token.pickle`."""

        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json',  # Login Credentials
                    ['https://www.googleapis.com/auth/drive.file'])  # read&write one file
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        return creds


    def read(self):
        result = self.sheet.values().get(spreadsheetId=self.sheet_id,
                                    range=self.sheet_range).execute()
        values = result.get('values', [])
        return values


    def write(self, values):
        body = { 'values': values}
        result = self.sheet.values().update(spreadsheetId=self.sheet_id,
                                       range=self.sheet_range,
                                       valueInputOption='USER_ENTERED',
                                       body=body).execute()
        return 'success'


    def append(self, values):
        initial_values = self.read()
        # Append to the old data:
        new_values = initial_values + values
        self.write(values=new_values)
        return 'success'


def check_connection(update, context):
    try:
        g_sheet = context.bot_data['google_sheet']
        return True
    except:
        return False


def read_secrets(path=None, token_name='pompfbot_token'):
    __location__ = os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__)))
    absolute_path = os.path.join(__location__, path)

    with open(path, 'r') as infile:
        json_dict = json.load(infile)
    api_token = json_dict[token_name]
    return api_token


def handle_data(text, update, context):
    """Extract names and scores from telegram input."""

    # eliminate double spaces
    clean_text = re.sub('\s+', ' ', text)

    words = clean_text.split(' ')
    if len(words) == 4:
        # e.g., Ludo Günther 10 6
        points = [words[2], words[3]]

        names = [words[0], words[1]]
        # Check if names are unique, no self-matches possible
        if names[0] == names[1]:
            update.message.reply_text(f'Names must be unequal: "{text}"')
            return

    else:
        # too many words, commands without slash, etc
        update.message.reply_text(f'Bad input format: {clean_text}')

    # validate that the score consists of natural numbers
    try:
        points[0], points[1] = int(points[0]), int(points[1])
    except:
        update.message.reply_text(f'Bad score format: {points}')
        return

    player_points, opponent_points = points[0], points[1]
    player_name, opponent_name = names[0], names[1]
    # Add a new data row like
    # 2020-20-6 max lu 4 10
    data = [[str(int(time.time())), player_name, opponent_name, 
             str(player_points), str(opponent_points)]]
    # Append a duplicate where player and opponent are swapped, for easier filtering, like
    # 2020-20-6 lu max 10 4
    data += [[str(int(time.time())), opponent_name, player_name, 
              str(opponent_points), str(player_points)]]

    columns = ['time', 'player', 'opponent', 'player_points', 'opponent_points']
    df = pd.DataFrame(data, columns=columns)
    return df


