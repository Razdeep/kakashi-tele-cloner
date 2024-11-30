from telethon import TelegramClient
import re
from config import api_id, api_hash, channel_id_source
import sqlite3
from pathlib import Path
import logging
from repository import conn
import constants


def check_filename_already_exists_in_local(filename):
    return Path(filename).exists()

def generate_new_filename(message_text, message_id):
    if message_text == '':
        return f'{message_id}.mp4'
    new_filename = re.sub('[^a-zA-Z ]+', '', message_text)[:30]
    if check_filename_already_exists_in_local(new_filename):
        new_filename = f'{new_filename}_{message_id}'
    new_filename = f'{new_filename}.mp4'
    return new_filename

async def download_videos():
    async with TelegramClient('session_name', api_id, api_hash) as client:
        async for message in client.iter_messages(channel_id_source, limit=100, reverse=True):
            if not message.video:
                print(f'skipping message id {message.id}, because it is not video')
                continue
            
            new_filename = generate_new_filename(message.message, message.id)

            should_download = check_should_download(int(message.id))

            if not should_download:
                print(f'skipping message id {message.id}, because it was already downloaded before')
                continue
            
            put_download_entry_in_db(int(message.id), new_filename, str(message.message))
            
            print(f"Downloading video Message ID: {message.id}, video size: {message.video.size // (1024*1024)} MB approx")

            video = await client.download_media(message.video, file=bytes)
            
            with open(f'{constants.DOWNLOAD_FOLDER}/{new_filename}', 'wb') as fp:
                fp.write(video)

            update_download_status(message.id, 'downloaded')


def update_download_status(message_id: str, status_text: str):
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE messages set download_status=? WHERE message_id=?
    """, (status_text, message_id))

    conn.commit()

def get_current_timestamp():
    from datetime import datetime
    current_datetime = datetime.now()
    datetime_str = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
    return str(datetime_str)

def check_should_download(message_id: int):
    cursor = conn.cursor()
    try:
        cursor.execute('''
        select message_id,download_status from messages where message_id=?
        ''', (message_id,))
        res = [item for item in cursor.fetchall()]
        if len(res) == 0:
            return True
        if res[0][0] == 'downloading':
            return True
    except Exception as ex:
        logging.exception(ex)
    return False

def put_download_entry_in_db(message_id: int, new_filename: str, message: str):
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT INTO messages("message_id","new_filename","download_status","upload_status","content","download_timestamp","upload_timestamp") 
                    VALUES (?,?,?,?,?,?,?);
        ''', (int(message_id),new_filename,'downloading','not started', str(message),'',''))
        conn.commit()
    except sqlite3.IntegrityError:
        return False
    except Exception as ex:
        logging.exception(ex)
        return False
    return True