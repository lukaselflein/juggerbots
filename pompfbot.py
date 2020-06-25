    #!/usr/bin/env python
    # -*- coding: utf-8 -*-
# This program is dedicated to the public domain under the CC0 license.
"""
Telegram bot for keeping the scores in a jugger team.
"""

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

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


def parse_cli():
    parser = argparse.ArgumentParser(description='Run a telegram bot for keeping stats.')
    parser.add_argument('--keyname', default='pompfbot_token',
                        help='Name of the secret API key for the bot')
    args = parser.parse_args()
    return args.keyname

def start(update, context):
    """Send a message when the command /start is issued."""
    # Set up a Google Sheet document as a database
    g_sheet = GoogleSheet(sheet_id='1Qmrj-YI5RokrKkfXf9wNubt2oezTGmb8bL-KCUyWf7o', 
                          sheet_range='Data!A1:E')
    context.bot_data['google_sheet'] = g_sheet
    update.message.reply_text('Google Sheet initialized.')



def help(update, context):
    """Send a message when the command /help is issued."""
    text = 'Usage:\n'
    text += 'lu linus 9 10 - add a new duel score\n'
    text += '/stats - all aggregate statistics\n'
    text += '/stats lu - Lu\'s statistics\n'
    text += '/stats lu linus - Lu-vs-Linus statistics\n'
    update.message.reply_text(text)


def handle_data(text, update, context):
    """Extract names and scores from telegram input."""

    # eliminate double spaces
    clean_text = re.sub('\s+', ' ', text)

    words = clean_text.split(' ')
    # e.g., "Ludo Günther"
    if len(words) >= 2:
        names = [words[0], words[1]]
        # Check if names are unique, no self-matches possible
        if names[0] == names[1]:
            update.message.reply_text(f'Names must be unequal: "{text}"')
            return

    # e.g., Ludo Günther 5-10
    if len(words) == 3:
        score = words[2]
        # allow more score formats like 5/10, 5:10
        for seperator in ['-', ':', '/']:
            if seperator in score:
                points = score.split(seperator)
                if len(points) != 2:
                    update.message.reply_text(f'Bad score format: {score}')
                    return

    # e.g., Ludo Günther 10 6
    if len(words) == 4:
        points = [words[2], words[3]]

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
    data = [[time.time(), player_name, opponent_name, 
             player_points, opponent_points]]
    # Append a duplicate where player and opponent are swapped, for easier filtering, like
    # 2020-20-6 lu max 10 4
    data += [[pd.Timestamp.now(), opponent_name, player_name, 
              opponent_points, player_points]]

    columns = ['time', 'player', 'opponent', 'player_points', 'opponent_points']
    df = pd.DataFrame(data, columns=columns)
    return df


def parse(update, context):
    """Parse text input, extract names and points."""

    text = update.message.text.lower()
    if text is None:
        update.message.reply_text('Error: Empty Message.')
        return

    # Sanity checks against overflows
    message_maxlen = 25000  # 1000 lines a 25 chars
    line_maxlen = 30  # names: 20 chars, + 5 chars for result
    if len(text) > message_maxlen:
        update.message.reply_text('Error: Message longer than {message_maxlen}.')
        return

    # Split the message into lines by
    lines = text.split('\n')
    for line in lines:
        if len(line) > line_maxlen:
            update.message.reply_text(f'Error: Line longer than {line_maxlen}.')
            return

        # Do the actual processing     
        df = handle_data(line, update, context)

        # Only use output if no error was encountered
        if df is not None:
            data = save_entry(update, context, df)

    return


def save_entry(update, context, df, path='./data/scores.csv'):
    """Append pandas dataframe to csv at rest."""

    google_sheet = context.bot_data['google_sheet']

    if google_sheet is None:
        # Load old data
        rest_data = read_db(path=path, update=None, context=None)

        if rest_data is not None:
            # If we have old data on disk, append the new data
            new_data = pd.concat([rest_data, df], ignore_index=True)
        else:
            # Otherwise, the new stuff is all we have 
            new_data = df

        new_data.to_csv(path, index=False)

    else:
        google_sheet.append(df.values)

    return new_data


def read_db(update=None, context=None, path='./data/scores.csv'):
    """Output the currently stored data as pandas dataframe"""

    google_sheet = context.bot_data['google_sheet']
    # Local fallback
    if google_sheet is None:
        try:
            # Check if we already have a file
            data = pd.read_csv(path)
        except:
            data = None
    # Google sheets database
    else:
        data = google_sheet.read()
    return data


def delete_db(update=None, context=None, path='./data/scores.csv'):
    """Backup & delete the database."""
    backup_path = path + '_bk_' + str(int(time.time()))
    os.rename(path, backup_path)
    update.message.reply_text('All scores deleted.')


def push_db():
    """Push the local database to the online google docs sheet."""


def pull_db():
    """Get the most recent version of the google docs table."""

def stats(update, context):
    """Output aggregated statistics"""
    # Parse & clean
    text = update.message.text.lower()
    clean_text = re.sub('\s+', ' ', text)
    words = text.split(' ')

    data = read_db()
    if data is None:
        update.message.reply_text(f'No data on disk.')
        return

    # Command is just "/stats"
    if len(words) == 1:
        filtered_data = data

    # Command is like "/stats max"
    elif len(words) == 2:
        player = words[1]
        filtered_data = data[data.player == player]

    # Command is like "/stats lu max"
    elif len(words) == 3:
        player, opponent = words[1], words[2]
        player_filtered_data = data[data.player == player]
        filtered_data = player_filtered_data[data.opponent == opponent]

    # Malformed command like '/stats a b c' or double spaces
    else:
        update.message.reply_text(f'Invalid command: \n"{text}".')
        return
        
    output = filtered_data.groupby(['player', 'opponent']).agg('sum')
    output['ratio'] = round(100 * output.player_points 
                            / (output.player_points + output.opponent_points),
                            0)
    output = output.reset_index()

    # Output formatting
    asci_table = ''
    for index, row in output.iterrows():
        asci_table += f'{row.player:10}{row.opponent:10}' 
        asci_table += f'{row.player_points:2}:{row.opponent_points:2}'
        asci_table += f' \t{int(row.ratio)}%\n'
        

    update.message.reply_text(f'{asci_table}')
    return


def read_secrets(path=None, token_name='pompfbot_token'):
    __location__ = os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__)))
    absolute_path = os.path.join(__location__, path)

    with open(path, 'r') as infile:
        json_dict = json.load(infile)
    api_token = json_dict[token_name]
    return api_token


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


class GoogleSheet:
    """A google spreadsheet."""
    def __init__(self, sheet_id, sheet_range):
        """Handle login and default parameters."""
        creds = self.auth()
        service = build('sheets', 'v4', credentials=creds)
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


    def write(self, values=None):
        if values is None:
            values = [
                ['Datetime', 'Player', 'Opponent', 'Player Score', 'Opponent Score'],
                ['1', 'lu', 'max', '10', '4'],
                ['2', 'lu', 'max', '9', '10'],
                ['3', 'test', 'test2', '1', '2'],
                ['4', 'test2', 'test', '2', '1']
            ]
        body = { 'values': values}
        result = self.sheet.values().update(spreadsheetId=self.sheet_id,
                                       range=self.sheet_range,
                                       valueInputOption='USER_ENTERED',
                                       body=body).execute()
        print(f'{result.get("updatedCells")} cells updated')


    def append(self, values=None):
        print(values)
        exit()
        if values is None:
            values = [['10', 'appended', 'a2', '1', '3']]
            values += [['10', 'a2', 'appended', '3', '1']]
        initial_values = self.read()
        # Append to the old data:
        new_values = initial_values + values
        self.write(values=new_values)
    

def main():
    """Start the bot."""


    # Read Command line interface parameters
    keyname = parse_cli()
    
    # Read Telegram secrets file
    token = read_secrets(path='./secrets.json', token_name=keyname)

    # Create the Updater and pass it your bot's token.
    updater = Updater(token, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("s", stats))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("clear", delete_db))
    dp.add_handler(CommandHandler("delete", delete_db))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, parse))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
